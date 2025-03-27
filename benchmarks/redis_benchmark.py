#!/usr/bin/env python
"""
CoolDB Redis性能基准测试

本脚本测试CoolDB Redis兼容层的性能，并可以选择与标准Redis进行比较。
支持测试各种命令，包括SET/GET、HSET/HGET和SADD/SISMEMBER等。

使用方法:
    python redis_benchmark.py [选项]

选项:
    --host HOST         要测试的Redis服务器地址，默认为localhost
    --port PORT         要测试的Redis服务器端口，默认为6379
    --compare           是否与标准Redis进行比较（需要标准Redis运行在6378端口）
    --operations N      每种命令执行的操作数，默认为10000
    --value-size N      值的大小（字节），默认为100
    --clients N         并发客户端数量，默认为10
    --tests TESTS       要运行的测试（逗号分隔），可选值: string,hash,set,all
                        默认为all

示例:
    # 运行所有基准测试
    python redis_benchmark.py
    
    # 比较CoolDB Redis与标准Redis
    python redis_benchmark.py --compare
    
    # 只测试字符串操作，使用50个客户端，每个操作5000次
    python redis_benchmark.py --tests string --clients 50 --operations 5000
"""

import os
import time
import random
import string
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor

import redis

class RedisBenchmark:
    """Redis性能基准测试类"""
    
    def __init__(self, host="localhost", port=6379, num_operations=10000, 
                 value_size=100, num_clients=10, compare_with_redis=False):
        """初始化基准测试
        
        Args:
            host: Redis服务器地址
            port: Redis服务器端口
            num_operations: 每种命令执行的操作数
            value_size: 值的大小（字节）
            num_clients: 并发客户端数量
            compare_with_redis: 是否与标准Redis进行比较
        """
        self.host = host
        self.port = port
        self.num_operations = num_operations
        self.value_size = value_size
        self.num_clients = num_clients
        self.compare_with_redis = compare_with_redis
        
        # 如果对比测试标准Redis，它应该运行在不同的端口上
        self.redis_port = 6378  # 标准Redis端口
        
        # 测试结果
        self.results = {}
    
    def _generate_random_string(self, size):
        """生成指定大小的随机字符串"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=size))
    
    def _string_operation_worker(self, client, worker_id, num_ops, results):
        """字符串操作工作线程"""
        ops_completed = 0
        start_time = time.time()
        
        value = self._generate_random_string(self.value_size)
        
        for i in range(num_ops):
            key = f"bench:str:{worker_id}:{i}"
            
            # SET操作
            client.set(key, value)
            
            # GET操作
            result = client.get(key)
            
            # DEL操作
            client.delete(key)
            
            ops_completed += 3  # 每次循环执行3个操作
        
        elapsed = time.time() - start_time
        results[worker_id] = (ops_completed, elapsed)
    
    def _hash_operation_worker(self, client, worker_id, num_ops, results):
        """哈希操作工作线程"""
        ops_completed = 0
        start_time = time.time()
        
        value = self._generate_random_string(self.value_size)
        
        for i in range(num_ops):
            key = f"bench:hash:{worker_id}:{i}"
            field = f"field:{i}"
            
            # HSET操作
            client.hset(key, field, value)
            
            # HGET操作
            result = client.hget(key, field)
            
            # HDEL操作
            client.hdel(key, field)
            
            ops_completed += 3  # 每次循环执行3个操作
        
        elapsed = time.time() - start_time
        results[worker_id] = (ops_completed, elapsed)
    
    def _set_operation_worker(self, client, worker_id, num_ops, results):
        """集合操作工作线程"""
        ops_completed = 0
        start_time = time.time()
        
        value = self._generate_random_string(10)  # 集合成员不需要太大
        
        for i in range(num_ops):
            key = f"bench:set:{worker_id}:{i}"
            member = f"member:{i}:{value}"
            
            # SADD操作
            client.sadd(key, member)
            
            # SISMEMBER操作
            result = client.sismember(key, member)
            
            # SREM操作
            client.srem(key, member)
            
            ops_completed += 3  # 每次循环执行3个操作
        
        elapsed = time.time() - start_time
        results[worker_id] = (ops_completed, elapsed)
    
    def _run_test(self, name, worker_func, redis_client=None):
        """运行指定测试
        
        Args:
            name: 测试名称
            worker_func: 工作线程函数
            redis_client: 可选的Redis客户端，用于对比测试
        """
        print(f"\n=== 运行 {name} 基准测试 ===")
        
        # 创建CoolDB Redis客户端池
        cooldb_clients = []
        for _ in range(self.num_clients):
            cooldb_clients.append(redis.Redis(
                host=self.host,
                port=self.port,
                socket_timeout=30.0
            ))
        
        # 如果有标准Redis客户端，也创建客户端池
        redis_clients = []
        if redis_client is not None:
            for _ in range(self.num_clients):
                redis_clients.append(redis.Redis(
                    host=self.host,
                    port=self.redis_port,
                    socket_timeout=30.0
                ))
        
        # CoolDB测试部分
        print(f"测试CoolDB Redis ({self.host}:{self.port}):")
        cooldb_results = {}
        
        # 计算每个客户端需要执行的操作数
        ops_per_client = self.num_operations // self.num_clients
        if ops_per_client == 0:
            ops_per_client = 1
        
        with ThreadPoolExecutor(max_workers=self.num_clients) as executor:
            futures = []
            for i in range(self.num_clients):
                client = cooldb_clients[i]
                futures.append(executor.submit(
                    worker_func, client, i, ops_per_client, cooldb_results
                ))
            
            # 等待所有操作完成
            for future in futures:
                future.result()
        
        # 计算总操作数和平均操作速率
        total_ops = sum(ops for ops, _ in cooldb_results.values())
        total_time = max(elapsed for _, elapsed in cooldb_results.values())
        cooldb_ops_per_sec = total_ops / total_time if total_time > 0 else 0
        
        print(f"总操作数: {total_ops:,}")
        print(f"总时间: {total_time:.2f}秒")
        print(f"操作速率: {cooldb_ops_per_sec:,.2f} ops/sec")
        
        # 标准Redis测试部分（如果启用）
        redis_ops_per_sec = 0
        if redis_client is not None:
            print(f"\n测试标准Redis ({self.host}:{self.redis_port}):")
            redis_test_results = {}
            
            with ThreadPoolExecutor(max_workers=self.num_clients) as executor:
                futures = []
                for i in range(self.num_clients):
                    client = redis_clients[i]
                    futures.append(executor.submit(
                        worker_func, client, i, ops_per_client, redis_test_results
                    ))
                
                # 等待所有操作完成
                for future in futures:
                    future.result()
            
            # 计算总操作数和平均操作速率
            total_ops = sum(ops for ops, _ in redis_test_results.values())
            total_time = max(elapsed for _, elapsed in redis_test_results.values())
            redis_ops_per_sec = total_ops / total_time if total_time > 0 else 0
            
            print(f"总操作数: {total_ops:,}")
            print(f"总时间: {total_time:.2f}秒")
            print(f"操作速率: {redis_ops_per_sec:,.2f} ops/sec")
        
        # 保存结果
        self.results[name] = {
            "cooldb": cooldb_ops_per_sec,
            "redis": redis_ops_per_sec,
            "ratio": redis_ops_per_sec / cooldb_ops_per_sec if cooldb_ops_per_sec > 0 and redis_ops_per_sec > 0 else 0
        }
        
        # 关闭所有客户端
        for client in cooldb_clients:
            client.close()
        
        for client in redis_clients:
            client.close()
    
    def run_string_benchmark(self, redis_client=None):
        """运行字符串基准测试"""
        self._run_test("字符串操作(SET/GET/DEL)", self._string_operation_worker, redis_client)
    
    def run_hash_benchmark(self, redis_client=None):
        """运行哈希基准测试"""
        self._run_test("哈希操作(HSET/HGET/HDEL)", self._hash_operation_worker, redis_client)
    
    def run_set_benchmark(self, redis_client=None):
        """运行集合基准测试"""
        self._run_test("集合操作(SADD/SISMEMBER/SREM)", self._set_operation_worker, redis_client)
    
    def run(self, tests=None):
        """运行所有基准测试
        
        Args:
            tests: 测试列表，可以是"string"、"hash"、"set"或"all"
        """
        if tests is None:
            tests = ["all"]
        
        # 连接标准Redis（如果启用了比较）
        redis_client = None
        if self.compare_with_redis:
            try:
                redis_client = redis.Redis(
                    host=self.host,
                    port=self.redis_port,
                    socket_timeout=5.0
                )
                # 测试连接
                redis_client.ping()
            except redis.exceptions.ConnectionError:
                print(f"警告: 无法连接到标准Redis服务器 {self.host}:{self.redis_port}")
                print("将只测试CoolDB Redis性能。")
                redis_client = None
        
        # 打印测试配置
        print("=" * 60)
        print(f"CoolDB Redis基准测试 - 配置:")
        print("=" * 60)
        print(f"服务器: {self.host}:{self.port}")
        print(f"每种命令操作数: {self.num_operations:,}")
        print(f"值大小: {self.value_size} 字节")
        print(f"并发客户端: {self.num_clients}")
        if redis_client is not None:
            print(f"对比标准Redis: 是 ({self.host}:{self.redis_port})")
        else:
            print("对比标准Redis: 否")
        print("=" * 60)
        
        # 运行指定的测试
        if "all" in tests or "string" in tests:
            self.run_string_benchmark(redis_client)
        
        if "all" in tests or "hash" in tests:
            self.run_hash_benchmark(redis_client)
        
        if "all" in tests or "set" in tests:
            self.run_set_benchmark(redis_client)
        
        # 打印摘要
        self._print_summary()
        
        # 关闭Redis客户端
        if redis_client is not None:
            redis_client.close()
    
    def _print_summary(self):
        """打印测试摘要"""
        print("\n" + "=" * 60)
        print("基准测试摘要:")
        print("=" * 60)
        
        if not self.results:
            print("未运行任何测试。")
            return
        
        # 计算所有测试的平均操作速率
        cooldb_avg = sum(result["cooldb"] for result in self.results.values()) / len(self.results)
        
        # 打印每个测试的结果
        for name, result in self.results.items():
            print(f"{name}:")
            print(f"  - CoolDB Redis: {result['cooldb']:,.2f} ops/sec")
            
            if result["redis"] > 0:
                print(f"  - 标准 Redis: {result['redis']:,.2f} ops/sec")
                print(f"  - 性能比率: {1/result['ratio']:.2%} (相对于标准Redis)")
            
            print()
        
        print(f"CoolDB Redis平均操作速率: {cooldb_avg:,.2f} ops/sec")
        
        if any(result["redis"] > 0 for result in self.results.values()):
            redis_avg = sum(result["redis"] for result in self.results.values()) / len(self.results)
            avg_ratio = redis_avg / cooldb_avg if cooldb_avg > 0 else 0
            print(f"标准Redis平均操作速率: {redis_avg:,.2f} ops/sec")
            print(f"平均性能比率: {1/avg_ratio:.2%} (相对于标准Redis)")
        
        print("=" * 60)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="CoolDB Redis性能基准测试")
    parser.add_argument("--host", type=str, default="localhost", help="Redis服务器地址")
    parser.add_argument("--port", type=int, default=6379, help="Redis服务器端口")
    parser.add_argument("--compare", action="store_true", help="与标准Redis比较（端口6378）")
    parser.add_argument("--operations", type=int, default=10000, help="每种命令执行的操作数")
    parser.add_argument("--value-size", type=int, default=100, help="值的大小（字节）")
    parser.add_argument("--clients", type=int, default=10, help="并发客户端数量")
    parser.add_argument("--tests", type=str, default="all", 
                        help="要运行的测试（逗号分隔），可选值: string,hash,set,all")
    
    args = parser.parse_args()
    
    # 解析测试列表
    tests = args.tests.lower().split(",")
    
    # 实例化基准测试
    benchmark = RedisBenchmark(
        host=args.host,
        port=args.port,
        num_operations=args.operations,
        value_size=args.value_size,
        num_clients=args.clients,
        compare_with_redis=args.compare
    )
    
    # 运行测试
    benchmark.run(tests)

if __name__ == "__main__":
    main() 