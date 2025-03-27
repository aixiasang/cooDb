import os
import platform

class FileLock:
    """跨平台文件锁实现"""
    
    def __init__(self, lock_file_path: str):
        """初始化文件锁
        
        Args:
            lock_file_path: 锁文件路径
        """
        self.lock_file_path = lock_file_path
        self.file_handle = None
        self.locked = False
        
    def acquire(self) -> bool:
        """获取文件锁
        
        Returns:
            是否成功获取锁
        """
        if self.locked:
            return True
            
        try:
            self.file_handle = open(self.lock_file_path, 'wb')
            
            if platform.system() == 'Windows':
                import msvcrt
                msvcrt.locking(self.file_handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                
            self.locked = True
            return True
        except (IOError, OSError):
            if self.file_handle:
                self.file_handle.close()
                self.file_handle = None
            return False
            
    def release(self):
        """释放文件锁"""
        if not self.locked:
            return
            
        try:
            if platform.system() == 'Windows':
                import msvcrt
                msvcrt.locking(self.file_handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file_handle.fileno(), fcntl.LOCK_UN)
        except:
            pass
        finally:
            if self.file_handle:
                self.file_handle.close()
                self.file_handle = None
            try:
                os.remove(self.lock_file_path)
            except:
                pass
            self.locked = False 