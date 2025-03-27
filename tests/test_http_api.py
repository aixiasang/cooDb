import os
import unittest
import json
import sys
import tempfile
import shutil
import requests
import threading
import time
import multiprocessing
import socket
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# 确保coodb模块可导入
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入FastAPI实现
from coodb.http.api import app, get_db

def find_free_port():
    """找到可用的空闲端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('0.0.0.0', 0))
        return s.getsockname()[1]

def start_server(host, port):
    """启动FastAPI服务器"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)

class TestHTTPAPI(unittest.TestCase):
    """测试CoolDB HTTP API (FastAPI实现)"""

    @classmethod
    def setUpClass(cls):
        """启动HTTP服务器"""
        cls.test_dir = tempfile.mkdtemp()
        os.environ['COODB_DIR'] = cls.test_dir
        
        # 使用随机空闲端口避免冲突
        cls.port = find_free_port()
        cls.host = "127.0.0.1"
        cls.base_url = f"http://{cls.host}:{cls.port}"
        
        # 使用多进程启动FastAPI服务器
        cls.server_process = multiprocessing.Process(
            target=start_server,
            args=(cls.host, cls.port),
            daemon=True
        )
        cls.server_process.start()
        
        # 等待服务器启动
        time.sleep(2)
        
        # 检查服务器是否启动
        retries = 5
        while retries > 0:
            try:
                response = requests.get(f"{cls.base_url}/")
                if response.status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(1)
            retries -= 1
        
        if retries == 0:
            raise Exception("HTTP服务器启动失败")

    @classmethod
    def tearDownClass(cls):
        """关闭HTTP服务器"""
        # 停止服务器进程
        if hasattr(cls, 'server_process'):
            cls.server_process.terminate()
            cls.server_process.join(timeout=2)
            if cls.server_process.is_alive():
                cls.server_process.kill()
        
        # 清理临时目录
        try:
            shutil.rmtree(cls.test_dir)
        except:
            pass
        
        # 清理环境变量
        if 'COODB_DIR' in os.environ:
            del os.environ['COODB_DIR']

    def test_root_endpoint(self):
        """测试根端点"""
        response = requests.get(f"{self.base_url}/")
        self.assertEqual(response.status_code, 200)

    def test_api_docs(self):
        """测试API文档页面
        
        注意：此测试需要访问FastAPI自动生成的文档页面
        """
        # 测试自动生成的Swagger UI文档
        response = requests.get(f"{self.base_url}/docs")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["Content-Type"])
        
        # 测试自动生成的OpenAPI JSON
        response = requests.get(f"{self.base_url}/openapi.json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response.headers["Content-Type"])

    def test_put_get_delete_key(self):
        """测试设置、获取和删除键值对"""
        key = "test_key"
        value = "test_value"
        
        # 设置键值对
        response = requests.put(
            f"{self.base_url}/api/v1/keys/{key}",
            json={"value": value}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        
        # 获取键值对
        response = requests.get(f"{self.base_url}/api/v1/keys/{key}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["key"], key)
        self.assertEqual(data["value"], value)
        
        # 获取所有键
        response = requests.get(f"{self.base_url}/api/v1/keys")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # 检查items中是否包含我们的键
        found = False
        for item in data["items"]:
            if item["key"] == key:
                found = True
                break
        self.assertTrue(found, f"键 {key} 未在列表中找到")
        
        # 删除键值对
        response = requests.delete(f"{self.base_url}/api/v1/keys/{key}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        
        # 确认键已删除
        response = requests.get(f"{self.base_url}/api/v1/keys/{key}")
        self.assertEqual(response.status_code, 404)

    def test_batch_operations(self):
        """测试批量操作"""
        batch_data = [
            {
                "operation": "put",
                "key": "batch_key_1",
                "value": "batch_value_1"
            },
            {
                "operation": "put",
                "key": "batch_key_2",
                "value": "batch_value_2"
            }
        ]
        
        # 执行批量操作
        response = requests.post(
            f"{self.base_url}/api/v1/batch",
            json=batch_data
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        
        # 验证批量操作结果
        response = requests.get(f"{self.base_url}/api/v1/keys/batch_key_1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["value"], "batch_value_1")
        
        response = requests.get(f"{self.base_url}/api/v1/keys/batch_key_2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["value"], "batch_value_2")
        
        # 批量删除
        batch_data = [
            {
                "operation": "delete",
                "key": "batch_key_1"
            },
            {
                "operation": "delete",
                "key": "batch_key_2"
            }
        ]
        
        response = requests.post(
            f"{self.base_url}/api/v1/batch",
            json=batch_data
        )
        self.assertEqual(response.status_code, 200)
        
        # 验证删除结果
        response = requests.get(f"{self.base_url}/api/v1/keys/batch_key_1")
        self.assertEqual(response.status_code, 404)
        
        response = requests.get(f"{self.base_url}/api/v1/keys/batch_key_2")
        self.assertEqual(response.status_code, 404)

    def test_stats(self):
        """测试获取数据库统计信息"""
        # 先添加一些数据
        for i in range(5):
            response = requests.put(
                f"{self.base_url}/api/v1/keys/stats_key_{i}",
                json={"value": f"stats_value_{i}"}
            )
            self.assertEqual(response.status_code, 200)
        
        # 获取统计信息
        response = requests.get(f"{self.base_url}/api/v1/stats")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # 检查统计信息字段
        self.assertIn("key_num", data)
        self.assertIn("data_files_num", data)  # 使用正确的字段名
        self.assertIn("reclaimable_size", data)
        self.assertIn("disk_size", data)
        
        # 数据库中应该至少有5个键
        self.assertGreaterEqual(data["key_num"], 5)
        
        # 清理数据
        for i in range(5):
            requests.delete(f"{self.base_url}/api/v1/keys/stats_key_{i}")

    def test_merge(self):
        """测试合并操作"""
        # 先添加一些数据
        for i in range(10):
            requests.put(
                f"{self.base_url}/api/v1/keys/merge_key_{i}",
                json={"value": f"merge_value_{i}"}
            )
        
        # 删除一半的数据来创建无效空间
        for i in range(5):
            requests.delete(f"{self.base_url}/api/v1/keys/merge_key_{i}")
        
        # 执行合并操作
        response = requests.post(f"{self.base_url}/api/v1/merge")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        
        # 验证剩余数据完好
        for i in range(5, 10):
            response = requests.get(f"{self.base_url}/api/v1/keys/merge_key_{i}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["value"], f"merge_value_{i}")
        
        # 清理数据
        for i in range(5, 10):
            requests.delete(f"{self.base_url}/api/v1/keys/merge_key_{i}")


if __name__ == "__main__":
    unittest.main()