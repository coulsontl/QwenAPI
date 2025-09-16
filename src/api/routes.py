import json
import time
import asyncio
import logging
import aiohttp
import tiktoken
import uuid
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from ..auth import check_auth
from ..oauth import OAuthManager, TokenManager
from ..database import TokenDatabase
from ..models import TokenData
from ..utils import get_token_id
from ..utils.timezone_utils import get_local_today_iso
from ..utils.tool_registry import get_tool_registry
from ..utils.tool_executor import ToolCallExecutor
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
        timeout = aiohttp.ClientTimeout(total=90, connect=10, sock_read=75)
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
_tool_executor = None

def set_version_manager(version_manager):
    global _version_manager
    _version_manager = version_manager
    token_manager.set_version_manager(version_manager)
    oauth_manager.set_version_manager(version_manager)

def get_tool_executor():
    global _tool_executor
    if _tool_executor is None:
        _tool_executor = ToolCallExecutor(get_tool_registry())
    return _tool_executor

async def parse_json(request: Request) -> Dict[str, Any]:
    try:
        body = await request.json()
        return body
    except json.JSONDecodeError:
        logger.warning("请求体解析失败，非 JSON 格式，路径: %s", request.url.path)
        raise HTTPException(400, "请求体不是合法的 JSON 格式")
    except Exception:
        logger.exception("解析请求体时出现异常，路径: %s", request.url.path)
        raise HTTPException(400, "解析请求体失败，请检查参数")

@router.post("/login")
async def api_login(request: Request):
    data = await parse_json(request)
    if data.get('password') == API_PASSWORD:
        logger.debug("API 登录验证成功")
        return JSONResponse({'success': True})
    logger.warning("API 登录失败，密码不匹配")
    raise HTTPException(401, "认证失败，密码无效")

@router.post("/upload-token")
async def api_upload_token(request: Request, auth: bool = Depends(check_auth)):
    data = await parse_json(request)
    access_token = data.get('access_token')
    refresh_token = data.get('refresh_token')
    
    if not access_token or not refresh_token:
        logger.warning("上传 token 时缺少必要字段")
        raise HTTPException(400, "缺少 access_token 或 refresh_token")
    
    token_id = get_token_id(refresh_token)
    token_data = TokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=data.get('expiry_date'),
        uploaded_at=int(time.time() * 1000)
    )
    
    token_manager.save_token(token_id, token_data)
    logger.info("新 token 上传成功，ID: %s", token_id)
    return JSONResponse({'success': True, 'tokenId': token_id})

@router.get("/token-status")
async def api_token_status(auth: bool = Depends(check_auth)):
    token_manager.load_tokens()
    logger.debug("查询 token 状态")
    return JSONResponse(token_manager.get_token_status())

@router.post("/refresh-single-token")
async def api_refresh_single_token(request: Request, auth: bool = Depends(check_auth)):
    data = await parse_json(request)
    token_id = data.get('tokenId')
    
    if not token_id:
        logger.warning("刷新单个 token 缺少 tokenId")
        raise HTTPException(400, "缺少 tokenId")
    
    token_manager.load_tokens()
    try:
        result = await token_manager.refresh_single_token(token_id)
        logger.info("手动刷新 token 成功，ID: %s", token_id)
        return JSONResponse(result)
    except Exception as e:
        logger.exception("手动刷新 token 失败，ID: %s", token_id)
        return JSONResponse({'success': False, 'error': str(e)}, 500)

@router.post("/delete-token")
async def api_delete_token(request: Request, auth: bool = Depends(check_auth)):
    data = await parse_json(request)
    token_id = data.get('tokenId')
    
    if not token_id:
        logger.warning("删除 token 缺少 tokenId")
        raise HTTPException(400, "缺少 tokenId")
    
    token_manager.load_tokens()
    if token_id not in token_manager.token_store:
        logger.warning("删除 token 时未找到记录，ID: %s", token_id)
        raise HTTPException(404, "指定 token 不存在")
    
    token_manager.delete_token(token_id)
    logger.info("已删除 token，ID: %s", token_id)
    return JSONResponse({'success': True, 'tokenId': token_id})

@router.post("/delete-all-tokens")
async def api_delete_all_tokens(auth: bool = Depends(check_auth)):
    deleted_count = len(token_manager.token_store)
    token_manager.delete_all_tokens()
    logger.warning("已通过接口清空所有 token，数量: %s", deleted_count)
    return JSONResponse({'success': True, 'deletedCount': deleted_count})

@router.post("/refresh-token")
async def api_refresh_token(auth: bool = Depends(check_auth)):
    token_manager.load_tokens()
    try:
        result = await token_manager.refresh_all_tokens()
        logger.debug("批量刷新 token 完成，剩余数量: %s", result.get('remainingTokens'))
        return JSONResponse(result)
    except Exception as e:
        logger.exception("批量刷新 token 失败")
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
        logger.exception("OAuth初始化接口错误")
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
        logger.warning("OAuth 轮询缺少 stateId")
        raise HTTPException(400, "缺少 stateId")
    
    result = await oauth_manager.poll_oauth_status(state_id)
    
    if result.get('success') and result.get('tokenData'):
        token_data = result['tokenData']
        token_id = get_token_id(token_data.refresh_token)
        token_manager.save_token(token_id, token_data)
        logger.info("OAuth 授权成功，已保存 token，ID: %s", token_id)
        return JSONResponse({'success': True, 'tokenId': token_id})
    
    logger.debug("OAuth 授权仍在进行，stateId: %s", state_id)
    return JSONResponse(result)

@router.post("/oauth-cancel")
async def api_oauth_cancel(request: Request, auth: bool = Depends(check_auth)):
    data = await parse_json(request)
    state_id = data.get('stateId')
    logger.info("收到取消 OAuth 请求，stateId: %s", state_id)
    return JSONResponse(oauth_manager.cancel_oauth(state_id))

@router.post("/chat")
async def api_chat(request: Request, auth: bool = Depends(check_auth)):
    logger.debug("收到聊天请求，路径: %s", request.url.path)
    return await handle_chat(await parse_json(request))

@router.get("/statistics/usage")
async def get_usage_statistics(request: Request, auth: bool = Depends(check_auth)):
    date = request.query_params.get('date') or get_local_today_iso()
    logger.debug("查询使用统计，日期: %s", date)
    return JSONResponse(db.get_usage_stats(date))

@router.get("/statistics/available-dates")
async def get_available_dates(auth: bool = Depends(check_auth)):
    dates = db.get_available_dates()
    logger.debug("查询使用统计可用日期，总数: %s", len(dates))
    return JSONResponse({"dates": dates})

@router.delete("/statistics/usage")
async def delete_usage_statistics(request: Request, auth: bool = Depends(check_auth)):
    data = await parse_json(request)
    date = data.get('date')
    if not date:
        logger.warning("删除使用统计缺少日期")
        raise HTTPException(400, "缺少 date 参数")
    
    deleted = db.delete_usage_stats(date)
    logger.info("删除使用统计完成，日期: %s，删除条目: %s", date, deleted)
    return JSONResponse({'success': True, 'deletedCount': deleted})

@router.get("/health")
async def health_check():
    try:
        tokens = db.load_all_tokens()
        logger.debug("健康检查访问，当前 token 数量: %s", len(tokens))
        return JSONResponse({
            "status": "ok",
            "timestamp": time.time(),
            "database": {"status": "healthy", "token_count": len(tokens)}
        })
    except Exception as e:
        logger.exception("健康检查失败")
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
        logger.exception("获取指标信息失败")
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
                logger.error("获取版本信息超时")
                return JSONResponse({"version": "获取超时", "timeout": True})
        else:
            logger.warning("版本管理器未初始化")
            return JSONResponse({"version": "未知"})
    except Exception as e:
        logger.exception("版本接口处理失败")
        return JSONResponse({"version": "错误", "error": str(e)})



async def _make_api_request_with_retry(session, url, json_data, headers, max_retries=5):
    last_exception = None
    for attempt in range(max_retries):
        try:
            logger.debug("发起 Qwen API 请求，第 %s 次尝试", attempt + 1)
            response = await session.post(url, json=json_data, headers=headers)
            return response
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            last_exception = e
            if attempt < max_retries - 1:
                logger.warning("Qwen API 请求失败，准备重试，第 %s 次，原因: %s", attempt + 1, e)
                await asyncio.sleep(2 ** attempt)
                continue
            raise last_exception

async def handle_chat(data: Dict[str, Any], max_tool_calls: int = 10):
    messages = data.get('messages', [])
    model = data.get('model', 'qwen3-coder-plus')
    stream = data.get('stream', False)
    tools = data.get('tools', [])
    tool_choice = data.get('tool_choice', 'auto')
    logger.debug(
        "处理聊天请求，模型: %s，消息数: %s，流式: %s，工具数: %s",
        model,
        len(messages),
        stream,
        len(tools)
    )
    
    if not messages or not isinstance(messages, list):
        logger.warning("聊天请求缺少消息体或格式错误")
        raise HTTPException(400, "messages 字段不能为空，且必须为数组")

    try:
        encoding = tiktoken.get_encoding("cl100k_base")
    except:
        encoding = tiktoken.encoding_for_model("gpt-4")

    prompt_tokens = sum(len(encoding.encode(str(msg.get('content', '')))) for msg in messages)
    token_manager.load_tokens()
    
    valid_token = await token_manager.get_valid_token()
    if not valid_token:
        logger.error("未找到可用 token")
        raise HTTPException(400, "没有可用的 token，请先上传或刷新 token")
    
    token_id, current_token = valid_token
    session = await get_session()
    
    headers = {
        'Authorization': f'Bearer {current_token.access_token}',
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream' if stream else 'application/json'
    }
    
    if _version_manager:
        headers['User-Agent'] = await _version_manager.get_user_agent_async()

    # 构建请求体
    body = {
        'model': model,
        'messages': messages,
        'temperature': data.get('temperature', 0.5),
        'top_p': data.get('top_p', 1),
        'stream': stream
    }
    
    # 添加工具调用支持
    if tools:
        body['tools'] = tools
        body['tool_choice'] = tool_choice

    # 处理工具调用对话
    conversation_messages = messages.copy()
    tool_call_count = 0
    result = None
    
    while tool_call_count < max_tool_calls:
        try:
            response = await _make_api_request_with_retry(session, QWEN_API_ENDPOINT, body, headers)
            if response.status != 200:
                logger.error("上游 API 返回非 200 状态码: %s", response.status)
                raise HTTPException(500, f'API error: {response.status}')
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            logger.error(f"API request failed after retries: {str(e)}")
            raise HTTPException(500, f'Request failed: {str(e)}')

        if stream:
            # 流式响应处理
            logger.debug("使用流式响应返回结果")
            return await _handle_stream_response(response, conversation_messages, token_id, model, encoding, prompt_tokens)
        
        result = await response.json()
        
        # 检查是否有工具调用
        has_tool_calls = False
        if 'choices' in result and len(result['choices']) > 0:
            choice = result['choices'][0]
            if 'message' in choice:
                message = choice['message']
                if 'tool_calls' in message and message['tool_calls']:
                    has_tool_calls = True
        
        if has_tool_calls:
            # 处理工具调用
            tool_executor = get_tool_executor()
            choice = result['choices'][0]
            message = choice['message']
            tool_calls = message['tool_calls']
            logger.debug("检测到工具调用，共 %s 个", len(tool_calls))
            
            # 添加助手响应到对话
            conversation_messages.append({
                "role": "assistant",
                "content": message.get("content", ""),
                "tool_calls": tool_calls
            })
            
            # 执行工具调用
            tool_results = await tool_executor.execute_tool_calls(tool_calls)
            logger.debug("工具调用执行完成，返回结果数量: %s", len(tool_results))
            
            # 添加工具结果到对话
            for tool_result in tool_results:
                conversation_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_result.get("tool_call_id", ""),
                    "content": tool_result.get("content", "")
                })
            
            # 更新请求体以继续对话
            body['messages'] = conversation_messages
            tool_call_count += 1
        else:
            # 没有工具调用，返回结果
            if 'usage' in result:
                db.update_token_usage(get_local_today_iso(), model, result['usage'].get('total_tokens', 0))
                db.increment_token_usage_count(token_id)
            logger.debug("聊天请求完成，使用 tokens: %s", result.get('usage', {}).get('total_tokens'))
            
            return JSONResponse(result)
    
    # 达到最大工具调用次数
    if result and 'usage' in result:
        db.update_token_usage(get_local_today_iso(), model, result['usage'].get('total_tokens', 0))
        db.increment_token_usage_count(token_id)
    logger.warning("达到工具调用最大次数 %s，返回最后一次结果", max_tool_calls)
    return JSONResponse(result or {'success': False, 'error': '已达到最大工具调用次数'})


async def _handle_stream_response(response, conversation_messages, token_id, model, encoding, prompt_tokens):
    """处理流式响应"""
    tool_executor = get_tool_executor()
    buffer = ""
    last_content = ""
    completion_text = ""
    tool_calls_detected = False
    logger.debug("开始处理流式响应，tokenId: %s，模型: %s", token_id, model)
    
    async def generate():
        nonlocal buffer, last_content, completion_text, tool_calls_detected
        
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
                            
                            # 检查工具调用
                            if 'tool_calls' in delta:
                                tool_calls_detected = True
                                logger.debug("流式响应检测到工具调用信号")
                            
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
            
        # 更新使用统计
        if completion_text:
            tokens = len(encoding.encode(completion_text))
            db.update_token_usage(get_local_today_iso(), model, prompt_tokens + tokens)
            db.increment_token_usage_count(token_id)
            logger.info("流式响应完成，累计 tokens: %s", prompt_tokens + tokens)
    
    return StreamingResponse(generate(), media_type="text/event-stream")
