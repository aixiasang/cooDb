import os
import sys
import shutil
import unittest
import random
import string
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coodb.db import DB
from coodb.options import Options, IndexType
from coodb.errors import ErrKeyNotFound

class TestDBStress(unittest.TestCase):
    """数据库压力测试"""
    
    def setUp(self):
        """初始化测试环境"""
        self.test_dir = "test_db_stress"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)
        
        # 使用较小的数据文件大小以便于测试文件轮转
        options = Options(
            dir_path=self.test_dir,
            max_file_size=64 * 1024,  # 64KB
            sync_writes=False,
            index_type=IndexType.BTREE
        )
        self.db = DB(options)
        
    def tearDown(self):
        """清理测试环境"""
        self.db.close()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            
    def generate_random_kv(self, key_size: int = 16, value_size: int = 128) -> tuple:
        """生成随机的键值对"""
        key = ''.join(random.choices(string.ascii_letters + string.digits, k=key_size)).encode()
        value = ''.join(random.choices(string.ascii_letters + string.digits, k=value_size)).encode()
        return key, value
        
    def test_concurrent_operations(self):
        """测试并发操作"""
        num_threads = 10
        ops_per_thread = 1000
        all_keys: Dict[bytes, bytes] = {}
        
        def worker():
            """工作线程函数"""
            local_keys: Dict[bytes, bytes] = {}
            for _ in range(ops_per_thread):
                key, value = self.generate_random_kv()
                
                # 写入数据
                self.db.put(key, value)
                local_keys[key] = value
                
                # 随机读取之前写入的键
                if local_keys:
                    read_key = random.choice(list(local_keys.keys()))
                    read_value = self.db.get(read_key)
                    self.assertEqual(read_value, local_keys[read_key])
                    
                # 随机删除一些键
                if random.random() < 0.1 and local_keys:  # 10%的概率删除
                    del_key = random.choice(list(local_keys.keys()))
                    self.db.delete(del_key)
                    del local_keys[del_key]
                    
            return local_keys
            
        # 使用线程池执行并发操作
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker) for _ in range(num_threads)]
            for future in futures:
                all_keys.update(future.result())
                
        # 验证所有未删除的键
        for key, expected_value in all_keys.items():
            try:
                actual_value = self.db.get(key)
                self.assertEqual(actual_value, expected_value)
            except ErrKeyNotFound:
                continue  # 键可能被其他线程删除
                
    def test_reopen_database(self):
        """测试数据库重新打开"""
        # 写入一些数据
        test_data = {}
        for i in range(1000):
            key, value = self.generate_random_kv()
            self.db.put(key, value)
            test_data[key] = value
            
        # 关闭数据库
        self.db.close()
        
        # 重新打开数据库
        options = Options(
            dir_path=self.test_dir,
            max_file_size=64 * 1024,
            sync_writes=False,
            index_type=IndexType.BTREE
        )
        self.db = DB(options)
        
        # 验证数据
        for key, expected_value in test_data.items():
            actual_value = self.db.get(key)
            self.assertEqual(actual_value, expected_value)
            
    def test_file_rotation(self):
        """测试文件轮转"""
        # 写入足够多的大数据以触发文件轮转
        keys = []
        values = []
        for i in range(100):
            key, value = self.generate_random_kv(key_size=32, value_size=1024)
            self.db.put(key, value)
            keys.append(key)
            values.append(value)
            
        # 验证文件轮转
        self.assertGreater(len(self.db.file_ids), 1)
        
        # 验证数据完整性
        for i, key in enumerate(keys):
            value = self.db.get(key)
            self.assertEqual(value, values[i])
            
    def test_batch_operations(self):
        """测试批量操作"""
        num_batches = 10
        ops_per_batch = 1000
        all_data: Dict[bytes, bytes] = {}
        
        for _ in range(num_batches):
            batch = self.db.new_batch()
            batch_data = {}
            
            # 写入数据
            for _ in range(ops_per_batch):
                key, value = self.generate_random_kv()
                batch.put(key, value)
                batch_data[key] = value
                
            # 提交批量操作
            batch.commit()
            all_data.update(batch_data)
            
        # 验证所有数据
        for key, expected_value in all_data.items():
            actual_value = self.db.get(key)
            self.assertEqual(actual_value, expected_value)
            
    def test_merge_stress(self):
        """测试合并操作的压力测试"""
        # 写入一些数据并执行删除操作以产生无效数据
        keys = []
        values = []
        for i in range(1000):
            key, value = self.generate_random_kv()
            self.db.put(key, value)
            if i % 2 == 0:  # 删除一半的数据
                self.db.delete(key)
            else:
                keys.append(key)
                values.append(value)
                
        # 执行合并操作
        self.db.merge()
        
        # 验证数据完整性
        for i, key in enumerate(keys):
            value = self.db.get(key)
            self.assertEqual(value, values[i])
            
    def test_large_values(self):
        """测试大数据值的处理"""
        # 写入一些大数据值
        test_data = {}
        for i in range(10):
            key = f"large_key_{i}".encode()
            value = os.urandom(1024 * 1024)  # 1MB的随机数据
            self.db.put(key, value)
            test_data[key] = value
            
        # 验证数据
        for key, expected_value in test_data.items():
            actual_value = self.db.get(key)
            self.assertEqual(actual_value, expected_value)
            
if __name__ == '__main__':
    unittest.main() 