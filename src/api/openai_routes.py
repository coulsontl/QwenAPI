"""
OpenAI-compatible API endpoints
"""
import json
import time
import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from ..utils import verify_password
from ..utils.version_manager import get_version_manager
from ..database import TokenDatabase
from ..oauth import TokenManager
from .routes import handle_chat


router = APIRouter()
logger = logging.getLogger(__name__)

# 初始化数据库和token管理器
db = TokenDatabase()
token_manager = TokenManager(db)


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


@router.get("/v1/qwen/access-token")
async def get_access_token(request: Request):
    """
    获取一个有效的access token并增加其使用次数，同时返回User-Agent
    """
    auth_header = request.headers.get('Authorization')
    if not verify_password(auth_header):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # 加载最新的token数据
    token_manager.load_tokens()
    
    # 获取一个有效的token
    valid_token = await token_manager.get_valid_token()
    if not valid_token:
        raise HTTPException(status_code=400, detail="No valid token available")
    
    token_id, token_data = valid_token
    
    # 增加使用次数
    db.increment_token_usage_count(token_id)
    
    # 获取User-Agent
    user_agent = "unknown"
    try:
        version_manager = get_version_manager()
        user_agent = await version_manager.get_user_agent_async()
    except:
        pass
    
    # 返回token信息和User-Agent
    return JSONResponse({
        "access_token": token_data.access_token,
        "token_id": token_id,
        "user_agent": user_agent
    })
