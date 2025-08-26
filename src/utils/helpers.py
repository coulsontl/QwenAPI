"""
Utility functions for Qwen Code API Server
"""
import secrets
import base64
import hashlib
from typing import Tuple, Optional


def generate_state_id() -> str:
    """生成随机状态ID"""
    return ''.join(secrets.choice('0123456789abcdef') for _ in range(32))


def get_token_id(refresh_token: str) -> str:
    """获取refresh_token的前8位作为标识符"""
    return refresh_token[:8]


async def generate_pkce_pair() -> Tuple[str, str]:
    """生成PKCE代码验证器和挑战码"""
    # 生成 code_verifier (43-128 字符的随机字符串)
    random_bytes = secrets.token_bytes(32)
    code_verifier = base64.urlsafe_b64encode(random_bytes).decode('utf-8').rstrip('=')
    
    # 生成 code_challenge (code_verifier 的 SHA256 哈希)
    sha256_hash = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(sha256_hash).decode('utf-8').rstrip('=')
    
    return code_verifier, code_challenge


def verify_password(authorization: Optional[str] = None, expected_password: str = None) -> bool:
    """验证请求密码"""
    if expected_password is None:
        from ..config.settings import API_PASSWORD
        expected_password = API_PASSWORD
    
    # 检查Authorization头
    if authorization and authorization == f"Bearer {expected_password}":
        return True
    
    return False