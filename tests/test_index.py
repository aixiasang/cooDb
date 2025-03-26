import os
import sys
import shutil
import unittest
import threading
import random
import time
from concurrent.futures import ThreadPoolExecutor

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coodb.index import BTree, ART, BPTree, SkipList
from coodb.data.log_record import LogRecordPos

class BaseIndexerTest:
    """索引器测试基类"""
    
    def setUp(self):
        """初始化测试环境"""
        self.indexer = self.create_indexer()
        
    def tearDown(self):
        """清理测试环境"""
        self.indexer.close()
            
    def test_basic_operations(self):
        """测试基本的增删改查操作"""
        # 插入数据
        pos1 = LogRecordPos(1, 0, 100)
        pos2 = LogRecordPos(1, 100, 100)
        pos3 = LogRecordPos(1, 200, 100)
        
        self.indexer.put(b"key1", pos1)
        self.indexer.put(b"key2", pos2)
        self.indexer.put(b"key3", pos3)
        
        # 查找数据
        self.assertEqual(self.indexer.get(b"key1"), pos1)
        self.assertEqual(self.indexer.get(b"key2"), pos2)
        self.assertEqual(self.indexer.get(b"key3"), pos3)
        
        # 更新数据
        new_pos = LogRecordPos(1, 300, 100)
        old_pos = self.indexer.put(b"key2", new_pos)
        self.assertEqual(old_pos, pos2)  # 验证返回旧值
        self.assertEqual(self.indexer.get(b"key2"), new_pos)
        
        # 删除数据
        old_pos = self.indexer.delete(b"key1")
        self.assertEqual(old_pos, pos1)  # 验证返回旧值
        self.assertIsNone(self.indexer.get(b"key1"))
        
    def test_large_dataset(self):
        """测试大量数据的处理"""
        # 插入1000个键值对
        positions = {}
        for i in range(1000):
            key = f"key{i}".encode()
            pos = LogRecordPos(1, i * 100, 100)
            positions[key] = pos
            old_pos = self.indexer.put(key, pos)
            self.assertIsNone(old_pos)  # 新键应该返回None
            
        # 验证所有数据
        for key, pos in positions.items():
            self.assertEqual(self.indexer.get(key), pos)
            
        # 删除一半的数据
        for i in range(0, 1000, 2):
            key = f"key{i}".encode()
            old_pos = self.indexer.delete(key)
            self.assertEqual(old_pos, positions[key])  # 验证返回旧值
            
        # 验证删除和未删除的数据
        for i in range(1000):
            key = f"key{i}".encode()
            if i % 2 == 0:
                self.assertIsNone(self.indexer.get(key))
            else:
                self.assertEqual(self.indexer.get(key), positions[key])
                
    def test_concurrent_operations(self):
        """测试并发操作"""
        num_threads = 10
        operations_per_thread = 100
        
        def worker():
            for i in range(operations_per_thread):
                key = f"concurrent_key_{threading.current_thread().name}_{i}".encode()
                pos = LogRecordPos(1, i * 100, 100)
                
                # 执行一系列操作
                old_pos = self.indexer.put(key, pos)
                self.assertIsNone(old_pos)  # 新键应该返回None
                self.assertEqual(self.indexer.get(key), pos)
                old_pos = self.indexer.delete(key)
                self.assertEqual(old_pos, pos)  # 验证返回旧值
                self.assertIsNone(self.indexer.get(key))
                
        # 创建线程池执行并发操作
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker) for _ in range(num_threads)]
            for future in futures:
                future.result()
                
    def test_iterator(self):
        """测试迭代器功能"""
        # 插入有序数据
        test_data = {
            b"iter1": LogRecordPos(1, 0, 100),
            b"iter2": LogRecordPos(1, 100, 100),
            b"iter3": LogRecordPos(1, 200, 100),
            b"iter4": LogRecordPos(1, 300, 100),
            b"iter5": LogRecordPos(1, 400, 100)
        }
        
        for key, pos in test_data.items():
            old_pos = self.indexer.put(key, pos)
            self.assertIsNone(old_pos)  # 新键应该返回None
            
        # 使用迭代器正向遍历
        iterator = self.indexer.iterator()
        collected_data = {}
        
        iterator.rewind()
        while iterator.valid():
            collected_data[iterator.key()] = iterator.value()
            iterator.next()
            
        # 验证遍历结果
        self.assertEqual(collected_data, test_data)
        
        # 使用迭代器反向遍历
        iterator = self.indexer.iterator(reverse=True)
        reverse_data = {}
        
        iterator.rewind()
        while iterator.valid():
            reverse_data[iterator.key()] = iterator.value()
            iterator.next()
            
        # 验证反向遍历结果
        self.assertEqual(len(reverse_data), len(test_data))
        self.assertEqual(list(reverse_data.keys()), list(reversed(test_data.keys())))
        
        # 测试seek功能
        iterator = self.indexer.iterator()
        iterator.seek(b"iter3")
        self.assertTrue(iterator.valid())
        self.assertEqual(iterator.key(), b"iter3")
        self.assertEqual(iterator.value(), test_data[b"iter3"])
        
    def test_size(self):
        """测试索引大小统计"""
        self.assertEqual(self.indexer.size(), 0)
        
        # 添加数据
        for i in range(10):
            key = f"key{i}".encode()
            pos = LogRecordPos(1, i * 100, 100)
            old_pos = self.indexer.put(key, pos)
            self.assertIsNone(old_pos)  # 新键应该返回None
            
        self.assertEqual(self.indexer.size(), 10)
        
        # 删除数据
        for i in range(5):
            key = f"key{i}".encode()
            old_pos = self.indexer.delete(key)
            self.assertIsNotNone(old_pos)  # 应该返回旧值
            
        self.assertEqual(self.indexer.size(), 5)
        
    def test_stress(self):
        """压力测试"""
        num_operations = 10000
        keys = []
        positions = {}
        
        # 顺序插入，避免重复key
        for i in range(num_operations):
            key = f"stress_key_{i}".encode()
            pos = LogRecordPos(1, i * 100, 100)
            old_pos = self.indexer.put(key, pos)
            self.assertIsNone(old_pos)  # 新键应该返回None
            keys.append(key)
            positions[key] = pos
            
        # 随机查询
        for key in random.sample(keys, len(keys) // 2):
            self.assertEqual(self.indexer.get(key), positions[key])
            
        # 随机删除
        for key in random.sample(keys, len(keys) // 3):
            old_pos = self.indexer.delete(key)
            self.assertEqual(old_pos, positions[key])  # 验证返回旧值

class TestBTree(BaseIndexerTest, unittest.TestCase):
    """测试B树索引器"""
    
    def create_indexer(self):
        """创建B树索引器"""
        return BTree[bytes, LogRecordPos]()

class TestART(BaseIndexerTest, unittest.TestCase):
    """测试自适应基数树索引器"""
    
    def create_indexer(self):
        """创建ART索引器"""
        return ART[bytes, LogRecordPos]()

class TestBPTree(BaseIndexerTest, unittest.TestCase):
    """测试B+树索引器"""
    
    def create_indexer(self):
        """创建B+树索引器"""
        return BPTree[bytes, LogRecordPos]()

class TestSkipList(BaseIndexerTest, unittest.TestCase):
    """测试跳表索引器"""
    
    def create_indexer(self):
        """创建跳表索引器"""
        return SkipList[bytes, LogRecordPos]()

if __name__ == '__main__':
    unittest.main() 