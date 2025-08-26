"""
Web interface module for Qwen Code API Server
"""
from .web_routes import router as web_router

__all__ = ['web_router']