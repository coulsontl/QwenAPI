from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import asyncio
import logging
from contextlib import asynccontextmanager

from src.config.settings import PORT, HOST, DEBUG, LOG_LEVEL as CONFIG_LOG_LEVEL
from src.api import api_router, openai_router
from src.web import web_router
from src.oauth import TokenManager
from src.database import TokenDatabase
from src.utils.version_manager import initialize_version_manager, get_version_manager
from src.utils import initialize_tools

# 设置日志
LOG_LEVEL = getattr(logging, str(CONFIG_LOG_LEVEL).upper(), logging.INFO)
if DEBUG:
    LOG_LEVEL = logging.DEBUG
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# 全局变量
_db = TokenDatabase()
_token_manager = TokenManager(_db)
_refresh_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("应用生命周期启动，正在初始化依赖组件")
    initialize_version_manager(_db)
    version_manager = get_version_manager()
    
    from src.api.routes import set_version_manager
    set_version_manager(version_manager)
    _token_manager.set_version_manager(version_manager)
    
    # 初始化工具系统
    try:
        tool_registry = initialize_tools()
        tool_count = len(tool_registry.get_all_tools()) if hasattr(tool_registry, "get_all_tools") else 0
        logger.debug("工具系统初始化完成，当前已注册工具数量: %s", tool_count)
    except Exception:
        logger.exception("工具系统初始化失败")
    
    try:
        initial_version = await version_manager.get_version()
        logger.info("版本管理器初始化完成，当前版本: %s", initial_version)
    except Exception:
        logger.exception("获取应用版本信息失败，将使用默认版本")
    
    _token_manager.load_tokens()
    logger.debug("Token 管理器已加载，当前可用 token 数量: %s", len(_token_manager.token_store))
    
    global _refresh_task
    _refresh_task = asyncio.create_task(auto_refresh_tokens())
    logger.info("启动 token 自动刷新任务")
    
    yield

    # 清理资源
    if _refresh_task:
        _refresh_task.cancel()
        try:
            await _refresh_task
        except asyncio.CancelledError:
            logger.debug("自动刷新任务已取消")

    # 清理 aiohttp ClientSession
    try:
        from src.api.routes import cleanup_session
        await cleanup_session()
        logger.debug("aiohttp ClientSession 资源已清理")
    except Exception:
        logger.exception("清理 aiohttp ClientSession 时发生异常")

    logger.info("应用生命周期结束，资源清理完成")

async def auto_refresh_tokens():
    # Token自动刷新间隔固定为60秒
    refresh_interval = 60
    logger.info("自动刷新任务已启动，刷新间隔: %s 秒", refresh_interval)

    while True:
        try:
            await asyncio.sleep(refresh_interval)
            
            try:
                version_manager = get_version_manager()
                refreshed_version = await version_manager.refresh_version()
                logger.debug("已同步远端版本信息，当前版本: %s", refreshed_version)
            except Exception:
                logger.exception("刷新版本信息失败")
            
            _token_manager.load_tokens()
            if _token_manager.token_store:
                result = await _token_manager.refresh_all_tokens()
                
                success_count = sum(1 for r in result['refreshResults'] if r['success'])
                total_count = len(result['refreshResults'])
                logger.debug("自动刷新 token 完成，成功: %s/%s", success_count, total_count)
                
            else:
                logger.info("自动刷新任务跳过执行，未找到可刷新 token")
                
        except asyncio.CancelledError:
            logger.info("收到取消信号，自动刷新任务即将退出")
            break
        except Exception:
            logger.exception("自动刷新 token 任务执行失败，将在 300 秒后重试")
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
