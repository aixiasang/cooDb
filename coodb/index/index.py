"""索引接口定义"""

from enum import Enum
from typing import Optional, TypeVar, Generic, Tuple
from dataclasses import dataclass

from coodb.iterator import Iterator
from ..data.log_record import LogRecordPos

KT = TypeVar('KT')
VT = TypeVar('VT')

class IndexType(Enum):
    """索引类型"""
    BTREE = "btree"
    ART = "art"
    BPTREE = "bptree"
    SKIPLIST = "skiplist"

class Indexer(Generic[KT, VT]):
    """索引器接口"""
    
    def get(self, key: KT) -> Optional[VT]:
        """获取键对应的值
        
        Args:
            key: 键
            
        Returns:
            值，如果不存在则返回None
        """
        raise NotImplementedError
        
    def put(self, key: KT, value: VT) -> Optional[VT]:
        """存入键值对
        
        Args:
            key: 键
            value: 值
            
        Returns:
            如果键已存在，返回旧值
        """
        raise NotImplementedError
        
    def delete(self, key: KT) -> Optional[VT]:
        """删除键值对
        
        Args:
            key: 键
            
        Returns:
            如果键存在，返回旧值
        """
        raise NotImplementedError
        
    def iterator(self, reverse: bool = False) -> "Iterator[KT, VT]":
        """创建迭代器
        
        Args:
            reverse: 是否反向遍历
            
        Returns:
            迭代器实例
        """
        raise NotImplementedError
        
    def size(self) -> int:
        """获取索引中的键值对数量
        
        Returns:
            键值对数量
        """
        raise NotImplementedError
        
    def close(self) -> None:
        """关闭索引"""
        raise NotImplementedError

def new_indexer(index_type: IndexType, dir_path: str, sync: bool = False) -> Indexer:
    """创建索引器实例
    
    Args:
        index_type: 索引类型
        dir_path: 数据目录路径
        sync: 是否同步写入
        
    Returns:
        索引器实例
    """
    from .btree import BTree
    from .art import ART
    from .bptree import BPTree
    from .skiplist import SkipList
    
    if index_type == IndexType.BTREE:
        return BTree()
    elif index_type == IndexType.ART:
        return ART()
    elif index_type == IndexType.BPTREE:
        return BPTree()
    elif index_type == IndexType.SKIPLIST:
        return SkipList()
    else:
        raise ValueError(f"Unknown index type: {index_type}") 