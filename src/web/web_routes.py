"""
Web interface module for Qwen Code API Server
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

router = APIRouter()

# 配置静态文件服务
static_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static')


@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """返回主页面"""
    template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'templates', 'index.html')
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Template not found</h1><p>Please check the template path.</p>", status_code=404)