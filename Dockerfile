FROM python:3.11-slim as builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# 生产阶段
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建非root用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# 复制已安装的依赖到系统路径
COPY --from=builder /root/.local /usr/local

# 复制应用代码
COPY --chown=appuser:appuser . .

# 创建数据目录并设置权限
RUN mkdir -p data && chown -R appuser:appuser /app

# 切换到非root用户
USER appuser

ENV PYTHONPATH=/app

# 健康检查
HEALTHCHECK --interval=600s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

EXPOSE 8000

# 使用uvicorn启动
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
