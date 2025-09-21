"""
API module for iFlow-Cli API Server
"""
from .routes import router as api_router
from .openai_routes import router as openai_router

__all__ = ['api_router', 'openai_router']