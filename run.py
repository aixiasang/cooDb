#!/usr/bin/env python
"""
CoolDB 服务启动脚本
运行 HTTP 服务器以提供数据库管理界面和 API

用法:
    python run.py [--host HOST] [--port PORT] [--dir DB_DIR]
选项:
    --host HOST    监听主机，默认为 0.0.0.0
    --port PORT    监听端口，默认为 8000
    --dir DB_DIR   数据库目录，默认为 ./coodb_data
"""

import os
import sys
import argparse
from coodb.http.server import Server

def main():
    # 创建命令行解析器
    parser = argparse.ArgumentParser(description="启动 CoolDB HTTP 服务")
    parser.add_argument('--host', type=str, default='0.0.0.0', 
                        help='监听主机 (默认: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8000, 
                        help='监听端口 (默认: 8000)')
    parser.add_argument('--dir', type=str, default='./coodb_data', 
                        help='数据库目录 (默认: ./coodb_data)')
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 设置环境变量以配置数据库
    os.environ['COODB_DIR'] = os.path.abspath(args.dir)
    
    # 打印服务配置信息
    print(f"启动 CoolDB HTTP 服务")
    print(f"  - 监听地址：http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}")
    print(f"  - 数据库目录：{os.environ['COODB_DIR']}")
    print(f"  - API文档：http://localhost:{args.port}/api")
    print(f"  - 管理面板：http://localhost:{args.port}/dashboard")
    print("使用 Ctrl+C 停止服务")
    
    # 启动服务器
    server = Server(host=args.host, port=args.port)
    server.start(block=True)

if __name__ == "__main__":
    main() 