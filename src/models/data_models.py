"""
Data models for Qwen Code API Server
"""
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Union
from enum import Enum


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


class ToolType(Enum):
    FUNCTION = "function"


@dataclass
class FunctionParameters:
    type: str = "object"
    properties: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "properties": self.properties,
            "required": self.required
        }


@dataclass
class FunctionDefinition:
    name: str
    description: str
    parameters: FunctionParameters
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters.to_dict()
        }


@dataclass
class Tool:
    type: ToolType = ToolType.FUNCTION
    function: FunctionDefinition = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "function": self.function.to_dict()
        }


@dataclass
class ToolCall:
    id: str
    type: ToolType = ToolType.FUNCTION
    function: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "function": self.function
        }


@dataclass
class ToolCallResult:
    tool_call_id: str
    role: str = "tool"
    content: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_call_id": self.tool_call_id,
            "role": self.role,
            "content": self.content
        }


@dataclass
class Choice:
    index: int
    message: Dict[str, Any]
    finish_reason: str = "stop"
    tool_calls: List[ToolCall] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "index": self.index,
            "message": self.message,
            "finish_reason": self.finish_reason
        }
        if self.tool_calls:
            result["tool_calls"] = [tool_call.to_dict() for tool_call in self.tool_calls]
        return result


@dataclass
class ChatCompletionResponse:
    id: str
    object: str = "chat.completion"
    created: int = field(default_factory=lambda: int(time.time()))
    model: str = "qwen3-coder-plus"
    choices: List[Choice] = field(default_factory=list)
    usage: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "model": self.model,
            "choices": [choice.to_dict() for choice in self.choices],
            "usage": self.usage
        }


@dataclass
class ChatCompletionStreamResponse:
    id: str
    object: str = "chat.completion.chunk"
    created: int = field(default_factory=lambda: int(time.time()))
    model: str = "qwen3-coder-plus"
    choices: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "model": self.model,
            "choices": self.choices
        }