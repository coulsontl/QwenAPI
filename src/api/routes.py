"""
API endpoints for Qwen Code API Server
"""
import json
import time
import aiohttp
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, Response

from ..auth import check_auth
from ..oauth import OAuthManager, TokenManager
from ..database import TokenDatabase
from ..models import TokenData
from ..utils import get_token_id
from ..config import API_PASSWORD, QWEN_API_ENDPOINT


router = APIRouter()

# Initialize managers
db = TokenDatabase()
oauth_manager = OAuthManager()
token_manager = TokenManager(db)


@router.post("/login")
async def api_login(request: Request):
    """处理登录请求"""
    try:
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="请求格式错误")
    
    password = data.get('password')
    
    if password == API_PASSWORD:
        return JSONResponse(content={'success': True})
    else:
        raise HTTPException(status_code=401, detail="密码错误")


@router.post("/upload-token")
async def api_upload_token(request: Request, auth: bool = Depends(check_auth)):
    """处理token上传"""
    try:
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="请求格式错误")
    
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
    try:
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="请求格式错误")
    
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
    try:
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="请求格式错误")
    
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
    try:
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="请求格式错误")
    
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
    try:
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="请求格式错误")
    
    state_id = data.get('stateId')
    
    result = oauth_manager.cancel_oauth(state_id)
    return JSONResponse(content=result)


@router.post("/chat")
async def api_chat(request: Request, auth: bool = Depends(check_auth)):
    """处理聊天API请求"""
    try:
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="请求格式错误")
    
    return await handle_chat(data)


async def handle_chat(data: Dict[str, Any]):
    """处理聊天API请求"""
    messages = data.get('messages')
    model = data.get('model', 'qwen3-coder-plus')
    stream = data.get('stream', False)
    
    # 验证messages数组格式
    if not messages or not isinstance(messages, list) or len(messages) == 0:
        raise HTTPException(status_code=400, detail="缺少消息内容")
    
    # 获取有效token
    token_manager.load_tokens()
    valid_token_result = await token_manager.get_valid_token()
    if not valid_token_result:
        raise HTTPException(status_code=400, detail="没有可用的token")
    
    token_id, current_token = valid_token_result
    
    # 异步处理API调用
    async with aiohttp.ClientSession() as session:
        headers = {
            'Authorization': f'Bearer {current_token.access_token}',
            'Content-Type': 'application/json'
        }
        
        if stream:
            headers['Accept'] = 'text/event-stream'
        
        request_body = {
            'model': model,
            'messages': messages,
            'temperature': 0,
            'top_p': 1,
            'stream': stream
        }
        
        async with session.post(
            QWEN_API_ENDPOINT,
            json=request_body,
            headers=headers
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise HTTPException(status_code=500, detail=f'API调用失败: {response.status} {error_text}')
            
            if stream:
                # 流式响应
                content = await response.read()
                return Response(content=content, media_type="text/event-stream")
            else:
                # 非流式响应
                text = await response.text()
                return JSONResponse(content=json.loads(text))