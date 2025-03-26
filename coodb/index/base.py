from abc import ABC, abstractmethod
from typing import Optional, Iterator as PyIterator, Any, TypeVar, Generic, Tuple
from ..data.data_file import LogRecordPos

K = TypeVar('K')
V = TypeVar('V')

class Iterator(Generic[K, V]):
    """迭代器接口"""
    
    def rewind(self) -> None:
        """重置迭代器到开始位置"""
        raise NotImplementedError
        
    def seek(self, key: K) -> None:
        """定位到指定键
        
        Args:
            key: 键
        """
        raise NotImplementedError
        
    def valid(self) -> bool:
        """检查迭代器是否有效"""
        raise NotImplementedError
        
    def next(self) -> None:
        """移动到下一个键值对"""
        raise NotImplementedError
        
    def key(self) -> K:
        """获取当前键
        
        Returns:
            当前键
            
        Raises:
            StopIteration: 迭代器无效
        """
        raise NotImplementedError
        
    def value(self) -> V:
        """获取当前值
        
        Returns:
            当前值
            
        Raises:
            StopIteration: 迭代器无效
        """
        raise NotImplementedError
        
    def close(self) -> None:
        """关闭迭代器"""
        raise NotImplementedError
        
    def __iter__(self) -> PyIterator[Tuple[K, V]]:
        """返回迭代器
        
        Returns:
            迭代器
        """
        while self.valid():
            yield self.key(), self.value()
            self.next()
        self.close()

class Indexer(Generic[K, V]):
    """索引器接口"""
    
    def get(self, key: K) -> Optional[V]:
        """获取键对应的值
        
        Args:
            key: 键
            
        Returns:
            值，如果不存在则返回None
        """
        raise NotImplementedError
        
    def put(self, key: K, value: V) -> None:
        """插入或更新键值对
        
        Args:
            key: 键
            value: 值
        """
        raise NotImplementedError
        
    def delete(self, key: K) -> None:
        """删除键值对
        
        Args:
            key: 键
        """
        raise NotImplementedError
        
    def iterator(self) -> Iterator[K, V]:
        """获取迭代器
        
        Returns:
            迭代器
        """
        raise NotImplementedError
        
    def size(self) -> int:
        """获取键值对数量
        
        Returns:
            键值对数量
        """
        raise NotImplementedError
        
    def close(self) -> None:
        """关闭索引器"""
        raise NotImplementedError 