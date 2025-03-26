import os
import mmap
from enum import Enum, auto
from typing import Optional, BinaryIO

# 数据文件权限
DATA_FILE_PERM = 0o644

class FileIOType(Enum):
    """文件IO类型"""
    STANDARD = auto()  # 标准文件IO
    MEMORY_MAP = auto()  # 内存映射IO

class IOManager:
    """IO管理器接口"""
    
    def read(self, buf: bytearray, offset: int) -> int:
        """从指定位置读取数据到缓冲区
        
        Args:
            buf: 目标缓冲区
            offset: 起始位置
            
        Returns:
            读取的字节数
        """
        raise NotImplementedError
        
    def write(self, buf: bytes) -> int:
        """写入数据
        
        Args:
            buf: 要写入的数据
            
        Returns:
            写入的字节数
        """
        raise NotImplementedError
        
    def sync(self) -> None:
        """同步数据到磁盘"""
        raise NotImplementedError
        
    def close(self) -> None:
        """关闭IO"""
        raise NotImplementedError
        
    @staticmethod
    def new_io_manager(filename: str, io_type: FileIOType) -> 'IOManager':
        """创建新的IO管理器
        
        Args:
            filename: 文件名
            io_type: IO类型
            
        Returns:
            IO管理器实例
        """
        if io_type == FileIOType.STANDARD:
            return FileIOManager(filename)
        elif io_type == FileIOType.MEMORY_MAP:
            return MMapIOManager(filename)
        else:
            raise ValueError(f"不支持的IO类型: {io_type}")

class FileIOManager(IOManager):
    """标准文件IO管理器"""
    
    def __init__(self, filename: str):
        """初始化文件IO管理器
        
        Args:
            filename: 文件名
        """
        self.filename = filename
        self.file: Optional[BinaryIO] = None
        self._open_file()
        
    def _open_file(self) -> None:
        """打开文件"""
        # 确保目录存在
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        
        # 打开文件
        if not os.path.exists(self.filename):
            self.file = open(self.filename, "wb+")
        else:
            self.file = open(self.filename, "rb+")
            
    def read(self, buf: bytearray, offset: int) -> int:
        """从指定位置读取数据到缓冲区"""
        if not self.file:
            raise IOError("文件未打开")
            
        self.file.seek(offset)
        return self.file.readinto(buf)
        
    def write(self, buf: bytes) -> int:
        """写入数据"""
        if not self.file:
            raise IOError("文件未打开")
            
        return self.file.write(buf)
        
    def sync(self) -> None:
        """同步数据到磁盘"""
        if not self.file:
            raise IOError("文件未打开")
            
        self.file.flush()
        os.fsync(self.file.fileno())
        
    def close(self) -> None:
        """关闭文件"""
        if self.file:
            self.file.close()
            self.file = None

class MMapIOManager(IOManager):
    """内存映射IO管理器"""
    
    def __init__(self, filename: str):
        """初始化内存映射IO管理器
        
        Args:
            filename: 文件名
        """
        self.filename = filename
        self.file: Optional[BinaryIO] = None
        self.mm: Optional[mmap.mmap] = None
        self._open_file()
        
    def _open_file(self) -> None:
        """打开文件并创建内存映射"""
        # 确保目录存在
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        
        # 打开文件
        if not os.path.exists(self.filename):
            self.file = open(self.filename, "wb+")
        else:
            self.file = open(self.filename, "rb+")
            
        # 获取文件大小
        self.file.seek(0, os.SEEK_END)
        size = self.file.tell()
        
        # 如果文件为空，写入一个字节以便创建映射
        if size == 0:
            self.file.write(b'\0')
            size = 1
            
        # 创建内存映射
        self.mm = mmap.mmap(
            self.file.fileno(),
            size,
            access=mmap.ACCESS_WRITE
        )
        
    def read(self, buf: bytearray, offset: int) -> int:
        """从指定位置读取数据到缓冲区"""
        if not self.mm:
            raise IOError("内存映射未创建")
            
        self.mm.seek(offset)
        data = self.mm.read(len(buf))
        buf[:len(data)] = data
        return len(data)
        
    def write(self, buf: bytes) -> int:
        """写入数据"""
        if not self.mm:
            raise IOError("内存映射未创建")
            
        # 如果需要更多空间，重新映射文件
        required_size = self.mm.tell() + len(buf)
        if required_size > self.mm.size():
            self.mm.close()
            
            # 调整文件大小
            self.file.truncate(required_size)
            
            # 重新创建映射
            self.mm = mmap.mmap(
                self.file.fileno(),
                required_size,
                access=mmap.ACCESS_WRITE
            )
            
        return self.mm.write(buf)
        
    def sync(self) -> None:
        """同步数据到磁盘"""
        if not self.mm:
            raise IOError("内存映射未创建")
            
        self.mm.flush()
        
    def close(self) -> None:
        """关闭内存映射和文件"""
        if self.mm:
            self.mm.close()
            self.mm = None
            
        if self.file:
            self.file.close()
            self.file = None 