import os
import tempfile
import threading
from threading import Lock
from typing import TypeVar, Generic, Tuple, Optional, Iterator as PyIterator
import struct
from BTrees.OOBTree import OOBTree # type: ignore
from .interface import Indexer, Iterator

KT = TypeVar('KT', bound=bytes)
VT = TypeVar('VT')

class BPTreeIterator(Generic[KT, VT], Iterator[KT, VT]):
    """B+ 树迭代器"""
    
    def __init__(self, tree: OOBTree, reverse: bool = False):
        """初始化迭代器
        
        Args:
            tree: B+ 树实例
            reverse: 是否反向迭代
        """
        self.tree = tree
        self.reverse = reverse
        self.iter = None
        self.rewind()
        
    def rewind(self) -> None:
        """重置迭代器到起始位置"""
        if self.reverse:
            self.iter = reversed(self.tree.keys())
        else:
            self.iter = iter(self.tree.keys())
            
    def seek(self, key: KT) -> None:
        """定位到指定键
        
        Args:
            key: 目标键
        """
        # 重置迭代器
        self.rewind()
        # 跳过小于目标键的元素
        if not self.reverse:
            while self.valid():
                if self.key() >= key:
                    break
                self.next()
        else:
            while self.valid():
                if self.key() <= key:
                    break
                self.next()
                
    def valid(self) -> bool:
        """检查迭代器是否有效"""
        try:
            self.key()
            return True
        except StopIteration:
            return False
            
    def next(self) -> None:
        """移动到下一个位置"""
        try:
            self._current_key = next(self.iter)
            self._current_value = self.tree[self._current_key]
        except StopIteration:
            self._current_key = None
            self._current_value = None
            
    def key(self) -> KT:
        """获取当前键
        
        Returns:
            当前键
            
        Raises:
            StopIteration: 如果迭代器无效
        """
        if not hasattr(self, '_current_key') or self._current_key is None:
            self.next()
        if self._current_key is None:
            raise StopIteration
        return self._current_key
        
    def value(self) -> VT:
        """获取当前值
        
        Returns:
            当前值
            
        Raises:
            StopIteration: 如果迭代器无效
        """
        if not hasattr(self, '_current_value') or self._current_value is None:
            self.next()
        if self._current_value is None:
            raise StopIteration
        # 反序列化值
        file_id, offset, size = struct.unpack('!QQQ', self._current_value)
        from coodb.data.log_record import LogRecordPos
        return LogRecordPos(file_id, offset, size)

class BPTree(Generic[KT, VT], Indexer[KT, VT]):
    """基于 B+ 树的索引实现"""
    
    def __init__(self):
        """初始化 B+ 树索引"""
        self.lock = threading.Lock()
        self.tree = OOBTree()
        
    def get(self, key: KT) -> Optional[VT]:
        """获取键对应的值
        
        Args:
            key: 键
            
        Returns:
            值，如果键不存在则返回 None
        """
        with self.lock:
            try:
                value_bytes = self.tree[key]
                # 反序列化值
                file_id, offset, size = struct.unpack('!QQQ', value_bytes)
                from coodb.data.log_record import LogRecordPos
                return LogRecordPos(file_id, offset, size)
            except KeyError:
                return None
                
    def put(self, key: KT, value: VT) -> Optional[VT]:
        """插入或更新键值对
        
        Args:
            key: 键
            value: 值
            
        Returns:
            如果键已存在，返回旧值
        """
        with self.lock:
            try:
                # 获取旧值
                old_value_bytes = self.tree.get(key)
                if old_value_bytes is not None:
                    # 反序列化旧值
                    file_id, offset, size = struct.unpack('!QQQ', old_value_bytes)
                    from coodb.data.log_record import LogRecordPos
                    old_value = LogRecordPos(file_id, offset, size)
                else:
                    old_value = None
                    
                # 序列化新值并更新
                value_bytes = struct.pack('!QQQ', value.file_id, value.offset, value.size)
                self.tree[key] = value_bytes
                
                return old_value
            except KeyError:
                return None
                
    def delete(self, key: KT) -> Optional[VT]:
        """删除键值对
        
        Args:
            key: 键
            
        Returns:
            如果键存在，返回旧值
        """
        with self.lock:
            try:
                value_bytes = self.tree[key]
                # 反序列化旧值
                file_id, offset, size = struct.unpack('!QQQ', value_bytes)
                from coodb.data.log_record import LogRecordPos
                old_value = LogRecordPos(file_id, offset, size)
                # 删除键值对
                del self.tree[key]
                return old_value
            except KeyError:
                return None
                
    def iterator(self, reverse: bool = False) -> Iterator[KT, VT]:
        """创建迭代器
        
        Args:
            reverse: 是否反向迭代
            
        Returns:
            迭代器实例
        """
        return BPTreeIterator(self.tree, reverse)
        
    def size(self) -> int:
        """获取索引大小
        
        Returns:
            键值对数量
        """
        with self.lock:
            return len(self.tree)
            
    def close(self) -> None:
        """关闭索引"""
        with self.lock:
            self.tree.clear() 