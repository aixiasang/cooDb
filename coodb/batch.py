"""批量写入实现

该模块提供了批量写入操作的支持,可以将多个写操作作为一个原子事务执行。
"""

import threading
from dataclasses import dataclass
from typing import Dict, Optional, List, Any
from .data.log_record import LogRecord, LogRecordType, LogRecordPos

@dataclass
class BatchOperation:
    """批量操作"""
    op_type: int
    key: bytes
    value: Optional[bytes] = None

class Batch:
    """批量写入类
    
    提供将多个写操作打包为一个原子事务的功能。所有操作要么全部成功,要么全部失败。
    """
    
    PUT = 1
    DELETE = 2
    
    def __init__(self, db: Any):
        """初始化批量写入实例
        
        Args:
            db: 数据库实例
        """
        self.db = db
        self.lock = threading.Lock()
        self.pending_ops: List[BatchOperation] = []
        
    def put(self, key: bytes, value: bytes) -> None:
        """添加写入操作
        
        Args:
            key: 键
            value: 值
        """
        with self.lock:
            self.pending_ops.append(BatchOperation(
                op_type=self.PUT,
                key=key,
                value=value
            ))
            
    def delete(self, key: bytes) -> None:
        """添加删除操作
        
        Args:
            key: 要删除的键
        """
        with self.lock:
            self.pending_ops.append(BatchOperation(
                op_type=self.DELETE,
                key=key
            ))
            
    def commit(self) -> None:
        """提交所有挂起的操作
        
        将所有挂起的操作作为一个原子事务执行。
        """
        with self.lock:
            # 获取数据库锁
            with self.db.mu:
                # 执行所有挂起的操作
                for op in self.pending_ops:
                    if op.op_type == self.PUT:
                        # 构造日志记录
                        record = LogRecord(
                            key=op.key,
                            value=op.value,
                            record_type=LogRecordType.NORMAL
                        )
                        pos = self.db._append_log_record(record)
                        
                        # 更新索引
                        old_pos = self.db.index.put(op.key, pos)
                        if old_pos:
                            self.db.reclaim_size += old_pos.size
                            
                    elif op.op_type == self.DELETE:
                        # 构造删除记录
                        record = LogRecord(
                            key=op.key,
                            value=b"",
                            record_type=LogRecordType.DELETED
                        )
                        pos = self.db._append_log_record(record)
                        
                        # 从索引中删除
                        old_pos = self.db.index.delete(op.key)
                        if old_pos:
                            self.db.reclaim_size += old_pos.size
                            
                # 清空挂起的操作
                self.pending_ops.clear()
            
    def rollback(self) -> None:
        """回滚所有挂起的操作"""
        with self.lock:
            self.pending_ops.clear() 