"""数据合并实现

该模块提供了数据文件合并功能,用于清理无效数据并优化存储空间。
"""

import os
import threading
from typing import Set, Dict, Optional, List
from .data.log_record import LogRecord, LogRecordType, LogRecordPos
from .db import DB
from .iterator import Iterator

class Merge:
    """数据合并类
    
    提供数据文件的合并功能,清理已删除和过期的数据。
    """
    
    def __init__(self, db: DB):
        """初始化合并实例
        
        Args:
            db: 数据库实例
        """
        self.db = db
        self.merge_lock = threading.Lock()
        
    def need_merge(self) -> bool:
        """检查是否需要执行合并
        
        Returns:
            如果需要合并则返回True
        """
        # 检查无效数据比例
        total_size = 0
        invalid_size = 0
        
        for file_id in self.db.file_ids:
            file_size = os.path.getsize(self.db.get_data_file_path(file_id))
            total_size += file_size
            
            # 统计无效数据大小
            offset = 0
            while offset < file_size:
                record = self.db.read_log_record_at(file_id, offset)
                if record is None:
                    break
                    
                if record.record_type == LogRecordType.DELETED:
                    invalid_size += record.size
                    
                offset += record.size
                
        # 如果无效数据超过50%,则需要合并
        return invalid_size > total_size * 0.5
        
    def merge(self) -> None:
        """执行数据合并
        
        将有效数据重写到新文件,删除旧文件。
        """
        with self.merge_lock:
            # 如果不需要合并则直接返回
            if not self.need_merge():
                return
                
            # 创建新的合并文件
            merge_file_id = max(self.db.file_ids) + 1
            merge_file_path = self.db.get_data_file_path(merge_file_id)
            
            # 遍历所有数据,将有效数据写入新文件
            iterator = self.db.iterator()
            iterator.rewind()
            
            while iterator.valid():
                key = iterator.key()
                value = iterator.value()
                
                # 写入新文件
                record = LogRecord(
                    key=key,
                    value=value,
                    record_type=LogRecordType.NORMAL
                )
                pos = self.db.append_log_record_to_file(record, merge_file_id)
                
                # 更新索引
                self.db.index.put(key, pos)
                
                iterator.next()
                
            # 删除旧文件
            for file_id in self.db.file_ids:
                if file_id != merge_file_id:
                    os.remove(self.db.get_data_file_path(file_id))
                    
            # 更新文件列表
            self.db.file_ids = [merge_file_id]

class MergeIterator:
    """合并迭代器,用于数据文件合并过程"""
    
    def __init__(self, db: DB):
        """初始化合并迭代器
        
        Args:
            db: 数据库实例
        """
        self.db = db
        self.iterator = db.iterator()
        self.current_key: Optional[bytes] = None
        self.current_value: Optional[bytes] = None
        
    def rewind(self) -> None:
        """重置迭代器到起始位置"""
        self.iterator.rewind()
        if self.valid():
            self.current_key = self.iterator.key()
            self.current_value = self.iterator.value()
            
    def seek(self, key: bytes) -> None:
        """查找指定key的位置
        
        Args:
            key: 要查找的key
        """
        self.iterator.seek(key)
        if self.valid():
            self.current_key = self.iterator.key()
            self.current_value = self.iterator.value()
            
    def next(self) -> None:
        """移动到下一个位置"""
        self.iterator.next()
        if self.valid():
            self.current_key = self.iterator.key()
            self.current_value = self.iterator.value()
        else:
            self.current_key = None
            self.current_value = None
            
    def valid(self) -> bool:
        """检查当前位置是否有效"""
        return self.iterator.valid()
        
    def key(self) -> Optional[bytes]:
        """获取当前位置的key"""
        return self.current_key
        
    def value(self) -> Optional[bytes]:
        """获取当前位置的value"""
        return self.current_value 