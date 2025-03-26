"""数据库测试"""

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

from coodb.db import DB
from coodb.options import Options
from coodb.errors import *
from coodb.batch import Batch
from coodb.index import IndexType

class TestDB(unittest.TestCase):
    """数据库测试类"""
    
    def setUp(self):
        """初始化测试环境"""
        self.test_dir = "test_db"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)
        
        options = Options(dir_path=self.test_dir)
        self.db = DB(options)
        
    def tearDown(self):
        """清理测试环境"""
        try:
            if self.db:
                self.db.close()
                
            # 等待一小段时间确保所有文件句柄都被释放
            time.sleep(0.1)
            
            # 尝试多次删除目录
            max_retries = 3
            for i in range(max_retries):
                try:
                    if os.path.exists(self.test_dir):
                        # 先尝试删除锁文件
                        lock_file = os.path.join(self.test_dir, "flock")
                        if os.path.exists(lock_file):
                            try:
                                os.remove(lock_file)
                            except:
                                pass
                                
                        # 再删除整个目录
                        shutil.rmtree(self.test_dir)
                    break
                except Exception as e:
                    if i == max_retries - 1:  # 最后一次尝试
                        print(f"Failed to clean up test directory: {e}")
                    else:
                        time.sleep(0.1)  # 短暂等待后重试
        except Exception as e:
            print(f"Error during test cleanup: {e}")
            
    def test_batch_operations(self):
        """测试批量操作"""
        batch = self.db.new_batch()
        
        # 添加多个操作
        test_data = {
            b"batch1": b"value1",
            b"batch2": b"value2",
            b"batch3": b"value3"
        }
        
        for key, value in test_data.items():
            batch.put(key, value)
            
        # 在提交前数据不应该可见
        for key in test_data:
            self.assertIsNone(self.db.get(key))
            
        # 提交批量操作
        batch.commit()
        
        # 验证所有数据
        for key, value in test_data.items():
            self.assertEqual(self.db.get(key), value)
            
        # 测试批量删除
        batch = self.db.new_batch()
        batch.delete(b"batch1")
        batch.delete(b"batch2")
        
        # 在提交前数据应该还在
        self.assertIsNotNone(self.db.get(b"batch1"))
        self.assertIsNotNone(self.db.get(b"batch2"))
        
        # 提交删除操作
        batch.commit()
        
        # 验证删除结果
        self.assertIsNone(self.db.get(b"batch1"))
        self.assertIsNone(self.db.get(b"batch2"))
        self.assertIsNotNone(self.db.get(b"batch3"))
        
        # 测试回滚
        batch = self.db.new_batch()
        batch.put(b"batch4", b"value4")
        batch.delete(b"batch3")
        
        # 回滚操作
        batch.rollback()
        
        # 验证回滚结果
        self.assertIsNone(self.db.get(b"batch4"))
        self.assertIsNotNone(self.db.get(b"batch3"))
        
    def test_iterator(self):
        """测试迭代器"""
        # 插入测试数据
        test_data = {
            b"iter1": b"value1",
            b"iter2": b"value2",
            b"iter3": b"value3",
            b"iter4": b"value4",
            b"iter5": b"value5"
        }
        
        for key, value in test_data.items():
            self.db.put(key, value)
            
        # 正向遍历
        iterator = self.db.iterator()
        collected_data = {}
        
        iterator.rewind()
        while iterator.valid():
            collected_data[iterator.key()] = iterator.value()
            iterator.next()
            
        self.assertEqual(collected_data, test_data)
        
        # 反向遍历
        iterator = self.db.iterator(reverse=True)
        reverse_data = {}
        
        iterator.rewind()
        while iterator.valid():
            reverse_data[iterator.key()] = iterator.value()
            iterator.next()
            
        self.assertEqual(len(reverse_data), len(test_data))
        self.assertEqual(list(reverse_data.keys()), list(reversed(test_data.keys())))
        
        # 测试seek
        iterator = self.db.iterator()
        iterator.seek(b"iter3")
        self.assertTrue(iterator.valid())
        self.assertEqual(iterator.key(), b"iter3")
        self.assertEqual(iterator.value(), b"value3")
        
    def test_merge(self):
        """测试数据合并"""
        # 写入一些数据
        for i in range(100):
            key = f"key{i}".encode()
            value = f"value{i}".encode()
            self.db.put(key, value)
            
        # 删除一半的数据制造无效空间
        for i in range(0, 100, 2):
            key = f"key{i}".encode()
            self.db.delete(key)
            
        # 执行合并
        self.db.merge()
        
        # 验证数据完整性
        for i in range(100):
            key = f"key{i}".encode()
            if i % 2 == 0:
                self.assertIsNone(self.db.get(key))
            else:
                value = f"value{i}".encode()
                self.assertEqual(self.db.get(key), value)
                
        # 验证文件数量
        self.assertEqual(len(self.db.file_ids), 1)

if __name__ == '__main__':
    unittest.main() 