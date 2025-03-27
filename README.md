# 🚀 CoolDB

CoolDB 是一个基于 Bitcask 模型的高性能键值存储数据库，使用 Python 实现。它具有高吞吐量、低延迟和简单的数据模型，适用于需要快速键值访问的应用场景。

## ✨ 特性

- **🚄 高性能**：所有写操作都是顺序写入，读操作通过内存索引实现
- **🧩 简单可靠**：数据模型简单，无复杂数据结构
- **🔄 崩溃恢复**：自动从崩溃中恢复
- **💾 易于备份**：数据文件可以直接复制进行备份
- **🌐 HTTP接口**：基于FastAPI提供高性能RESTful API接口
- **🔌 Redis兼容**：实现Redis协议兼容层，支持Redis客户端直接连接
- **📚 自动文档**：集成OpenAPI文档，交互式API测试
- **📊 可视化管理**：Web 界面可视化管理数据库

## 📦 项目结构

项目由以下主要模块组成：

- **📁 coodb/** - 核心数据库实现
  - **🔑 db.py** - 数据库核心功能
  - **📇 index/** - 索引实现（B树和ART索引）
  - **📄 data_file.py** - 数据文件管理
  - **⚙️ options.py** - 配置选项
  - **📋 batch.py** - 批量操作支持
  - **🔍 iterator.py** - 迭代器实现
  
- **🌐 coodb/http/** - HTTP接口实现
  - **🔄 api.py** - FastAPI REST接口
  - **📊 dashboard.py** - Web管理界面

- **🔌 coodb/redis/** - Redis协议兼容层
  - **🧰 types.py** - Redis数据结构实现
  - **🌉 server.py** - Redis协议服务器
  - **💬 protocol.py** - Redis协议解析与响应

- **🧪 tests/** - 测试用例
  - **🔬 单元测试和集成测试**
  
- **⚡ benchmarks/** - 性能基准测试
  - **📏 redis_benchmark.py** - Redis性能测试
  
- **🔍 examples/** - 使用示例
  - **📝 redis_examples.py** - Redis客户端使用示例

## 🛠️ 安装

```bash
# 克隆仓库
git clone https://github.com/aixiasang/cooldb.git
cd cooldb

# 安装依赖
pip install -r requirements.txt

# 安装 CoolDB
pip install -e .
```

## 📘 作为库使用

```python
from coodb.db import DB
from coodb.options import Options

# 创建数据库实例
options = Options(dir_path="./data")
db = DB(options)

# 写入数据
db.put(b"hello", b"world")

# 读取数据
value = db.get(b"hello")
print(value)  # b"world"

# 删除数据
db.delete(b"hello")

# 批量操作
batch = db.new_batch()
batch.put(b"key1", b"value1")
batch.put(b"key2", b"value2")
batch.delete(b"key3")
batch.commit()

# 遍历所有键值对
it = db.iterator()
it.rewind()
while it.valid():
    key = it.key()
    it.next()
    print(key)

# 合并数据文件（回收空间）
db.merge()

# 关闭数据库
db.close()
```

## 🌐 HTTP 服务

CoolDB 提供了基于 FastAPI 的 HTTP 服务，包括 RESTful API 和 Web 管理界面。

### 🚀 启动 HTTP 服务

```bash
# 使用默认配置
python start_coodb.py

# 自定义配置
python start_coodb.py --port 8080 --dir /path/to/data

# 开发模式（热重载）
python start_coodb.py --reload
```

### 📚 API 文档

FastAPI 自动生成交互式 API 文档，可通过以下地址访问：

- 🔍 Swagger UI：http://localhost:8000/docs
- 📖 ReDoc：http://localhost:8000/redoc

### 🔌 HTTP API

API 基于 RESTful 设计，支持以下操作：

- `GET /api/v1/keys` - 📋 获取所有键列表（支持分页和搜索）
- `GET /api/v1/keys/{key}` - 🔍 获取指定键的值
- `PUT /api/v1/keys/{key}` - ✏️ 设置键值对
- `DELETE /api/v1/keys/{key}` - 🗑️ 删除键值对
- `POST /api/v1/batch` - 📦 批量操作
- `POST /api/v1/merge` - 🔄 执行数据合并
- `GET /api/v1/stats` - 📊 获取数据库统计信息
- `GET /api/v1/backup` - 💾 下载数据库备份
- `GET /api/v1/export` - 📤 导出数据为 JSON 格式
- `POST /api/v1/import` - 📥 从 JSON 导入数据

### 📊 Web 管理界面

访问 `/dashboard` 页面进入 Web 管理界面，提供：

- 📈 数据库统计信息可视化
- 🔑 键值对浏览、创建、编辑、删除
- 🛠️ 数据库操作：备份、导入/导出、合并
- 🔍 检索功能：分页和搜索

## 🔌 Redis 协议支持

CoolDB实现了完整的Redis协议兼容层，允许Redis客户端直接连接到CoolDB进行操作。启动Redis服务后，您可以使用任何Redis客户端连接到CoolDB。

### 🚀 启动Redis服务

使用以下命令启动Redis服务：

```bash
# 使用默认配置
python start_redis.py

# 使用自定义配置
python start_redis.py --port 7379 --dir /path/to/data
```

### 📋 支持的Redis命令

CoolDB的Redis兼容层支持以下命令：
- 📝 **字符串操作**: `SET`, `GET`, `DEL`
- 🗃️ **哈希操作**: `HSET`, `HGET`, `HDEL`, `HEXISTS`
- 📑 **集合操作**: `SADD`, `SISMEMBER`, `SREM`
- 🛠️ **通用操作**: `PING`, `TYPE`, `QUIT`

### 🔄 Redis客户端连接示例

您可以使用`redis-cli`或任何Redis客户端库连接到CoolDB：

```bash
# 使用redis-cli连接
redis-cli -p 6379

# 基本操作
> SET mykey "Hello, CoolDB!"
OK
> GET mykey
"Hello, CoolDB!"
```

使用Python redis库：
```python
import redis

# 连接到CoolDB Redis服务
r = redis.Redis(host='localhost', port=6379)

# 字符串操作
r.set('mykey', 'Hello, CoolDB!')
value = r.get('mykey')
print(value)  # b'Hello, CoolDB!'

# 哈希操作
r.hset('myhash', 'field1', 'value1')
field_value = r.hget('myhash', 'field1')
print(field_value)  # b'value1'

# 集合操作
r.sadd('myset', 'member1', 'member2')
is_member = r.sismember('myset', 'member1')
print(is_member)  # True
```

### 📊 Redis性能基准测试

CoolDB提供了基准测试工具，用于测试Redis兼容层的性能，并可以与标准Redis进行比较。

#### 🚀 运行基准测试

```bash
# 快速测试
python benchmarks/run_benchmarks.py

# 标准测试，并与标准Redis进行比较（需要标准Redis运行在6378端口）
python benchmarks/run_benchmarks.py --profile standard --compare

# 直接使用基准测试脚本进行自定义测试
python benchmarks/redis_benchmark.py --operations 10000 --clients 20 --tests string,hash
```

#### ⚙️ 基准测试选项

- `--profile`: 🔖 预设配置文件，可选值: quick, standard, comprehensive
- `--compare`: 🔄 是否与标准Redis进行比较
- `--operations`: 🔢 每种命令执行的操作数
- `--value-size`: 📏 值的大小（字节）
- `--clients`: 👥 并发客户端数量
- `--tests`: 🧪 要运行的测试，可选值: string,hash,set,all

#### 🚀 性能优化提示

- 🔥 对于高性能写入场景，建议将`sync_writes`设置为`False`
- 📦 使用批处理操作可以显著提高性能
- 📈 增加`max_file_size`可以减少合并操作，但会增加内存使用

## ⚙️ 配置选项

`Options` 类支持以下配置选项：

- `dir_path`：📁 数据目录路径
- `max_file_size`：📏 数据文件最大大小（字节），默认 32MB
- `sync_writes`：💾 是否同步写入磁盘，默认 False
- `index_type`：🔍 索引类型（BTREE 或 ART），默认 BTREE

## 🔧 性能调优

- 🚀 对于高性能写入场景，可以设置 `sync_writes=False` 并定期手动 `sync()`
- 📦 使用批处理操作（Batch）可以提高写入吞吐量
- 🧹 定期执行 `merge()` 操作，回收无效空间

## 🧪 测试

CoolDB包含全面的测试套件，确保所有功能正常工作：

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_db.py
pytest tests/test_redis.py
```

## 📝 示例

`examples`目录包含展示CoolDB各种功能的示例脚本：

- **basic_usage.py** - 📘 基本数据库操作
- **redis_examples.py** - 🔌 Redis客户端示例
- **batch_operations.py** - 📦 批量操作示例
- **http_client.py** - 🌐 HTTP API客户端示例

## 📋 待办事项

- [ ] 🔒 添加身份验证
- [ ] 📊 增强监控功能
- [ ] 🧠 实现更多Redis数据结构
- [ ] 🌟 扩展HTTP API功能

## 📄 许可证

[MIT License](LICENSE) 