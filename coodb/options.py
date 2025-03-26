from dataclasses import dataclass
from typing import Optional
from .index.index import IndexType

@dataclass
class Options:
    """数据库配置选项"""
    
    dir_path: str  # 数据目录
    max_file_size: int = 256 * 1024 * 1024  # 数据文件最大大小，默认256MB
    sync_writes: bool = False  # 是否同步写入
    index_type: IndexType = IndexType.BTREE  # 索引类型
    mmap_at_startup: bool = False  # 是否在启动时使用内存映射
    byte_write_buffer_size: Optional[int] = None  # 写缓冲区大小
    merge_ratio_threshold: float = 0.5  # merge触发阈值
    disable_wal: bool = False  # 是否禁用WAL
    bytes_per_sync: int = 0  # 每写入多少字节同步一次，0表示不自动同步

    def __init__(self, 
                 dir_path: str,
                 max_file_size: int = 256 * 1024 * 1024,  # 256MB
                 sync_writes: bool = False,
                 index_type: IndexType = IndexType.BTREE,
                 mmap_at_startup: bool = False,
                 bytes_per_sync: int = 0  # 新增选项：每写入多少字节同步一次
                 ):
        """初始化数据库选项
        
        Args:
            dir_path: 数据目录路径
            max_file_size: 单个数据文件的最大大小
            sync_writes: 是否同步写入
            index_type: 索引类型
            mmap_at_startup: 是否在启动时使用内存映射
            bytes_per_sync: 每写入多少字节同步一次，0表示不自动同步
        """
        self.dir_path = dir_path
        self.max_file_size = max_file_size
        self.sync_writes = sync_writes
        self.index_type = index_type
        self.mmap_at_startup = mmap_at_startup
        self.bytes_per_sync = bytes_per_sync  # 新增属性 