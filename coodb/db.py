import os
import time
import threading
import msvcrt
import struct
from typing import Optional, Dict, List, Callable, Any, Set, Iterator, Tuple, BinaryIO
from .options import Options
from .errors import *
from .data.data_file import DataFile
from .data.log_record import LogRecord, LogRecordType, LogRecordPos
from .index.index import Indexer, IndexType, new_indexer
from .index import BTree, ART, BPTree, SkipList
from .batch import Batch
from .iterator import Iterator

# 常量定义
SEQ_NO_KEY = "seq_no"
MERGE_FINISHED_KEY = "merge_finished"
MERGE_FILENAME = "merge.data"
FILE_LOCK_NAME = "flock"
NON_TRANSACTION_SEQ_NO = 0

class DB:
    """数据库核心实现"""
    
    NORMAL_RECORD = 1   # 正常记录
    DELETED_RECORD = 2  # 删除记录
    
    def __init__(self, options: Options):
        """初始化数据库实例"""
        self.options = options
        self.mu = threading.RLock()  # 使用可重入锁
        self.active_file: Optional[DataFile] = None
        self.older_files: Dict[int, DataFile] = {}
        self.index: Indexer = new_indexer(options.index_type, options.dir_path, options.sync_writes)
        self.file_ids: List[int] = []
        self.is_closed = False
        
        # 新增属性
        self.seq_no = 0  # 事务序列号
        self.is_merging = False  # 是否正在merge
        self.seq_no_file_exists = False  # 事务序列号文件是否存在
        self.is_initial = False  # 是否首次初始化数据目录
        self.bytes_write = 0  # 累计写入字节数
        self.reclaim_size = 0  # 可回收的空间大小
        
        # 文件锁相关
        self.file_lock: Optional[BinaryIO] = None
        self.file_lock_path = os.path.join(options.dir_path, FILE_LOCK_NAME)
        
        # 创建数据目录
        if not os.path.exists(options.dir_path):
            self.is_initial = True
            os.makedirs(options.dir_path)
            
        try:
            # 获取文件锁
            self._acquire_file_lock()
            
            # 加载数据文件
            self.load_data_files()
            
            # 加载merge文件
            self._load_merge_files()
            
            # 从数据文件加载索引
            # 从hint文件加载索引
            self._load_index_from_hint_file()
            # 从数据文件加载索引
            self.load_index_from_files()
            
            # 如果启用了内存映射，重置IO类型
            if options.mmap_at_startup:
                self._reset_io_type()
            
            # 加载事务序列号
            if options.index_type == IndexType.BTREE:
                self.seq_no = self._load_seq_no()
                if self.active_file:
                    self.active_file.write_off = self.active_file.size()
        except:
            # 出错时释放文件锁
            self._release_file_lock()
            raise
        
    def _acquire_file_lock(self):
        """获取文件锁"""
        try:
            self.file_lock = open(self.file_lock_path, 'wb')
            msvcrt.locking(self.file_lock.fileno(), msvcrt.LK_NBLCK, 1)
        except IOError:
            if self.file_lock:
                self.file_lock.close()
            raise ErrDatabaseIsUsing()
            
    def _release_file_lock(self):
        """释放文件锁"""
        if self.file_lock:
            try:
                msvcrt.locking(self.file_lock.fileno(), msvcrt.LK_UNLCK, 1)
            except:
                pass
            finally:
                self.file_lock.close()
                self.file_lock = None
                try:
                    os.remove(self.file_lock_path)
                except:
                    pass
        
    def load_data_files(self):
        """加载数据文件"""
        files = [f for f in os.listdir(self.options.dir_path) 
                if f.endswith('.data') and not f.startswith(('seq_no', 'hint-index', 'merge-finished'))]
        file_ids = []
        
        # 获取所有文件ID
        for name in files:
            file_id = int(name.split('.')[0])
            file_ids.append(file_id)
            
        # 按ID排序
        file_ids.sort()
        self.file_ids = file_ids
        
        # 加载所有数据文件
        if not file_ids:
            # 创建第一个数据文件
            self.active_file = DataFile(self.options.dir_path, file_id=1)
            self.file_ids = [1]
        else:
            # 加载已有的数据文件
            for file_id in file_ids[:-1]:
                self.older_files[file_id] = DataFile(self.options.dir_path, file_id)
            # 最后一个文件作为活跃文件
            self.active_file = DataFile(self.options.dir_path, file_ids[-1])
                
    def load_index_from_files(self):
        """从数据文件加载索引"""
        if not self.file_ids:  # 没有数据文件
            return
            
        # 遍历所有数据文件
        for file_id in self.file_ids:
            data_file = self.active_file if file_id == self.file_ids[-1] else self.older_files.get(file_id, None)
            if not data_file:
                continue
                
            # 读取文件中的所有记录
            offset = 0
            while True:
                try:
                    result = data_file.read_log_record(offset)
                    if result is None:
                        break
                        
                    record, size = result
                    if not record:
                        break
                        
                    # 更新索引
                    if record.type == LogRecordType.NORMAL:
                        pos = LogRecordPos(file_id, offset, size)
                        old_pos = self.index.put(record.key, pos)
                        if old_pos:
                            self.reclaim_size += old_pos.size
                        self.bytes_write += len(record.key) + len(record.value)
                    elif record.type == LogRecordType.DELETED:
                        old_pos = self.index.delete(record.key)
                        if old_pos:
                            self.reclaim_size += old_pos.size
                        
                    # 移动到下一条记录
                    offset += size
                except Exception as e:
                    print(f"加载索引时出错: {str(e)}")
                    break

    def put(self, key: bytes, value: bytes) -> None:
        """写入键值对"""
        if self.is_closed:
            raise ErrDatabaseClosed()
            
        if not key:
            raise ErrKeyIsEmpty()
            
        # 构造日志记录
        record = LogRecord(
            key=key,
            value=value,
            record_type=LogRecordType.NORMAL
        )
        
        # 在同一个锁的保护下执行所有操作
        with self.mu:
            pos = self._append_log_record(record)
            
            # 更新索引
            old_pos = self.index.put(key, pos)
            if old_pos:
                self.reclaim_size += old_pos.size
            
            # 更新写入字节数统计
            self.bytes_write += len(key) + len(value)
            
            # 检查是否需要同步
            if self.options.sync_writes or (self.options.bytes_per_sync > 0 and self.bytes_write >= self.options.bytes_per_sync):
                self.active_file.sync()
                self.bytes_write = 0

    def get(self, key: bytes) -> Optional[bytes]:
        """获取键对应的值"""
        if self.is_closed:
            raise ErrDatabaseClosed()
            
        # 从索引获取记录位置
        with self.mu:
            pos = self.index.get(key)
            if not pos:
                return None
            
        # 获取值
        value = self._get_value_by_position(pos)
        if not value:
            return None
            
        return value
        
    def delete(self, key: bytes) -> None:
        """删除键值对"""
        if self.is_closed:
            raise ErrDatabaseClosed()
            
        if not key:
            raise ErrKeyIsEmpty()
            
        with self.mu:
            # 先检查key是否存在
            if not self.index.get(key):
                return
                
            # 构造删除记录
            record = LogRecord(
                key=key,
                value=b"",
                record_type=LogRecordType.DELETED
            )
            
            pos = self._append_log_record(record)
            
            # 从索引中删除并更新可回收空间
            old_pos = self.index.delete(key)
            if old_pos:
                self.reclaim_size += old_pos.size
                
            # 更新写入字节数统计
            self.bytes_write += len(key)
            
            # 检查是否需要同步
            if self.options.sync_writes or (self.options.bytes_per_sync > 0 and self.bytes_write >= self.options.bytes_per_sync):
                self.active_file.sync()
                self.bytes_write = 0

    def close(self):
        """关闭数据库"""
        if self.is_closed:
            return
            
        with self.mu:
            try:
                # 保存事务序列号
                if self.options.index_type == IndexType.BTREE:
                    self._save_seq_no()
                    
                # 关闭文件
                if self.active_file:
                    self.active_file.close()
                    self.active_file = None
                    
                for file_id, file in self.older_files.items():
                    file.close()
                self.older_files.clear()
                    
                # 关闭索引
                if self.index:
                    self.index.close()
                    
                # 释放文件锁
                self._release_file_lock()
            finally:
                self.is_closed = True
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def _load_seq_no(self):
        """加载事务序列号"""
        seq_no_path = os.path.join(self.options.dir_path, f"{SEQ_NO_KEY}.data")
        if not os.path.exists(seq_no_path):
            return 0
            
        self.seq_no_file_exists = True
        with open(seq_no_path, 'rb') as f:
            data = f.read()
            if data:
                record = LogRecord.decode(data)
                if record and record.value:
                    return int(record.value.decode())
                    
    def _save_seq_no(self):
        """保存事务序列号"""
        seq_no_path = os.path.join(self.options.dir_path, f"{SEQ_NO_KEY}.data")
        record = LogRecord(
            key=SEQ_NO_KEY.encode(),
            value=str(self.seq_no).encode(),
            record_type=LogRecordType.NORMAL
        )
        with open(seq_no_path, 'wb') as f:
            encoded, _ = record.encode()
            f.write(encoded)
            if self.options.sync_writes:
                f.flush()
                os.fsync(f.fileno())
                
    def _reset_io_type(self):
        """重置IO类型为标准文件IO"""
        if self.active_file:
            self.active_file.reset_io_type()
        for file in self.older_files.values():
            file.reset_io_type()
            
    def _load_merge_files(self):
        """加载merge文件"""
        # TODO: 实现merge文件加载逻辑
        pass
        
    def _load_index_from_hint_file(self):
        """从hint文件加载索引"""
        # TODO: 实现从hint文件加载索引的逻辑
        pass
        
    def stat(self) -> dict:
        """返回数据库的统计信息"""
        if self.is_closed:
            raise ErrDatabaseClosed()
            
        data_files = len(self.older_files)
        if self.active_file:
            data_files += 1
            
        # 计算数据目录大小
        dir_size = 0
        for root, _, files in os.walk(self.options.dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                dir_size += os.path.getsize(file_path)
                
        return {
            'key_num': self.index.size(),
            'data_file_num': data_files,
            'reclaimable_size': self.reclaim_size,
            'disk_size': dir_size
        }
        
    def backup(self, dir_path: str) -> None:
        """备份数据库到指定目录"""
        if self.is_closed:
            raise ErrDatabaseClosed()
            
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            
        # 复制所有文件到备份目录
        for root, _, files in os.walk(self.options.dir_path):
            for file in files:
                if file == FILE_LOCK_NAME:  # 不复制文件锁
                    continue
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, self.options.dir_path)
                dst_path = os.path.join(dir_path, rel_path)
                
                # 确保目标目录存在
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                
                # 复制文件
                with open(src_path, 'rb') as src, open(dst_path, 'wb') as dst:
                    dst.write(src.read())
                    
    def fold(self, fn: Callable[[bytes, bytes], bool]) -> None:
        """遍历所有键值对
        
        Args:
            fn: 处理函数，接收key和value作为参数，返回是否继续遍历
        """
        if self.is_closed:
            raise ErrDatabaseClosed()
            
        for key in self.index.list_keys():
            value = self.get(key)
            if value is None:
                continue
            if not fn(key, value):
                break 
        
    def _append_log_record(self, record: LogRecord) -> LogRecordPos:
        """追加日志记录（无需加锁，因为外层已有锁保护）"""
        # 如果活跃文件不存在或已达到最大大小，创建新文件
        if not self.active_file or self.active_file.write_offset >= self.options.max_file_size:
            # 获取新文件ID
            new_file_id = self.file_ids[-1] + 1 if self.file_ids else 1
            
            # 如果存在当前活跃文件，先同步并转为旧文件
            if self.active_file:
                self.active_file.sync()
                self.older_files[self.active_file.file_id] = self.active_file
                
            # 创建新的活跃文件
            self.active_file = DataFile(
                dir_path=self.options.dir_path,
                file_id=new_file_id
            )
            self.file_ids.append(new_file_id)
            
        # 写入记录
        offset, size = self.active_file.write_log_record(record)
            
        # 返回记录位置
        return LogRecordPos(
            file_id=self.active_file.file_id,
            offset=offset,
            size=size
        )
        
    def _get_value_by_position(self, pos: LogRecordPos) -> Optional[bytes]:
        """根据位置信息获取值"""
        # 从对应文件读取记录
        data_file = None
        if pos.file_id == self.active_file.file_id:
            data_file = self.active_file
        else:
            data_file = self.older_files.get(pos.file_id)
            
        if not data_file:
            raise ErrDataFileNotFound()
            
        record, _ = data_file.read_log_record(pos.offset)
        if not record or not record.value:
            return None
            
        return record.value
        
    def _read_log_record(self, pos: LogRecordPos) -> Optional[LogRecord]:
        """读取日志记录
        
        Args:
            pos: 记录位置
            
        Returns:
            日志记录对象
        """
        data_file = None
        if pos.file_id == self.active_file.file_id:
            data_file = self.active_file
        else:
            data_file = self.older_files.get(pos.file_id)
            
        if not data_file:
            raise ErrDataFileNotFound()
            
        record, _ = data_file.read_log_record(pos.offset)
        return record
        
    def iterator(self, reverse: bool = False) -> Iterator:
        """创建数据库迭代器
        
        Args:
            reverse: 是否反向遍历
            
        Returns:
            数据库迭代器实例
        """
        if self.is_closed:
            raise ErrDatabaseClosed()
            
        return Iterator(self, self.index.iterator(reverse))
        
    def merge(self) -> None:
        """执行数据合并操作"""
        if self.is_closed:
            raise ErrDatabaseClosed()
            
        with self.mu:
            # 创建合并文件
            merge_path = os.path.join(self.options.dir_path, MERGE_FILENAME)
            offset = 0  # 记录写入位置
            with open(merge_path, "wb") as merge_file:
                # 遍历所有有效数据
                iterator = self.iterator()
                iterator.rewind()
                while iterator.valid():
                    key = iterator.key()
                    value = iterator.value()
                    
                    # 写入新记录
                    record = LogRecord(
                        key=key,
                        value=value,
                        record_type=LogRecordType.NORMAL
                    )
                    encoded, size = record.encode()
                    merge_file.write(encoded)
                    
                    # 更新索引
                    pos = LogRecordPos(1, offset, size)
                    self.index.put(key, pos)
                    
                    offset += size
                    iterator.next()
                    
            # 关闭所有文件句柄
            if self.active_file:
                self.active_file.close()
            for file in self.older_files.values():
                file.close()
                    
            # 删除旧文件
            for file_id in self.file_ids:
                try:
                    os.remove(os.path.join(self.options.dir_path, f"{str(file_id)}.data"))
                except:
                    pass
                    
            # 重命名合并文件
            target_path = os.path.join(self.options.dir_path, "1.data")
            if os.path.exists(target_path):
                os.remove(target_path)
            os.rename(merge_path, target_path)
            
            # 重新打开文件
            self.file_ids = [1]
            self.older_files = {}
            self.active_file = DataFile(self.options.dir_path, 1)
            
            # 写入合并完成标记
            record = LogRecord(
                key=MERGE_FINISHED_KEY.encode(),
                value=b"",
                record_type=LogRecordType.NORMAL
            )
            self._append_log_record(record)
            
    def new_batch(self) -> Batch:
        """创建新的批量写入实例
        
        Returns:
            批量写入实例
        """
        if self.is_closed:
            raise ErrDatabaseClosed()
        return Batch(self) 