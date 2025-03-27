#!/usr/bin/env python
"""
CoolDB Redis客户端使用示例

本脚本展示了如何使用标准Redis客户端连接到CoolDB的Redis兼容层，
并执行各种类型的操作，包括字符串、哈希、集合等。

使用前确保已经启动了CoolDB Redis服务器:
    python start_redis.py
"""

import time
import redis
import random

def test_string_operations(client):
    """演示字符串操作"""
    print("\n=== 字符串操作 ===")
    
    # 设置字符串
    print("设置键: mystring -> Hello, CoolDB!")
    client.set("mystring", "Hello, CoolDB!")
    
    # 获取字符串
    value = client.get("mystring")
    print(f"获取键: mystring = {value.decode()}")
    
    # 设置带过期时间的字符串
    print("设置带过期时间的键: expiring_string -> 将在3秒后过期")
    client.setex("expiring_string", 3, "将在3秒后过期")
    
    # 立即获取
    value = client.get("expiring_string")
    print(f"立即获取: expiring_string = {value.decode()}")
    
    # 等待过期
    print("等待3秒让键过期...")
    time.sleep(3)
    value = client.get("expiring_string")
    print(f"3秒后获取: expiring_string = {value}")
    
    # 删除键
    print("删除键: mystring")
    client.delete("mystring")
    value = client.get("mystring")
    print(f"删除后获取: mystring = {value}")
    
    # 追加字符串内容
    try:
        print("\n=== 高级字符串操作 ===")
        client.set("greeting", "Hello")
        print("初始字符串: greeting = Hello")
        
        client.append("greeting", ", World!")
        result = client.get("greeting")
        print(f"追加后: greeting = {result.decode() if result else None}")
        
        # 获取字符串长度
        length = client.strlen("greeting")
        print(f"字符串长度: len(greeting) = {length}")
        
        # 部分替换字符串
        client.setrange("greeting", 0, "你好")
        result = client.get("greeting")
        print(f"替换部分后: greeting = {result.decode() if result else None}")
    except redis.exceptions.ResponseError as e:
        print(f"高级字符串操作错误: {e}")

def test_hash_operations(client):
    """演示哈希操作"""
    print("\n=== 哈希操作 ===")
    
    # 创建哈希
    print("创建哈希: user:1 -> {name: 张三, age: 30, email: zhangsan@example.com}")
    client.hset("user:1", "name", "张三")
    client.hset("user:1", "age", "30")
    client.hset("user:1", "email", "zhangsan@example.com")
    
    # 批量设置哈希字段
    print("创建哈希: user:2 -> {name: 李四, age: 25, email: lisi@example.com}")
    client.hset("user:2", "name", "李四")
    client.hset("user:2", "age", "25")
    client.hset("user:2", "email", "lisi@example.com")
    
    # 获取单个字段
    name = client.hget("user:1", "name")
    print(f"获取单个字段: user:1.name = {name.decode()}")
    
    # 获取不存在的字段
    nonexistent = client.hget("user:1", "address")
    print(f"获取不存在的字段: user:1.address = {nonexistent}")
    
    # 删除字段
    print("删除字段: user:1.email")
    client.hdel("user:1", "email")
    email = client.hget("user:1", "email")
    print(f"删除后获取: user:1.email = {email}")
    
    # 批量删除字段
    print("批量删除字段: user:2.age 和 user:2.email")
    client.hdel("user:2", "age", "email")
    
    # 数据类型
    type_value = client.type("user:1")
    print(f"键类型: user:1 的类型是 {type_value.decode()}")
    
    # 哈希高级操作
    try:
        print("\n=== 哈希高级操作 ===")
        # 创建测试哈希
        client.hset("product:1", "name", "智能手机")
        client.hset("product:1", "price", "3999")
        client.hset("product:1", "stock", "100")
        print("创建哈希: product:1 -> {name: 智能手机, price: 3999, stock: 100}")
        
        # 检查字段是否存在
        exists = client.hexists("product:1", "price")
        print(f"检查字段是否存在: product:1.price 存在? {exists}")
        
        exists = client.hexists("product:1", "color")
        print(f"检查字段是否存在: product:1.color 存在? {exists}")
        
        # 获取所有字段
        try:
            all_fields = client.hkeys("product:1")
            print(f"获取所有字段名: product:1 的字段有: {[f.decode() for f in all_fields]}")
        except redis.exceptions.ResponseError as e:
            print(f"获取所有字段名错误: {e}")
        
        # 获取所有值
        try:
            all_values = client.hvals("product:1")
            print(f"获取所有字段值: product:1 的值有: {[v.decode() for v in all_values]}")
        except redis.exceptions.ResponseError as e:
            print(f"获取所有字段值错误: {e}")
        
        # 获取哈希长度
        try:
            length = client.hlen("product:1")
            print(f"哈希长度: product:1 包含 {length} 个字段")
        except redis.exceptions.ResponseError as e:
            print(f"获取哈希长度错误: {e}")
    except redis.exceptions.ResponseError as e:
        print(f"哈希高级操作错误: {e}")

def test_set_operations(client):
    """演示集合操作"""
    print("\n=== 集合操作 ===")
    
    # 创建集合
    print("创建集合: fruits -> {apple, banana, orange}")
    client.sadd("fruits", "apple")
    client.sadd("fruits", "banana", "orange")
    
    # 检查成员是否存在
    is_member = client.sismember("fruits", "apple")
    print(f"检查成员: apple 是否在 fruits 集合中? {is_member}")
    
    is_member = client.sismember("fruits", "grape")
    print(f"检查成员: grape 是否在 fruits 集合中? {is_member}")
    
    # 创建另一个集合
    print("创建集合: vegetables -> {carrot, potato, tomato}")
    client.sadd("vegetables", "carrot", "potato", "tomato")
    
    # 移除成员
    print("移除成员: fruits 中的 banana")
    client.srem("fruits", "banana")
    is_member = client.sismember("fruits", "banana")
    print(f"检查成员: banana 是否在 fruits 集合中? {is_member}")
    
    # 数据类型
    type_value = client.type("fruits")
    print(f"键类型: fruits 的类型是 {type_value.decode()}")
    
    # 集合高级操作
    try:
        print("\n=== 集合高级操作 ===")
        # 创建测试集合
        client.sadd("colors:warm", "red", "orange", "yellow")
        client.sadd("colors:cool", "blue", "green", "purple")
        print("创建集合: colors:warm -> {red, orange, yellow}")
        print("创建集合: colors:cool -> {blue, green, purple}")
        
        
        # 获取集合所有成员
        try:
            members = client.smembers("colors:warm")
            print(f"获取所有成员: colors:warm = {[m.decode() for m in members]}")
        except redis.exceptions.ResponseError as e:
            print(f"获取所有成员错误: {e}")
        
        # 获取集合成员数量
        try:
            count = client.scard("colors:warm")
            print(f"集合成员数量: colors:warm 有 {count} 个成员")
        except redis.exceptions.ResponseError as e:
            print(f"获取集合成员数量错误: {e}")
        
        # 随机获取成员
        try:
            random_member = client.srandmember("colors:warm")
            print(f"随机获取成员: 从 colors:warm 中获取 -> {random_member.decode() if random_member else None}")
        except redis.exceptions.ResponseError as e:
            print(f"随机获取成员错误: {e}")
        
        # 尝试集合差集操作
        try:
            diff = client.sdiff("colors:warm", "colors:cool")
            print(f"集合差集: colors:warm - colors:cool = {[d.decode() for d in diff]}")
        except redis.exceptions.ResponseError as e:
            print(f"集合差集操作错误: {e}")
    except redis.exceptions.ResponseError as e:
        print(f"集合高级操作错误: {e}")

def test_key_management(client):
    """演示键管理操作"""
    print("\n=== 键管理操作 ===")
    
    # 设置一些测试键
    client.set("key1", "value1")
    client.set("key2", "value2")
    client.set("key3", "value3")
    print("设置键: key1, key2, key3")
    
    # 检查键是否存在
    try:
        exists = client.exists("key1")
        print(f"键存在? key1 存在: {exists}")
        
        exists = client.exists("nonexistent")
        print(f"键存在? nonexistent 存在: {exists}")
    except redis.exceptions.ResponseError as e:
        print(f"检查键存在错误: {e}")
    
    # 设置过期时间
    try:
        client.expire("key1", 10)
        print("为key1设置10秒的过期时间")
        
        # 获取剩余过期时间
        ttl = client.ttl("key1")
        print(f"key1剩余过期时间: {ttl}秒")
        
        ttl = client.ttl("key2")
        print(f"key2剩余过期时间: {ttl}秒 (无过期时间)")
    except redis.exceptions.ResponseError as e:
        print(f"设置/获取过期时间错误: {e}")
    
    # 重命名键
    try:
        client.rename("key2", "key2_new")
        print("重命名key2为key2_new")
        
        value = client.get("key2_new")
        print(f"获取重命名后的键: key2_new = {value.decode() if value else None}")
        
        exists = client.exists("key2")
        print(f"原键是否存在? key2 存在: {exists}")
    except redis.exceptions.ResponseError as e:
        print(f"重命名键错误: {e}")
    
    # 获取键模式
    try:
        keys = client.keys("key*")
        print(f"匹配模式'key*'的键: {[k.decode() for k in keys]}")
    except redis.exceptions.ResponseError as e:
        print(f"获取键模式错误: {e}")

def test_bulk_operations(client):
    """演示批量操作"""
    print("\n=== 批量操作 ===")
    
    # 批量设置键值对
    try:
        key_values = {
            "batch1": "value1",
            "batch2": "value2",
            "batch3": "value3",
            "batch4": "value4"
        }
        client.mset(key_values)
        print(f"批量设置键值对: {list(key_values.items())}")
    except redis.exceptions.ResponseError as e:
        print(f"批量设置键值对错误: {e}")
        # 如果不支持mset，单独设置键
        for k, v in key_values.items():
            client.set(k, v)
        print("使用单独set命令设置键值对")
    
    # 批量获取值
    try:
        values = client.mget(["batch1", "batch2", "batch3", "nonexistent"])
        print("批量获取值:")
        for i, key in enumerate(["batch1", "batch2", "batch3", "nonexistent"]):
            val = values[i]
            print(f"  {key} = {val.decode() if val else None}")
    except redis.exceptions.ResponseError as e:
        print(f"批量获取值错误: {e}")
        # 如果不支持mget，单独获取键
        print("使用单独get命令获取值:")
        for key in ["batch1", "batch2", "batch3", "nonexistent"]:
            val = client.get(key)
            print(f"  {key} = {val.decode() if val else None}")
    
    # 批量删除键
    try:
        count = client.delete("batch1", "batch2", "nonexistent")
        print(f"批量删除键: 成功删除 {count} 个键")
    except redis.exceptions.ResponseError as e:
        print(f"批量删除键错误: {e}")

def test_pipeline(client):
    """演示管道操作（批量执行命令）"""
    try:
        print("\n=== 管道操作 ===")
        
        # 创建管道
        pipe = client.pipeline()
        
        # 向管道添加命令
        pipe.set("pipe1", "value1")
        pipe.set("pipe2", "value2")
        pipe.sadd("pipeset", "member1", "member2")
        pipe.get("pipe1")
        pipe.smembers("pipeset")
        
        # 执行管道中的所有命令
        print("执行包含5个命令的管道")
        results = pipe.execute()
        
        # 处理结果
        print("管道执行结果:")
        print(f"  设置pipe1: {results[0]}")
        print(f"  设置pipe2: {results[1]}")
        print(f"  添加集合成员: {results[2]}")
        print(f"  获取pipe1: {results[3].decode() if results[3] else None}")
        print(f"  获取集合成员: {[m.decode() for m in results[4]]}")
    except redis.exceptions.ResponseError as e:
        print(f"管道操作错误: {e}")
    except AttributeError as e:
        print(f"管道操作不支持: {e}")

def test_random_data(client):
    """演示使用随机数据进行测试"""
    try:
        print("\n=== 随机数据测试 ===")
        
        # 生成一些随机键值对
        key_count = 10
        print(f"生成{key_count}个随机键值对")
        
        for i in range(key_count):
            key = f"random:{random.randint(1000, 9999)}"
            value = "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(20))
            client.set(key, value)
            print(f"  设置: {key} -> {value}")
        
        # 随机对字符串键执行操作
        if random.choice([True, False]):
            random_key = f"random:{random.randint(1000, 9999)}"
            client.set(random_key, "0")
            print(f"尝试对{random_key}执行自增操作")
            try:
                for _ in range(5):
                    client.incr(random_key)
                value = client.get(random_key)
                print(f"  自增5次后: {random_key} = {value.decode() if value else None}")
            except redis.exceptions.ResponseError as e:
                print(f"  自增操作错误: {e}")
        
        # 随机生成一个集合
        random_set = f"randomset:{random.randint(1000, 9999)}"
        members = [f"member{i}" for i in range(1, 6)]
        client.sadd(random_set, *members)
        print(f"创建随机集合: {random_set} -> {members}")
        
        # 随机获取并删除一个成员
        try:
            popped = client.spop(random_set)
            print(f"随机弹出成员: {popped.decode() if popped else None}")
            
            remaining = client.smembers(random_set)
            print(f"剩余成员: {[m.decode() for m in remaining]}")
        except redis.exceptions.ResponseError as e:
            print(f"随机弹出操作错误: {e}")
    except Exception as e:
        print(f"随机数据测试错误: {e}")

def demonstrate_error_handling(client):
    """演示错误处理"""
    print("\n=== 错误处理 ===")
    
    # 设置字符串
    client.set("mykey", "Hello")
    
    try:
        # 尝试对字符串键执行哈希操作 (类型错误)
        print("尝试对字符串键执行哈希操作:")
        client.hget("mykey", "field")
    except redis.exceptions.ResponseError as e:
        print(f"错误: {e}")
    
    try:
        # 尝试执行不支持的命令
        print("尝试执行不支持的命令:")
        client.execute_command("UNSUPPORTED")
    except redis.exceptions.ResponseError as e:
        print(f"错误: {e}")
    
    try:
        # 参数不足
        print("参数不足:")
        client.execute_command("GET")
    except redis.exceptions.ResponseError as e:
        print(f"错误: {e}")
    
    try:
        # 尝试对集合使用字符串命令
        client.sadd("myset", "value")
        print("尝试对集合使用字符串命令:")
        client.append("myset", "more")
    except redis.exceptions.ResponseError as e:
        print(f"错误: {e}")
    
    try:
        # 尝试对不存在的键使用del以外的命令
        print("尝试对不存在的键使用类型命令:")
        result = client.type("nonexistent:key")
        print(f"结果: {result.decode() if result else None}")
    except redis.exceptions.ResponseError as e:
        print(f"错误: {e}")
    
    try:
        # 错误的命令格式
        print("错误的命令格式:")
        client.execute_command("SET", "key")
    except redis.exceptions.ResponseError as e:
        print(f"错误: {e}")

def run_redis_examples():
    """运行Redis示例"""
    # 创建Redis客户端
    client = redis.Redis(
        host="localhost",
        port=6379,  # 默认端口
        socket_timeout=5.0
    )
    
    try:
        # 测试连接
        print("测试连接到CoolDB Redis服务器...")
        if client.ping():
            print("连接成功!\n")
        
        # 运行各种操作示例
        test_string_operations(client)
        test_hash_operations(client)
        test_set_operations(client)
        test_key_management(client)
        test_bulk_operations(client)
        test_pipeline(client)
        test_random_data(client)
        demonstrate_error_handling(client)
        
        print("\n所有示例执行完毕!")
    except redis.exceptions.ConnectionError:
        print("""
连接失败! 请确保CoolDB Redis服务器已启动。

使用以下命令启动服务器:
    python start_redis.py
        """)
    finally:
        # 关闭客户端连接
        client.close()

if __name__ == "__main__":
    run_redis_examples() 