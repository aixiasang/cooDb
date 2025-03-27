"""
CoolDB FastAPI接口
提供基于FastAPI的HTTP接口和API文档
"""

import os
import sys
import json
import math
import base64
import io
import zipfile
import datetime
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Depends, Body, File, UploadFile, Request, Form
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

# 添加coodb模块到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from coodb.db import DB
from coodb.options import Options, IndexType
from coodb.errors import ErrKeyNotFound, ErrKeyIsEmpty, ErrDatabaseClosed

# 全局数据库实例
db_instance = None

# API版本
API_VERSION = "1.0.0"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理器"""
    # 启动时不做任何操作
    yield
    # 关闭时清理资源
    global db_instance
    if db_instance is not None and not db_instance.is_closed:
        db_instance.close()
        db_instance = None

# 创建FastAPI应用
app = FastAPI(
    title="CoolDB API",
    description="CoolDB键值存储数据库的HTTP接口",
    version="1.0.0",
    lifespan=lifespan,
)

# 静态文件和模板设置
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(current_dir / "static")), name="static")
templates = Jinja2Templates(directory=str(current_dir / "templates"))

# API版本
API_VERSION = "1.0.0"

# 模型定义
class KeyValue(BaseModel):
    """键值对模型"""
    key: str
    value: Optional[str] = None
    raw_key: Optional[str] = None

class PaginationInfo(BaseModel):
    """分页信息模型"""
    page: int
    per_page: int
    total_count: int
    total_pages: int

class KeyValueListResponse(BaseModel):
    """键值对列表响应模型"""
    items: List[KeyValue]
    pagination: PaginationInfo

class KeyValueResponse(BaseModel):
    """单个键值对响应模型"""
    key: str
    value: Optional[str] = None
    encoding: Optional[str] = None

class ValueUpdate(BaseModel):
    """值更新模型"""
    value: str
    encoding: Optional[str] = None

class SuccessResponse(BaseModel):
    """成功响应模型"""
    success: bool = True

class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str

class BatchOperation(BaseModel):
    """批处理操作模型"""
    operation: str
    key: str
    value: Optional[str] = None
    encoding: Optional[str] = None

class ImportResponse(BaseModel):
    """导入响应模型"""
    success: bool = True
    processed: int
    errors: List[str] = []

def get_db() -> DB:
    """获取数据库实例，如果不存在则创建"""
    global db_instance
    if db_instance is None or db_instance.is_closed:
        # 数据库配置
        db_dir = os.environ.get('COODB_DIR', os.path.join(os.getcwd(), "coodb_data"))
        options = Options(
            dir_path=db_dir,
            max_file_size=32 * 1024 * 1024,  # 32MB
            sync_writes=False,
            index_type=IndexType.BTREE
        )
        # 确保数据目录存在
        os.makedirs(options.dir_path, exist_ok=True)
        db_instance = DB(options)
    return db_instance

@app.get("/", include_in_schema=False)
async def root():
    """重定向到API文档页面"""
    return RedirectResponse(url="/docs")

@app.get("/api", include_in_schema=False)
async def api_docs(request: Request):
    """API文档页面"""
    return templates.TemplateResponse("api_docs.html", {"request": request, "api_version": API_VERSION})

@app.get("/dashboard", include_in_schema=False)
async def dashboard(request: Request):
    """数据库仪表盘页面"""
    return templates.TemplateResponse("dashboard.html", {"request": request, "api_version": API_VERSION})

@app.get("/api/v1/stats", response_model=Dict[str, Any], tags=["信息"])
async def get_stats():
    """获取数据库统计信息"""
    db = get_db()
    try:
        stats = db.stat()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/keys", response_model=KeyValueListResponse, tags=["键值对"])
async def list_keys(
    page: int = Query(1, description="页码"),
    per_page: int = Query(20, description="每页记录数"),
    search: str = Query("", description="搜索关键字")
):
    """列出所有键，支持分页和搜索"""
    db = get_db()
    
    try:
        # 限制每页最大数量
        per_page = min(per_page, 100)
        
        # 使用迭代器获取所有键
        all_keys = []
        it = db.iterator()
        it.rewind()
        while it.valid():
            key = it.key()
            try:
                decoded_key = key.decode('utf-8', errors='replace')
                # 如果有搜索关键字，则过滤
                if not search or search.lower() in decoded_key.lower():
                    all_keys.append(key)
            except:
                # 如果键无法解码为UTF-8，则跳过
                pass
            it.next()
            
        # 计算总页数
        total_count = len(all_keys)
        total_pages = math.ceil(total_count / per_page)
        
        # 获取当前页的键
        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, total_count)
        paginated_keys = all_keys[start_idx:end_idx]
        
        # 获取键值对
        items = []
        for key in paginated_keys:
            try:
                value = db.get(key)
                decoded_key = key.decode('utf-8', errors='replace')
                
                # 尝试将值解码为字符串，失败则用base64编码
                try:
                    if value is not None:
                        decoded_value = value.decode('utf-8', errors='replace')
                    else:
                        decoded_value = None
                except:
                    decoded_value = f"[BINARY] {base64.b64encode(value).decode('ascii')[:100]}..."
                    
                items.append(KeyValue(
                    key=decoded_key,
                    value=decoded_value,
                    raw_key=base64.b64encode(key).decode('ascii')
                ))
            except Exception as e:
                print(f"Error getting value for key {key}: {str(e)}")
        
        pagination = PaginationInfo(
            page=page,
            per_page=per_page,
            total_count=total_count,
            total_pages=total_pages
        )
        
        return KeyValueListResponse(
            items=items,
            pagination=pagination
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/keys/{key}", response_model=KeyValueResponse, tags=["键值对"])
async def get_value(key: str, is_base64: bool = Query(False, description="是否为base64编码的键", alias="base64")):
    """获取键对应的值"""
    db = get_db()
    try:
        # 转换键为字节
        if is_base64:
            key_bytes = base64.b64decode(key)
        else:
            key_bytes = key.encode('utf-8')
            
        value = db.get(key_bytes)
        
        if value is None:
            raise HTTPException(status_code=404, detail="Key not found")
            
        # 尝试将值解码为字符串，如果失败则返回base64编码
        try:
            value_str = value.decode('utf-8')
            return KeyValueResponse(key=key, value=value_str)
        except UnicodeDecodeError:
            value_b64 = base64.b64encode(value).decode('ascii')
            return KeyValueResponse(key=key, value=value_b64, encoding="base64")
            
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/keys/{key}", response_model=SuccessResponse, tags=["键值对"])
@app.post("/api/v1/keys/{key}", response_model=SuccessResponse, tags=["键值对"])
async def put_value(key: str, data: ValueUpdate, is_base64_key: bool = Query(False, description="是否为base64编码的键", alias="base64_key")):
    """设置键值对"""
    db = get_db()
    try:
        # 转换键值为字节
        if is_base64_key:
            key_bytes = base64.b64decode(key)
        else:
            key_bytes = key.encode('utf-8')
        
        # 处理值的编码
        if data.encoding == "base64":
            value_bytes = base64.b64decode(data.value)
        else:
            value_bytes = data.value.encode('utf-8')
            
        # 写入数据库
        db.put(key_bytes, value_bytes)
        return SuccessResponse()
        
    except ErrKeyIsEmpty:
        raise HTTPException(status_code=400, detail="Key cannot be empty")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/keys/{key}", response_model=SuccessResponse, tags=["键值对"])
async def delete_value(key: str, is_base64: bool = Query(False, description="是否为base64编码的键", alias="base64")):
    """删除键值对"""
    db = get_db()
    try:
        # 转换键为字节
        if is_base64:
            key_bytes = base64.b64decode(key)
        else:
            key_bytes = key.encode('utf-8')
        
        # 先检查键是否存在
        value = db.get(key_bytes)
        if value is None:
            raise HTTPException(status_code=404, detail="Key not found")
            
        # 删除键
        db.delete(key_bytes)
        return SuccessResponse()
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/batch", response_model=SuccessResponse, tags=["批处理"])
async def batch_operations(operations: List[BatchOperation]):
    """批量操作"""
    db = get_db()
    try:
        # 创建批处理
        batch = db.new_batch()
        
        # 处理每个操作
        for op in operations:
            key_bytes = op.key.encode('utf-8')
            
            if op.operation == 'put':
                # 处理值的编码
                if op.encoding == 'base64':
                    value_bytes = base64.b64decode(op.value)
                else:
                    value_bytes = op.value.encode('utf-8')
                    
                batch.put(key_bytes, value_bytes)
                
            elif op.operation == 'delete':
                batch.delete(key_bytes)
                
            else:
                raise HTTPException(status_code=400, detail=f"Unknown operation: {op.operation}")
                
        # 提交批处理
        batch.commit()
        return SuccessResponse()
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/merge", response_model=SuccessResponse, tags=["数据库操作"])
async def merge_database():
    """执行数据库合并操作"""
    db = get_db()
    try:
        db.merge()
        return SuccessResponse()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/backup", tags=["数据库操作"])
async def backup_database():
    """创建数据库备份"""
    db = get_db()
    try:
        # 创建内存中的zip文件
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 获取数据库目录
            db_dir = db.options.dir_path
            
            # 添加数据库文件到zip
            for root, dirs, files in os.walk(db_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, start=os.path.dirname(db_dir))
                    zf.write(file_path, rel_path)
            
            # 添加元数据文件
            stats = db.stat()
            metadata = {
                "timestamp": datetime.datetime.now().isoformat(),
                "version": API_VERSION,
                "stats": stats
            }
            zf.writestr("metadata.json", json.dumps(metadata, indent=2))
        
        # 设置指针到文件开头
        memory_file.seek(0)
        
        # 生成文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"coodb_backup_{timestamp}.zip"
        
        # 返回文件流
        return StreamingResponse(
            iter([memory_file.getvalue()]), 
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/export", tags=["数据库操作"])
async def export_data(limit: int = Query(10000, description="最大导出记录数")):
    """导出数据库中的所有键值对为JSON格式"""
    db = get_db()
    try:
        # 收集所有键值对
        data = []
        it = db.iterator()
        it.rewind()
        
        # 限制导出数量，防止内存溢出
        count = 0
        
        while it.valid() and count < limit:
            key = it.key()
            value = db.get(key)
            
            # 尝试将键值解码为字符串
            try:
                key_str = key.decode('utf-8')
            except UnicodeDecodeError:
                key_str = f"base64:{base64.b64encode(key).decode('ascii')}"
                
            # 尝试将值解码为字符串
            try:
                if value is not None:
                    value_str = value.decode('utf-8')
                else:
                    value_str = None
            except UnicodeDecodeError:
                value_str = f"base64:{base64.b64encode(value).decode('ascii')}"
                
            data.append({
                "key": key_str,
                "value": value_str
            })
            
            it.next()
            count += 1
            
        # 创建JSON响应
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"coodb_export_{timestamp}.json"
        
        # 将JSON数据写入内存文件
        json_data = json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
        
        # 返回文件流
        return StreamingResponse(
            iter([json_data]), 
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/import", response_model=ImportResponse, tags=["数据库操作"])
async def import_data(file: UploadFile = File(...)):
    """从JSON文件导入键值对到数据库"""
    db = get_db()
    try:
        # 检查文件类型
        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="只支持JSON文件导入")
            
        # 读取JSON数据
        try:
            content = await file.read()
            data = json.loads(content.decode('utf-8'))
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="无效的JSON格式")
            
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="JSON数据必须是键值对数组")
            
        # 创建批处理
        batch = db.new_batch()
        processed = 0
        errors = []
        
        # 处理每个键值对
        for item in data:
            if not isinstance(item, dict) or 'key' not in item or 'value' not in item:
                errors.append(f"无效的数据项: {str(item)}")
                continue
                
            # 处理键
            key_str = item['key']
            if key_str.startswith('base64:'):
                key_bytes = base64.b64decode(key_str[7:])
            else:
                key_bytes = key_str.encode('utf-8')
                
            # 处理值
            value = item['value']
            if value is None:
                # 如果值为null，则删除该键
                batch.delete(key_bytes)
            else:
                if isinstance(value, str):
                    if value.startswith('base64:'):
                        value_bytes = base64.b64decode(value[7:])
                    else:
                        value_bytes = value.encode('utf-8')
                else:
                    value_bytes = str(value).encode('utf-8')
                    
                batch.put(key_bytes, value_bytes)
                
            processed += 1
            
        # 提交批处理
        batch.commit()
        
        return ImportResponse(
            success=True,
            processed=processed,
            errors=errors
        )
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

def start_server(host="0.0.0.0", port=8000):
    """启动FastAPI服务器"""
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    start_server() 