import os
import unittest
import json
import sys
import tempfile
import shutil
import requests
import threading
import time
from multiprocessing import Process
from flask import Flask

# 确保coodb模块可导入
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coodb.http.server import Server

class TestHTTPAPI(unittest.TestCase):
    """测试Coodb HTTP API"""

    @classmethod
    def setUpClass(cls):
        """启动HTTP服务器"""
        cls.test_dir = tempfile.mkdtemp()
        os.environ['COODB_DATA_DIR'] = cls.test_dir
        
        # 启动测试服务器
        cls.port = 8080
        cls.host = "127.0.0.1"
        cls.base_url = f"http://{cls.host}:{cls.port}"
        
        # 使用Server类启动HTTP服务
        cls.server = Server(host=cls.host, port=cls.port)
        cls.server.start(block=False)  # 非阻塞方式启动
        
        # 等待服务器启动
        time.sleep(1)
        
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
        # 停止服务器
        if hasattr(cls, 'server'):
            cls.server.stop()
        
        # 清理临时目录
        try:
            shutil.rmtree(cls.test_dir)
        except:
            pass
        
        # 清理环境变量
        if 'COODB_DATA_DIR' in os.environ:
            del os.environ['COODB_DATA_DIR']

    def test_root_endpoint(self):
        """测试根端点"""
        response = requests.get(f"{self.base_url}/")
        self.assertEqual(response.status_code, 200)

    def test_get_openapi_spec(self):
        """测试获取OpenAPI规范"""
        response = requests.get(f"{self.base_url}/coodb.json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["info"]["title"], "Coodb API")

    def test_api_docs(self):
        """测试API文档页面"""
        response = requests.get(f"{self.base_url}/api")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["Content-Type"])

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
        self.assertIn(key, data["keys"])
        
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
        self.assertIn("data_file_num", data)
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