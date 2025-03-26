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

# 常量定义
DATA_FILE_NAME_SUFFIX = ".data"
HINT_FILE_NAME = "hint-index"
MERGE_FINISHED_FILE_NAME = "merge-finished"
SEQ_NO_FILE_NAME = "seq-no"

# 日志记录类型
LOG_RECORD_NORMAL = LogRecordType.NORMAL
LOG_RECORD_DELETED = LogRecordType.DELETED
LOG_RECORD_TXN_FINISHED = LogRecordType.TXNCOMMIT

@dataclass
class LogRecordHeader:
    """LogRecord 的头部信息"""
    crc: int           # crc 校验值
    record_type: int   # 标识 LogRecord 的类型
    key_size: int      # key 的长度
    value_size: int    # value 的长度

class DataFile:
    """数据文件，用于存储数据库的数据记录"""
    
    def __init__(self, dir_path: str, file_id: int):
        """初始化数据文件
        
        Args:
            dir_path: 数据目录路径
            file_id: 文件ID
        """
        self.dir_path = dir_path
        self.file_id = file_id
        self.write_offset = 0
        self.file = None
        self._mu = threading.RLock()  # 使用可重入锁
        self._locked = False  # 文件锁状态
        
        # 确保目录存在
        os.makedirs(dir_path, exist_ok=True)
        
        # 构建文件路径
        self.file_path = os.path.join(dir_path, f"{file_id}.data")
        
        # 创建或打开文件
        try:
            if not os.path.exists(self.file_path):
                self.file = open(self.file_path, "wb+")
            else:
                self.file = open(self.file_path, "rb+")
                self.write_offset = os.path.getsize(self.file_path)
        except Exception as e:
            print(f"打开文件失败: {str(e)}")
            raise
    
    def acquire_lock(self) -> None:
        """获取文件锁"""
        with self._mu:
            if self._locked:
                raise RuntimeError("文件已被锁定")
            try:
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
                self._locked = True
            except IOError:
                raise ErrDataFileIsUsing()
                
    def release_lock(self) -> None:
        """释放文件锁"""
        with self._mu:
            if not self._locked:
                return
            try:
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            except:
                pass
            finally:
                self._locked = False
    
    def read_log_record(self, offset: int) -> Optional[Tuple[LogRecord, int]]:
        """从指定位置读取一条日志记录
        
        Args:
            offset: 文件偏移量
            
        Returns:
            日志记录和实际大小的元组，如果读取失败返回None
        """
        with self._mu:
            try:
                # 确保文件已打开
                if not self.file:
                    return None
                
                # 检查偏移量是否超出文件范围
                if offset >= self.file_size:
                    return None
                
                # 读取头部
                self.file.seek(offset)
                header_data = self.file.read(HEADER_SIZE)
                if not header_data or len(header_data) < HEADER_SIZE:
                    return None
                    
                # 解析头部
                header_result = self.decode_log_record_header(header_data)
                if not header_result or not header_result[0]:
                    return None
                    
                header, _ = header_result
                
                # 验证头部数据的合理性
                if header.key_size < 0 or header.value_size < 0 or header.key_size + header.value_size > 100 * 1024 * 1024:  # 最大100MB
                    return None
                    
                # 计算总大小
                total_size = HEADER_SIZE + header.key_size + header.value_size
                
                # 读取完整记录
                self.file.seek(offset)
                full_data = self.file.read(total_size)
                if len(full_data) < total_size:
                    return None
                    
                # 验证CRC
                actual_crc = zlib.crc32(full_data[4:])
                if header.crc != actual_crc:
                    return None
                    
                # 提取键值
                key = full_data[HEADER_SIZE:HEADER_SIZE + header.key_size]
                value = full_data[HEADER_SIZE + header.key_size:total_size] if header.value_size > 0 else b""
                
                # 创建记录
                record = LogRecord(key, value, LogRecordType(header.record_type))
                return record, total_size
                
            except Exception as e:
                print(f"读取日志记录失败: {str(e)}")
                return None
    
    def write_log_record(self, log_record: LogRecord) -> Tuple[int, int]:
        """写入一条日志记录
        
        Args:
            log_record: 要写入的日志记录
            
        Returns:
            写入位置和写入大小的元组
        """
        with self._mu:
            try:
                # 获取写入位置
                offset = self.write_offset
                
                # 编码日志记录
                encoded_data, size = log_record.encode()
                
                # 写入数据
                self.file.seek(offset)
                self.file.write(encoded_data)
                self.file.flush()
                
                # 更新写入偏移量
                self.write_offset += size
                
                return offset, size
                
            except Exception as e:
                print(f"写入日志记录失败: {str(e)}")
                raise
    
    def sync(self) -> None:
        """同步文件到磁盘"""
        with self._mu:
            if self.file:
                self.file.flush()
                os.fsync(self.file.fileno())
    
    def close(self) -> None:
        """关闭文件"""
        with self._mu:
            if self.file:
                # 释放文件锁
                self.release_lock()
                # 关闭文件
                self.file.close()
                self.file = None
    
    def __del__(self):
        """析构函数，确保文件被关闭"""
        try:
            self.close()
        except:
            pass
    
    @property
    def file_size(self) -> int:
        """获取文件大小
        
        Returns:
            文件大小(字节)
        """
        return os.path.getsize(self.file_path)

    @classmethod
    def open_data_file(cls, dir_path: str, file_id: int, io_type: FileIOType) -> 'DataFile':
        """打开新的数据文件"""
        file_name = cls.get_data_file_name(dir_path, file_id)
        return cls.new_data_file(file_name, file_id, io_type)
        
    @classmethod
    def open_hint_file(cls, dir_path: str) -> 'DataFile':
        """打开 Hint 索引文件"""
        file_name = os.path.join(dir_path, HINT_FILE_NAME)
        return cls.new_data_file(file_name, 0, FileIOType.STANDARD)
        
    @classmethod
    def open_merge_finished_file(cls, dir_path: str) -> 'DataFile':
        """打开标识 merge 完成的文件"""
        file_name = os.path.join(dir_path, MERGE_FINISHED_FILE_NAME)
        return cls.new_data_file(file_name, 0, FileIOType.STANDARD)
        
    @classmethod
    def open_seq_no_file(cls, dir_path: str) -> 'DataFile':
        """打开事务序列号文件"""
        file_name = os.path.join(dir_path, SEQ_NO_FILE_NAME)
        return cls.new_data_file(file_name, 0, FileIOType.STANDARD)
        
    @staticmethod
    def get_data_file_name(dir_path: str, file_id: int) -> str:
        """获取数据文件名"""
        return os.path.join(dir_path, f"{file_id:09d}{DATA_FILE_NAME_SUFFIX}")
        
    @classmethod
    def new_data_file(cls, file_name: str, file_id: int, io_type: FileIOType) -> 'DataFile':
        """创建新的数据文件"""
        # 确保目录存在
        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        io_manager = IOManager.new_io_manager(file_name, io_type)
        return cls(file_name, file_id)
        
    def read_n_bytes(self, offset: int, n: int) -> Optional[bytes]:
        """读取指定字节数"""
        try:
            buf = bytearray(n)
            self.file.seek(offset)
            self.file.read(buf)
            return bytes(buf)
        except Exception:
            return None
            
    def write(self, buf: bytes) -> int:
        """写入字节数组"""
        with self._mu:
            n = self.file.write(buf)
            self.write_offset += n
            return n
        
    def write_hint_record(self, key: bytes, pos: LogRecordPos) -> None:
        """写入索引信息到 hint 文件"""
        record = LogRecord(
            key=key,
            value=self.encode_log_record_pos(pos),
            type=LOG_RECORD_NORMAL
        )
        enc_record = self.encode_log_record(record)
        self.write(enc_record)
        
    @staticmethod
    def encode_log_record(record: LogRecord) -> bytes:
        """对 LogRecord 进行编码"""
        # 计算 key 和 value 的长度
        key_size = len(record.key)
        value_size = len(record.value)
        
        # 构造头部
        header = bytearray(4 + 1 + 4 + 4)  # CRC(4) + Type(1) + KeySize(4) + ValueSize(4)
        header[4] = record.type
        struct.pack_into('>I', header, 5, key_size)
        struct.pack_into('>I', header, 9, value_size)
        
        # 构造完整记录
        enc_bytes = bytearray(len(header) + key_size + value_size)
        enc_bytes[4:] = header[4:]  # 跳过 CRC
        pos = len(header)
        enc_bytes[pos:pos + key_size] = record.key
        pos += key_size
        enc_bytes[pos:pos + value_size] = record.value
        
        # 计算并写入 CRC
        crc = zlib.crc32(enc_bytes[4:])
        struct.pack_into('>I', enc_bytes, 0, crc)
        
        return bytes(enc_bytes)
        
    @staticmethod
    def encode_log_record_pos(pos: LogRecordPos) -> bytes:
        """对位置信息进行编码"""
        buf = bytearray(12)  # 3个4字节整数
        struct.pack_into('>I', buf, 0, pos.file_id)
        struct.pack_into('>I', buf, 4, pos.offset)
        struct.pack_into('>I', buf, 8, pos.size)
        return bytes(buf)
        
    @staticmethod
    def decode_log_record_header(buf: bytes) -> Tuple[Optional[LogRecordHeader], int]:
        """解码日志记录头部"""
        if len(buf) <= 4:
            return None, 0
            
        header = LogRecordHeader(
            crc=struct.unpack('>I', buf[:4])[0],
            record_type=buf[4],
            key_size=struct.unpack('>I', buf[5:9])[0],
            value_size=struct.unpack('>I', buf[9:13])[0]
        )
        
        return header, 13
        
    @staticmethod
    def get_log_record_crc(record: LogRecord, header: bytes) -> int:
        """计算日志记录的 CRC 值"""
        if not record:
            return 0
            
        crc = zlib.crc32(header)
        crc = zlib.crc32(record.key, crc)
        crc = zlib.crc32(record.value, crc)
        return crc 

    @staticmethod
    def get_data_file_path(dir_path: str, file_id: int) -> str:
        """获取数据文件路径
        
        Args:
            dir_path: 数据目录路径
            file_id: 文件ID
            
        Returns:
            数据文件完整路径
        """
        return os.path.join(dir_path, f"{file_id}.data") 

    def size(self) -> int:
        """获取文件大小

        Returns:
            文件大小（字节）
        """
        current_pos = self.file.tell()
        self.file.seek(0, os.SEEK_END)
        size = self.file.tell()
        self.file.seek(current_pos)
        return size 