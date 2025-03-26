import os
import mmap
from typing import Optional
from .io_manager import IOManager, DATA_FILE_PERM

class MMapIO(IOManager):
    """内存映射IO实现"""
    
    def __init__(self, fd: int, m: mmap.mmap):
        """初始化MMapIO
        
        Args:
            fd: 文件描述符
            m: 内存映射对象
        """
        self._fd = fd
        self._mmap = m
        
    @classmethod
    def new_mmap_io_manager(cls, filename: str) -> 'MMapIO':
        """创建MMapIO实例
        
        Args:
            filename: 文件名
            
        Returns:
            MMapIO实例
        """
        # 以读写模式打开文件
        fd = os.open(filename, os.O_RDWR | os.O_CREAT)
        # 设置文件权限
        os.chmod(filename, DATA_FILE_PERM)
        # 获取文件大小
        size = os.path.getsize(filename)
        if size == 0:
            # 如果是新文件，先写入一个字节以便映射
            os.write(fd, b'\x00')
            size = 1
        # 创建内存映射
        m = mmap.mmap(fd, size, access=mmap.ACCESS_WRITE)
        return cls(fd, m)
        
    def read(self, buf: bytearray, offset: int) -> int:
        """从文件的给定位置读取对应的数据
        
        Args:
            buf: 用于存储读取数据的缓冲区
            offset: 读取的起始位置
            
        Returns:
            读取的字节数
        """
        # 定位到offset
        self._mmap.seek(offset)
        # 读取数据到缓冲区
        data = self._mmap.read(len(buf))
        buf[:len(data)] = data
        return len(data)
        
    def write(self, data: bytes) -> int:
        """写入字节数组到文件中
        
        Args:
            data: 要写入的数据
            
        Returns:
            写入的字节数
        """
        # 如果需要更多空间，扩展映射
        current_size = self._mmap.size()
        write_size = self._mmap.tell() + len(data)
        if write_size > current_size:
            # 关闭当前映射
            self._mmap.close()
            # 扩展文件
            os.truncate(self._fd, write_size)
            # 重新映射
            self._mmap = mmap.mmap(self._fd, write_size, access=mmap.ACCESS_WRITE)
            self._mmap.seek(current_size)
        
        return self._mmap.write(data)
        
    def sync(self) -> None:
        """持久化数据"""
        self._mmap.flush()
        
    def close(self) -> None:
        """关闭文件"""
        if self._mmap:
            self._mmap.close()
        if self._fd:
            os.close(self._fd)
            
    def size(self) -> int:
        """获取文件大小
        
        Returns:
            文件大小（字节数）
        """
        return self._mmap.size() 