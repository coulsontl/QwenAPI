"""
Configuration constants and settings for Qwen Code API Server
"""
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 时区设置
TZ = os.getenv("TZ", "Asia/Shanghai")
if TZ != "UTC":
    # 设置时区环境变量
    os.environ["TZ"] = TZ
    try:
        import time
        time.tzset()
    except (AttributeError, OSError):
        # 在某些系统上可能不支持tzset()
        pass

# Server Configuration
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
API_PASSWORD = os.getenv("API_PASSWORD", "qwen123")  # 默认密码，生产环境应通过环境变量设置
DATABASE_URL = os.getenv("DATABASE_URL", "data/tokens.db")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

# OAuth2 Configuration
QWEN_OAUTH_BASE_URL = os.getenv("QWEN_OAUTH_BASE_URL", "https://chat.qwen.ai")
QWEN_OAUTH_DEVICE_CODE_ENDPOINT = f"{QWEN_OAUTH_BASE_URL}/api/v1/oauth2/device/code"
QWEN_OAUTH_TOKEN_ENDPOINT = f"{QWEN_OAUTH_BASE_URL}/api/v1/oauth2/token"

# OAuth Client Configuration
QWEN_OAUTH_CLIENT_ID = os.getenv("QWEN_OAUTH_CLIENT_ID", "f0304373b74a44d2b584a3fb70ca9e56")
QWEN_OAUTH_SCOPE = os.getenv("QWEN_OAUTH_SCOPE", "openid profile email model.completion")
QWEN_OAUTH_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"

# API Configuration
QWEN_API_ENDPOINT = os.getenv("QWEN_API_ENDPOINT", "https://portal.qwen.ai/v1/chat/completions")

# Database Configuration
DATABASE_TABLE_NAME = "tokens"

# Security Configuration
HASH_ALGORITHM = "sha256"
PKCE_VERIFIER_LENGTH = 32
STATE_ID_LENGTH = 32

# Web Interface Configuration
HTML_TEMPLATE_PATH = "templates/index.html"