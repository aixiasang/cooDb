import os
import mmap
from .io_manager import DATA_FILE_PERM

class MMap:
    """内存映射IO"""
    
    def __init__(self, file_name: str):
        """初始化内存映射IO
        
        Args:
            file_name: 文件名
        """
        # 创建文件（如果不存在）
        fd = os.open(file_name, os.O_CREAT | os.O_RDWR, DATA_FILE_PERM)
        try:
            # 获取文件大小
            size = os.fstat(fd).st_size
            if size == 0:
                # 如果是空文件，至少分配一页大小
                os.truncate(fd, mmap.PAGESIZE)
                size = mmap.PAGESIZE
                
            # 创建内存映射
            self.mm = mmap.mmap(
                fd,
                size,
                access=mmap.ACCESS_READ
            )
        finally:
            os.close(fd)
            
    def read(self, b: bytearray, offset: int) -> int:
        """从文件的给定位置读取数据
        
        Args:
            b: 要读入的字节数组
            offset: 读取位置的偏移量
            
        Returns:
            读取的字节数
        """
        return self.mm.readinto(b, offset)
        
    def write(self, b: bytes) -> int:
        """写入字节数组到文件
        
        Args:
            b: 要写入的字节数组
            
        Returns:
            写入的字节数
        """
        raise NotImplementedError("内存映射IO不支持写入操作")
        
    def sync(self) -> None:
        """持久化数据"""
        raise NotImplementedError("内存映射IO不支持同步操作")
        
    def close(self) -> None:
        """关闭文件"""
        if self.mm:
            self.mm.close()
            
    def size(self) -> int:
        """获取文件大小
        
        Returns:
            文件大小（字节）
        """
        return self.mm.size() 