"""
API endpoints for Qwen Code API Server
"""
import json
import time
import aiohttp
import tiktoken
from typing import Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, Response, StreamingResponse

from ..auth import check_auth
from ..oauth import OAuthManager, TokenManager
from ..database import TokenDatabase
from ..models import TokenData
from ..utils import get_token_id
from ..utils.timezone_utils import get_local_today, get_local_today_iso, utc_to_local
from ..config import API_PASSWORD, QWEN_API_ENDPOINT


router = APIRouter()


async def parse_json_request(request: Request) -> Dict[str, Any]:
    """通用JSON请求解析函数"""
    try:
        return await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON解析错误")


# Initialize managers
db = TokenDatabase()
oauth_manager = OAuthManager()
token_manager = TokenManager(db)


@router.post("/login")
async def api_login(request: Request):
    """处理登录请求"""
    data = await parse_json_request(request)
    
    password = data.get('password')
    
    if password == API_PASSWORD:
        return JSONResponse(content={'success': True})
    else:
        raise HTTPException(status_code=401, detail="密码错误")


@router.post("/upload-token")
async def api_upload_token(request: Request, auth: bool = Depends(check_auth)):
    """处理token上传"""
    data = await parse_json_request(request)
    
    access_token = data.get('access_token')
    refresh_token = data.get('refresh_token')
    
    if not access_token or not refresh_token:
        raise HTTPException(status_code=400, detail="缺少必要的token字段")
    
    # 使用refresh_token前8位作为标识符
    token_id = get_token_id(refresh_token)
    
    # 创建token数据
    token_data = TokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=data.get('expires_at') or data.get('expiry_date'),
        uploaded_at=int(time.time() * 1000)
    )
    
    # 存储token
    token_manager.save_token(token_id, token_data)
    
    return JSONResponse(content={'success': True})


@router.get("/token-status")
async def api_token_status(auth: bool = Depends(check_auth)):
    """处理token状态查询"""
    # 从数据库加载最新的token数据
    token_manager.load_tokens()
    
    return JSONResponse(content=token_manager.get_token_status())


@router.post("/refresh-single-token")
async def api_refresh_single_token(request: Request, auth: bool = Depends(check_auth)):
    """处理刷新单个token"""
    data = await parse_json_request(request)
    
    token_id = data.get('tokenId')
    
    if not token_id:
        raise HTTPException(status_code=400, detail="缺少tokenId参数")
    
    # 从数据库加载最新的token数据
    token_manager.load_tokens()
    
    try:
        result = await token_manager.refresh_single_token(token_id)
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(
            content={'success': False, 'error': str(e)},
            status_code=500
        )


@router.post("/delete-token")
async def api_delete_token(request: Request, auth: bool = Depends(check_auth)):
    """处理删除单个token"""
    data = await parse_json_request(request)
    
    token_id = data.get('tokenId')
    
    if not token_id:
        raise HTTPException(status_code=400, detail="缺少tokenId参数")
    
    # 从数据库加载最新的token数据
    token_manager.load_tokens()
    
    token = token_manager.token_store.get(token_id)
    if not token:
        raise HTTPException(status_code=404, detail="Token不存在")
    
    # 删除token
    token_manager.delete_token(token_id)
    
    return JSONResponse(content={
        'success': True,
        'tokenId': token_id,
        'message': 'Token删除成功'
    })


@router.post("/delete-all-tokens")
async def api_delete_all_tokens(auth: bool = Depends(check_auth)):
    """处理删除所有token"""
    deleted_count = len(token_manager.token_store)
    token_manager.delete_all_tokens()
    
    return JSONResponse(content={
        'success': True,
        'deletedCount': deleted_count,
        'message': f'成功删除 {deleted_count} 个Token'
    })


@router.post("/refresh-token")
async def api_refresh_token(auth: bool = Depends(check_auth)):
    """处理token刷新（强制刷新所有token）"""
    # 从数据库加载最新的token数据
    token_manager.load_tokens()
    
    try:
        result = await token_manager.refresh_all_tokens()
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(
            content={'success': False, 'error': str(e)},
            status_code=500
        )


@router.post("/oauth-init")
async def api_oauth_init(auth: bool = Depends(check_auth)):
    """处理OAuth设备授权初始化"""
    return JSONResponse(content=await oauth_manager.init_oauth())


@router.post("/oauth-poll")
async def api_oauth_poll(request: Request, auth: bool = Depends(check_auth)):
    """处理OAuth轮询状态"""
    data = await parse_json_request(request)
    
    state_id = data.get('stateId')
    
    if not state_id:
        raise HTTPException(status_code=400, detail="缺少stateId参数")
    
    result = await oauth_manager.poll_oauth_status(state_id)
    
    if result.get('success') and result.get('tokenData'):
        # 存储token
        token_data = result['tokenData']
        token_id = get_token_id(token_data.refresh_token)
        token_manager.save_token(token_id, token_data)
        
        return JSONResponse(content={
            'success': True,
            'tokenId': token_id,
            'message': '认证成功'
        })
    
    return JSONResponse(content=result)


@router.post("/oauth-cancel")
async def api_oauth_cancel(request: Request, auth: bool = Depends(check_auth)):
    """取消OAuth认证"""
    data = await parse_json_request(request)
    
    state_id = data.get('stateId')
    
    result = oauth_manager.cancel_oauth(state_id)
    return JSONResponse(content=result)


@router.post("/chat")
async def api_chat(request: Request, auth: bool = Depends(check_auth)):
    """处理聊天API请求"""
    data = await parse_json_request(request)
    
    return await handle_chat(data)


@router.get("/statistics/usage")
async def get_usage_statistics(request: Request, auth: bool = Depends(check_auth)):
    """获取指定日期的token使用量"""
    date_param = request.query_params.get('date')
    if date_param is None:
        date_param = get_local_today_iso()
    
    stats = db.get_usage_stats(date_param)
    return JSONResponse(content=stats)


@router.delete("/statistics/usage")
async def delete_usage_statistics(request: Request, auth: bool = Depends(check_auth)):
    """删除指定日期的token使用量"""
    data = await parse_json_request(request)
    
    date_param = data.get('date')
    if not date_param:
        raise HTTPException(status_code=400, detail="缺少date参数")
    
    deleted_count = db.delete_usage_stats(date_param)
    
    return JSONResponse(content={
        'success': True,
        'deletedCount': deleted_count,
        'date': date_param,
        'message': f'成功删除 {date_param} 的 {deleted_count} 条用量记录'
    })


async def handle_chat(data: Dict[str, Any]):
    """处理聊天API请求，并手动计算token"""
    messages = data.get('messages')
    model = data.get('model', 'qwen3-coder-plus')
    stream = data.get('stream', False)
    temperature = data.get('temperature', 0.5)
    top_p = data.get('top_p', 1)
    
    if not messages or not isinstance(messages, list) or len(messages) == 0:
        raise HTTPException(status_code=400, detail="缺少消息内容")

    # --- Token Manual Calculation ---
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        # Fallback for environments where downloading might fail
        encoding = tiktoken.encoding_for_model("gpt-4")

    prompt_tokens = 0
    for message in messages:
        prompt_tokens += len(encoding.encode(message.get('content', '')))
    # --- End Token Calculation ---

    token_manager.load_tokens()
    valid_token_result = await token_manager.get_valid_token()
    if not valid_token_result:
        raise HTTPException(status_code=400, detail="没有可用的token")
    
    token_id, current_token = valid_token_result
    
    session = aiohttp.ClientSession()
    headers = {
        'Authorization': f'Bearer {current_token.access_token}',
        'Content-Type': 'application/json'
    }

    if stream:
        headers['Accept'] = 'text/event-stream'

    request_body = {
        'model': model,
        'messages': messages,
        'temperature': temperature,
        'top_p': top_p,
        'stream': stream
    }

    response = await session.post(
        QWEN_API_ENDPOINT,
        json=request_body,
        headers=headers
    )

    if response.status != 200:
        error_text = await response.text()
        await session.close()
        raise HTTPException(status_code=500, detail=f'API调用失败: {response.status} {error_text}')

    if stream:
        async def generator():
            completion_text = ""
            buffer = ""
            try:
                async for chunk in response.content.iter_any():
                    yield chunk
                    buffer += chunk.decode('utf-8')
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        if line.startswith('data:'):
                            line_data = line[len('data:'):].strip()
                            if line_data == '[DONE]':
                                continue
                            try:
                                json_data = json.loads(line_data)
                                if json_data['choices'][0]['delta'] and 'content' in json_data['choices'][0]['delta']:
                                    completion_text += json_data['choices'][0]['delta']['content']
                            except (json.JSONDecodeError, KeyError, IndexError):
                                pass
            finally:
                completion_tokens = len(encoding.encode(completion_text))
                total_tokens = prompt_tokens + completion_tokens
                today = get_local_today_iso()
                db.update_token_usage(today, model, total_tokens)
                db.increment_token_usage_count(token_id) # Increment usage count for the token
                await session.close()
        return StreamingResponse(generator(), media_type="text/event-stream")
    else:
        response_json = await response.json()
        await session.close()
        if 'usage' in response_json and 'total_tokens' in response_json['usage']:
            today = get_local_today_iso()
            tokens_used = response_json['usage']['total_tokens']
            db.update_token_usage(today, model, tokens_used)
            db.increment_token_usage_count(token_id) # Increment usage count for the token
        return JSONResponse(content=response_json)

