import os
from .io_manager import DATA_FILE_PERM

class FileIO:
    """标准系统文件IO"""
    
    def __init__(self, file_name: str):
        """初始化标准文件IO
        
        Args:
            file_name: 文件名
        """
        self.fd = os.open(
            file_name,
            os.O_CREAT | os.O_RDWR | os.O_APPEND,
            DATA_FILE_PERM
        )
        
    def read(self, b: bytearray, offset: int) -> int:
        """从文件的给定位置读取数据
        
        Args:
            b: 要读入的字节数组
            offset: 读取位置的偏移量
            
        Returns:
            读取的字节数
        """
        return os.pread(self.fd, len(b), offset, b)
        
    def write(self, b: bytes) -> int:
        """写入字节数组到文件
        
        Args:
            b: 要写入的字节数组
            
        Returns:
            写入的字节数
        """
        return os.write(self.fd, b)
        
    def sync(self) -> None:
        """持久化数据"""
        os.fsync(self.fd)
        
    def close(self) -> None:
        """关闭文件"""
        os.close(self.fd)
        
    def size(self) -> int:
        """获取文件大小
        
        Returns:
            文件大小（字节）
        """
        return os.fstat(self.fd).st_size 