"""
Main application entry point for Qwen Code API Server
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import os

from src.config.settings import PORT, HOST, DEBUG
from src.api import api_router, openai_router
from src.web import web_router

app = FastAPI(title="Qwen Code API Server", description="Qwen Code API Server with FastAPI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_path = os.path.join(os.path.dirname(__file__), '..', 'static')
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

app.include_router(web_router, tags=["Web Interface"])
app.include_router(api_router, prefix="/api", tags=["API"])
app.include_router(openai_router, tags=["OpenAI API"])

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="debug" if DEBUG else "info"
    )