import os
import struct
import zlib  # 用于 CRC32 校验
from dataclasses import dataclass
from typing import Optional, Iterator, Tuple, BinaryIO
import msvcrt  # Windows文件锁
from ..fio.io_manager import IOManager, FileIOManager, FileIOType
from ..errors import ErrDataFileNotFound, ErrInvalidCRC, ErrDataFileIsUsing
from .log_record import LogRecord, MAX_LOG_RECORD_HEADER_SIZE, HEADER_SIZE, LogRecordType, LogRecordPos
import threading
import traceback

# 常量定义
DATA_FILE_NAME_SUFFIX = ".data"
HINT_FILE_NAME = "hint-index"
MERGE_FINISHED_FILE_NAME = "merge-finished"
SEQ_NO_FILE_NAME = "seq-no"

# 日志记录类型
LOG_RECORD_NORMAL = LogRecordType.NORMAL
LOG_RECORD_DELETED = LogRecordType.DELETED
LOG_RECORD_TXN_FINISHED = LogRecordType.TXNFINISHED

@dataclass
class LogRecordHeader:
    """LogRecord 的头部信息"""
    crc: int           # crc 校验值
    record_type: int   # 标识 LogRecord 的类型
    key_size: int      # key 的长度
    value_size: int    # value 的长度

class DataFile:
    """数据文件，用于存储数据库的数据记录"""
    
    def __init__(self, dir_path: str, file_id: int, io_type: FileIOType = FileIOType.StandardFIO):
        """初始化数据文件
        
        Args:
            dir_path: 数据目录路径
            file_id: 文件ID
            io_type: IO类型，默认为标准文件IO
        """
        self.dir_path = dir_path
        self.file_id = file_id
        self.write_offset = 0
        self._mu = threading.RLock()  # 使用可重入锁
        self._locked = False  # 文件锁状态
        
        # 构建文件路径
        self.file_path = self.get_data_file_path(dir_path, file_id)
        
        # 创建IO管理器
        self.io_manager = IOManager.new_io_manager(self.file_path, io_type)
        
        # 获取文件大小作为写入偏移量
        try:
            self.write_offset = self.io_manager.size()
        except Exception as e:
            print(f"获取文件大小失败: {str(e)}")
            self.write_offset = 0
            
    def acquire_lock(self) -> bool:
        """获取文件锁，返回是否成功
        
        Returns:
            锁定是否成功
        """
        with self._mu:
            if self._locked:
                return True  # 已经持有锁
            try:
                # 使用底层文件描述符获取锁
                if hasattr(self.io_manager, 'fd'):
                    msvcrt.locking(self.io_manager.fd.fileno(), msvcrt.LK_NBLCK, 1)
                    self._locked = True
                    return True
                else:
                    return False  # 无法获取文件描述符
            except IOError:
                return False  # 无法获取锁
                
    def release_lock(self) -> bool:
        """释放文件锁，返回是否成功
        
        Returns:
            释放是否成功
        """
        with self._mu:
            if not self._locked:
                return True  # 未持有锁
            try:
                if hasattr(self.io_manager, 'fd'):
                    msvcrt.locking(self.io_manager.fd.fileno(), msvcrt.LK_UNLCK, 1)
                    self._locked = False
                    return True
                else:
                    return False
            except:
                self._locked = False  # 即使释放失败也标记为未锁定
                return False
    
    def read_log_record(self, offset: int) -> Optional[Tuple[LogRecord, int]]:
        """从指定位置读取一条日志记录
        
        Args:
            offset: 文件偏移量
            
        Returns:
            日志记录和实际大小的元组，如果读取失败返回None
        """
        try:
            # 获取文件大小
            file_size = self.io_manager.size()
            
            # 如果偏移量超出文件范围，返回None
            if offset >= file_size:
                return None
            
            # 如果剩余文件大小不足以包含一个完整头部，返回None
            if offset + HEADER_SIZE > file_size:
                return None
            
            # 读取头部数据
            header_buf = bytearray(HEADER_SIZE)
            if self.io_manager.read(header_buf, offset) != HEADER_SIZE:
                return None
            
            # 解析头部
            crc = struct.unpack(">I", header_buf[:4])[0]
            record_type = header_buf[4]
            key_size = struct.unpack(">I", header_buf[5:9])[0]
            value_size = struct.unpack(">I", header_buf[9:13])[0]
            
            # 检查头部数据合法性
            if record_type not in [LogRecordType.NORMAL.value, LogRecordType.DELETED.value, LogRecordType.TXNFINISHED.value]:
                return None
            
            if key_size <= 0 or value_size < 0 or key_size + value_size > 100 * 1024 * 1024:
                return None
            
            # 计算总大小并检查范围
            total_size = HEADER_SIZE + key_size + value_size
            if offset + total_size > file_size:
                return None
            
            # 读取完整记录
            record_buf = bytearray(total_size)
            if self.io_manager.read(record_buf, offset) != total_size:
                return None
            
            # 验证CRC
            computed_crc = zlib.crc32(record_buf[4:])
            if crc != computed_crc:
                return None
            
            # 提取键和值
            key = bytes(record_buf[HEADER_SIZE:HEADER_SIZE + key_size])
            value = bytes(record_buf[HEADER_SIZE + key_size:]) if value_size > 0 else b""
            
            # 创建LogRecord对象
            log_record = LogRecord(
                key=key,
                value=value,
                record_type=LogRecordType(record_type)
            )
            
            return log_record, total_size
            
        except Exception as e:
            return None
    
    def write_log_record(self, log_record: LogRecord) -> Tuple[int, int]:
        """写入一条日志记录
        
        Args:
            log_record: 要写入的日志记录
            
        Returns:
            写入位置和写入大小的元组
        """
        with self._mu:
            # 获取写入位置
            offset = self.write_offset
            
            # 编码日志记录
            encoded_data, size = log_record.encode()
            
            # 写入数据
            write_size = self.io_manager.write(encoded_data)
            if write_size != len(encoded_data):
                raise IOError(f"写入数据不完整: {write_size} != {len(encoded_data)}")
            
            # 更新写入偏移量
            self.write_offset += size
            
            return offset, size
    
    def sync(self) -> None:
        """同步文件到磁盘"""
        with self._mu:
            self.io_manager.sync()
    
    def close(self) -> None:
        """关闭文件"""
        with self._mu:
            self.io_manager.close()
    
    @property
    def file_size(self) -> int:
        """获取文件大小
        
        Returns:
            文件大小(字节)
        """
        return self.io_manager.size()

    @classmethod
    def open_data_file(cls, dir_path: str, file_id: int, io_type: FileIOType) -> 'DataFile':
        """打开新的数据文件"""
        return cls(dir_path, file_id, io_type)
        
    @classmethod
    def open_hint_file(cls, dir_path: str) -> 'DataFile':
        """打开 Hint 索引文件"""
        hint_file = cls(dir_path, 0)
        hint_file.file_path = os.path.join(dir_path, HINT_FILE_NAME)
        return hint_file
        
    @classmethod
    def open_merge_finished_file(cls, dir_path: str) -> 'DataFile':
        """打开标识 merge 完成的文件"""
        merge_file = cls(dir_path, 0)
        merge_file.file_path = os.path.join(dir_path, MERGE_FINISHED_FILE_NAME)
        return merge_file
        
    @classmethod
    def open_seq_no_file(cls, dir_path: str) -> 'DataFile':
        """打开事务序列号文件"""
        seq_file = cls(dir_path, 0)
        seq_file.file_path = os.path.join(dir_path, SEQ_NO_FILE_NAME)
        return seq_file
        
    @staticmethod
    def get_data_file_path(dir_path: str, file_id: int) -> str:
        """获取数据文件路径
        
        Args:
            dir_path: 数据目录路径
            file_id: 文件ID
            
        Returns:
            数据文件完整路径
        """
        return os.path.join(dir_path, f"{file_id:09d}{DATA_FILE_NAME_SUFFIX}")
        
    def reset_io_type(self, io_type: FileIOType = FileIOType.StandardFIO) -> None:
        """重置IO类型，相当于bitcask-go中的SetIOManager方法
        
        Args:
            io_type: 新的IO类型
        """
        with self._mu:
            old_offset = self.write_offset  # 保存当前写入位置
            
            # 关闭当前IO管理器
            self.io_manager.close()
            
            # 创建新的IO管理器
            self.io_manager = IOManager.new_io_manager(self.file_path, io_type)
            
            # 恢复写入位置
            self.write_offset = old_offset
        
    def read_n_bytes(self, n: int, offset: int) -> Optional[bytes]:
        """读取指定字节数
        
        Args:
            n: 要读取的字节数
            offset: 起始偏移量
            
        Returns:
            读取的字节数据，失败返回None
        """
        buf = bytearray(n)
        read_size = self.io_manager.read(buf, offset)
        if read_size != n:
            return None
        return bytes(buf)
            
    def write(self, buf: bytes) -> int:
        """写入字节数组
        
        Args:
            buf: 要写入的数据
            
        Returns:
            写入的字节数
        """
        with self._mu:
            write_size = self.io_manager.write(buf)
            self.write_offset += write_size
            return write_size
        
    def write_hint_record(self, key: bytes, pos: LogRecordPos) -> None:
        """写入索引信息到 hint 文件
        
        Args:
            key: 键
            pos: 位置信息
        """
        # 创建日志记录，值为位置信息的编码
        record = LogRecord(
            key=key,
            value=pos.encode(),
            record_type=LogRecordType.NORMAL
        )
        
        # 编码日志记录
        encoded_data, _ = record.encode()
        
        # 写入数据
        self.write(encoded_data)
        
    @staticmethod
    def decode_log_record_header(buf: bytes) -> Tuple[Optional[LogRecordHeader], int]:
        """解码日志记录头部
        
        Args:
            buf: 头部字节数据
            
        Returns:
            头部信息对象和头部大小的元组
        """
        if len(buf) < HEADER_SIZE:
            return None, 0
        
        try:
            # 解析头部字段
            crc = struct.unpack(">I", buf[:4])[0]
            record_type = buf[4]
            key_size = struct.unpack(">I", buf[5:9])[0]
            value_size = struct.unpack(">I", buf[9:13])[0]
            
            header = LogRecordHeader(
                crc=crc,
                record_type=record_type,
                key_size=key_size,
                value_size=value_size
            )
            
            return header, HEADER_SIZE
        except Exception as e:
            return None, 0

    def size(self) -> int:
        """获取文件大小

        Returns:
            文件大小（字节）
        """
        return self.io_manager.size() 