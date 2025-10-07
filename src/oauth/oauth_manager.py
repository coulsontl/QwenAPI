"""
OAuth2 management for iFlow-Cli API Server
"""
from ast import Return
import time
import aiohttp
import asyncio
import logging
from typing import Dict, Optional, Any

from src.config.settings import OAUTH2_CLIENT_SECRET
from ..models import OAuthState, TokenData
from ..utils import generate_state_id, generate_pkce_pair
from ..config import (
    OAUTH2_CLIENT_ID,
    OAUTH2_VERIFICATION_URI,
    OAUTH2_TOKEN_ENDPOINT,
    OAUTH2_CALLBACK_URL,
    USER_INFO_ENDPOINT,
    get_oauth2_authorization_header
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
        logger.debug("已生成 PKCE 参数")
        
        headers = {}
        if self._version_manager:
            try:
                user_agent = await asyncio.wait_for(
                    self._version_manager.get_user_agent_async(),
                    timeout=3
                )
                headers['User-Agent'] = user_agent
                logger.debug("初始化 OAuth 时使用自定义 User-Agent")
            except asyncio.TimeoutError:
                headers['User-Agent'] = self._version_manager.get_user_agent()
            except Exception:
                headers['User-Agent'] = self._version_manager.get_user_agent()
        
        state_id = generate_state_id()
        auth_state = OAuthState(
            verification_uri=OAUTH2_VERIFICATION_URI,
            verification_uri_complete=f"{OAUTH2_VERIFICATION_URI}?loginMethod=phone&type=phone&redirect={OAUTH2_CALLBACK_URL.replace(':', '%3A').replace('/', '%2F')}&state={state_id}&client_id={OAUTH2_CLIENT_ID}",
            code_verifier=code_verifier,
            expires_at=time.time()*1000 + 1000*60*15,
        )
        self.oauth_states[state_id] = auth_state
        logger.info("设备授权流程启动，stateId: %s", state_id)
        
        return {
            'success': True,
            'stateId': state_id,
            'userCode': "",
            'deviceCode': "",
            'verificationUri': auth_state.verification_uri,
            'verificationUriComplete': auth_state.verification_uri_complete,
            'expiresAt': auth_state.expires_at,
            'expiresIn': int((auth_state.expires_at - time.time() * 1000) / 1000)
        }
    
    async def poll_oauth_status(self, state_id: str) -> Dict[str, Any]:
        now = int(time.time() * 1000)
        state = self.oauth_states.get(state_id)
        if not state:
            logger.warning("OAuth 轮询失败，stateId 无效: %s", state_id)
            raise Exception("无效的stateId")
        
        if state.expires_at and now > state.expires_at + 10000:
            self.oauth_states.pop(state_id, None)
            logger.warning("设备授权码已过期，stateId: %s", state_id)
            raise Exception("设备授权码已过期")
        
        # 如果接近过期，提醒用户
        if state.expires_at and now > state.expires_at - 60000:
            logger.debug("设备授权码即将过期，stateId: %s", state_id)
            return {
                'success': False,
                'status': 'pending',
                'warning': '设备授权码即将过期，请尽快完成授权',
                'pollInterval': state.poll_interval
            }
        
        # 检查是否有授权码
        if not state.code:
            logger.debug("设备授权尚未完成，stateId: %s", state_id)
            return {
                'success': False,
                'status': 'pending',
                'remainingTime': max(0, int((state.expires_at - now) / 1000)) if state.expires_at else 0,
                'pollInterval': state.poll_interval
            } 
        # 有授权码，尝试交换token
        try:
            token_data = await self._exchange_code_for_token(state.code, state_id)
            
            self.oauth_states.pop(state_id, None)
            logger.info("OAuth 授权成功，stateId: %s", state_id)

            return {
                'success': True,
                'tokenData': token_data,
                'message': '认证成功'
            }
        except Exception as error:
            self.oauth_states.pop(state_id, None)
            logger.warning("OAuth token 交换失败，stateId: %s，错误: %s", state_id, error)
            raise Exception(str(error))
    
    async def handle_oauth_callback(self, code: str, state: str) -> Dict[str, Any]:
        """处理OAuth2回调，保存授权码到内存"""
        if state not in self.oauth_states:
            logger.warning("OAuth 回调收到无效的 state: %s", state)
            raise Exception("无效的state参数")
        
        # 保存授权码到对应的OAuth状态
        self.oauth_states[state].code = code
        logger.info("OAuth 回调成功，已保存授权码，state: %s", state)
        
        return {
            'success': True,
            'message': '授权成功，请直接关闭当前页面，然后返回管理后台刷新页面'
        }
    
    async def _exchange_code_for_token(self, code: str, state_id: str) -> TokenData:
        """使用授权码交换token，使用curl方式"""
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
        
        form_data = aiohttp.FormData()
        form_data.add_field('grant_type', 'authorization_code')
        form_data.add_field('code', code)
        form_data.add_field('redirect_uri', OAUTH2_CALLBACK_URL)
        form_data.add_field('client_id', OAUTH2_CLIENT_ID)
        
        # 只有当 OAUTH2_CLIENT_SECRET 存在时才添加
        if OAUTH2_CLIENT_SECRET:
            form_data.add_field('client_secret', OAUTH2_CLIENT_SECRET)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                OAUTH2_TOKEN_ENDPOINT, 
                data=form_data, 
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                try:
                    token_response = await response.json()
                except Exception as json_error:
                    logger.error("解析 token 交换响应失败，stateId: %s，错误: %s", state_id, json_error)
                    raise Exception(f'Token exchange response parse failed: {json_error}')
                
                # 检查响应中的 success 字段
                if not token_response.get('success', True):
                    error_code = str(token_response.get('code', 'unknown'))
                    error_message = token_response.get('message', '未知错误')
                    logger.error("Token 交换失败，stateId: %s，错误码: %s，消息: %s", state_id, error_code, error_message)
                    raise Exception(f'Token exchange failed: {error_code} - {error_message}')
                
                # 检查是否有 error 字段（兼容旧的错误格式）
                if 'error' in token_response:
                    error_code = str(token_response.get('error'))
                    error_message = token_response.get('error_description', token_response.get('message', '未知错误'))
                    logger.error("Token 交换失败，stateId: %s，错误: %s，消息: %s", state_id, error_code, error_message)
                    raise Exception(f'Token exchange failed: {error_code} - {error_message}')
                
                logger.debug("Token 交换成功，stateId: %s", state_id)
                
                # 创建 TokenData 对象
                token_data = TokenData(
                    access_token=token_response['access_token'],
                    refresh_token=token_response['refresh_token'],
                    expires_at=int(time.time() * 1000) + token_response.get('expires_in', 3600) * 1000,
                    uploaded_at=int(time.time() * 1000)
                )
                
                # 获取用户信息
                user_info = await self._get_user_info(token_response['access_token'])
                if user_info:
                    token_data.user_info = user_info
                    token_data.api_key = user_info.get('apiKey')
                    logger.debug("OAuth 交换时成功获取用户信息，用户ID: %s", user_info.get('userId'))
                
                return token_data
    
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
    
    def cancel_oauth(self, state_id: str) -> Dict[str, Any]:
        if state_id:
            self.oauth_states.pop(state_id, None)
            logger.info("已取消 OAuth 流程，stateId: %s", state_id)
        
        return {
            'success': True,
            'message': 'OAuth认证已取消'
        }
