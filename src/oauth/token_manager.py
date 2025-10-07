"""
Token management for iFlow-Cli API Server
"""
import time
import random
import aiohttp
import logging
import os
import threading
from typing import Dict, Optional, Tuple, List, Any
from ..models import TokenData
from ..database import TokenDatabase
from ..utils import get_token_id
from ..utils.timezone_utils import timestamp_to_local_datetime, format_local_datetime
from ..config import OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET, OAUTH2_TOKEN_ENDPOINT, USER_INFO_ENDPOINT, get_oauth2_authorization_header

logger = logging.getLogger(__name__)


class TokenManager:

    def __init__(self, db: TokenDatabase):
        self.db = db
        self.token_store: Dict[str, TokenData] = {}
        self._version_manager = None

        # 添加用于跟踪正在使用的 token 的属性
        self._in_use_tokens: Dict[str, float] = {}  # token_id -> start_time
        self._in_use_lock = threading.Lock()

        # 添加用于跟踪被禁用的 token 的属性（429错误）
        self._disabled_tokens: Dict[str, float] = {}  # token_id -> disable_until_timestamp
        self._disabled_lock = threading.Lock()

    def set_version_manager(self, version_manager):
        self._version_manager = version_manager

    def load_tokens(self) -> None:
        self.token_store = self.db.load_all_tokens()
        logger.debug("Token 数据已加载，数量: %s", len(self.token_store))

    def save_token(self, token_id: str, token_data: TokenData) -> None:
        self.token_store[token_id] = token_data
        self.db.save_token(token_id, token_data)
        logger.info("已保存/更新 token，ID: %s", token_id)

    def delete_token(self, token_id: str) -> None:
        # 在删除前获取用户信息用于日志记录
        token_data = self.token_store.get(token_id)
        user_name = "未知用户"
        if token_data and token_data.user_info:
            user_name = token_data.user_info.get('userName', '未知用户')
        
        self.token_store.pop(token_id, None)
        self.db.delete_token(token_id)
        logger.info("已删除 token，ID: %s，用户: %s", token_id, user_name)

    def delete_all_tokens(self) -> None:
        self.token_store.clear()
        self.db.delete_all_tokens()
        logger.warning("已清空所有 token 数据")

    def increment_token_usage_count(self, token_id: str) -> None:
        """增加token使用次数，同时更新数据库和内存缓存"""
        # 更新数据库
        self.db.increment_token_usage_count(token_id)

        # 更新内存缓存
        if token_id in self.token_store:
            self.token_store[token_id].usage_count += 1
            logger.debug("已更新内存中 token 使用次数，ID: %s，新次数: %s", token_id, self.token_store[token_id].usage_count)
        else:
            logger.warning("内存中未找到 token，ID: %s", token_id)

    def get_token_status(self) -> Dict[str, Any]:
        token_list = []
        for token_id, token in self.token_store.items():
            is_expired = token.expires_at and (time.time() * 1000) > token.expires_at

            expires_at_str = format_local_datetime(timestamp_to_local_datetime(token.expires_at)) if token.expires_at else "未知"
            uploaded_at_str = format_local_datetime(timestamp_to_local_datetime(token.uploaded_at)) if token.uploaded_at else "未知"

            token_data = {
                'id': token_id,
                'expiresAt': token.expires_at,
                'expiresAtDisplay': expires_at_str,
                'isExpired': is_expired,
                'uploadedAt': token.uploaded_at,
                'uploadedAtDisplay': uploaded_at_str,
                'usageCount': token.usage_count,
                'userInfo': token.user_info,
                'apiKey': token.api_key
            }

            if is_expired:
                token_data['refreshFailed'] = True

            token_list.append(token_data)

        return {
            'hasToken': len(self.token_store) > 0,
            'tokenCount': len(self.token_store),
            'tokens': token_list
        }

    async def refresh_single_token(self, token_id: str) -> Dict[str, Any]:
        token = self.token_store.get(token_id)
        if not token:
            raise Exception("Token不存在")

        # 强制刷新单个token
        refreshed_token, should_remove, error_message = await self._force_refresh_token(token_id, token)

        if refreshed_token:
            logger.info("单个 token 刷新成功，ID: %s", token_id)
            return {
                'success': True,
                'tokenId': token_id,
                'message': 'Token刷新成功'
            }
        else:
            # 刷新失败，移除token
            if should_remove:
                self.delete_token(token_id)
                logger.error("单个 token 刷新失败，已移除，ID: %s", token_id)
                raise Exception("Token刷新失败，已删除")
            logger.warning("单个 token 刷新失败，准备稍后重试，ID: %s", token_id)
            raise Exception(error_message or "Token刷新失败，请稍后重试")

    async def _force_refresh_token(self, token_id: str, token: TokenData) -> Tuple[Optional[TokenData], bool, Optional[str]]:
        """刷新 token，返回 (刷新后的 token, 是否应删除, 错误信息)"""
        try:
            headers = {
                'User-Agent': 'node',
                'Accept-Encoding': 'br, gzip, deflate',
                'Content-Type': 'application/x-www-form-urlencoded',
                'accept-language': '*',
                'sec-fetch-mode': 'cors'
            }

            # 生成并添加 Basic Authorization header
            auth_header = get_oauth2_authorization_header()
            if auth_header:
                headers['Authorization'] = auth_header

            if self._version_manager:
                try:
                    headers['User-Agent'] = await self._version_manager.get_user_agent_async()
                except Exception:
                    headers['User-Agent'] = self._version_manager.get_user_agent()

            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('grant_type', 'refresh_token')
                data.add_field('refresh_token', token.refresh_token)
                data.add_field('client_id', OAUTH2_CLIENT_ID)

                # 只有当 OAUTH2_CLIENT_SECRET 存在时才添加
                if OAUTH2_CLIENT_SECRET:
                    data.add_field('client_secret', OAUTH2_CLIENT_SECRET)

                async with session.post(
                    OAUTH2_TOKEN_ENDPOINT,
                    data=data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    try:
                        result = await response.json()
                    except Exception as json_error:
                        logger.error("解析刷新 token 响应失败，ID: %s，错误: %s", token_id, json_error)
                        return None, False, f"解析响应失败: {json_error}"

                    # 检查响应中的 success 字段
                    if not result.get('success', True):
                        error_code = str(result.get('code', '200'))
                        error_message = result.get('message', '未知错误')
                        logger.warning("刷新 token 返回错误，ID: %s，错误码: %s，消息: %s", token_id, error_code, error_message)

                        # 根据错误码判断是否应该删除token
                        should_remove = error_code in {'400', '401', '403', '500'}
                        return None, should_remove, f"{error_code}: {error_message}"

                    # 检查是否有 error 字段（兼容旧的错误格式）
                    if 'error' in result:
                        error_code = str(result.get('error'))
                        logger.warning("刷新 token 返回错误，ID: %s，错误: %s", token_id, error_code)
                        should_remove = error_code in {'invalid_grant', 'invalid_client', 'unauthorized_client'}
                        description = result.get('error_description') or result.get('message')
                        error_message = f"{error_code}: {description}" if description else error_code
                        return None, should_remove, error_message

                    updated_token = TokenData(
                        access_token=result['access_token'],
                        refresh_token=result.get('refresh_token', token.refresh_token),
                        expires_at=int(time.time() * 1000) + result.get('expires_in', 3600) * 1000,
                        uploaded_at=token.uploaded_at,
                        usage_count=token.usage_count,
                        user_info=token.user_info,  # 保持原有用户信息
                        api_key=token.api_key  # 保持原有API密钥
                    )

                    # 获取用户信息
                    user_info = await self._get_user_info(result['access_token'])
                    if user_info:
                        updated_token.user_info = user_info
                        updated_token.api_key = user_info.get('apiKey')
                        logger.debug("刷新 token 时成功获取用户信息，用户ID: %s", user_info.get('userId'))

                    self.save_token(token_id, updated_token)

                    return updated_token, False, None
        except Exception as error:
            logger.exception("刷新 token 过程中出现异常，ID: %s", token_id)
            return None, False, str(error)

    async def refresh_all_tokens(self) -> Dict[str, Any]:
        if not self.token_store:
            raise Exception("没有可用的token")

        refresh_results = []
        tokens_to_remove = []
        current_time_ms = time.time() * 1000
        # 从环境变量读取刷新时间阈值，默认为2小时（毫秒）
        refresh_threshold_ms = int(os.getenv('TOKEN_REFRESH_THRESHOLD_SECONDS', '7200')) * 1000

        for token_id, token in self.token_store.items():
            # 检查是否需要刷新：如果距离过期时间大于阈值，则跳过刷新
            if token.expires_at and (token.expires_at - current_time_ms) > refresh_threshold_ms:
                remaining_hours = (token.expires_at - current_time_ms) / (60 * 60 * 1000)
                refresh_results.append({
                    'id': token_id,
                    'success': True,
                    'skipped': True,
                    'reason': f'距离过期还有{remaining_hours:.1f}小时，跳过刷新'
                })
                logger.debug("Token距离过期还有%.1f小时，跳过刷新，ID: %s", remaining_hours, token_id)
                continue

            refreshed_token, should_remove, error_message = await self._force_refresh_token(token_id, token)

            if refreshed_token:
                refresh_results.append({'id': token_id, 'success': True})
            else:
                refresh_results.append({
                    'id': token_id,
                    'success': False,
                    'error': error_message or 'Token刷新失败'
                })
                if should_remove:
                    tokens_to_remove.append(token_id)

        for token_id in tokens_to_remove:
            self.delete_token(token_id)
            logger.error("批量刷新失败，已移除 token，ID: %s", token_id)

        return {
            'success': True,
            'refreshResults': refresh_results,
            'remainingTokens': len(self.token_store),
            'isForcedRefresh': True
        }

    async def get_valid_token(self) -> Optional[Tuple[str, TokenData]]:
        """
        获取一个有效的 token，考虑以下因素：
        1. Token 不能过期
        2. Token 不能正在被使用（除非没有其他选择）
        3. Token 不能被禁用（429错误后10秒内）
        """
        if not self.token_store:
            return None

        # 清理过期的禁用记录
        self._cleanup_disabled_tokens()

        valid_tokens = []
        usable_tokens = []  # 不在使用中的可用token
        token_entries = list(self.token_store.items())

        # 随机打乱顺序以避免总是选择相同的token
        random.shuffle(token_entries)

        current_time = time.time()

        for token_id, token in token_entries:
            # 检查是否过期
            is_expired = token.expires_at and (current_time * 1000) > token.expires_at

            if is_expired:
                # 尝试刷新过期的token
                refreshed_token, should_remove, _ = await self._force_refresh_token(token_id, token)
                if refreshed_token:
                    token = refreshed_token
                    is_expired = False
                elif should_remove:
                    self.delete_token(token_id)
                    logger.warning("在获取可用 token 时检测到无效 token，已删除，ID: %s", token_id)
                    continue

            # 如果token未过期，添加到有效tokens列表
            if not is_expired:
                valid_tokens.append((token_id, token))

                # 检查token是否正在使用中
                with self._in_use_lock:
                    is_in_use = token_id in self._in_use_tokens

                # 检查token是否被禁用（429错误）
                with self._disabled_lock:
                    is_disabled = token_id in self._disabled_tokens and current_time < self._disabled_tokens[token_id]

                # 如果token既不在使用中也没有被禁用，则添加到可用tokens列表
                if not is_in_use and not is_disabled:
                    usable_tokens.append((token_id, token))

        # 优先选择不在使用中的可用token
        if usable_tokens:
            logger.debug("找到可用且未在使用的 token，数量: %s", len(usable_tokens))
            return random.choice(usable_tokens)

        # 如果没有可用的token，但在有效tokens中有token，则随机选择一个
        # 这种情况可能发生在所有token都在使用中的情况下
        if valid_tokens:
            logger.debug("没有可用的未使用 token，但从有效 tokens 中选择，数量: %s", len(valid_tokens))
            return random.choice(valid_tokens)

        return None

    def mark_token_in_use(self, token_id: str) -> None:
        """标记token为正在使用中"""
        with self._in_use_lock:
            self._in_use_tokens[token_id] = time.time()
        logger.debug("标记 token 为正在使用，ID: %s", token_id)

    def mark_token_finished(self, token_id: str) -> None:
        """标记token为使用完成"""
        with self._in_use_lock:
            if token_id in self._in_use_tokens:
                del self._in_use_tokens[token_id]
        logger.debug("标记 token 为使用完成，ID: %s", token_id)

    def disable_token_temporarily(self, token_id: str, duration_seconds: int = 10) -> None:
        """临时禁用token一段时间（默认10秒），用于处理429错误"""
        disable_until = time.time() + duration_seconds
        with self._disabled_lock:
            self._disabled_tokens[token_id] = disable_until
        logger.warning("临时禁用 token %d 秒，ID: %s", duration_seconds, token_id)

    def _cleanup_disabled_tokens(self) -> None:
        """清理过期的禁用记录"""
        current_time = time.time()
        with self._disabled_lock:
            expired_tokens = [
                token_id for token_id, disable_until in self._disabled_tokens.items()
                if current_time >= disable_until
            ]
            for token_id in expired_tokens:
                del self._disabled_tokens[token_id]
        if expired_tokens:
            logger.debug("清理了 %d 个过期的禁用 token 记录", len(expired_tokens))

    async def _get_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """获取用户信息"""
        try:
            headers = {
                'User-Agent': 'node',
                'Accept-Encoding': 'br, gzip, deflate',
                'accept-language': '*',
                'sec-fetch-mode': 'cors'
            }

            if self._version_manager:
                try:
                    headers['User-Agent'] = await self._version_manager.get_user_agent_async()
                except Exception:
                    headers['User-Agent'] = self._version_manager.get_user_agent()

            async with aiohttp.ClientSession() as session:
                url = f"{USER_INFO_ENDPOINT}?accessToken={access_token}"
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    try:
                        result = await response.json()
                    except Exception as json_error:
                        logger.error("解析用户信息响应失败，错误: %s", json_error)
                        return None

                    # 检查响应中的 success 字段
                    if not result.get('success', True):
                        error_code = str(result.get('code', 'unknown'))
                        error_message = result.get('message', '未知错误')
                        logger.warning("获取用户信息失败，错误码: %s，消息: %s", error_code, error_message)
                        return None

                    user_data = result.get('data')
                    if user_data:
                        logger.debug("成功获取用户信息，用户ID: %s", user_data.get('userId'))
                        return user_data
                    else:
                        logger.warning("用户信息响应中没有 data 字段")
                        return None

        except Exception as error:
            logger.exception("获取用户信息过程中出现异常: %s", error)
            return None