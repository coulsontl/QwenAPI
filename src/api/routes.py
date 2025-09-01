"""
API endpoints for Qwen Code API Server
"""
import json
import time
import aiohttp
import tiktoken
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from ..auth import check_auth
from ..oauth import OAuthManager, TokenManager
from ..database import TokenDatabase
from ..models import TokenData
from ..utils import get_token_id
from ..utils.timezone_utils import get_local_today_iso
from ..config import API_PASSWORD, QWEN_API_ENDPOINT

# 全局连接池
_session = None

async def get_http_session() -> aiohttp.ClientSession:
    """获取全局HTTP会话"""
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=30)
        _session = aiohttp.ClientSession(connector=connector, timeout=timeout)
    return _session

router = APIRouter()
db = TokenDatabase()
oauth_manager = OAuthManager()
token_manager = TokenManager(db)

async def parse_json_request(request: Request) -> Dict[str, Any]:
    """通用JSON请求解析"""
    try:
        return await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON解析错误")

@router.post("/login")
async def api_login(request: Request):
    """用户登录"""
    data = await parse_json_request(request)
    password = data.get('password')
    
    if password == API_PASSWORD:
        return JSONResponse(content={'success': True})
    raise HTTPException(status_code=401, detail="密码错误")

@router.post("/upload-token")
async def api_upload_token(request: Request, auth: bool = Depends(check_auth)):
    """上传token"""
    data = await parse_json_request(request)
    
    access_token = data.get('access_token')
    refresh_token = data.get('refresh_token')
    
    if not access_token or not refresh_token:
        raise HTTPException(status_code=400, detail="缺少必要的token字段")
    
    token_id = get_token_id(refresh_token)
    token_data = TokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=data.get('expires_at'),
        uploaded_at=int(time.time() * 1000)
    )
    
    token_manager.save_token(token_id, token_data)
    return JSONResponse(content={'success': True})

@router.get("/token-status")
async def api_token_status(auth: bool = Depends(check_auth)):
    """获取token状态"""
    token_manager.load_tokens()
    return JSONResponse(content=token_manager.get_token_status())

@router.post("/refresh-single-token")
async def api_refresh_single_token(request: Request, auth: bool = Depends(check_auth)):
    """刷新单个token"""
    data = await parse_json_request(request)
    token_id = data.get('tokenId')
    
    if not token_id:
        raise HTTPException(status_code=400, detail="缺少tokenId参数")
    
    token_manager.load_tokens()
    try:
        result = await token_manager.refresh_single_token(token_id)
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={'success': False, 'error': str(e)}, status_code=500)

@router.post("/delete-token")
async def api_delete_token(request: Request, auth: bool = Depends(check_auth)):
    """删除token"""
    data = await parse_json_request(request)
    token_id = data.get('tokenId')
    
    if not token_id:
        raise HTTPException(status_code=400, detail="缺少tokenId参数")
    
    token_manager.load_tokens()
    token = token_manager.token_store.get(token_id)
    if not token:
        raise HTTPException(status_code=404, detail="Token不存在")
    
    token_manager.delete_token(token_id)
    return JSONResponse(content={'success': True, 'tokenId': token_id})

@router.post("/delete-all-tokens")
async def api_delete_all_tokens(auth: bool = Depends(check_auth)):
    """删除所有token"""
    deleted_count = len(token_manager.token_store)
    token_manager.delete_all_tokens()
    return JSONResponse(content={'success': True, 'deletedCount': deleted_count})

@router.post("/refresh-token")
async def api_refresh_token(auth: bool = Depends(check_auth)):
    """刷新所有token"""
    token_manager.load_tokens()
    try:
        result = await token_manager.refresh_all_tokens()
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={'success': False, 'error': str(e)}, status_code=500)

@router.post("/oauth-init")
async def api_oauth_init(auth: bool = Depends(check_auth)):
    """初始化OAuth"""
    return JSONResponse(content=await oauth_manager.init_oauth())

@router.post("/oauth-poll")
async def api_oauth_poll(request: Request, auth: bool = Depends(check_auth)):
    """轮询OAuth状态"""
    data = await parse_json_request(request)
    state_id = data.get('stateId')
    
    if not state_id:
        raise HTTPException(status_code=400, detail="缺少stateId参数")
    
    result = await oauth_manager.poll_oauth_status(state_id)
    
    if result.get('success') and result.get('tokenData'):
        token_data = result['tokenData']
        token_id = get_token_id(token_data.refresh_token)
        token_manager.save_token(token_id, token_data)
        return JSONResponse(content={'success': True, 'tokenId': token_id})
    
    return JSONResponse(content=result)

@router.post("/oauth-cancel")
async def api_oauth_cancel(request: Request, auth: bool = Depends(check_auth)):
    """取消OAuth"""
    data = await parse_json_request(request)
    state_id = data.get('stateId')
    result = oauth_manager.cancel_oauth(state_id)
    return JSONResponse(content=result)

@router.post("/chat")
async def api_chat(request: Request, auth: bool = Depends(check_auth)):
    """聊天API"""
    data = await parse_json_request(request)
    return await handle_chat(data)

@router.get("/statistics/usage")
async def get_usage_statistics(request: Request, auth: bool = Depends(check_auth)):
    """获取用量统计"""
    date_param = request.query_params.get('date') or get_local_today_iso()
    stats = db.get_usage_stats(date_param)
    return JSONResponse(content=stats)

@router.delete("/statistics/usage")
async def delete_usage_statistics(request: Request, auth: bool = Depends(check_auth)):
    """删除用量统计"""
    data = await parse_json_request(request)
    date_param = data.get('date')
    
    if not date_param:
        raise HTTPException(status_code=400, detail="缺少date参数")
    
    deleted_count = db.delete_usage_stats(date_param)
    return JSONResponse(content={'success': True, 'deletedCount': deleted_count})

@router.get("/health")
async def health_check():
    """健康检查"""
    try:
        tokens = db.load_all_tokens()
        return JSONResponse(content={
            "status": "ok",
            "timestamp": time.time(),
            "database": {"status": "healthy", "token_count": len(tokens)}
        })
    except Exception as e:
        return JSONResponse(content={"status": "error", "error": str(e)}, status_code=503)

@router.get("/metrics")
async def get_metrics(auth: bool = Depends(check_auth)):
    """性能指标"""
    try:
        tokens = db.load_all_tokens()
        valid_tokens = sum(1 for _, token in tokens.items() 
                         if not (token.expires_at and time.time() * 1000 > token.expires_at))
        
        today = get_local_today_iso()
        usage_stats = db.get_usage_stats(today)
        
        return JSONResponse(content={
            "tokens": {"total": len(tokens), "valid": valid_tokens},
            "usage": {"today": usage_stats},
            "performance": {"timestamp": time.time()}
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

async def handle_chat(data: Dict[str, Any]):
    """处理聊天请求"""
    messages = data.get('messages')
    model = data.get('model', 'qwen3-coder-plus')
    stream = data.get('stream', False)
    
    if not messages or not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="缺少消息内容")

    try:
        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        encoding = tiktoken.encoding_for_model("gpt-4")

    prompt_tokens = sum(len(encoding.encode(msg.get('content', ''))) for msg in messages)

    token_manager.load_tokens()
    valid_token = await token_manager.get_valid_token()
    if not valid_token:
        raise HTTPException(status_code=400, detail="没有可用的token")
    
    token_id, current_token = valid_token
    session = await get_http_session()
    
    headers = {
        'Authorization': f'Bearer {current_token.access_token}',
        'Content-Type': 'application/json'
    }
    if stream:
        headers['Accept'] = 'text/event-stream'

    request_body = {
        'model': model,
        'messages': messages,
        'temperature': data.get('temperature', 0.5),
        'top_p': data.get('top_p', 1),
        'stream': stream
    }

    try:
        response = await session.post(QWEN_API_ENDPOINT, json=request_body, headers=headers)
        
        if response.status != 200:
            error_text = await response.text()
            raise HTTPException(status_code=500, detail=f'API调用失败: {response.status} {error_text}')

        if stream:
            async def generator():
                completion_text = ""
                try:
                    async for chunk in response.content.iter_any():
                        yield chunk
                        chunk_str = chunk.decode('utf-8')
                        for line in chunk_str.split('\n'):
                            if line.startswith('data:'):
                                line_data = line[5:].strip()
                                if line_data and line_data != '[DONE]':
                                    try:
                                        json_data = json.loads(line_data)
                                        delta = json_data.get('choices', [{}])[0].get('delta', {})
                                        if 'content' in delta:
                                            completion_text += delta['content']
                                    except:
                                        pass
                finally:
                    completion_tokens = len(encoding.encode(completion_text))
                    total_tokens = prompt_tokens + completion_tokens
                    db.update_token_usage(get_local_today_iso(), model, total_tokens)
                    db.increment_token_usage_count(token_id)
            return StreamingResponse(generator(), media_type="text/event-stream")
        else:
            response_json = await response.json()
            if 'usage' in response_json:
                tokens_used = response_json['usage'].get('total_tokens', 0)
                db.update_token_usage(get_local_today_iso(), model, tokens_used)
                db.increment_token_usage_count(token_id)
            return JSONResponse(content=response_json)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))