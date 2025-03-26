import os
import shutil
import platform
from typing import List, Optional

def dir_size(dir_path: str) -> int:
    """获取目录大小
    
    Args:
        dir_path: 目录路径
        
    Returns:
        目录大小（字节）
    """
    total_size = 0
    for dirpath, _, filenames in os.walk(dir_path):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            total_size += os.path.getsize(file_path)
    return total_size

def available_disk_size() -> int:
    """获取当前磁盘可用空间
    
    Returns:
        可用空间大小（字节）
    """
    if platform.system() == 'Windows':
        import ctypes
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(os.getcwd()),
            None,
            None,
            ctypes.pointer(free_bytes)
        )
        return free_bytes.value
    else:
        st = os.statvfs(os.getcwd())
        return st.f_bavail * st.f_frsize

def copy_dir(src: str, dest: str, exclude: Optional[List[str]] = None) -> None:
    """复制目录
    
    Args:
        src: 源目录
        dest: 目标目录
        exclude: 要排除的文件名模式列表
    """
    if not os.path.exists(dest):
        os.makedirs(dest)
        
    for item in os.listdir(src):
        # 检查是否需要排除
        if exclude:
            skip = False
            for pattern in exclude:
                if pattern == item:
                    skip = True
                    break
            if skip:
                continue
                
        s = os.path.join(src, item)
        d = os.path.join(dest, item)
        
        if os.path.isdir(s):
            copy_dir(s, d, exclude)
        else:
            shutil.copy2(s, d) 