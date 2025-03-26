import os
import sys
import tempfile
import unittest
import random
import shutil
import time

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coodb.fio.io_manager import IOManager, FileIOType

class TestIOManager(unittest.TestCase):
    def setUp(self):
        # 创建测试目录
        self.test_dir = os.path.join(os.path.dirname(__file__), "test_fio")
        os.makedirs(self.test_dir, exist_ok=True)
        self.io_managers = []
        
    def tearDown(self):
        # 关闭所有IO管理器
        for manager in self.io_managers:
            try:
                manager.close()
            except:
                pass
                
        # 等待文件句柄释放
        time.sleep(0.1)
        
        # 清理测试目录
        retry_count = 3
        while retry_count > 0:
            try:
                if os.path.exists(self.test_dir):
                    shutil.rmtree(self.test_dir)
                break
            except PermissionError:
                time.sleep(0.1)
                retry_count -= 1
            
    def test_standard_io(self):
        # 测试标准文件IO
        file_path = os.path.join(self.test_dir, "test.data")
        io_manager = IOManager.new_io_manager(file_path, FileIOType.STANDARD)
        self.io_managers.append(io_manager)
        
        # 写入数据
        test_data = b"Hello, World!"
        written = io_manager.write(test_data)
        self.assertEqual(written, len(test_data))
        
        # 读取数据
        buf = bytearray(len(test_data))
        read = io_manager.read(buf, 0)
        self.assertEqual(read, len(test_data))
        self.assertEqual(bytes(buf), test_data)
        
        # 同步
        io_manager.sync()
        
    def test_mmap_io(self):
        # 测试内存映射IO
        file_path = os.path.join(self.test_dir, "test.mmap")
        io_manager = IOManager.new_io_manager(file_path, FileIOType.MEMORY_MAP)
        self.io_managers.append(io_manager)
        
        # 写入数据
        test_data = b"Memory Mapped IO Test"
        written = io_manager.write(test_data)
        self.assertEqual(written, len(test_data))
        
        # 读取数据
        buf = bytearray(len(test_data))
        read = io_manager.read(buf, 0)
        self.assertEqual(read, len(test_data))
        self.assertEqual(bytes(buf), test_data)
        
        # 同步
        io_manager.sync()
        
    def test_large_data(self):
        # 测试大数据
        file_path = os.path.join(self.test_dir, "large.data")
        io_manager = IOManager.new_io_manager(file_path, FileIOType.STANDARD)
        self.io_managers.append(io_manager)
        
        # 生成1MB的测试数据
        test_data = b"x" * (1024 * 1024)
        
        # 写入数据
        written = io_manager.write(test_data)
        self.assertEqual(written, len(test_data))
        
        # 分块读取数据
        chunk_size = 8192
        offset = 0
        while offset < len(test_data):
            buf = bytearray(min(chunk_size, len(test_data) - offset))
            read = io_manager.read(buf, offset)
            self.assertEqual(read, len(buf))
            self.assertEqual(bytes(buf), test_data[offset:offset + len(buf)])
            offset += read
            
    def test_invalid_io_type(self):
        # 测试无效的IO类型
        file_path = os.path.join(self.test_dir, "invalid.data")
        with self.assertRaises(ValueError):
            IOManager.new_io_manager(file_path, "INVALID")
            
    def test_sequential_writes(self):
        # 测试顺序写入
        file_path = os.path.join(self.test_dir, "sequential.data")
        io_manager = IOManager.new_io_manager(file_path, FileIOType.STANDARD)
        self.io_managers.append(io_manager)
        
        # 写入第一段数据
        data1 = b"First Write"
        written1 = io_manager.write(data1)
        self.assertEqual(written1, len(data1))
        io_manager.sync()
        
        # 写入第二段数据
        data2 = b"Second Write"
        written2 = io_manager.write(data2)
        self.assertEqual(written2, len(data2))
        io_manager.sync()
        
        # 读取所有数据
        total_len = len(data1) + len(data2)
        buf = bytearray(total_len)
        read = io_manager.read(buf, 0)
        self.assertEqual(read, total_len)
        
        # 验证数据
        expected = data1 + data2
        self.assertEqual(bytes(buf), expected)

if __name__ == '__main__':
    unittest.main() 