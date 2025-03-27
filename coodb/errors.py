"""错误定义模块

该模块定义了数据库操作中可能遇到的各种错误类型。
"""

class ErrKeyNotFound(Exception):
    """键不存在错误"""
    def __init__(self, message="Key not found"):
        self.message = message
        super().__init__(self.message)

class ErrKeyIsEmpty(Exception):
    """键为空错误"""
    def __init__(self, message="Key is empty"):
        self.message = message
        super().__init__(self.message)

class ErrDataFileNotFound(Exception):
    """数据文件不存在错误"""
    def __init__(self, message="Data file not found"):
        self.message = message
        super().__init__(self.message)

class ErrIndexUpdateFailed(Exception):
    """索引更新失败错误"""
    def __init__(self, message="Failed to update index"):
        self.message = message
        super().__init__(self.message)

class ErrDataDirectoryCorrupted(Exception):
    """数据目录损坏错误"""
    def __init__(self, message="Data directory is corrupted"):
        self.message = message
        super().__init__(self.message)

class ErrInvalidCRC(Exception):
    """CRC校验错误"""
    def __init__(self, message="Invalid CRC checksum"):
        self.message = message
        super().__init__(self.message)

class ErrDatabaseIsUsing(Exception):
    """数据库已被使用错误"""
    def __init__(self, message="Database is being used by another process"):
        self.message = message
        super().__init__(self.message)

class ErrDataFileIsUsing(Exception):
    """数据文件已被使用错误"""
    def __init__(self, message="Data file is being used by another process"):
        self.message = message
        super().__init__(self.message)

class ErrDatabaseClosed(Exception):
    """数据库已关闭错误"""
    def __init__(self, message="Database is closed"):
        self.message = message
        super().__init__(self.message)

class ErrBatchClosed(Exception):
    """批处理已关闭错误"""
    def __init__(self, message="Batch is closed"):
        self.message = message
        super().__init__(self.message)

class ErrTxnFinished(Exception):
    """事务已完成错误"""
    def __init__(self, message="Transaction is finished"):
        self.message = message
        super().__init__(self.message)

class ErrActiveTransactionExceeded(Exception):
    """活跃事务数超限错误"""
    def __init__(self, message="Exceeded max number of active transactions"):
        self.message = message
        super().__init__(self.message)

class ErrMergeRunning(Exception):
    """合并操作正在运行错误"""
    def __init__(self, message="Merge operation is running"):
        self.message = message
        super().__init__(self.message)

class ErrUnsupportedOperation(Exception):
    """不支持的操作错误"""
    def __init__(self, message="Unsupported operation"):
        self.message = message
        super().__init__(self.message)

class ErrDirPathNotExist(Exception):
    """数据目录不存在错误"""
    pass

class ErrDataFileIsUsing(Exception):
    """数据文件正在使用中"""
    pass