"""
Data models for Qwen Code API Server
"""
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class TokenData:
    access_token: str
    refresh_token: str
    expires_at: Optional[int] = field(default_factory=lambda: int(time.time() * 1000) + 3600 * 1000)
    uploaded_at: Optional[int] = field(default_factory=lambda: int(time.time() * 1000))
    usage_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'expires_at': self.expires_at,
            'uploaded_at': self.uploaded_at,
            'usage_count': self.usage_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TokenData':
        return cls(
            access_token=data['access_token'],
            refresh_token=data['refresh_token'],
            expires_at=data.get('expires_at'),
            uploaded_at=data.get('uploaded_at'),
            usage_count=data.get('usage_count', 0)
        )


@dataclass
class OAuthState:
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    code_verifier: str
    expires_at: int
    poll_interval: int = 2


@dataclass
class RefreshResult:
    token_id: str
    success: bool
    error: Optional[str] = None
    message: Optional[str] = None