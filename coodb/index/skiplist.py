from typing import Optional, Iterator as PyIterator, TypeVar, Generic, Tuple, TYPE_CHECKING
from threading import Lock
from sortedcontainers import SortedDict

if TYPE_CHECKING:
    from .base import Iterator, Indexer

K = TypeVar('K')
V = TypeVar('V')

class SkipListIterator(Generic[K, V]):
    """跳表迭代器"""
    
    def __init__(self, skiplist: 'SkipList[K, V]', reverse: bool = False):
        """初始化迭代器
        
        Args:
            skiplist: 跳表
            reverse: 是否反向遍历
        """
        self.skiplist = skiplist
        self.items = list(skiplist.tree.items())
        if reverse:
            self.items.reverse()
        self.index = 0
        
    def rewind(self) -> None:
        """重置迭代器到开始位置"""
        self.index = 0
        
    def seek(self, key: K) -> None:
        """定位到指定键
        
        Args:
            key: 键
        """
        for i, (k, _) in enumerate(self.items):
            if k >= key:
                self.index = i
                return
        self.index = len(self.items)
        
    def valid(self) -> bool:
        """检查迭代器是否有效"""
        return 0 <= self.index < len(self.items)
        
    def next(self) -> None:
        """移动到下一个键值对"""
        self.index += 1
        
    def key(self) -> K:
        """获取当前键
        
        Returns:
            当前键
            
        Raises:
            StopIteration: 迭代器无效
        """
        if not self.valid():
            raise StopIteration
        return self.items[self.index][0]
        
    def value(self) -> V:
        """获取当前值
        
        Returns:
            当前值
            
        Raises:
            StopIteration: 迭代器无效
        """
        if not self.valid():
            raise StopIteration
        return self.items[self.index][1]
        
    def close(self) -> None:
        """关闭迭代器"""
        self.items = []
        self.index = 0

class SkipList(Generic[K, V]):
    """跳表实现的索引器"""
    
    def __init__(self):
        """初始化跳表"""
        self.tree = SortedDict()
        self.lock = Lock()
        
    def get(self, key: K) -> Optional[V]:
        """获取键对应的值
        
        Args:
            key: 键
            
        Returns:
            值，如果不存在则返回None
        """
        with self.lock:
            return self.tree.get(key)
            
    def put(self, key: K, value: V) -> Optional[V]:
        """插入或更新键值对
        
        Args:
            key: 键
            value: 值
            
        Returns:
            如果键已存在，返回旧值
        """
        with self.lock:
            old_value = self.tree.get(key)
            self.tree[key] = value
            return old_value
            
    def delete(self, key: K) -> Optional[V]:
        """删除键值对
        
        Args:
            key: 键
            
        Returns:
            如果键存在，返回旧值
        """
        with self.lock:
            old_value = self.tree.get(key)
            if old_value is not None:
                del self.tree[key]
                return old_value
            return None
        
    def iterator(self, reverse: bool = False) -> 'Iterator[K, V]':
        """获取迭代器
        
        Args:
            reverse: 是否反向遍历
            
        Returns:
            迭代器
        """
        return SkipListIterator(self, reverse)
        
    def size(self) -> int:
        """获取键值对数量
        
        Returns:
            键值对数量
        """
        with self.lock:
            return len(self.tree)
            
    def close(self) -> None:
        """关闭索引器"""
        with self.lock:
            self.tree.clear() 