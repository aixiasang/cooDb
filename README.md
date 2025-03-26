# Coodb

Coodb是一个基于Bitcask模型的高性能键值存储数据库，使用Python实现。它提供了简单而高效的键值存储功能，同时支持事务、合并压缩、索引等高级特性。

## 特性

- **高性能**: 基于Bitcask模型，所有键都存储在内存中，提供快速的查询性能
- **持久化**: 所有数据都会被写入磁盘，确保数据安全
- **事务支持**: 支持批量操作的原子性事务
- **多种索引结构**: 支持B树、B+树、ART(自适应基数树)和跳表等多种索引结构
- **合并压缩**: 自动合并数据文件，回收空间
- **HTTP API**: 提供REST风格的HTTP接口
- **并发安全**: 支持多线程并发操作

## 安装

```bash
pip install coodb
```

## 快速开始

### 基本使用

```python
from coodb.db import DB
from coodb.options import Options

# 创建数据库选项
options = Options(dir_path="./coodb_data")

# 打开数据库
db = DB(options)

# 写入数据
db.put(b"hello", b"world")

# 读取数据
value = db.get(b"hello")
print(value)  # 输出: b'world'

# 删除数据
db.delete(b"hello")

# 关闭数据库
db.close()
```

### 使用事务

```python
from coodb.db import DB
from coodb.options import Options

# 创建数据库
options = Options(dir_path="./coodb_data")
db = DB(options)

# 创建一个批处理
batch = db.new_batch()

# 添加操作到批处理
batch.put(b"key1", b"value1")
batch.put(b"key2", b"value2")
batch.delete(b"key3")

# 提交批处理
batch.commit()

# 关闭数据库
db.close()
```

### 使用迭代器

```python
from coodb.db import DB
from coodb.options import Options

# 创建数据库
options = Options(dir_path="./coodb_data")
db = DB(options)

# 向数据库写入一些数据
db.put(b"key1", b"value1")
db.put(b"key2", b"value2")
db.put(b"key3", b"value3")

# 创建迭代器
iterator = db.iterator()

# 迭代所有键值对
iterator.rewind()  # 将迭代器移至起始位置
while iterator.valid():
    print(f"Key: {iterator.key()}, Value: {iterator.value()}")
    iterator.next()

# 关闭数据库
db.close()
```

### 使用HTTP API

Coodb内置了HTTP服务器，可以通过HTTP API访问数据库。

```python
from coodb.http.server import Server
from coodb.options import Options

# 创建数据库选项
options = Options(dir_path="./coodb_data")

# 创建HTTP服务器
server = Server(options, host="localhost", port=8080)

# 启动服务器
server.start()

# 停止服务器
# server.stop()
```

HTTP API示例：

```bash
# 写入数据
curl -X PUT http://localhost:8080/api/key/hello -d "world"

# 读取数据
curl http://localhost:8080/api/key/hello

# 删除数据
curl -X DELETE http://localhost:8080/api/key/hello
```

## 高级配置

Coodb提供了多种配置选项，可以通过Options类进行设置：

```python
from coodb.options import Options
from coodb.index import IndexType

options = Options(
    dir_path="./coodb_data",      # 数据目录路径
    index_type=IndexType.BTREE,    # 索引类型(BTREE, ART, BPTREE, SKIPLIST)
    sync_writes=False,             # 是否同步写入磁盘
    max_file_size=1024*1024*100,   # 数据文件最大大小(100MB)
    max_batch_num=10000,           # 批处理最大操作数
    max_batch_delay=10,            # 批处理最大延迟(秒)
    mmap_at_startup=True,          # 启动时是否使用内存映射
    merge_ratio=0.5                # 合并触发比例
)
```

## 性能优化

为获得最佳性能，推荐以下设置：

1. 将`sync_writes`设为False(提高写入性能，但在崩溃时可能丢失数据)
2. 启用`mmap_at_startup`(提高读取性能)
3. 定期调用`merge()`方法回收空间

## 贡献

欢迎提交问题和Pull Request！

## 许可证

MIT License