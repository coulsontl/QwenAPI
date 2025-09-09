import json
import time
import asyncio
import logging
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

logger = logging.getLogger(__name__)

_session = None

async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(
            limit=200,
            limit_per_host=50,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        timeout = aiohttp.ClientTimeout(total=30, connect=5)
        _session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            connector_owner=True
        )
    return _session

router = APIRouter()
db = TokenDatabase()
oauth_manager = OAuthManager()
token_manager = TokenManager(db)
_version_manager = None

def set_version_manager(version_manager):
    global _version_manager
    _version_manager = version_manager
    token_manager.set_version_manager(version_manager)
    oauth_manager.set_version_manager(version_manager)

async def parse_json(request: Request) -> Dict[str, Any]:
    try:
        return await request.json()
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")

@router.post("/login")
async def api_login(request: Request):
    data = await parse_json(request)
    if data.get('password') == API_PASSWORD:
        return JSONResponse({'success': True})
    raise HTTPException(401, "Invalid password")

@router.post("/upload-token")
async def api_upload_token(request: Request, auth: bool = Depends(check_auth)):
    data = await parse_json(request)
    access_token = data.get('access_token')
    refresh_token = data.get('refresh_token')
    
    if not access_token or not refresh_token:
        raise HTTPException(400, "Missing token fields")
    
    token_id = get_token_id(refresh_token)
    token_data = TokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=data.get('expiry_date'),
        uploaded_at=int(time.time() * 1000)
    )
    
    token_manager.save_token(token_id, token_data)
    return JSONResponse({'success': True})

@router.get("/token-status")
async def api_token_status(auth: bool = Depends(check_auth)):
    token_manager.load_tokens()
    return JSONResponse(token_manager.get_token_status())

@router.post("/refresh-single-token")
async def api_refresh_single_token(request: Request, auth: bool = Depends(check_auth)):
    data = await parse_json(request)
    token_id = data.get('tokenId')
    
    if not token_id:
        raise HTTPException(400, "Missing tokenId")
    
    token_manager.load_tokens()
    try:
        return JSONResponse(await token_manager.refresh_single_token(token_id))
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, 500)

@router.post("/delete-token")
async def api_delete_token(request: Request, auth: bool = Depends(check_auth)):
    data = await parse_json(request)
    token_id = data.get('tokenId')
    
    if not token_id:
        raise HTTPException(400, "Missing tokenId")
    
    token_manager.load_tokens()
    if token_id not in token_manager.token_store:
        raise HTTPException(404, "Token not found")
    
    token_manager.delete_token(token_id)
    return JSONResponse({'success': True, 'tokenId': token_id})

@router.post("/delete-all-tokens")
async def api_delete_all_tokens(auth: bool = Depends(check_auth)):
    deleted_count = len(token_manager.token_store)
    token_manager.delete_all_tokens()
    return JSONResponse({'success': True, 'deletedCount': deleted_count})

@router.post("/refresh-token")
async def api_refresh_token(auth: bool = Depends(check_auth)):
    token_manager.load_tokens()
    try:
        return JSONResponse(await token_manager.refresh_all_tokens())
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, 500)

@router.post("/oauth-init")
async def api_oauth_init(auth: bool = Depends(check_auth)):
    try:
        result = await asyncio.wait_for(
            oauth_manager.init_oauth(), 
            timeout=12
        )
        return JSONResponse(result)
    except asyncio.TimeoutError:
        logger.error("OAuth初始化接口超时")
        return JSONResponse({
            'success': False,
            'error': 'Request timeout',
            'error_description': 'The OAuth initialization request timed out'
        })
    except Exception as e:
        logger.error(f"OAuth初始化接口错误: {e}")
        return JSONResponse({
            'success': False,
            'error': 'Internal error',
            'error_description': str(e)
        }, 500)

@router.post("/oauth-poll")
async def api_oauth_poll(request: Request, auth: bool = Depends(check_auth)):
    data = await parse_json(request)
    state_id = data.get('stateId')
    
    if not state_id:
        raise HTTPException(400, "Missing stateId")
    
    result = await oauth_manager.poll_oauth_status(state_id)
    
    if result.get('success') and result.get('tokenData'):
        token_data = result['tokenData']
        token_id = get_token_id(token_data.refresh_token)
        token_manager.save_token(token_id, token_data)
        return JSONResponse({'success': True, 'tokenId': token_id})
    
    return JSONResponse(result)

@router.post("/oauth-cancel")
async def api_oauth_cancel(request: Request, auth: bool = Depends(check_auth)):
    data = await parse_json(request)
    return JSONResponse(oauth_manager.cancel_oauth(data.get('stateId')))

@router.post("/chat")
async def api_chat(request: Request, auth: bool = Depends(check_auth)):
    return await handle_chat(await parse_json(request))

@router.get("/statistics/usage")
async def get_usage_statistics(request: Request, auth: bool = Depends(check_auth)):
    date = request.query_params.get('date') or get_local_today_iso()
    return JSONResponse(db.get_usage_stats(date))

@router.get("/statistics/available-dates")
async def get_available_dates(auth: bool = Depends(check_auth)):
    return JSONResponse({"dates": db.get_available_dates()})

@router.delete("/statistics/usage")
async def delete_usage_statistics(request: Request, auth: bool = Depends(check_auth)):
    data = await parse_json(request)
    date = data.get('date')
    if not date:
        raise HTTPException(400, "Missing date")
    
    return JSONResponse({'success': True, 'deletedCount': db.delete_usage_stats(date)})

@router.get("/health")
async def health_check():
    try:
        tokens = db.load_all_tokens()
        return JSONResponse({
            "status": "ok",
            "timestamp": time.time(),
            "database": {"status": "healthy", "token_count": len(tokens)}
        })
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, 503)

@router.get("/metrics")
async def get_metrics(auth: bool = Depends(check_auth)):
    try:
        tokens = db.load_all_tokens()
        valid = sum(1 for _, token in tokens.items() 
                   if not (token.expires_at and time.time() * 1000 > token.expires_at))
        
        return JSONResponse({
            "tokens": {"total": len(tokens), "valid": valid},
            "usage": {"today": db.get_usage_stats(get_local_today_iso())},
            "performance": {"timestamp": time.time()}
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)

@router.get("/version")
async def get_version(auth: bool = Depends(check_auth)):
    try:
        if _version_manager:
            try:
                version = await asyncio.wait_for(
                    _version_manager.get_version(), 
                    timeout=8
                )
                return JSONResponse({"version": version})
            except asyncio.TimeoutError:
                return JSONResponse({"version": "获取超时", "timeout": True})
        else:
            return JSONResponse({"version": "未知"})
    except Exception as e:
        logger.error(f"版本接口错误: {e}")
        return JSONResponse({"version": "错误", "error": str(e)})

async def handle_chat(data: Dict[str, Any]):
    messages = data.get('messages')
    model = data.get('model', 'qwen3-coder-plus')
    stream = data.get('stream', False)
    
    if not messages or not isinstance(messages, list):
        raise HTTPException(400, "Invalid messages")

    try:
        encoding = tiktoken.get_encoding("cl100k_base")
    except:
        encoding = tiktoken.encoding_for_model("gpt-4")

    prompt_tokens = sum(len(encoding.encode(str(msg.get('content', '')))) for msg in messages)
    token_manager.load_tokens()
    
    valid_token = await token_manager.get_valid_token()
    if not valid_token:
        raise HTTPException(400, "No valid token")
    
    token_id, current_token = valid_token
    session = await get_session()
    
    headers = {
        'Authorization': f'Bearer {current_token.access_token}',
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream' if stream else 'application/json'
    }
    
    if _version_manager:
        headers['User-Agent'] = await _version_manager.get_user_agent_async()

    body = {
        'model': model,
        'messages': messages,
        'temperature': data.get('temperature', 0.5),
        'top_p': data.get('top_p', 1),
        'stream': stream
    }

    response = await session.post(QWEN_API_ENDPOINT, json=body, headers=headers)
    if response.status != 200:
        raise HTTPException(500, f'API error: {response.status}')

    if stream:
        async def generate():
            buffer = ""
            last_content = ""
            completion_text = ""
            
            async for chunk in response.content.iter_any():
                buffer += chunk.decode('utf-8')
                
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.startswith('data:'):
                        line_data = line[5:].strip()
                        if line_data and line_data != '[DONE]':
                            try:
                                json_data = json.loads(line_data)
                                delta = json_data.get('choices', [{}])[0].get('delta', {})
                                current_content = delta.get('content', '')
                                
                                if current_content and current_content != last_content:
                                    last_content = current_content
                                    completion_text += current_content
                                    yield line + '\n'
                                elif not current_content:
                                    yield line + '\n'
                            except:
                                yield line + '\n'
                        else:
                            yield line + '\n'
                    else:
                        yield line + '\n'
            
            if buffer:
                yield buffer
                
            if completion_text:
                tokens = len(encoding.encode(completion_text))
                db.update_token_usage(get_local_today_iso(), model, prompt_tokens + tokens)
                db.increment_token_usage_count(token_id)
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    
    result = await response.json()
    if 'usage' in result:
        db.update_token_usage(get_local_today_iso(), model, result['usage'].get('total_tokens', 0))
        db.increment_token_usage_count(token_id)
    
    return JSONResponse(result)