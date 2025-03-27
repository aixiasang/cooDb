import os
import time
import threading
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
from .fio.io_manager import FileIOType
from .fio.file_lock import FileLock

# 常量定义
SEQ_NO_KEY = "seq_no"
MERGE_FINISHED_KEY = "merge_finished"
MERGE_FILENAME = "merge.data"
FILE_LOCK_NAME = "flock"
NON_TRANSACTION_SEQ_NO = 0
DATA_FILE_NAME_SUFFIX = ".data"

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
        self.file_lock_path = os.path.join(options.dir_path, FILE_LOCK_NAME)
        self.file_lock = FileLock(self.file_lock_path)
        
        # 创建数据目录
        if not os.path.exists(options.dir_path):
            self.is_initial = True
            os.makedirs(options.dir_path)
            
        try:
            # 获取文件锁
            if not self.file_lock.acquire():
                raise ErrDatabaseIsUsing()
            
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
                    self.active_file.write_offset = self.active_file.size()
        except:
            # 出错时释放文件锁
            self.file_lock.release()
            raise
        
    def load_data_files(self):
        """加载数据文件"""
        files = [f for f in os.listdir(self.options.dir_path) 
                if f.endswith(DATA_FILE_NAME_SUFFIX) and not f.startswith(('seq_no', 'hint-index', 'merge-finished'))]
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
            
        if not key:
            raise ErrKeyIsEmpty()
            
        # 从索引获取记录位置
        with self.mu:
            pos = self.index.get(key)
            if not pos:
                return None
            
            # 获取值
            try:
                value = self._get_value_by_position(pos)
                return value
            except Exception:
                return None
        
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
                self.file_lock.release()
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
            self.active_file.reset_io_type(FileIOType.StandardFIO)
        for file_id, file in self.older_files.items():
            file.reset_io_type(FileIOType.StandardFIO)
            
    def _load_merge_files(self):
        """加载merge文件，检查是否存在未完成的merge操作"""
        merge_finished_path = os.path.join(self.options.dir_path, f"{MERGE_FINISHED_KEY}{DATA_FILE_NAME_SUFFIX}")
        
        # 如果不存在merge完成标记文件，说明没有进行过merge或上次merge未完成
        if not os.path.exists(merge_finished_path):
            return
        
        # 读取merge完成标记文件内容
        with open(merge_finished_path, 'rb') as f:
            data = f.read()
            if not data:
                return
            
            # 解码记录
            record = LogRecord.decode(data)
            if not record:
                return
            
            # 清理旧的数据文件，除了文件ID为1的文件
            for file_id in self.file_ids:
                if file_id > 1:  # 保留merge后生成的第一个文件
                    file_path = os.path.join(self.options.dir_path, f"{file_id:09d}{DATA_FILE_NAME_SUFFIX}")
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"清理旧数据文件失败: {str(e)}")
                        
            # 删除merge完成标记文件
            try:
                os.remove(merge_finished_path)
            except Exception as e:
                print(f"删除merge完成标记文件失败: {str(e)}")
            
            # 重置文件ID列表
            self.file_ids = [1]

    def _load_index_from_hint_file(self):
        """从hint文件加载索引，提高启动速度"""
        hint_file_path = os.path.join(self.options.dir_path, "hint-index")
        
        # 如果hint文件不存在，直接返回
        if not os.path.exists(hint_file_path):
            return
        
        # 打开hint文件
        hint_file = None
        try:
            # 使用DataFile打开hint文件
            hint_file = DataFile(self.options.dir_path, 0)
            hint_file.file_path = hint_file_path
            
            # 读取文件中的所有记录
            offset = 0
            while True:
                result = hint_file.read_log_record(offset)
                if result is None:
                    break
                
                record, size = result
                if not record:
                    break
                
                # 从record中解码位置信息
                key = record.key
                pos_data = record.value
                if len(pos_data) == 0:
                    offset += size
                    continue
                
                # 解码位置信息
                try:
                    file_id, record_offset, record_size = struct.unpack("=IQI", pos_data)
                    pos = LogRecordPos(file_id, record_offset, record_size)
                    
                    # 更新索引
                    self.index.put(key, pos)
                except Exception as e:
                    print(f"解码位置信息出错: {str(e)}")
                
                # 移动到下一条记录
                offset += size
        except Exception as e:
            print(f"从hint文件加载索引时出错: {str(e)}")
        finally:
            if hint_file:
                hint_file.close()
        
    def stat(self) -> dict:
        """返回数据库的统计信息
        
        Returns:
            包含数据库统计信息的字典
        """
        if self.is_closed:
            raise ErrDatabaseClosed()
            
        with self.mu:
            # 计算数据文件数量
            data_files_num = len(self.older_files)
            if self.active_file:
                data_files_num += 1
            
            # 计算数据目录大小
            disk_size = 0
            for root, _, files in os.walk(self.options.dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    disk_size += os.path.getsize(file_path)
            
            return {
                'key_num': self.index.size(),         # 键值对数量
                'data_files_num': data_files_num,     # 数据文件数量
                'disk_size': disk_size,               # 磁盘占用大小(字节)
                'reclaimable_size': self.reclaim_size # 可回收空间大小(字节)
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
        """遍历所有键值对并应用函数，类似于bitcask-go的Fold方法
        
        Args:
            fn: 处理函数，接收key和value作为参数，返回是否继续遍历
        """
        if self.is_closed:
            raise ErrDatabaseClosed()
            
        with self.mu:
            it = self.iterator(False)
            it.rewind()
            while it.valid():
                key = it.key()
                value = it.value()
                if value is not None:
                    if not fn(key, value):
                        break
                it.next()
        
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
            
        # 从数据文件读取记录
        result = data_file.read_log_record(pos.offset)
        if result is None:
            return None
        
        record, _ = result
        if not record or record.type == LogRecordType.DELETED:
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
            
        # 从数据文件读取记录
        result = data_file.read_log_record(pos.offset)
        if result is None:
            return None
        
        record, _ = result
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
        
    def list_keys(self) -> List[bytes]:
        """获取数据库中所有的键列表
        
        Returns:
            所有键的列表
        """
        if self.is_closed:
            raise ErrDatabaseClosed()
            
        keys = []
        it = self.iterator(False)
        it.rewind()
        while it.valid():
            keys.append(it.key())
            it.next()
        return keys
        
    def merge(self) -> None:
        """执行数据合并操作，将多个数据文件合并为一个，并删除无效数据"""
        if self.is_closed:
            raise ErrDatabaseClosed()
            
        # 已经在合并中则返回
        if self.is_merging:
            return
            
        with self.mu:
            self.is_merging = True
            
            try:
                # 创建临时的合并文件
                merge_file_path = os.path.join(self.options.dir_path, MERGE_FILENAME)
                merge_file = open(merge_file_path, "wb")
                
                # 写入位置
                offset = 0
                
                # 创建新的索引映射，记录新旧位置关系
                new_pos_map = {}
                
                # 遍历所有有效数据，写入合并文件
                it = self.iterator()
                it.rewind()
                
                while it.valid():
                    key = it.key()
                    value = it.value()
                    
                    # 创建新记录
                    record = LogRecord(
                        key=key,
                        value=value,
                        record_type=LogRecordType.NORMAL
                    )
                    
                    # 编码记录
                    encoded_data, size = record.encode()
                    
                    # 写入合并文件
                    merge_file.write(encoded_data)
                    
                    # 更新索引映射
                    new_pos = LogRecordPos(1, offset, size)
                    new_pos_map[key] = new_pos
                    
                    # 更新写入位置
                    offset += size
                    
                    # 移动到下一个键
                    it.next()
                    
                # 关闭合并文件
                merge_file.flush()
                os.fsync(merge_file.fileno())
                merge_file.close()
                
                # 关闭并清理当前所有数据文件
                if self.active_file:
                    self.active_file.close()
                    self.active_file = None
                    
                for file_id, file in self.older_files.items():
                    file.close()
                self.older_files.clear()
                
                # 删除旧的数据文件
                for file_id in self.file_ids:
                    try:
                        file_path = os.path.join(self.options.dir_path, f"{file_id:09d}{DATA_FILE_NAME_SUFFIX}")
                        os.remove(file_path)
                    except Exception as e:
                        print(f"删除旧数据文件失败: {str(e)}")
                        
                # 将合并文件重命名为第一个数据文件
                target_path = os.path.join(self.options.dir_path, f"000000001{DATA_FILE_NAME_SUFFIX}")
                if os.path.exists(target_path):
                    os.remove(target_path)
                os.rename(merge_file_path, target_path)
                
                # 清空文件ID列表，只保留ID 1
                self.file_ids = [1]
                
                # 打开新的活跃文件
                self.active_file = DataFile(self.options.dir_path, 1)
                
                # 更新索引
                for key, pos in new_pos_map.items():
                    self.index.put(key, pos)
                
                # 创建并写入merge完成标记文件
                merge_finished_path = os.path.join(self.options.dir_path, f"{MERGE_FINISHED_KEY}{DATA_FILE_NAME_SUFFIX}")
                with open(merge_finished_path, "wb") as f:
                    # 创建标记记录
                    record = LogRecord(
                        key=MERGE_FINISHED_KEY.encode(),
                        value=b"",
                        record_type=LogRecordType.NORMAL
                    )
                    encoded_data, _ = record.encode()
                    f.write(encoded_data)
                    f.flush()
                    os.fsync(f.fileno())
                    
                # 重置可回收空间大小
                self.reclaim_size = 0
                
            except Exception as e:
                print(f"合并操作失败: {str(e)}")
                raise
            finally:
                self.is_merging = False
        
    def new_batch(self) -> Batch:
        """创建新的批量写入实例
        
        Returns:
            批量写入实例
        """
        if self.is_closed:
            raise ErrDatabaseClosed()
        return Batch(self) 