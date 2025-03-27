#!/usr/bin/env python
"""
CoolDB HTTP服务启动脚本 (简化版)
绕过server.py，直接使用app.py启动服务

用法:
    python run_http.py [--port PORT] [--dir DB_DIR]
选项:
    --port PORT    监听端口，默认为 8000
    --dir DB_DIR   数据库目录，默认为 ./coodb_data
"""

import os
import sys
import argparse
import traceback

def main():
    # 创建命令行解析器
    parser = argparse.ArgumentParser(description="启动 CoolDB HTTP 服务")
    parser.add_argument('--port', type=int, default=8000, 
                        help='监听端口 (默认: 8000)')
    parser.add_argument('--dir', type=str, default='./coodb_data', 
                        help='数据库目录 (默认: ./coodb_data)')
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 设置环境变量以配置数据库
    os.environ['COODB_DIR'] = os.path.abspath(args.dir)
    os.environ['PORT'] = str(args.port)
    
    # 打印服务配置信息
    print(f"启动 CoolDB HTTP 服务")
    print(f"  - 监听地址：http://localhost:{args.port}")
    print(f"  - 数据库目录：{os.environ['COODB_DIR']}")
    print(f"  - API文档：http://localhost:{args.port}/api")
    print(f"  - 管理面板：http://localhost:{args.port}/dashboard")
    print("使用 Ctrl+C 停止服务")
    
    try:
        # 尝试使用修复的werkzeug url_quote处理
        print("正在加载Flask依赖...")
        try:
            from werkzeug.urls import url_quote
        except ImportError:
            try:
                from werkzeug.utils import url_quote
                print("使用werkzeug.utils中的url_quote")
            except ImportError:
                from urllib.parse import quote as url_quote
                print("使用urllib.parse中的quote作为url_quote的替代")
        
        # 确保模块路径正确
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        # 尝试直接导入并运行app
        print("加载CoolDB HTTP应用...")
        from coodb.http.app import app
        
        # 启动服务器
        print("启动HTTP服务器...")
        app.run(host='0.0.0.0', port=args.port, debug=False)
    except ImportError as e:
        print(f"导入错误: {e}")
        print("\n解决方案:")
        print("1. 请确保安装了兼容的Flask和Werkzeug版本:")
        print("   pip install flask==2.0.1 werkzeug==2.0.1")
        print("2. 如果仍然有问题，尝试创建一个新的虚拟环境:")
        print("   python -m venv env")
        print("   source env/bin/activate  # 在Windows上使用: env\\Scripts\\activate")
        print("   pip install -r requirements.txt")
        traceback.print_exc()
    except Exception as e:
        print(f"启动服务器时出错: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main() 