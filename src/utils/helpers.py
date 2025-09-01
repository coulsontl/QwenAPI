"""
Utility functions for Qwen Code API Server
"""
import secrets
import base64
import hashlib
from typing import Tuple, Optional


def generate_state_id() -> str:
    return ''.join(secrets.choice('0123456789abcdef') for _ in range(32))


def get_token_id(refresh_token: str) -> str:
    return refresh_token[:8]


async def generate_pkce_pair() -> Tuple[str, str]:
    random_bytes = secrets.token_bytes(32)
    code_verifier = base64.urlsafe_b64encode(random_bytes).decode('utf-8').rstrip('=')
    
    sha256_hash = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(sha256_hash).decode('utf-8').rstrip('=')
    
    return code_verifier, code_challenge


def verify_password(authorization: Optional[str] = None, expected_password: str = None) -> bool:
    if expected_password is None:
        from ..config.settings import API_PASSWORD
        expected_password = API_PASSWORD
    
    if authorization and authorization == f"Bearer {expected_password}":
        return True
    
    return False