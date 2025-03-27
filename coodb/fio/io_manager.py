import os
import mmap
from enum import Enum
from typing import BinaryIO, Optional

class FileIOType(Enum):
    """文件IO类型"""
    StandardFIO = 0   # 标准文件IO
    MemoryMap = 1     # 内存映射IO

DATA_FILE_PERM = 0o644  # 文件权限

class IOManager:
    """IO管理器接口"""
    
    @staticmethod
    def new_io_manager(file_path: str, io_type: FileIOType):
        """创建新的IO管理器
        
        Args:
            file_path: 文件路径
            io_type: IO类型
            
        Returns:
            IO管理器实例
        """
        if io_type == FileIOType.StandardFIO:
            return FileIOManager(file_path)
        elif io_type == FileIOType.MemoryMap:
            return MMapIOManager(file_path)
        else:
            raise ValueError(f"不支持的IO类型: {io_type}")

class FileIOManager:
    """标准文件IO管理器"""
    
    def __init__(self, file_path: str):
        """初始化标准文件IO管理器
        
        Args:
            file_path: 文件路径
        """
        self.file_path = file_path
        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        # 打开文件，如果不存在则创建
        self.fd = open(file_path, "ab+")
        
    def read(self, b: bytearray, offset: int) -> int:
        """从指定位置读取数据
        
        Args:
            b: 用于存储读取数据的字节数组
            offset: 文件中的偏移位置
            
        Returns:
            实际读取的字节数
        """
        self.fd.seek(offset)
        return self.fd.readinto(b)
        
    def write(self, b: bytes) -> int:
        """写入数据
        
        Args:
            b: 要写入的数据
            
        Returns:
            实际写入的字节数
        """
        return self.fd.write(b)
        
    def sync(self) -> None:
        """将数据同步到磁盘"""
        self.fd.flush()
        os.fsync(self.fd.fileno())
        
    def close(self) -> None:
        """关闭文件"""
        if self.fd:
            self.fd.close()
            
    def size(self) -> int:
        """获取文件大小
        
        Returns:
            文件大小（字节）
        """
        current_pos = self.fd.tell()
        self.fd.seek(0, os.SEEK_END)
        size = self.fd.tell()
        self.fd.seek(current_pos)
        return size

class MMapIOManager:
    """内存映射IO管理器"""
    
    def __init__(self, file_path: str):
        """初始化内存映射IO管理器
        
        Args:
            file_path: 文件路径
        """
        self.file_path = file_path
        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        # 打开文件，如果不存在则创建
        self.fd = open(file_path, "ab+")
        self.mmap = None
        self.size_value = 0
        # 初始化内存映射
        self._init_mmap()
        
    def _init_mmap(self) -> None:
        """初始化内存映射"""
        size = self.fd.seek(0, os.SEEK_END)
        self.size_value = size
        
        if size > 0:
            # 如果文件不为空，则创建内存映射
            self.mmap = mmap.mmap(self.fd.fileno(), size, access=mmap.ACCESS_WRITE)
        else:
            # 文件为空的情况，不创建内存映射
            self.mmap = None
            
    def _grow(self, new_size: int) -> None:
        """增大内存映射区域
        
        Args:
            new_size: 新的大小
        """
        # 关闭旧的映射
        if self.mmap:
            self.mmap.close()
            
        # 调整文件大小
        self.fd.seek(new_size - 1)
        self.fd.write(b'\0')
        self.fd.flush()
        
        # 创建新的映射
        self.size_value = new_size
        self.mmap = mmap.mmap(self.fd.fileno(), new_size, access=mmap.ACCESS_WRITE)
        
    def read(self, b: bytearray, offset: int) -> int:
        """从指定位置读取数据
        
        Args:
            b: 用于存储读取数据的字节数组
            offset: 文件中的偏移位置
            
        Returns:
            实际读取的字节数
        """
        if offset >= self.size_value:
            return 0
            
        # 如果文件为空或内存映射还没创建
        if not self.mmap:
            return 0
            
        # 计算可读取的最大长度
        read_size = min(len(b), self.size_value - offset)
        self.mmap.seek(offset)
        data = self.mmap.read(read_size)
        b[:read_size] = data
        return read_size
        
    def write(self, b: bytes) -> int:
        """写入数据
        
        Args:
            b: 要写入的数据
            
        Returns:
            实际写入的字节数
        """
        # 获取当前文件大小
        current_size = self.size_value
        # 计算写入后的新大小
        new_size = current_size + len(b)
        
        # 如果需要增大映射区域
        if current_size < new_size:
            self._grow(new_size)
            
        # 写入数据
        self.mmap.seek(current_size)
        self.mmap.write(b)
        return len(b)
        
    def sync(self) -> None:
        """将数据同步到磁盘"""
        if self.mmap:
            self.mmap.flush()
        self.fd.flush()
        os.fsync(self.fd.fileno())
        
    def close(self) -> None:
        """关闭文件"""
        if self.mmap:
            self.mmap.close()
            self.mmap = None
        if self.fd:
            self.fd.close()
            self.fd = None
            
    def size(self) -> int:
        """获取文件大小
        
        Returns:
            文件大小（字节）
        """
        return self.size_value 