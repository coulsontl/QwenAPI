"""
OpenAI-compatible API endpoints
"""
import json
import time
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from ..utils import verify_password
from .routes import handle_chat


router = APIRouter()


@router.get("/v1/models")
async def get_models(request: Request):
    """获取模型列表"""
    auth_header = request.headers.get('Authorization')
    if not verify_password(auth_header):
        raise HTTPException(status_code=401, detail="未授权")
    
    models = {
        "object": "list",
        "data": [
            {
                "id": "qwen3-coder-plus",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "qwen"
            },
            {
                "id": "qwen3-coder-flash",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "qwen"
            }
        ]
    }
    
    return JSONResponse(content=models)


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """处理聊天API请求"""
    auth_header = request.headers.get('Authorization')
    if not verify_password(auth_header):
        raise HTTPException(status_code=401, detail="未授权")
    
    try:
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="请求格式错误")
    
    return await handle_chat(data)