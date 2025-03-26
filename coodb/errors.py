class ErrKeyIsEmpty(Exception):
    """键为空错误"""
    pass

class ErrKeyNotFound(Exception):
    """键不存在错误"""
    pass

class ErrDirPathNotExist(Exception):
    """数据目录不存在错误"""
    pass

class ErrDataFileNotFound(Exception):
    """数据文件不存在错误"""
    pass

class ErrDatabaseClosed(Exception):
    """数据库已关闭错误"""
    pass

class ErrDatabaseIsUsing(Exception):
    """数据库正在被使用错误"""
    pass

class ErrMergeInProgress(Exception):
    """正在进行merge操作错误"""
    pass

class ErrInvalidOptions(Exception):
    """无效的配置选项错误"""
    pass

class ErrTransactionNotStarted(Exception):
    """事务未开始错误"""
    pass

class ErrTransactionAlreadyStarted(Exception):
    """事务已经开始错误"""
    pass

class ErrIndexUpdateFailed(Exception):
    """索引更新失败错误"""
    pass

class ErrIOError(Exception):
    """IO错误"""
    pass 
class ErrInvalidCRC(Exception):
    "crc检验错误"
    pass

class ErrDataFileIsUsing(Exception):
    """数据文件正在使用中"""
    pass