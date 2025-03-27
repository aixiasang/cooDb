import os
import unittest
import sys
import tempfile
import shutil

# 确保coodb模块可导入
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coodb.db import DB
from coodb.options import Options, IndexType
from coodb.errors import ErrKeyIsEmpty

class TestCoreDB(unittest.TestCase):
    """测试CoolDB核心功能"""

    def setUp(self):
        """准备测试环境"""
        self.test_dir = tempfile.mkdtemp()
        self.options = Options(
            dir_path=self.test_dir,
            max_file_size=1024*1024,  # 1MB
            sync_writes=False,
            index_type=IndexType.BTREE
        )
        self.db = DB(self.options)
        
    def tearDown(self):
        """清理测试环境"""
        if hasattr(self, 'db'):
            self.db.close()
            
        try:
            shutil.rmtree(self.test_dir)
        except:
            pass

    def test_put_get_delete(self):
        """测试基本的写入、读取和删除操作"""
        # 写入数据
        self.db.put(b"key1", b"value1")
        
        # 读取数据
        value = self.db.get(b"key1")
        self.assertEqual(value, b"value1")
        
        # 删除数据
        self.db.delete(b"key1")
        value = self.db.get(b"key1")
        self.assertIsNone(value)
        
    def test_empty_key(self):
        """测试空键处理"""
        with self.assertRaises(ErrKeyIsEmpty):
            self.db.put(b"", b"value")
            
        with self.assertRaises(ErrKeyIsEmpty):
            self.db.delete(b"")

    def test_batch_operations(self):
        """测试批量操作"""
        batch = self.db.new_batch()
        batch.put(b"batch_key1", b"batch_value1")
        batch.put(b"batch_key2", b"batch_value2")
        batch.delete(b"non_exist_key")  # 删除不存在的键应该不会报错
        batch.commit()
        
        # 验证批量写入结果
        self.assertEqual(self.db.get(b"batch_key1"), b"batch_value1")
        self.assertEqual(self.db.get(b"batch_key2"), b"batch_value2")
        
        # 再次批量操作，删除刚才写入的键
        batch = self.db.new_batch()
        batch.delete(b"batch_key1")
        batch.delete(b"batch_key2")
        batch.commit()
        
        # 验证删除结果
        self.assertIsNone(self.db.get(b"batch_key1"))
        self.assertIsNone(self.db.get(b"batch_key2"))

    def test_iterator(self):
        """测试迭代器"""
        # 写入一批数据
        test_data = {
            b"a": b"value_a",
            b"b": b"value_b",
            b"c": b"value_c",
            b"d": b"value_d"
        }
        
        for key, value in test_data.items():
            self.db.put(key, value)
            
        # 使用迭代器正向遍历
        iterator = self.db.iterator(reverse=False)
        iterator.rewind()
        
        keys = []
        while iterator.valid():
            key = iterator.key()
            value = iterator.value()
            self.assertEqual(value, test_data[key])
            keys.append(key)
            iterator.next()
            
        # 验证遍历到了所有键，且顺序正确
        self.assertEqual(set(keys), set(test_data.keys()))
        self.assertTrue(keys == sorted(keys))
        
        # 测试反向迭代
        iterator = self.db.iterator(reverse=True)
        iterator.rewind()
        
        reverse_keys = []
        while iterator.valid():
            reverse_keys.append(iterator.key())
            iterator.next()
            
        # 验证反向遍历的顺序正确
        self.assertEqual(reverse_keys, sorted(test_data.keys(), reverse=True))

    def test_merge(self):
        """测试合并操作"""
        # 写入一些测试数据
        test_data = {}
        for i in range(100):
            key = f"key{i}".encode()
            value = f"value{i}".encode()
            self.db.put(key, value)
            test_data[key] = value
            
        # 删除一部分数据，产生无效记录
        for i in range(50):
            key = f"key{i}".encode()
            self.db.delete(key)
            del test_data[key]
            
        # 记录合并前的状态
        stats_before = self.db.stat()
        
        # 执行合并操作
        self.db.merge()
        
        # 验证合并后的数据一致性
        for i in range(50, 100):
            key = f"key{i}".encode()
            value = self.db.get(key)
            self.assertEqual(value, f"value{i}".encode())
        
        # 验证删除的数据确实不存在
        for i in range(50):
            key = f"key{i}".encode()
            value = self.db.get(key)
            self.assertIsNone(value)
        
        # 验证合并后的文件数量减少
        stats_after = self.db.stat()
        self.assertEqual(stats_after["key_num"], len(test_data))
        self.assertLessEqual(stats_after["data_files_num"], stats_before["data_files_num"])

if __name__ == "__main__":
    unittest.main() 