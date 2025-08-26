"""
Authentication and authorization for Qwen Code API Server
"""
from fastapi import HTTPException, Request, status, Depends
from typing import Optional
from ..config import API_PASSWORD


def get_password_from_header(request: Request) -> Optional[str]:
    """从请求头获取密码"""
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header[7:]  # 去掉 "Bearer " 前缀
    return None


def check_auth(password: str = Depends(get_password_from_header)):
    """检查认证"""
    if not password or password != API_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授权",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True