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
from ..config import QWEN_OAUTH_TOKEN_ENDPOINT, QWEN_OAUTH_CLIENT_ID


class TokenManager:
    """Token lifecycle management"""
    
    def __init__(self, db: TokenDatabase):
        self.db = db
        self.token_store: Dict[str, TokenData] = {}
    
    def load_tokens(self):
        """从数据库加载所有token"""
        self.token_store = self.db.load_all_tokens()
    
    def save_token(self, token_id: str, token_data: TokenData):
        """保存token到数据库和内存"""
        self.token_store[token_id] = token_data
        self.db.save_token(token_id, token_data)
    
    def delete_token(self, token_id: str):
        """删除token"""
        self.token_store.pop(token_id, None)
        self.db.delete_token(token_id)
    
    def delete_all_tokens(self):
        """删除所有token"""
        self.token_store.clear()
        self.db.delete_all_tokens()
    
    def get_token_status(self) -> Dict[str, Any]:
        """获取所有token的状态"""
        token_list = []
        for token_id, token in self.token_store.items():
            is_expired = token.expires_at and (time.time() * 1000) > token.expires_at
            
            if is_expired:
                # 过期的token，直接标记为过期
                token_list.append({
                    'id': token_id,
                    'expiresAt': token.expires_at,
                    'isExpired': True,
                    'uploadedAt': token.uploaded_at,
                    'refreshFailed': True
                })
            else:
                token_list.append({
                    'id': token_id,
                    'expiresAt': token.expires_at,
                    'isExpired': False,
                    'uploadedAt': token.uploaded_at
                })
        
        return {
            'hasToken': len(self.token_store) > 0,
            'tokenCount': len(self.token_store),
            'tokens': token_list
        }
    
    async def refresh_single_token(self, token_id: str) -> Dict[str, Any]:
        """刷新单个token"""
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
        """强制刷新单个token"""
        try:
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('grant_type', 'refresh_token')
                data.add_field('refresh_token', token.refresh_token)
                data.add_field('client_id', QWEN_OAUTH_CLIENT_ID)
                
                async with session.post(QWEN_OAUTH_TOKEN_ENDPOINT, data=data) as response:
                    if response.status != 200:
                        return None
                    
                    try:
                        result = await response.json()
                    except Exception as json_error:
                        return None
                    
                    # 检查响应中是否包含错误
                    if 'error' in result:
                        return None
                    
                    # 创建更新后的token数据
                    updated_token = TokenData(
                        access_token=result['access_token'],
                        refresh_token=result.get('refresh_token', token.refresh_token),
                        expires_at=int(time.time() * 1000) + result.get('expires_in', 3600) * 1000,
                        uploaded_at=token.uploaded_at
                    )
                    
                    # 更新存储
                    self.save_token(token_id, updated_token)
                    
                    return updated_token
        except Exception as error:
            return None
    
    async def refresh_all_tokens(self) -> Dict[str, Any]:
        """强制刷新所有token"""
        if not self.token_store:
            raise Exception("没有可用的token")
        
        # 强制刷新所有token
        refresh_results = []
        tokens_to_remove = []
        
        for token_id, token in self.token_store.items():
            refreshed_token = await self._force_refresh_token(token_id, token)
            
            if refreshed_token:
                refresh_results.append({'id': token_id, 'success': True})
            else:
                refresh_results.append({'id': token_id, 'success': False, 'error': 'Token刷新失败'})
                tokens_to_remove.append(token_id)
        
        # 移除刷新失败的token
        for token_id in tokens_to_remove:
            self.delete_token(token_id)
        
        return {
            'success': True,
            'refreshResults': refresh_results,
            'remainingTokens': len(self.token_store),
            'isForcedRefresh': True
        }
    
    async def get_valid_token(self) -> Optional[Tuple[str, TokenData]]:
        """获取有效的token（会自动刷新过期的token）"""
        if not self.token_store:
            return None
        
        # 收集所有有效的token
        valid_tokens = []
        token_entries = list(self.token_store.items())
        
        # 随机打乱token顺序，实现负载均衡
        random.shuffle(token_entries)
        
        # 验证并收集有效token
        for token_id, token in token_entries:
            is_expired = token.expires_at and (time.time() * 1000) > token.expires_at
            
            if not is_expired:
                valid_tokens.append((token_id, token))
            else:
                # 尝试刷新过期的token
                refreshed_token = await self._force_refresh_token(token_id, token)
                if refreshed_token:
                    valid_tokens.append((token_id, refreshed_token))
        
        # 如果有有效token，随机返回一个
        if valid_tokens:
            return random.choice(valid_tokens)
        
        return None