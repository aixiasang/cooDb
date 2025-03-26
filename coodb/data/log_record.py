import struct
import zlib
from enum import Enum, auto
from typing import Optional, Tuple

# 日志记录头部大小常量
HEADER_SIZE = 13  # 类型(1) + 键长度(4) + 值长度(4) + CRC(4)
MAX_LOG_RECORD_HEADER_SIZE = HEADER_SIZE + 4  # 额外的4字节用于存储事务ID

class LogRecordType(Enum):
    """日志记录类型"""
    NORMAL = 1      # 正常记录
    DELETED = 2     # 删除标记
    TXNSTART = 3    # 事务开始
    TXNCOMMIT = 4   # 事务提交
    TXNABORT = 5    # 事务回滚

class LogRecord:
    """日志记录"""
    
    def __init__(self, key: bytes = b"", value: bytes = b"", 
                 record_type: LogRecordType = LogRecordType.NORMAL):
        """初始化日志记录
        
        Args:
            key: 键
            value: 值
            record_type: 记录类型
        """
        self.key = key if key is not None else b""
        self.value = value if value is not None else b""
        self.type = record_type
        
    def encode(self) -> Tuple[bytes, int]:
        """编码日志记录
        
        Returns:
            编码后的字节串和总长度
        """
        key_size = len(self.key)
        value_size = len(self.value)
        
        # 计算总长度
        total_size = HEADER_SIZE + key_size + value_size
        
        # 构造头部（不包含CRC）
        header = struct.pack(
            ">BII",  # 类型(1) + 键长度(4) + 值长度(4)
            self.type.value,
            key_size,
            value_size,
        )
        
        # 组装完整记录（不包含CRC）
        body = header + self.key + self.value
        
        # 计算CRC
        crc = zlib.crc32(body)
        
        # 在开头添加CRC
        encoded = struct.pack(">I", crc) + body
        
        return encoded, total_size
        
    @staticmethod
    def decode(data: bytes) -> Optional['LogRecord']:
        """解码日志记录
        
        Args:
            data: 编码后的字节串
            
        Returns:
            解码后的日志记录，如果解码失败返回None
        """
        if len(data) < HEADER_SIZE:
            return None
            
        try:
            # 提取并验证CRC
            stored_crc = struct.unpack(">I", data[:4])[0]
            actual_crc = zlib.crc32(data[4:])
            if stored_crc != actual_crc:
                return None
                
            # 解析头部
            record_type, key_size, value_size = struct.unpack(
                ">BII",
                data[4:13]
            )
            
            # 验证数据完整性
            total_size = HEADER_SIZE + key_size + value_size
            if len(data) < total_size:
                return None
                
            # 提取键值
            start = HEADER_SIZE
            key = data[start:start + key_size]
            value = data[start + key_size:start + key_size + value_size]
            
            # 验证键值完整性
            if len(key) != key_size or len(value) != value_size:
                return None
                
            # 创建记录
            return LogRecord(
                key,
                value,
                LogRecordType(record_type)
            )
        except Exception:
            return None

class LogRecordPos:
    """日志记录位置信息"""
    
    def __init__(self, file_id: int, offset: int, size: int):
        """初始化位置信息
        
        Args:
            file_id: 文件ID
            offset: 偏移量
            size: 记录大小
        """
        self.file_id = file_id
        self.offset = offset
        self.size = size
        
    def __eq__(self, other: object) -> bool:
        """比较两个位置信息是否相等
        
        Args:
            other: 另一个位置信息对象
            
        Returns:
            是否相等
        """
        if not isinstance(other, LogRecordPos):
            return False
        return (self.file_id == other.file_id and
                self.offset == other.offset and
                self.size == other.size)
                
    def __hash__(self) -> int:
        """获取哈希值
        
        Returns:
            哈希值
        """
        return hash((self.file_id, self.offset, self.size))
        
    def encode(self) -> bytes:
        """编码位置信息
        
        Returns:
            编码后的字节串
        """
        return struct.pack("=IQI", self.file_id, self.offset, self.size)
        
    @staticmethod
    def decode(data: bytes) -> 'LogRecordPos':
        """解码位置信息
        
        Args:
            data: 编码后的字节串
            
        Returns:
            解码后的位置信息
        """
        try:
            file_id, offset, size = struct.unpack("=IQI", data)
            return LogRecordPos(file_id, offset, size)
        except:
            raise ValueError("Invalid log record position data")

class TransactionRecord:
    """事务记录"""
    
    def __init__(self, txn_id: int, record_type: LogRecordType):
        """初始化事务记录
        
        Args:
            txn_id: 事务ID
            record_type: 记录类型
        """
        self.txn_id = txn_id
        self.type = record_type
        
    def encode(self) -> bytes:
        """编码事务记录
        
        Returns:
            编码后的字节串
        """
        return struct.pack("=IB", self.txn_id, self.type.value)
        
    @staticmethod
    def decode(data: bytes) -> 'TransactionRecord':
        """解码事务记录
        
        Args:
            data: 编码后的字节串
            
        Returns:
            解码后的事务记录
        """
        try:
            txn_id, record_type = struct.unpack("=IB", data)
            return TransactionRecord(txn_id, LogRecordType(record_type))
        except:
            raise ValueError("Invalid transaction record data") 