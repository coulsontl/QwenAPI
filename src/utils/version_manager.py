import asyncio
import aiohttp
import logging
import time
from typing import Optional
from ..database import TokenDatabase

logger = logging.getLogger(__name__)

class VersionManager:
    
    REGISTRY_URL = "https://registry.npmjs.org/@qwen-code/qwen-code/latest"
    DEFAULT_VERSION = "0.0.10"
    CACHE_TTL = 3600
    
    def __init__(self, db: TokenDatabase):
        self.db = db
        self._cached_version: Optional[str] = None
        self._cache_timestamp: Optional[float] = None
        self._lock = asyncio.Lock()
    
    async def get_version(self) -> str:
        async with self._lock:
            if self._is_cache_valid():
                return self._cached_version
            
            version = await self._fetch_version_from_registry()
            if version:
                await self._update_cache_and_storage(version)
                return version
            
            version = self.db.get_app_version()
            if version:
                self._cached_version = version
                self._cache_timestamp = time.time()
                logger.warning(f"Qwen-code版本号获取失败，使用数据库缓存版本: {version}")
                return version
            
            logger.error(f"Qwen-code版本号获取失败，使用默认版本: {self.DEFAULT_VERSION}")
            return self.DEFAULT_VERSION
    
    async def refresh_version(self) -> str:
        async with self._lock:
            self._cached_version = None
            self._cache_timestamp = None
            return await self.get_version()
    
    def get_user_agent(self, version: Optional[str] = None) -> str:
        if version is None:
            if self._is_cache_valid():
                version = self._cached_version
            else:
                version = self.db.get_app_version() or self.DEFAULT_VERSION
        
        return f"QwenCode/{version} (linux; x64)"
    
    async def get_user_agent_async(self) -> str:
        version = await self.get_version()
        return self.get_user_agent(version)
    
    def _is_cache_valid(self) -> bool:
        if not self._cached_version or not self._cache_timestamp:
            return False
        return time.time() - self._cache_timestamp < self.CACHE_TTL
    
    async def _fetch_version_from_registry(self) -> Optional[str]:
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.REGISTRY_URL) as response:
                    if response.status == 200:
                        data = await response.json()
                        version = data.get('version')
                        if version:
                            return version
        except:
            pass
        
        return None
    
    async def _update_cache_and_storage(self, version: str):
        self._cached_version = version
        self._cache_timestamp = time.time()
        self.db.save_app_version(version)


_version_manager: Optional[VersionManager] = None

def initialize_version_manager(db: TokenDatabase):
    global _version_manager
    _version_manager = VersionManager(db)

def get_version_manager() -> VersionManager:
    if _version_manager is None:
        raise RuntimeError("版本管理器未初始化，请先调用 initialize_version_manager")
    return _version_manager