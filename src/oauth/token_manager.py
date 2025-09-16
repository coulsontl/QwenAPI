"""
Token management for Qwen Code API Server
"""
import time
import random
import aiohttp
import logging
from typing import Dict, Optional, Tuple, List, Any
from ..models import TokenData
from ..database import TokenDatabase
from ..utils import get_token_id
from ..utils.timezone_utils import timestamp_to_local_datetime, format_local_datetime
from ..config import QWEN_OAUTH_TOKEN_ENDPOINT, QWEN_OAUTH_CLIENT_ID

logger = logging.getLogger(__name__)


class TokenManager:
    
    def __init__(self, db: TokenDatabase):
        self.db = db
        self.token_store: Dict[str, TokenData] = {}
        self._version_manager = None
    
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
        self.token_store.pop(token_id, None)
        self.db.delete_token(token_id)
        logger.info("已删除 token，ID: %s", token_id)
    
    def delete_all_tokens(self) -> None:
        self.token_store.clear()
        self.db.delete_all_tokens()
        logger.warning("已清空所有 token 数据")
    
    def get_token_status(self) -> Dict[str, Any]:
        token_list = []
        for token_id, token in self.token_store.items():
            is_expired = token.expires_at and (time.time() * 1000) > token.expires_at
            
            expires_at_str = format_local_datetime(timestamp_to_local_datetime(token.expires_at)) if token.expires_at else "未知"
            uploaded_at_str = format_local_datetime(timestamp_to_local_datetime(token.uploaded_at)) if token.uploaded_at else "未知"
            
            if is_expired:
                token_list.append({
                    'id': token_id,
                    'expiresAt': token.expires_at,
                    'expiresAtDisplay': expires_at_str,
                    'isExpired': True,
                    'uploadedAt': token.uploaded_at,
                    'uploadedAtDisplay': uploaded_at_str,
                    'usageCount': token.usage_count,
                    'refreshFailed': True
                })
            else:
                token_list.append({
                    'id': token_id,
                    'expiresAt': token.expires_at,
                    'expiresAtDisplay': expires_at_str,
                    'isExpired': False,
                    'uploadedAt': token.uploaded_at,
                    'uploadedAtDisplay': uploaded_at_str,
                    'usageCount': token.usage_count
                })
        
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
            headers = {}
            if self._version_manager:
                headers['User-Agent'] = await self._version_manager.get_user_agent_async()
            
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('grant_type', 'refresh_token')
                data.add_field('refresh_token', token.refresh_token)
                data.add_field('client_id', QWEN_OAUTH_CLIENT_ID)
                
                async with session.post(QWEN_OAUTH_TOKEN_ENDPOINT, data=data, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.warning("刷新 token 请求失败，状态码: %s，ID: %s", response.status, token_id)
                        should_remove = response.status in (400, 401, 403)
                        return None, should_remove, error_text or f"HTTP {response.status}"
                    
                    try:
                        result = await response.json()
                    except Exception as json_error:
                        logger.error("解析刷新 token 响应失败，ID: %s，错误: %s", token_id, json_error)
                        return None, False, f"解析响应失败: {json_error}"
                    
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
                        usage_count=token.usage_count
                    )
                    
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
        
        for token_id, token in self.token_store.items():
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
        if not self.token_store:
            return None
        
        valid_tokens = []
        token_entries = list(self.token_store.items())
        
        random.shuffle(token_entries)
        
        for token_id, token in token_entries:
            is_expired = token.expires_at and (time.time() * 1000) > token.expires_at
            
            if not is_expired:
                valid_tokens.append((token_id, token))
            else:
                refreshed_token, should_remove, _ = await self._force_refresh_token(token_id, token)
                if refreshed_token:
                    valid_tokens.append((token_id, refreshed_token))
                elif should_remove:
                    self.delete_token(token_id)
                    logger.warning("在获取可用 token 时检测到无效 token，已删除，ID: %s", token_id)
        
        if valid_tokens:
            logger.debug("找到可用 token，数量: %s", len(valid_tokens))
            return random.choice(valid_tokens)
        
        return None
