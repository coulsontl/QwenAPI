from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import asyncio
import logging
from contextlib import asynccontextmanager

from src.config.settings import PORT, HOST, DEBUG
from src.api import api_router, openai_router
from src.web import web_router
from src.oauth import TokenManager
from src.database import TokenDatabase
from src.utils.version_manager import initialize_version_manager, get_version_manager
from src.config.settings import os

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局变量
_db = TokenDatabase()
_token_manager = TokenManager(_db)
_refresh_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_version_manager(_db)
    version_manager = get_version_manager()
    
    from src.api.routes import set_version_manager
    set_version_manager(version_manager)
    
    try:
        initial_version = await version_manager.get_version()
        logger.info(f"QwenCode版本初始化完成: {initial_version}")
    except Exception as e:
        logger.warning(f"版本号获取失败: {e}")
    
    _token_manager.load_tokens()
    
    global _refresh_task
    _refresh_task = asyncio.create_task(auto_refresh_tokens())
    logger.info("自动Token刷新任务已启动，每4小时执行一次")
    
    yield
    
    if _refresh_task:
        _refresh_task.cancel()
        try:
            await _refresh_task
        except asyncio.CancelledError:
            pass
        logger.info("自动Token刷新任务已停止")

async def auto_refresh_tokens():
    refresh_interval = int(os.getenv('TOKEN_REFRESH_INTERVAL', '14400'))
    
    while True:
        try:
            await asyncio.sleep(refresh_interval)
            
            try:
                version_manager = get_version_manager()
                await version_manager.refresh_version()
                logger.info("版本号已刷新")
            except Exception as e:
                logger.warning(f"版本号刷新失败: {e}")
            
            _token_manager.load_tokens()
            if _token_manager.token_store:
                logger.info(f"开始自动刷新所有token（间隔：{refresh_interval}秒）...")
                result = await _token_manager.refresh_all_tokens()
                
                success_count = sum(1 for r in result['refreshResults'] if r['success'])
                total_count = len(result['refreshResults'])
                
                logger.info(f"自动刷新完成: 成功 {success_count}/{total_count}")
            else:
                logger.info("没有token需要刷新")
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"自动刷新token失败: {e}")
            await asyncio.sleep(300)

app = FastAPI(title="Qwen Code API Server", lifespan=lifespan)

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

app.include_router(web_router)
app.include_router(api_router, prefix="/api")
app.include_router(openai_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=DEBUG)