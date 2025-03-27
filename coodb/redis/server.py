"""
CoolDB Redis协议服务器
提供Redis协议兼容层，允许Redis客户端连接到CoolDB
"""

import socket
import selectors
import threading
import time
import logging
import struct
import os
from typing import Dict, List, Tuple, Optional, Any, Callable, Union

from coodb.options import Options
from coodb.redis.types import RedisDataStructure, ErrWrongTypeOperation

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('redis_server')

# Redis协议常量
REDIS_STRING = '+'
REDIS_ERROR = '-'
REDIS_INTEGER = ':'
REDIS_BULK = '$'
REDIS_ARRAY = '*'
REDIS_CRLF = '\r\n'

class RedisReply:
    """Redis协议回复生成器"""
    
    @staticmethod
    def ok() -> bytes:
        """返回OK"""
        return f"{REDIS_STRING}OK{REDIS_CRLF}".encode()
    
    @staticmethod
    def error(msg: str) -> bytes:
        """返回错误信息"""
        return f"{REDIS_ERROR}ERR {msg}{REDIS_CRLF}".encode()
    
    @staticmethod
    def integer(num: int) -> bytes:
        """返回整数"""
        return f"{REDIS_INTEGER}{num}{REDIS_CRLF}".encode()
    
    @staticmethod
    def bulk(data: Optional[bytes]) -> bytes:
        """返回批量字符串"""
        if data is None:
            return f"{REDIS_BULK}-1{REDIS_CRLF}".encode()
        return f"{REDIS_BULK}{len(data)}{REDIS_CRLF}".encode() + data + REDIS_CRLF.encode()
    
    @staticmethod
    def array(items: List[Optional[bytes]]) -> bytes:
        """返回数组"""
        result = f"{REDIS_ARRAY}{len(items)}{REDIS_CRLF}".encode()
        for item in items:
            result += RedisReply.bulk(item)
        return result
    
    @staticmethod
    def null_array() -> bytes:
        """返回空数组"""
        return f"{REDIS_ARRAY}-1{REDIS_CRLF}".encode()

class RedisClient:
    """Redis客户端连接处理器"""
    
    def __init__(self, conn: socket.socket, addr: Tuple[str, int], redis_db: RedisDataStructure):
        """初始化客户端连接
        
        Args:
            conn: 客户端连接的socket
            addr: 客户端地址
            redis_db: Redis数据结构服务
        """
        self.conn = conn
        self.addr = addr
        self.db = redis_db
        self.buffer = b''
        self.is_closed = False
    
    def read_command(self) -> Optional[List[bytes]]:
        """从缓冲区中读取一个完整的命令
        
        Returns:
            命令参数列表，如果没有完整命令则返回None
        """
        if not self.buffer:
            return None
        
        # 尝试解析命令
        try:
            # 一个完整的命令以 *<参数数量>\r\n 开始
            if self.buffer[0] != ord('*'):
                # 清空缓冲区并返回None
                self.buffer = b''
                return None
            
            # 查找第一个CRLF的位置
            pos = self.buffer.find(b'\r\n')
            if pos == -1:
                return None
            
            # 解析参数数量
            try:
                arg_count = int(self.buffer[1:pos])
            except ValueError:
                self.buffer = b''
                return None
            
            # 跳过 *<参数数量>\r\n
            self.buffer = self.buffer[pos + 2:]
            
            # 解析每个参数
            args = []
            for _ in range(arg_count):
                # 每个参数以 $<长度>\r\n 开始
                if not self.buffer or self.buffer[0] != ord('$'):
                    return None
                
                # 查找第一个CRLF的位置
                pos = self.buffer.find(b'\r\n')
                if pos == -1:
                    return None
                
                # 解析参数长度
                try:
                    arg_len = int(self.buffer[1:pos])
                except ValueError:
                    self.buffer = b''
                    return None
                
                # 跳过 $<长度>\r\n
                self.buffer = self.buffer[pos + 2:]
                
                # 检查缓冲区是否包含完整的参数
                if len(self.buffer) < arg_len + 2:  # +2 for CRLF
                    return None
                
                # 提取参数
                arg = self.buffer[:arg_len]
                self.buffer = self.buffer[arg_len + 2:]  # +2 for CRLF
                args.append(arg)
            
            return args
        except Exception as e:
            logger.error(f"Error parsing command: {e}")
            self.buffer = b''
            return None
    
    def process_data(self, data: bytes) -> None:
        """处理接收到的数据
        
        Args:
            data: 接收到的数据
        """
        self.buffer += data
        
        # 尝试解析并执行命令
        while True:
            args = self.read_command()
            if args is None:
                break
            
            # 执行命令
            try:
                self.execute_command(args)
            except Exception as e:
                logger.error(f"Error executing command: {e}")
                self.conn.sendall(RedisReply.error(str(e)))
    
    def execute_command(self, args: List[bytes]) -> None:
        """执行Redis命令
        
        Args:
            args: 命令参数列表
        """
        if not args:
            self.conn.sendall(RedisReply.error("empty command"))
            return
        
        # 获取命令名称（转为小写）
        cmd = args[0].decode('utf-8', errors='ignore').lower()
        
        # 命令处理
        try:
            if cmd == 'ping':
                self.conn.sendall(RedisReply.ok())
            elif cmd == 'quit':
                self.conn.sendall(RedisReply.ok())
                self.close()
            elif cmd == 'set':
                self._handle_set(args[1:])
            elif cmd == 'get':
                self._handle_get(args[1:])
            elif cmd == 'del':
                self._handle_del(args[1:])
            elif cmd == 'hset':
                self._handle_hset(args[1:])
            elif cmd == 'hget':
                self._handle_hget(args[1:])
            elif cmd == 'hdel':
                self._handle_hdel(args[1:])
            elif cmd == 'sadd':
                self._handle_sadd(args[1:])
            elif cmd == 'sismember':
                self._handle_sismember(args[1:])
            elif cmd == 'srem':
                self._handle_srem(args[1:])
            elif cmd == 'type':
                self._handle_type(args[1:])
            else:
                self.conn.sendall(RedisReply.error(f"unknown command '{cmd}'"))
        except Exception as e:
            logger.error(f"Error handling command {cmd}: {e}")
            self.conn.sendall(RedisReply.error(str(e)))
    
    def _handle_set(self, args: List[bytes]) -> None:
        """处理SET命令
        
        Args:
            args: 命令参数列表，不包含命令名
        """
        if len(args) < 2:
            self.conn.sendall(RedisReply.error("wrong number of arguments for 'set' command"))
            return
        
        key, value = args[0], args[1]
        ttl = 0
        
        # 检查是否有过期时间选项
        i = 2
        while i < len(args):
            if args[i].lower() == b'ex':
                if i + 1 >= len(args):
                    self.conn.sendall(RedisReply.error("syntax error"))
                    return
                try:
                    seconds = int(args[i + 1])
                    ttl = seconds * 1000  # 转换为毫秒
                    i += 2
                except ValueError:
                    self.conn.sendall(RedisReply.error("value is not an integer or out of range"))
                    return
            elif args[i].lower() == b'px':
                if i + 1 >= len(args):
                    self.conn.sendall(RedisReply.error("syntax error"))
                    return
                try:
                    ttl = int(args[i + 1])
                    i += 2
                except ValueError:
                    self.conn.sendall(RedisReply.error("value is not an integer or out of range"))
                    return
            else:
                i += 1
        
        # 设置值
        try:
            self.db.set(key, ttl, value)
            self.conn.sendall(RedisReply.ok())
        except Exception as e:
            self.conn.sendall(RedisReply.error(str(e)))
    
    def _handle_get(self, args: List[bytes]) -> None:
        """处理GET命令
        
        Args:
            args: 命令参数列表，不包含命令名
        """
        if len(args) != 1:
            self.conn.sendall(RedisReply.error("wrong number of arguments for 'get' command"))
            return
        
        key = args[0]
        try:
            value = self.db.get(key)
            self.conn.sendall(RedisReply.bulk(value))
        except ErrWrongTypeOperation:
            self.conn.sendall(RedisReply.error("WRONGTYPE Operation against a key holding the wrong kind of value"))
        except Exception as e:
            self.conn.sendall(RedisReply.error(str(e)))
    
    def _handle_del(self, args: List[bytes]) -> None:
        """处理DEL命令
        
        Args:
            args: 命令参数列表，不包含命令名
        """
        if not args:
            self.conn.sendall(RedisReply.error("wrong number of arguments for 'del' command"))
            return
        
        count = 0
        for key in args:
            try:
                if self.db.delete(key):
                    count += 1
            except Exception:
                pass
        
        self.conn.sendall(RedisReply.integer(count))
    
    def _handle_hset(self, args: List[bytes]) -> None:
        """处理HSET命令
        
        Args:
            args: 命令参数列表，不包含命令名
        """
        if len(args) < 3 or len(args) % 2 == 0:
            self.conn.sendall(RedisReply.error("wrong number of arguments for 'hset' command"))
            return
        
        key = args[0]
        count = 0
        
        # 设置多个字段
        for i in range(1, len(args), 2):
            field, value = args[i], args[i+1]
            try:
                if self.db.hset(key, field, value):
                    count += 1
            except ErrWrongTypeOperation:
                self.conn.sendall(RedisReply.error("WRONGTYPE Operation against a key holding the wrong kind of value"))
                return
            except Exception as e:
                self.conn.sendall(RedisReply.error(str(e)))
                return
        
        self.conn.sendall(RedisReply.integer(count))
    
    def _handle_hget(self, args: List[bytes]) -> None:
        """处理HGET命令
        
        Args:
            args: 命令参数列表，不包含命令名
        """
        if len(args) != 2:
            self.conn.sendall(RedisReply.error("wrong number of arguments for 'hget' command"))
            return
        
        key, field = args[0], args[1]
        try:
            value = self.db.hget(key, field)
            self.conn.sendall(RedisReply.bulk(value))
        except ErrWrongTypeOperation:
            self.conn.sendall(RedisReply.error("WRONGTYPE Operation against a key holding the wrong kind of value"))
        except Exception as e:
            self.conn.sendall(RedisReply.error(str(e)))
    
    def _handle_hdel(self, args: List[bytes]) -> None:
        """处理HDEL命令
        
        Args:
            args: 命令参数列表，不包含命令名
        """
        if len(args) < 2:
            self.conn.sendall(RedisReply.error("wrong number of arguments for 'hdel' command"))
            return
        
        key = args[0]
        count = 0
        
        for field in args[1:]:
            try:
                if self.db.hdel(key, field):
                    count += 1
            except ErrWrongTypeOperation:
                self.conn.sendall(RedisReply.error("WRONGTYPE Operation against a key holding the wrong kind of value"))
                return
            except Exception as e:
                self.conn.sendall(RedisReply.error(str(e)))
                return
        
        self.conn.sendall(RedisReply.integer(count))
    
    def _handle_sadd(self, args: List[bytes]) -> None:
        """处理SADD命令
        
        Args:
            args: 命令参数列表，不包含命令名
        """
        if len(args) < 2:
            self.conn.sendall(RedisReply.error("wrong number of arguments for 'sadd' command"))
            return
        
        key = args[0]
        count = 0
        
        for member in args[1:]:
            try:
                if self.db.sadd(key, member):
                    count += 1
            except ErrWrongTypeOperation:
                self.conn.sendall(RedisReply.error("WRONGTYPE Operation against a key holding the wrong kind of value"))
                return
            except Exception as e:
                self.conn.sendall(RedisReply.error(str(e)))
                return
        
        self.conn.sendall(RedisReply.integer(count))
    
    def _handle_sismember(self, args: List[bytes]) -> None:
        """处理SISMEMBER命令
        
        Args:
            args: 命令参数列表，不包含命令名
        """
        if len(args) != 2:
            self.conn.sendall(RedisReply.error("wrong number of arguments for 'sismember' command"))
            return
        
        key, member = args[0], args[1]
        try:
            result = self.db.sismember(key, member)
            self.conn.sendall(RedisReply.integer(1 if result else 0))
        except ErrWrongTypeOperation:
            self.conn.sendall(RedisReply.error("WRONGTYPE Operation against a key holding the wrong kind of value"))
        except Exception as e:
            self.conn.sendall(RedisReply.error(str(e)))
    
    def _handle_srem(self, args: List[bytes]) -> None:
        """处理SREM命令
        
        Args:
            args: 命令参数列表，不包含命令名
        """
        if len(args) < 2:
            self.conn.sendall(RedisReply.error("wrong number of arguments for 'srem' command"))
            return
        
        key = args[0]
        count = 0
        
        for member in args[1:]:
            try:
                if self.db.srem(key, member):
                    count += 1
            except ErrWrongTypeOperation:
                self.conn.sendall(RedisReply.error("WRONGTYPE Operation against a key holding the wrong kind of value"))
                return
            except Exception as e:
                self.conn.sendall(RedisReply.error(str(e)))
                return
        
        self.conn.sendall(RedisReply.integer(count))
    
    def _handle_type(self, args: List[bytes]) -> None:
        """处理TYPE命令
        
        Args:
            args: 命令参数列表，不包含命令名
        """
        if len(args) != 1:
            self.conn.sendall(RedisReply.error("wrong number of arguments for 'type' command"))
            return
        
        key = args[0]
        try:
            type_value = self.db.get_type(key)
            
            if type_value is None:
                self.conn.sendall(f"{REDIS_STRING}none{REDIS_CRLF}".encode())
            else:
                type_name = {
                    0: "string",
                    1: "hash",
                    2: "set",
                    3: "list",
                    4: "zset"
                }.get(type_value.value, "unknown")
                
                self.conn.sendall(f"{REDIS_STRING}{type_name}{REDIS_CRLF}".encode())
        except Exception as e:
            self.conn.sendall(RedisReply.error(str(e)))
    
    def close(self) -> None:
        """关闭连接"""
        if not self.is_closed:
            try:
                self.conn.close()
            except Exception:
                pass
            self.is_closed = True

class RedisServer:
    """Redis协议服务器"""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 6379, db_path: str = './cooldb_redis'):
        """初始化Redis服务器
        
        Args:
            host: 服务器地址
            port: 服务器端口
            db_path: 数据库路径
        """
        self.host = host
        self.port = port
        self.db_path = db_path
        self.running = False
        self.server_socket = None
        self.selector = selectors.DefaultSelector()
        self.clients = {}
        self.redis_db = None
        
        # 创建数据库目录
        os.makedirs(db_path, exist_ok=True)
    
    def start(self) -> None:
        """启动Redis服务器"""
        if self.running:
            return
        
        # 初始化Redis数据结构服务
        options = Options(dir_path=self.db_path)
        self.redis_db = RedisDataStructure.open(options)
        
        # 创建服务器socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(128)
        self.server_socket.setblocking(False)
        
        # 注册服务器socket到selector
        self.selector.register(self.server_socket, selectors.EVENT_READ, self._accept)
        
        # 标记服务器为运行状态
        self.running = True
        
        logger.info(f"Redis server started on {self.host}:{self.port}")
        
        # 启动事件循环
        try:
            self._event_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
    
    def stop(self) -> None:
        """停止Redis服务器"""
        if not self.running:
            return
        
        # 标记服务器为非运行状态
        self.running = False
        
        # 关闭所有客户端连接
        for client in list(self.clients.values()):
            client.close()
        self.clients.clear()
        
        # 关闭selector
        self.selector.close()
        
        # 关闭服务器socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        
        # 关闭Redis数据结构服务
        if self.redis_db:
            self.redis_db.close()
        
        logger.info("Redis server stopped")
    
    def _accept(self, sock: socket.socket, mask: int) -> None:
        """接受新的客户端连接
        
        Args:
            sock: 服务器socket
            mask: 事件掩码
        """
        conn, addr = sock.accept()
        logger.info(f"New connection from {addr}")
        conn.setblocking(False)
        
        # 创建客户端处理器
        client = RedisClient(conn, addr, self.redis_db)
        self.clients[conn] = client
        
        # 注册客户端socket到selector
        self.selector.register(conn, selectors.EVENT_READ, self._read)
    
    def _read(self, conn: socket.socket, mask: int) -> None:
        """处理客户端数据
        
        Args:
            conn: 客户端连接
            mask: 事件掩码
        """
        client = self.clients.get(conn)
        if not client:
            try:
                self.selector.unregister(conn)
            except:
                pass
            try:
                conn.close()
            except:
                pass
            return
        
        try:
            data = conn.recv(4096)
            if data:
                client.process_data(data)
            else:
                # 客户端关闭连接
                logger.info(f"Connection closed by {client.addr}")
                try:
                    self.selector.unregister(conn)
                except:
                    pass
                client.close()
                if conn in self.clients:
                    del self.clients[conn]
        except ConnectionError:
            # 连接错误
            logger.info(f"Connection error from {client.addr}")
            try:
                self.selector.unregister(conn)
            except:
                pass
            client.close()
            if conn in self.clients:
                del self.clients[conn]
        except Exception as e:
            # 其他错误
            logger.error(f"Error handling client {client.addr}: {e}")
            try:
                self.selector.unregister(conn)
            except Exception:
                pass
            client.close()
            if conn in self.clients:
                del self.clients[conn]
    
    def _event_loop(self) -> None:
        """事件循环"""
        while self.running:
            try:
                events = self.selector.select(timeout=1)
                for key, mask in events:
                    try:
                        callback = key.data
                        callback(key.fileobj, mask)
                    except Exception as e:
                        logger.error(f"Error in event callback: {e}")
            except Exception as e:
                if not self.running:
                    break
                logger.error(f"Error in event loop: {e}")
                time.sleep(0.1)

def start_redis_server(host: str = '127.0.0.1', port: int = 6379, db_path: str = './cooldb_redis'):
    """启动Redis协议服务器
    
    Args:
        host: 服务器地址
        port: 服务器端口
        db_path: 数据库路径
    """
    server = RedisServer(host, port, db_path)
    server.start()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CoolDB Redis Protocol Server")
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Bind address (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=6379, help='Bind port (default: 6379)')
    parser.add_argument('--db', type=str, default='./cooldb_redis', help='Database path (default: ./cooldb_redis)')
    
    args = parser.parse_args()
    start_redis_server(args.host, args.port, args.db) 