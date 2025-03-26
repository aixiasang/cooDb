#!/usr/bin/env python
"""
Coodb HTTP 服务启动脚本
用法: python -m coodb.http.run
"""

import os
import sys
from .server import Server

if __name__ == "__main__":
    print("启动 Coodb HTTP 服务...")
    server = Server()
    server.start()