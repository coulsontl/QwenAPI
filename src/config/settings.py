"""
Configuration constants and settings for iFlow-Cli API Server
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
OAUTH2_CLIENT_ID = os.getenv("OAUTH2_CLIENT_ID")
OAUTH2_CLIENT_SECRET = os.getenv("OAUTH2_CLIENT_SECRET")
OAUTH2_GRANT_TYPE = "authorization_code"
OAUTH2_VERIFICATION_URI = os.getenv("OAUTH2_VERIFICATION_URI", "https://iflow.cn/oauth")

# OAuth2 Callback Configuration
OAUTH2_CALLBACK_PORT = os.getenv("OAUTH2_CALLBACK_PORT", PORT)
OAUTH2_CALLBACK_HOST = os.getenv("OAUTH2_CALLBACK_HOST", "localhost")
OAUTH2_CALLBACK_URL = f"http://{OAUTH2_CALLBACK_HOST}:{OAUTH2_CALLBACK_PORT}/oauth2callback"

# OAuth2 Token Exchange Configuration
OAUTH2_TOKEN_ENDPOINT = os.getenv("OAUTH2_TOKEN_ENDPOINT", "https://iflow.cn/oauth/token")
OAUTH2_AUTHORIZATION_HEADER = os.getenv("OAUTH2_AUTHORIZATION_HEADER")

# User Info Configuration
USER_INFO_ENDPOINT = os.getenv("USER_INFO_ENDPOINT", "https://iflow.cn/api/oauth/getUserInfo")

# API Configuration
API_ENDPOINT = os.getenv("API_ENDPOINT", "https://apis.iflow.cn/v1/chat/completions")

# Database Configuration
DATABASE_TABLE_NAME = "tokens"

# Security Configuration
HASH_ALGORITHM = "sha256"
PKCE_VERIFIER_LENGTH = 32
STATE_ID_LENGTH = 32

# Web Interface Configuration
HTML_TEMPLATE_PATH = "templates/index.html"