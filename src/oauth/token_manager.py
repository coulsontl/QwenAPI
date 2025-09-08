"""
Token management for Qwen Code API Server
"""
import time
import random
import aiohttp
from typing import Dict, Optional, Tuple, List, Any
from ..models import TokenData, RefreshResult
from ..database import TokenDatabase
from ..utils import get_token_id
from ..utils.timezone_utils import timestamp_to_local_datetime, format_local_datetime
from ..config import QWEN_OAUTH_TOKEN_ENDPOINT, QWEN_OAUTH_CLIENT_ID


class TokenManager:
    
    def __init__(self, db: TokenDatabase):
        self.db = db
        self.token_store: Dict[str, TokenData] = {}
        self._version_manager = None
    
    def set_version_manager(self, version_manager):
        self._version_manager = version_manager
    
    def load_tokens(self) -> None:
        self.token_store = self.db.load_all_tokens()
    
    def save_token(self, token_id: str, token_data: TokenData) -> None:
        self.token_store[token_id] = token_data
        self.db.save_token(token_id, token_data)
    
    def delete_token(self, token_id: str) -> None:
        self.token_store.pop(token_id, None)
        self.db.delete_token(token_id)
    
    def delete_all_tokens(self) -> None:
        self.token_store.clear()
        self.db.delete_all_tokens()
    
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
        refreshed_token = await self._force_refresh_token(token_id, token)
        
        if refreshed_token:
            return {
                'success': True,
                'tokenId': token_id,
                'message': 'Token刷新成功'
            }
        else:
            # 刷新失败，移除token
            self.delete_token(token_id)
            raise Exception("Token刷新失败，已删除")
    
    async def _force_refresh_token(self, token_id: str, token: TokenData) -> Optional[TokenData]:
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
                        return None
                    
                    try:
                        result = await response.json()
                    except Exception as json_error:
                        return None
                    
                    if 'error' in result:
                        return None
                    
                    updated_token = TokenData(
                        access_token=result['access_token'],
                        refresh_token=result.get('refresh_token', token.refresh_token),
                        expires_at=int(time.time() * 1000) + result.get('expires_in', 3600) * 1000,
                        uploaded_at=token.uploaded_at,
                        usage_count=token.usage_count
                    )
                    
                    self.save_token(token_id, updated_token)
                    
                    return updated_token
        except Exception as error:
            return None
    
    async def refresh_all_tokens(self) -> Dict[str, Any]:
        if not self.token_store:
            raise Exception("没有可用的token")
        
        refresh_results = []
        tokens_to_remove = []
        
        for token_id, token in self.token_store.items():
            refreshed_token = await self._force_refresh_token(token_id, token)
            
            if refreshed_token:
                refresh_results.append({'id': token_id, 'success': True})
            else:
                refresh_results.append({'id': token_id, 'success': False, 'error': 'Token刷新失败'})
                tokens_to_remove.append(token_id)
        
        for token_id in tokens_to_remove:
            self.delete_token(token_id)
        
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
                refreshed_token = await self._force_refresh_token(token_id, token)
                if refreshed_token:
                    valid_tokens.append((token_id, refreshed_token))
        
        if valid_tokens:
            return random.choice(valid_tokens)
        
        return None