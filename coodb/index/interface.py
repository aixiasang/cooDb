from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, Tuple

KT = TypeVar('KT')
VT = TypeVar('VT')

class Iterator(Generic[KT, VT], ABC):
    """索引迭代器接口"""
    
    @abstractmethod
    def rewind(self) -> None:
        """重置迭代器到起始位置"""
        pass
        
    @abstractmethod
    def seek(self, key: KT) -> None:
        """查找指定的键
        
        Args:
            key: 要查找的键
        """
        pass
        
    @abstractmethod
    def valid(self) -> bool:
        """检查迭代器是否有效
        
        Returns:
            如果迭代器指向有效位置则返回True
        """
        pass
        
    @abstractmethod
    def next(self) -> None:
        """移动到下一个位置"""
        pass
        
    @abstractmethod
    def key(self) -> KT:
        """获取当前键
        
        Returns:
            当前位置的键
            
        Raises:
            ValueError: 如果迭代器无效
        """
        pass
        
    @abstractmethod
    def value(self) -> VT:
        """获取当前值
        
        Returns:
            当前位置的值
            
        Raises:
            ValueError: 如果迭代器无效
        """
        pass

class Indexer(Generic[KT, VT], ABC):
    """索引器接口"""
    
    @abstractmethod
    def get(self, key: KT) -> Optional[VT]:
        """获取键对应的值
        
        Args:
            key: 键
            
        Returns:
            值，如果不存在则返回None
        """
        pass
        
    @abstractmethod
    def put(self, key: KT, value: VT) -> None:
        """存入键值对
        
        Args:
            key: 键
            value: 值
        """
        pass
        
    @abstractmethod
    def delete(self, key: KT) -> Tuple[Optional[VT], bool]:
        """删除键值对
        
        Args:
            key: 键
            
        Returns:
            (旧值, 是否成功删除)的元组
        """
        pass
        
    @abstractmethod
    def iterator(self, reverse: bool = False) -> Iterator[KT, VT]:
        """创建迭代器
        
        Args:
            reverse: 是否反向遍历
            
        Returns:
            迭代器实例
        """
        pass
        
    @abstractmethod
    def size(self) -> int:
        """获取索引中的键值对数量
        
        Returns:
            键值对数量
        """
        pass
        
    @abstractmethod
    def close(self) -> None:
        """关闭索引"""
        pass 