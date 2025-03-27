#!/usr/bin/env python
"""
CoolDB Redis服务器启动脚本

使用方法:
    python start_redis.py [选项]

选项:
    --host HOST    绑定地址 (默认: 127.0.0.1)
    --port PORT    绑定端口 (默认: 6379)
    --db PATH      数据库目录路径 (默认: ./cooldb_redis)
    
示例:
    # 使用默认配置启动Redis服务器
    python start_redis.py
    
    # 指定端口和数据目录
    python start_redis.py --port 6380 --db /path/to/data
"""

import os
import sys
import argparse
from coodb.redis.server import start_redis_server

def main():
    """启动Redis服务器入口函数"""
    
    parser = argparse.ArgumentParser(description="CoolDB Redis Protocol Server")
    parser.add_argument('--host', type=str, default='127.0.0.1', help='绑定地址 (默认: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=6379, help='绑定端口 (默认: 6379)')
    parser.add_argument('--db', type=str, default='./cooldb_redis', help='数据库目录 (默认: ./cooldb_redis)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"CoolDB Redis服务器 v1.0.0")
    print("=" * 60)
    print(f"  系统信息: Python {sys.version}")
    print(f"  监听地址: {args.host}:{args.port}")
    print(f"  数据库目录: {os.path.abspath(args.db)}")
    print("=" * 60)
    print("服务器启动中，使用Ctrl+C停止...")
    print("等待客户端连接...")
    
    try:
        # 启动Redis服务器
        start_redis_server(args.host, args.port, args.db)
    except KeyboardInterrupt:
        print("\n接收到中断信号，服务器正在关闭...")
    except Exception as e:
        print(f"\n服务器启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 