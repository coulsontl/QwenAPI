"""
OpenAI-compatible API endpoints
"""
import json
import time
import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from ..utils import verify_password
from .routes import handle_chat


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/v1/models")
async def get_models(request: Request):
    auth_header = request.headers.get('Authorization')
    if not verify_password(auth_header):
        logger.warning("OpenAI 兼容接口鉴权失败：models")
        raise HTTPException(status_code=401, detail="Unauthorized")
    
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
    
    logger.debug("返回模型列表，数量: %s", len(models["data"]))
    return JSONResponse(content=models)


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    auth_header = request.headers.get('Authorization')
    if not verify_password(auth_header):
        logger.warning("OpenAI 兼容接口鉴权失败：chat completions")
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        data = await request.json()
    except Exception:
        logger.exception("解析 OpenAI 聊天请求失败")
        raise HTTPException(status_code=400, detail="Request format error")
    
    logger.debug("OpenAI chat completions 请求已通过验证")
    return await handle_chat(data)
