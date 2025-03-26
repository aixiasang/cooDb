"""迭代器实现

该模块提供了数据库迭代器的支持,可以按顺序遍历数据库中的键值对。
"""

from typing import Any, Optional
from .data.log_record import LogRecord, LogRecordType, LogRecordPos

class Iterator:
    """数据库迭代器类
    
    提供按顺序遍历数据库中键值对的功能。
    """
    
    def __init__(self, db: Any, index_iter: Any):
        """初始化迭代器实例
        
        Args:
            db: 数据库实例
            index_iter: 索引迭代器
        """
        self.db = db
        self.index_iter = index_iter
        
    def rewind(self) -> None:
        """重置迭代器到起始位置"""
        self.index_iter.rewind()
        
    def seek(self, key: bytes) -> None:
        """定位到指定键
        
        Args:
            key: 目标键
        """
        self.index_iter.seek(key)
        
    def next(self) -> None:
        """移动到下一个键值对"""
        self.index_iter.next()
        
    def valid(self) -> bool:
        """检查迭代器是否有效
        
        Returns:
            如果迭代器指向有效的键值对则返回True
        """
        return self.index_iter.valid()
        
    def key(self) -> bytes:
        """获取当前键
        
        Returns:
            当前键
        """
        return self.index_iter.key()
        
    def value(self) -> bytes:
        """获取当前值
        
        Returns:
            当前值
        """
        pos = self.index_iter.value()
        record = self.db._read_log_record(pos)
        if not record:
            return None
        return record.value 