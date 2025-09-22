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
from ..config import API_PASSWORD, API_ENDPOINT

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

async def cleanup_session():
    """清理全局 aiohttp ClientSession 资源"""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None

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
    # 获取原始请求体以支持多媒体JSON等复杂数据
    try:
        raw_body = await request.body()
    except Exception as e:
        logger.exception("读取请求体失败")
        raise HTTPException(status_code=400, detail="Failed to read request body")

    return await handle_chat(await parse_json(request), request, raw_body)

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


async def handle_chat(data: Dict[str, Any], request: Request = None, raw_body: bytes = None):
    """
    处理聊天请求，支持透传headers和参数，保留User-Agent和计数逻辑
    """
    messages = data.get('messages', [])
    model = data.get('model', 'qwen3-coder')
    stream = data.get('stream', False)

    # 重试逻辑
    max_retries = 3
    for attempt in range(max_retries):
        result = await _handle_chat_with_retry(data, request, raw_body, model, stream, attempt)
        if result is not None:
            return result
        # 如果是最后一次尝试，直接返回错误
        if attempt == max_retries - 1:
            raise HTTPException(status_code=500, detail="All retry attempts failed")

    raise HTTPException(status_code=500, detail="All retry attempts failed")


async def _handle_chat_with_retry(data: Dict[str, Any], request: Request, raw_body: bytes, model: str, stream: bool, attempt: int):
    """
    处理聊天请求并支持重试逻辑
    """
    messages = data.get('messages', [])

    # 详细调试日志 - 入参
    logger.debug("=== 聊天请求入参调试 ===")
    logger.debug("原始请求数据: %s", json.dumps(data, ensure_ascii=False, indent=2))
    if request:
        logger.debug("请求headers: %s", dict(request.headers))
        logger.debug("请求URL: %s", str(request.url))
        logger.debug("请求方法: %s", request.method)
    logger.debug("解析后参数 - 模型: %s，消息数: %s，流式: %s", model, len(messages), stream)
    logger.debug("重试尝试次数: %s", attempt)

    if not messages or not isinstance(messages, list):
        logger.warning("聊天请求缺少消息体或格式错误")
        raise HTTPException(400, "messages 字段不能为空，且必须为数组")

    # 获取有效的token
    token_manager.load_tokens()
    valid_token = await token_manager.get_valid_token()
    if not valid_token:
        logger.error("未找到可用 token")
        raise HTTPException(400, "没有可用的 token，请先上传或刷新 token")

    token_id, current_token = valid_token

    # 标记token为正在使用中
    token_manager.mark_token_in_use(token_id)

    try:
        # 构建透传的headers
        passthrough_headers = {}
        if request:
            # 如果有request对象，透传所有headers除了Authorization和Host
            # Host header需要被移除，以避免上游服务器路由错误
            for key, value in request.headers.items():
                if key.lower() not in ['authorization', 'host']:
                    passthrough_headers[key] = value

        # 使用我们的token替换Authorization
        auth_token = current_token.api_key if current_token.api_key else current_token.access_token
        passthrough_headers['Authorization'] = f'Bearer {auth_token}'

        # 添加User-Agent（保留原有逻辑，但如果原始请求已有则不覆盖）
        if 'User-Agent' not in passthrough_headers and 'user-agent' not in passthrough_headers:
            try:
                from ..utils.version_manager import get_version_manager
                version_manager = get_version_manager()
                if version_manager:
                    passthrough_headers['User-Agent'] = await version_manager.get_user_agent_async()
            except Exception as e:
                logger.warning("获取User-Agent失败: %s", e)
                passthrough_headers['User-Agent'] = 'iFlow-Cli-API-Server'

        # 确保Content-Type正确设置（如果原始请求体存在）
        if raw_body is not None and 'content-type' not in passthrough_headers and 'Content-Type' not in passthrough_headers:
            passthrough_headers['Content-Type'] = request.headers.get('content-type', 'application/json')

        # 确保Accept正确设置（如果原始请求没有设置）
        if 'accept' not in passthrough_headers and 'Accept' not in passthrough_headers:
            passthrough_headers['Accept'] = 'text/event-stream' if stream else 'application/json'

        # 详细调试日志 - 透传参数
        logger.debug("=== 透传参数调试 ===")
        logger.debug("透传headers: %s", json.dumps(passthrough_headers, ensure_ascii=False, indent=2))
        logger.debug("透传数据: %s", json.dumps(data, ensure_ascii=False, indent=2))
        logger.debug("目标API端点: %s", API_ENDPOINT)
        logger.debug("透传聊天请求，模型: %s，流式: %s，headers数量: %s",
                    model, stream, len(passthrough_headers))

        # 发起透传请求
        session = await get_session()

        try:
            logger.debug("=== 发起上游API请求 ===")
            # 使用原始请求体进行透传，支持多媒体JSON等复杂数据
            async with session.post(
                API_ENDPOINT,
                data=raw_body if raw_body is not None else json.dumps(data),
                headers=passthrough_headers,
                timeout=aiohttp.ClientTimeout(total=90)
            ) as response:

                # 详细调试日志 - 上游API响应
                logger.debug("=== 上游API响应调试 ===")
                logger.debug("响应状态码: %s", response.status)
                logger.debug("响应headers: %s", dict(response.headers))

                # 处理特定的错误码
                if response.status == 401:
                    logger.warning("上游API返回401状态码，标记当前token为过期并尝试刷新")
                    # 标记当前token为过期（设置过期时间为当前时间）
                    current_token.expires_at = int(time.time() * 1000)
                    token_manager.save_token(token_id, current_token)

                    # 尝试刷新token
                    try:
                        await token_manager.refresh_single_token(token_id)
                        logger.info("Token刷新成功，ID: %s", token_id)
                        # 重新获取有效的token
                        token_manager.load_tokens()
                        new_valid_token = await token_manager.get_valid_token()
                        if new_valid_token and new_valid_token[0] != token_id:
                            # 使用新的token重试请求
                            logger.info("使用新的token重试请求，新token ID: %s", new_valid_token[0])
                            return None  # 返回None表示需要重试
                        else:
                            # 如果没有其他token，继续使用当前token重试
                            logger.warning("没有其他可用token，继续使用当前token重试")
                            return None  # 返回None表示需要重试
                    except Exception as refresh_error:
                        logger.error("刷新token失败: %s", str(refresh_error))
                        # 尝试使用其他token
                        token_manager.load_tokens()
                        other_token = await token_manager.get_valid_token()
                        if other_token and other_token[0] != token_id:
                            logger.info("使用其他token重试请求，新token ID: %s", other_token[0])
                            return None  # 返回None表示需要重试
                        else:
                            # 没有其他token，直接返回错误
                            error_text = await response.text()
                            logger.error("上游API错误响应内容: %s", error_text)
                            raise HTTPException(status_code=401, detail=f"Upstream API error: {error_text}")

                elif response.status == 429:
                    logger.warning("上游API返回429状态码，临时禁用token并尝试使用其他token重试")
                    # 临时禁用当前token 10秒钟
                    token_manager.disable_token_temporarily(token_id, 10)

                    # 尝试使用其他token
                    token_manager.load_tokens()
                    other_token = await token_manager.get_valid_token()
                    if other_token and other_token[0] != token_id:
                        logger.info("使用其他token重试请求，新token ID: %s", other_token[0])
                        return None  # 返回None表示需要重试
                    else:
                        # 没有其他token，直接返回错误
                        error_text = await response.text()
                        logger.error("上游API错误响应内容: %s", error_text)
                        raise HTTPException(status_code=429, detail=f"Upstream API error: {error_text}")

                elif response.status != 200:
                    logger.error("上游API返回非200状态码: %s", response.status)
                    error_text = await response.text()
                    logger.error("上游API错误响应内容: %s", error_text)
                    raise HTTPException(status_code=response.status, detail=f"Upstream API error: {error_text}")

                if stream:
                    # 流式响应透传
                    logger.debug("=== 开始透传流式响应 ===")

                    # 透传上游响应的headers
                    response_headers = {}
                    for key, value in response.headers.items():
                        # 跳过可能冲突的headers
                        if key.lower() not in ['content-encoding', 'content-length', 'transfer-encoding', 'connection']:
                            response_headers[key] = value

                    async def generate_stream():
                        try:
                            async for chunk in response.content.iter_any():
                                yield chunk
                        except Exception as e:
                            logger.warning("流式响应传输过程中出现异常: %s", str(e))
                            # 可以选择在这里 yield 一个错误消息给客户端
                            yield f"data: {{\"error\": \"Stream transmission error: {str(e)}\"}}\n\n"

                    return StreamingResponse(
                        generate_stream(),
                        media_type=response.headers.get('content-type', 'text/event-stream'),
                        headers=response_headers
                    )
                else:
                    # 非流式响应透传
                    try:
                        result = await response.json()
                        logger.debug("=== 上游API响应内容 ===")
                        logger.debug("响应数据: %s", json.dumps(result, ensure_ascii=False, indent=2))

                        # 更新使用统计（保留原有计数逻辑）
                        if 'usage' in result:
                            usage_tokens = result.get('usage', {}).get('total_tokens', 0)
                            logger.debug("更新使用统计 - 模型: %s, tokens: %s", model, usage_tokens)
                            db.update_token_usage(get_local_today_iso(), model, usage_tokens)
                            token_manager.increment_token_usage_count(token_id)

                        logger.debug("=== 返回最终响应 ===")
                        return JSONResponse(content=result)
                    except Exception as e:
                        # 如果无法解析为JSON，直接返回文本内容
                        logger.warning("无法解析上游API响应为JSON，将返回原始文本内容: %s", str(e))
                        text_content = await response.text()
                        return JSONResponse(content={"text": text_content})

        except aiohttp.ClientError as e:
            logger.error("透传请求失败: %s", str(e))
            raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")
        except Exception as e:
            logger.exception("透传过程中发生异常")
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
        finally:
            # 标记token为使用完成
            token_manager.mark_token_finished(token_id)
    except Exception as e:
        # 确保即使在异常情况下也标记token为使用完成
        token_manager.mark_token_finished(token_id)
        raise e