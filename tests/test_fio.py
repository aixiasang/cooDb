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
        """测试标准文件IO"""
        # 创建临时文件
        file_path = os.path.join(self.test_dir, "test_standard.dat")
        
        # 创建标准IO管理器
        io_manager = IOManager.new_io_manager(file_path, FileIOType.StandardFIO)
        self.io_managers.append(io_manager)
        
        # 测试写入和读取
        test_data = b"Hello, CoolDB!"
        
        # 写入数据
        write_size = io_manager.write(test_data)
        self.assertEqual(write_size, len(test_data))
        
        # 读取数据
        read_buffer = bytearray(len(test_data))
        read_size = io_manager.read(read_buffer, 0)
        self.assertEqual(read_size, len(test_data))
        self.assertEqual(bytes(read_buffer), test_data)
        
        # 测试文件大小
        file_size = io_manager.size()
        self.assertEqual(file_size, len(test_data))
        
    def test_mmap_io(self):
        # 测试内存映射IO
        file_path = os.path.join(self.test_dir, "test_mmap.dat")
        io_manager = IOManager.new_io_manager(file_path, FileIOType.MemoryMap)
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
        """测试大数据量读写"""
        # 创建临时文件
        file_path = os.path.join(self.test_dir, "test_large.dat")
        
        # 创建标准IO管理器
        io_manager = IOManager.new_io_manager(file_path, FileIOType.StandardFIO)
        self.io_managers.append(io_manager)
        
        # 生成1MB测试数据
        data_size = 1024 * 1024
        test_data = os.urandom(data_size)
        
        # 写入数据
        io_manager.write(test_data)
        
        # 读取数据
        read_buffer = bytearray(data_size)
        io_manager.read(read_buffer, 0)
        
        # 验证数据一致性
        self.assertEqual(test_data, bytes(read_buffer))
        
    def test_invalid_io_type(self):
        # 测试无效的IO类型
        file_path = os.path.join(self.test_dir, "invalid.data")
        with self.assertRaises(ValueError):
            IOManager.new_io_manager(file_path, "INVALID")
            
    def test_sequential_writes(self):
        """测试连续写入"""
        # 创建临时文件
        file_path = os.path.join(self.test_dir, "test_sequential.dat")
        
        # 创建标准IO管理器
        io_manager = IOManager.new_io_manager(file_path, FileIOType.StandardFIO)
        self.io_managers.append(io_manager)
        
        # 测试数据
        test_data1 = b"First chunk of data"
        test_data2 = b"Second chunk of data"
        test_data3 = b"Third chunk of data"
        
        # 连续写入数据
        offset1 = 0
        write_size1 = io_manager.write(test_data1)
        offset2 = offset1 + write_size1
        write_size2 = io_manager.write(test_data2)
        offset3 = offset2 + write_size2
        write_size3 = io_manager.write(test_data3)
        
        # 读取并验证数据
        read_buffer1 = bytearray(len(test_data1))
        io_manager.read(read_buffer1, offset1)
        self.assertEqual(bytes(read_buffer1), test_data1)
        
        read_buffer2 = bytearray(len(test_data2))
        io_manager.read(read_buffer2, offset2)
        self.assertEqual(bytes(read_buffer2), test_data2)
        
        read_buffer3 = bytearray(len(test_data3))
        io_manager.read(read_buffer3, offset3)
        self.assertEqual(bytes(read_buffer3), test_data3)

if __name__ == '__main__':
    unittest.main() 