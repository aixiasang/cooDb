"""
Coodb HTTP服务器模块
提供HTTP服务器功能
"""

import os
import sys
import threading
import signal
from flask import Flask

from .app import app

class Server:
    """HTTP服务器类"""
    
    def __init__(self, host="0.0.0.0", port=8000):
        """初始化服务器
        
        Args:
            host: 监听主机，默认为0.0.0.0
            port: 监听端口，默认为8000
        """
        self.host = host
        self.port = port
        self.server_thread = None
        self.is_running = False
        self._app = app
        
    def start(self, block=True):
        """启动HTTP服务器
        
        Args:
            block: 是否阻塞主线程，默认为True
        """
        if self.is_running:
            return
            
        def run_server():
            # 使用线程安全的方式运行Flask
            self._app.run(
                host=self.host, 
                port=self.port,
                use_reloader=False,  # 禁用reloader以避免启动多个线程
                threaded=True,       # 启用多线程
                debug=False          # 禁用debug模式
            )
            
        self.server_thread = threading.Thread(target=run_server)
        self.server_thread.daemon = True  # 设置为守护线程，随主线程退出而退出
        self.server_thread.start()
        self.is_running = True
        
        print(f"Coodb HTTP服务启动在 http://{self.host}:{self.port}")
        
        if block:
            try:
                # 设置信号处理，以便捕获Ctrl+C
                signal.signal(signal.SIGINT, self._signal_handler)
                signal.signal(signal.SIGTERM, self._signal_handler)
                
                # 保持主线程运行
                while self.is_running:
                    signal.pause()  # 等待信号
            except (KeyboardInterrupt, SystemExit):
                self.stop()
    
    def _signal_handler(self, sig, frame):
        """信号处理函数"""
        self.stop()
            
    def stop(self):
        """停止HTTP服务器"""
        if not self.is_running:
            return
            
        self.is_running = False
        print("HTTP服务已停止")