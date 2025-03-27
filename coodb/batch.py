"""批量写入实现

该模块提供了批量写入操作的支持,可以将多个写操作作为一个原子事务执行。
"""

import threading
from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple, Any
from .data.log_record import LogRecord, LogRecordType, LogRecordPos
from .errors import ErrBatchClosed
from .index.index import IndexType

@dataclass
class BatchOperation:
    """批量操作"""
    op_type: int
    key: bytes
    value: Optional[bytes] = None

class Batch:
    """批量写入类，提供事务支持"""
    
    def __init__(self, db):
        """初始化批量写入实例
        
        Args:
            db: 数据库实例
        """
        self.db = db
        self.is_committed = False
        self.writes: Dict[bytes, Optional[bytes]] = {}
        
    def put(self, key: bytes, value: bytes) -> None:
        """添加写入操作
        
        Args:
            key: 键
            value: 值
        """
        if self.is_committed:
            raise ErrBatchClosed()
            
        if not key:
            raise ValueError("Key cannot be empty")
            
        # 记录操作，将None替换为实际值
        self.writes[key] = value
        
    def delete(self, key: bytes) -> None:
        """添加删除操作
        
        Args:
            key: 键
        """
        if self.is_committed:
            raise ErrBatchClosed()
            
        if not key:
            raise ValueError("Key cannot be empty")
            
        # 记录删除操作，使用None表示删除
        self.writes[key] = None
        
    def commit(self) -> None:
        """提交所有操作"""
        if self.is_committed:
            raise ErrBatchClosed()
            
        # 防止空批次提交
        if not self.writes:
            self.is_committed = True
            return
            
        # 获取事务ID（仅在BTree索引时使用）
        txn_id = self.db.seq_no
        if self.db.options.index_type == IndexType.BTREE:
            txn_id = self.db.seq_no + 1
        
        # 开始事务
        with self.db.mu:
            try:
                # 写入事务开始标记
                if txn_id > 0:
                    start_record = LogRecord(
                        key=str(txn_id).encode(),
                        value=b"",
                        record_type=LogRecordType.TXNSTART
                    )
                    self.db._append_log_record(start_record)
                
                # 写入所有操作
                positions = {}
                for key, value in self.writes.items():
                    if value is None:
                        # 删除操作
                        record = LogRecord(
                            key=key,
                            value=b"",
                            record_type=LogRecordType.DELETED
                        )
                    else:
                        # 写入操作
                        record = LogRecord(
                            key=key,
                            value=value,
                            record_type=LogRecordType.NORMAL
                        )
                    pos = self.db._append_log_record(record)
                    positions[key] = (pos, value is not None)
                
                # 写入事务完成标记
                if txn_id > 0:
                    finish_record = LogRecord(
                        key=str(txn_id).encode(),
                        value=b"",
                        record_type=LogRecordType.TXNFINISHED
                    )
                    self.db._append_log_record(finish_record)
                    # 更新事务ID
                    self.db.seq_no = txn_id
                
                # 更新索引
                for key, (pos, is_put) in positions.items():
                    if is_put:
                        # 写入操作
                        old_pos = self.db.index.put(key, pos)
                        if old_pos:
                            self.db.reclaim_size += old_pos.size
                    else:
                        # 删除操作
                        old_pos = self.db.index.delete(key)
                        if old_pos:
                            self.db.reclaim_size += old_pos.size
                
                # 同步到磁盘
                if self.db.options.sync_writes:
                    self.db.active_file.sync()
            except Exception as e:
                # 如果发生错误，尝试写入事务中止标记
                if txn_id > 0:
                    try:
                        abort_record = LogRecord(
                            key=str(txn_id).encode(),
                            value=b"",
                            record_type=LogRecordType.TXNABORT
                        )
                        self.db._append_log_record(abort_record)
                    except:
                        pass
                raise e
        
        self.is_committed = True 