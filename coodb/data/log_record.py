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
    TXNFINISHED = 4  # 事务提交
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
        """编码日志记录，使用定长编码
        
        Returns:
            编码后的字节串和总长度
        """
        key_size = len(self.key)
        value_size = len(self.value)
        
        # 定长编码 - 头部使用固定长度
        # 计算总长度
        total_size = HEADER_SIZE + key_size + value_size
        
        # 构造完整记录（不包含CRC部分）
        enc_bytes = bytearray(total_size)
        
        # 设置类型（第5字节）
        enc_bytes[4] = self.type.value
        
        # 设置key size（第6-9字节）
        struct.pack_into(">I", enc_bytes, 5, key_size)
        
        # 设置value size（第10-13字节）
        struct.pack_into(">I", enc_bytes, 9, value_size)
        
        # 复制key和value
        pos = HEADER_SIZE
        enc_bytes[pos:pos + key_size] = self.key
        pos += key_size
        enc_bytes[pos:pos + value_size] = self.value
        
        # 计算CRC（对整个记录除了CRC字段外的所有数据）
        crc = zlib.crc32(enc_bytes[4:])
        
        # 在开头添加CRC（第1-4字节）
        struct.pack_into(">I", enc_bytes, 0, crc)
        
        return bytes(enc_bytes), total_size
        
    @staticmethod
    def decode(data: bytes) -> Optional['LogRecord']:
        """解码字节数据为日志记录
        
        Args:
            data: 编码后的日志记录数据
            
        Returns:
            日志记录对象，解码失败则返回None
        """
        if len(data) < HEADER_SIZE:
            return None
        
        try:
            # 提取头部信息
            crc = struct.unpack(">I", data[:4])[0]
            record_type = data[4]
            key_size = struct.unpack(">I", data[5:9])[0]
            value_size = struct.unpack(">I", data[9:13])[0]
            
            # 验证CRC
            computed_crc = zlib.crc32(data[4:])
            if crc != computed_crc:
                return None
            
            # 提取键和值
            key = data[HEADER_SIZE:HEADER_SIZE + key_size]
            value = data[HEADER_SIZE + key_size:HEADER_SIZE + key_size + value_size] if value_size > 0 else b""
            
            # 创建LogRecord对象
            return LogRecord(
                key=key,
                value=value,
                record_type=LogRecordType(record_type)
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
        """编码位置信息，使用定长编码
        
        Returns:
            编码后的字节串
        """
        # 使用定长编码 - 文件ID(4) + 偏移量(8) + 大小(4)
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