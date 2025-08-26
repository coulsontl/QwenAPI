#!/bin/bash

# Qwen CLI to API FastAPI 版本运行脚本

# 检查 Python 是否已安装
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3，请先安装 Python3"
    exit 1
fi

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt

# 设置环境变量（可选）
export PORT=${PORT:-8000}
export HOST=${HOST:-0.0.0.0}
export API_PASSWORD=${API_PASSWORD:-qwen123}
export DATABASE_URL=${DATABASE_URL:-data/tokens.db}
export DEBUG=${DEBUG:-false}

echo "启动服务器..."
echo "访问地址: http://localhost:$PORT"
echo "默认密码: qwen123"
echo "按 Ctrl+C 停止服务器"

# 运行服务器
uvicorn src.main:app --host 0.0.0.0 --port $PORT --reload