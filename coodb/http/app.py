import os
import sys
import json
import flask
from flask import Flask, request, jsonify, render_template, abort, Response, redirect
from typing import Dict, Optional, List, Any

# 导入coodb模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from coodb.db import DB
from coodb.options import Options, IndexType
from coodb.errors import ErrKeyNotFound, ErrKeyIsEmpty, ErrDatabaseClosed

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

# 全局数据库实例
db_instance = None

# API版本
API_VERSION = "1.0.0"

def get_db() -> DB:
    """获取数据库实例，如果不存在则创建"""
    global db_instance
    if db_instance is None or db_instance.is_closed:
        # 数据库配置
        options = Options(
            dir_path=os.path.join(os.getcwd(), "coodb_data"),
            max_file_size=32 * 1024 * 1024,  # 32MB
            sync_writes=False,
            index_type=IndexType.BTREE
        )
        # 确保数据目录存在
        os.makedirs(options.dir_path, exist_ok=True)
        db_instance = DB(options)
    return db_instance

@app.route('/')
def index():
    """重定向到API文档页面"""
    return redirect('/api')

@app.route('/coodb.json')
def openapi_spec():
    """返回OpenAPI规范"""
    with open(os.path.join(os.path.dirname(__file__), 'static', 'docs', 'coodb.json'), 'r') as f:
        spec = json.load(f)
    return jsonify(spec)

@app.route('/api')
def api_docs():
    """API文档页面"""
    return render_template('api_docs.html', api_version=API_VERSION)

@app.route('/api/v1/keys', methods=['GET'])
def list_keys():
    """列出所有键"""
    db = get_db()
    keys = []
    
    try:
        # 使用迭代器遍历所有键
        it = db.iterator()
        while it.valid():
            keys.append(it.key().decode('utf-8', errors='replace'))
            it.next()
        
        return jsonify({"keys": keys})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v1/keys/<path:key>', methods=['GET'])
def get_value(key):
    """获取键对应的值"""
    db = get_db()
    try:
        # 转换键为字节
        key_bytes = key.encode('utf-8')
        value = db.get(key_bytes)
        
        if value is None:
            return jsonify({"error": "Key not found"}), 404
            
        # 尝试将值解码为字符串，如果失败则返回base64编码
        try:
            value_str = value.decode('utf-8')
            return jsonify({"key": key, "value": value_str})
        except UnicodeDecodeError:
            import base64
            value_b64 = base64.b64encode(value).decode('ascii')
            return jsonify({"key": key, "value": value_b64, "encoding": "base64"})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v1/keys/<path:key>', methods=['PUT', 'POST'])
def put_value(key):
    """设置键值对"""
    db = get_db()
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or 'value' not in data:
            return jsonify({"error": "Missing value in request body"}), 400
            
        # 转换键值为字节
        key_bytes = key.encode('utf-8')
        
        # 处理值的编码
        if isinstance(data['value'], str):
            # 检查是否是base64编码
            if 'encoding' in data and data['encoding'] == 'base64':
                import base64
                value_bytes = base64.b64decode(data['value'])
            else:
                value_bytes = data['value'].encode('utf-8')
        else:
            return jsonify({"error": "Value must be a string"}), 400
            
        # 写入数据库
        db.put(key_bytes, value_bytes)
        return jsonify({"success": True}), 200
        
    except ErrKeyIsEmpty:
        return jsonify({"error": "Key cannot be empty"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v1/keys/<path:key>', methods=['DELETE'])
def delete_value(key):
    """删除键值对"""
    db = get_db()
    try:
        # 转换键为字节
        key_bytes = key.encode('utf-8')
        
        # 先检查键是否存在
        value = db.get(key_bytes)
        if value is None:
            return jsonify({"error": "Key not found"}), 404
            
        # 删除键
        db.delete(key_bytes)
        return jsonify({"success": True}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v1/batch', methods=['POST'])
def batch_operations():
    """批量操作"""
    db = get_db()
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or not isinstance(data, list):
            return jsonify({"error": "Request body must be a list of operations"}), 400
            
        # 创建批处理
        batch = db.new_batch()
        
        # 处理每个操作
        for op in data:
            if not isinstance(op, dict) or 'operation' not in op or 'key' not in op:
                return jsonify({"error": "Each operation must have 'operation' and 'key' fields"}), 400
                
            key_bytes = op['key'].encode('utf-8')
            
            if op['operation'] == 'put':
                if 'value' not in op:
                    return jsonify({"error": "Put operation must have a 'value' field"}), 400
                    
                # 处理值的编码
                if 'encoding' in op and op['encoding'] == 'base64':
                    import base64
                    value_bytes = base64.b64decode(op['value'])
                else:
                    value_bytes = op['value'].encode('utf-8')
                    
                batch.put(key_bytes, value_bytes)
                
            elif op['operation'] == 'delete':
                batch.delete(key_bytes)
                
            else:
                return jsonify({"error": f"Unknown operation: {op['operation']}"}), 400
                
        # 提交批处理
        batch.commit()
        return jsonify({"success": True}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v1/stats', methods=['GET'])
def get_stats():
    """获取数据库统计信息"""
    db = get_db()
    try:
        stats = db.stat()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v1/merge', methods=['POST'])
def merge_database():
    """执行数据库合并操作"""
    db = get_db()
    try:
        db.merge()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    """处理404错误"""
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def server_error(e):
    """处理500错误"""
    return jsonify({"error": "Internal server error"}), 500

@app.teardown_appcontext
def close_db(error):
    """应用程序上下文结束时关闭数据库连接"""
    global db_instance
    if db_instance is not None and not db_instance.is_closed:
        db_instance.close()
        db_instance = None

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)