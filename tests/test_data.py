import os
import sys
import shutil
import unittest
import tempfile
import struct
import random
import time
from typing import List, Tuple, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coodb.index import Indexer
from coodb.data.log_record import LogRecord, LogRecordType, LogRecordPos
from coodb.data.data_file import DataFile

class TestLogRecord(unittest.TestCase):
    """测试日志记录相关功能"""
    
    def test_log_record_encode_decode(self):
        """测试基本的编码解码"""
        key = b"test_key"
        value = b"test_value"
        record = LogRecord(key, value)
        
        # 编码
        encoded, size = record.encode()
        self.assertIsInstance(encoded, bytes)
        self.assertEqual(size, len(encoded))
        
        # 解码
        decoded = LogRecord.decode(encoded)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.key, key)
        self.assertEqual(decoded.value, value)
        self.assertEqual(decoded.type, LogRecordType.NORMAL)
        
    def test_log_record_empty_values(self):
        """测试空值"""
        record = LogRecord()
        encoded, size = record.encode()
        decoded = LogRecord.decode(encoded)
        
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.key, b"")
        self.assertEqual(decoded.value, b"")
        self.assertEqual(decoded.type, LogRecordType.NORMAL)
        
    def test_log_record_types(self):
        """测试不同的记录类型"""
        for record_type in LogRecordType:
            record = LogRecord(b"key", b"value", record_type)
            encoded, _ = record.encode()
            decoded = LogRecord.decode(encoded)
            
            self.assertIsNotNone(decoded)
            self.assertEqual(decoded.type, record_type)
            
    def test_log_record_large_data(self):
        """测试大数据"""
        key = b"x" * 1024  # 1KB key
        value = b"y" * (1024 * 1024)  # 1MB value
        record = LogRecord(key, value)
        
        encoded, size = record.encode()
        decoded = LogRecord.decode(encoded)
        
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.key, key)
        self.assertEqual(decoded.value, value)
        
    def test_log_record_invalid_data(self):
        """测试无效数据"""
        # 空数据
        self.assertIsNone(LogRecord.decode(b""))
        
        # 损坏的数据
        self.assertIsNone(LogRecord.decode(b"invalid data"))
        
        # 不完整的数据
        record = LogRecord(b"key", b"value")
        encoded, _ = record.encode()
        self.assertIsNone(LogRecord.decode(encoded[:10]))

class TestLogRecordPos(unittest.TestCase):
    def test_log_record_pos_encode_decode(self):
        # 测试位置信息的编码解码
        pos = LogRecordPos(1, 100, 200)
        encoded = pos.encode()
        
        decoded = LogRecordPos.decode(encoded)
        self.assertEqual(decoded.file_id, 1)
        self.assertEqual(decoded.offset, 100)
        self.assertEqual(decoded.size, 200)
        
    def test_log_record_pos_invalid_data(self):
        # 测试无效数据
        with self.assertRaises(ValueError):
            LogRecordPos.decode(b"invalid")
            
    def test_log_record_pos_boundary_values(self):
        # 测试边界值
        test_cases = [
            (0, 0, 0),
            (2**32-1, 2**64-1, 2**32-1),  # 最大值测试
        ]
        
        for file_id, offset, size in test_cases:
            pos = LogRecordPos(file_id, offset, size)
            encoded = pos.encode()
            decoded = LogRecordPos.decode(encoded)
            
            self.assertEqual(decoded.file_id, file_id)
            self.assertEqual(decoded.offset, offset)
            self.assertEqual(decoded.size, size)

class TestDataFile(unittest.TestCase):
    """测试数据文件相关功能"""
    
    def setUp(self):
        """初始化测试环境"""
        self.test_dir = os.path.join(os.path.dirname(__file__), "test_data")
        if os.path.exists(self.test_dir):
            self._clean_test_dir()
        os.makedirs(self.test_dir)
        
    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.test_dir):
            self._clean_test_dir()
            
    def _clean_test_dir(self):
        """清理测试目录"""
        for filename in os.listdir(self.test_dir):
            filepath = os.path.join(self.test_dir, filename)
            try:
                if os.path.isfile(filepath):
                    os.unlink(filepath)
            except Exception as e:
                print(f"清理文件失败: {str(e)}")
        try:
            os.rmdir(self.test_dir)
        except Exception as e:
            print(f"删除目录失败: {str(e)}")
    
    def test_data_file_write_read(self):
        """测试文件的读写操作"""
        data_file = None
        try:
            data_file = DataFile(self.test_dir, 1)
            
            # 写入记录
            record = LogRecord(b"test_key", b"test_value")
            offset, size = data_file.write_log_record(record)
            
            # 读取记录
            read_record, read_size = data_file.read_log_record(offset)
            
            # 验证结果
            self.assertIsNotNone(read_record)
            self.assertEqual(read_record.key, record.key)
            self.assertEqual(read_record.value, record.value)
            self.assertEqual(read_size, size)
        finally:
            if data_file:
                data_file.close()
    
    def test_data_file_multiple_records(self):
        """测试多条记录的读写"""
        data_file = None
        try:
            data_file = DataFile(self.test_dir, 2)
            records = [
                LogRecord(f"key{i}".encode(), f"value{i}".encode())
                for i in range(5)
            ]
            
            # 写入多条记录
            positions = []
            for record in records:
                offset, size = data_file.write_log_record(record)
                positions.append((offset, size))
                
            # 读取并验证每条记录
            for i, (offset, size) in enumerate(positions):
                read_record, read_size = data_file.read_log_record(offset)
                self.assertIsNotNone(read_record)
                self.assertEqual(read_record.key, records[i].key)
                self.assertEqual(read_record.value, records[i].value)
                self.assertEqual(read_size, size)
        finally:
            if data_file:
                data_file.close()
    
    def test_data_file_sync(self):
        """测试文件同步"""
        data_file = None
        try:
            data_file = DataFile(self.test_dir, 2)
            record = LogRecord(b"sync_key", b"sync_value")
            
            # 写入并同步
            data_file.write_log_record(record)
            data_file.sync()
        finally:
            if data_file:
                data_file.close()
    
    def test_data_file_lock(self):
        """测试文件锁"""
        data_file = None
        try:
            data_file = DataFile(self.test_dir, 3)
            
            # 获取锁
            data_file.acquire_lock()
            
            # 写入记录
            record = LogRecord(b"locked_key", b"locked_value")
            data_file.write_log_record(record)
            
            # 释放锁
            data_file.release_lock()
        finally:
            if data_file:
                data_file.close()
    
    def test_data_file_concurrent_access(self):
        """测试并发访问"""
        data_file = None
        try:
            data_file = DataFile(self.test_dir, 5)
            
            # 第一次获取锁
            data_file.acquire_lock()
            
            # 尝试再次获取锁应该失败
            with self.assertRaises(RuntimeError):
                data_file.acquire_lock()
                
            # 释放锁后应该可以再次获取
            data_file.release_lock()
            data_file.acquire_lock()
            data_file.release_lock()
        finally:
            if data_file:
                data_file.close()

if __name__ == '__main__':
    unittest.main() 