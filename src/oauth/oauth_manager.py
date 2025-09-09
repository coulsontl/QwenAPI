"""
OAuth2 management for Qwen Code API Server
"""
import time
import aiohttp
import asyncio
import logging
from typing import Dict, Optional, Any
from ..models import OAuthState, TokenData
from ..utils import generate_state_id, generate_pkce_pair
from ..config import (
    QWEN_OAUTH_DEVICE_CODE_ENDPOINT,
    QWEN_OAUTH_TOKEN_ENDPOINT,
    QWEN_OAUTH_CLIENT_ID,
    QWEN_OAUTH_SCOPE,
    QWEN_OAUTH_GRANT_TYPE
)

logger = logging.getLogger(__name__)


class OAuthManager:
    
    def __init__(self):
        self.oauth_states: Dict[str, OAuthState] = {}
        self._version_manager = None
        self.REQUEST_TIMEOUT = 10
    
    def set_version_manager(self, version_manager):
        self._version_manager = version_manager
    
    async def init_oauth(self) -> Dict[str, Any]:
        try:
            return await asyncio.wait_for(
                self._init_oauth_internal(), 
                timeout=self.REQUEST_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error("OAuth初始化超时")
            return {
                'success': False,
                'error': 'OAuth initialization timeout',
                'error_description': 'The OAuth request timed out. Please try again.'
            }
        except Exception as error:
            logger.error(f"OAuth初始化失败: {error}")
            return {
                'success': False,
                'error': str(error),
                'error_description': str(error)
            }
    
    async def _init_oauth_internal(self) -> Dict[str, Any]:
        code_verifier, code_challenge = await generate_pkce_pair()
        
        headers = {}
        if self._version_manager:
            try:
                user_agent = await asyncio.wait_for(
                    self._version_manager.get_user_agent_async(),
                    timeout=3
                )
                headers['User-Agent'] = user_agent
            except asyncio.TimeoutError:
                headers['User-Agent'] = 'QwenCode/unknown'
        
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            data = aiohttp.FormData()
            data.add_field('client_id', QWEN_OAUTH_CLIENT_ID)
            data.add_field('scope', QWEN_OAUTH_SCOPE)
            data.add_field('code_challenge', code_challenge)
            data.add_field('code_challenge_method', 'S256')
            
            async with session.post(QWEN_OAUTH_DEVICE_CODE_ENDPOINT, data=data, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f'Device authorization failed: {response.status} {response.statusText}. Response: {error_text}')
                
                result = await response.json()
                
                if 'error' in result:
                    raise Exception(f'Device authorization failed: {result["error"]} - {result.get("error_description", "")}')
                
                auth_state = OAuthState(
                    device_code=result['device_code'],
                    user_code=result['user_code'],
                    verification_uri=result['verification_uri'],
                    verification_uri_complete=result['verification_uri_complete'],
                    code_verifier=code_verifier,
                    expires_at=int(time.time() * 1000) + result['expires_in'] * 1000,
                    poll_interval=result.get('interval', 2)
                )
                
                state_id = generate_state_id()
                self.oauth_states[state_id] = auth_state
                
                return {
                    'success': True,
                    'stateId': state_id,
                    'userCode': auth_state.user_code,
                    'verificationUri': auth_state.verification_uri,
                    'verificationUriComplete': auth_state.verification_uri_complete,
                    'expiresAt': auth_state.expires_at,
                    'expiresIn': int((auth_state.expires_at - time.time() * 1000) / 1000)
                }
    
    async def poll_oauth_status(self, state_id: str) -> Dict[str, Any]:
        state = self.oauth_states.get(state_id)
        if not state:
            raise Exception("无效的stateId")
        
        # 检查是否过期
        now = int(time.time() * 1000)
        if state.expires_at and now > state.expires_at + 10000:
            self.oauth_states.pop(state_id, None)
            raise Exception("设备授权码已过期")
        
        # 如果接近过期，提醒用户
        if state.expires_at and now > state.expires_at - 60000:
            return {
                'success': False,
                'status': 'pending',
                'warning': '设备授权码即将过期，请尽快完成授权'
            }
        
        try:
            headers = {}
            if self._version_manager:
                headers['User-Agent'] = await self._version_manager.get_user_agent_async()
                
            async with aiohttp.ClientSession() as session:
                form_data = aiohttp.FormData()
                form_data.add_field('grant_type', QWEN_OAUTH_GRANT_TYPE)
                form_data.add_field('client_id', QWEN_OAUTH_CLIENT_ID)
                form_data.add_field('device_code', state.device_code)
                form_data.add_field('code_verifier', state.code_verifier)
                
                async with session.post(QWEN_OAUTH_TOKEN_ENDPOINT, data=form_data, headers=headers) as response:
                    if response.status != 200:
                        try:
                            error_data = await response.json()
                            
                            if response.status == 400 and error_data.get('error') == 'authorization_pending':
                                return {
                                    'success': False,
                                    'status': 'pending',
                                    'remainingTime': max(0, int((state.expires_at - now) / 1000)) if state.expires_at else 0
                                }
                            
                            if response.status == 429 and error_data.get('error') == 'slow_down':
                                state.pollInterval = min(state.pollInterval * 1.5, 10)
                                return {
                                    'success': False,
                                    'status': 'pending',
                                    'remainingTime': max(0, int((state.expires_at - now) / 1000)) if state.expires_at else 0
                                }
                            
                            raise Exception(f'Device token poll failed: {error_data.get("error")} - {error_data.get("error_description", "")}')
                        except:
                            error_text = await response.text()
                            raise Exception(f'Device token poll failed: {response.status} {response.statusText}. Response: {error_text}')
                    
                    token_response = await response.json()
                    
                    token_data = TokenData(
                        access_token=token_response['access_token'],
                        refresh_token=token_response['refresh_token'],
                        expires_at=int(time.time() * 1000) + token_response.get('expires_in', 3600) * 1000,
                        uploaded_at=int(time.time() * 1000)
                    )
                    
                    self.oauth_states.pop(state_id, None)
                    
                    return {
                        'success': True,
                        'tokenData': token_data,
                        'message': '认证成功'
                    }
        except Exception as error:
            if any(keyword in str(error).lower() for keyword in ['timed out', 'expired', 'invalid', '401']):
                self.oauth_states.pop(state_id, None)
                raise Exception(str(error))
            else:
                return {
                    'success': False,
                    'status': 'pending'
                }
    
    def cancel_oauth(self, state_id: str) -> Dict[str, Any]:
        if state_id:
            self.oauth_states.pop(state_id, None)
        
        return {
            'success': True,
            'message': 'OAuth认证已取消'
        }