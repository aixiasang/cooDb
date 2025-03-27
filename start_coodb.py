#!/usr/bin/env python
"""
CoolDB FastAPI服务器启动脚本
使用FastAPI和Uvicorn提供高性能HTTP接口

用法:
    python start_coodb.py [--port PORT] [--dir DB_DIR]
选项:
    --port PORT    监听端口，默认为 8000
    --dir DB_DIR   数据库目录，默认为 ./coodb_data
"""

import os
import sys
import argparse
import uvicorn
from pathlib import Path

def main():
    print("CoolDB - 高性能键值数据库服务器")
    print("=" * 50)
    
    # 创建命令行解析器
    parser = argparse.ArgumentParser(description="启动 CoolDB HTTP 服务")
    parser.add_argument('--port', type=int, default=8000, 
                        help='监听端口 (默认: 8000)')
    parser.add_argument('--dir', type=str, default='./coodb_data', 
                        help='数据库目录 (默认: ./coodb_data)')
    parser.add_argument('--reload', action='store_true',
                        help='启用代码热重载 (开发模式)')
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 设置环境变量以配置数据库
    os.environ['COODB_DIR'] = os.path.abspath(args.dir)
    
    # 确保数据目录存在
    os.makedirs(os.environ['COODB_DIR'], exist_ok=True)
    
    # 打印服务配置信息
    print(f"系统信息: Python {sys.version}")
    print("\n服务配置:")
    print(f"  - 监听地址：http://localhost:{args.port}")
    print(f"  - 数据库目录：{os.environ['COODB_DIR']}")
    print(f"  - API文档：http://localhost:{args.port}/docs")
    print(f"  - 交互式API文档：http://localhost:{args.port}/redoc")
    print(f"  - 管理面板：http://localhost:{args.port}/dashboard")
    print("使用 Ctrl+C 停止服务\n")
    
    # 启动uvicorn服务器
    uvicorn.run(
        "coodb.http.api:app",
        host="0.0.0.0",
        port=args.port,
        reload=args.reload,
        log_level="info"
    )

if __name__ == "__main__":
    main() 