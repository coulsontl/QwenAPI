"""
Authentication and authorization for Qwen Code API Server
"""
from fastapi import HTTPException, Request, status, Depends
from typing import Optional
from ..config import API_PASSWORD


def get_password_from_header(request: Request) -> Optional[str]:
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header[7:]
    return None


def check_auth(password: str = Depends(get_password_from_header)):
    if not password or password != API_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True