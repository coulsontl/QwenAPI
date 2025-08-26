@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

REM Qwen CLI to API FastAPI 版本运行脚本

REM 检查 Python 是否已安装
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到 Python，请先安装 Python
    pause
    exit /b 1
)

REM 检查虚拟环境是否存在
if not exist "venv" (
    echo 创建虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 安装依赖
echo 安装依赖...
pip install -r requirements.txt

REM 设置环境变量（可选）
if not defined PORT set PORT=8000
if not defined HOST set HOST=0.0.0.0
if not defined API_PASSWORD set API_PASSWORD=qwen123
if not defined DATABASE_URL set DATABASE_URL=data/tokens.db
if not defined DEBUG set DEBUG=false

echo 启动服务器...
echo 访问地址: http://localhost:%PORT%
echo 默认密码: qwen123
echo 按 Ctrl+C 停止服务器

REM 运行服务器
uvicorn src.main:app --host %HOST% --port %PORT% --reload

pause