# Qwen API Server

FastAPI 服务器，提供 Qwen 模型的 API 接口，兼容 OpenAI API 格式。

[English Version](README_en.md) | [中文版本](README.md)

## 功能特性

- 🔐 密码保护访问
- 📁 支持上传 oauth_creds.json 文件
- 🔑 OAuth 设备码授权登录
- 💬 OpenAI 兼容的 API 接口
- 🔄 自动 token 刷新
- 📊 Token 状态管理
- 💾 SQLite 持久化存储
- 🌐 Web 管理界面
- 🏗️ 模块化架构设计

## 系统要求

- Python 3.8+
- pip 包管理器

## 安装和运行

### 方式一：使用运行脚本（推荐）

#### Linux/macOS

```bash
# 克隆或下载项目
cd QwenAPI

# 运行脚本
./run.sh
```

#### Windows

```cmd
# 克隆或下载项目
cd QwenAPI

# 运行脚本
run.bat
```

### 方式二：手动安装

```bash
# 1. 创建虚拟环境
python3 -m venv venv

# Linux/macOS 激活虚拟环境
source venv/bin/activate

# Windows 激活虚拟环境
venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行服务器
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 环境变量配置

支持两种方式配置环境变量：

#### 方式一：使用 .env 文件（推荐）

1. 复制示例文件：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件：
```bash
# 服务器配置
PORT=8000
HOST=0.0.0.0
API_PASSWORD=your_secure_password
DATABASE_URL=data/tokens.db
DEBUG=false

# OAuth2 配置
QWEN_OAUTH_BASE_URL=https://chat.qwen.ai
QWEN_OAUTH_CLIENT_ID=f0304373b74a44d2b584a3fb70ca9e56
```

#### 方式二：直接设置环境变量

##### Linux/macOS

```bash
export PORT=8000              # 服务器端口
export HOST=0.0.0.0          # 监听地址
export API_PASSWORD=yourpass  # 访问密码
export DATABASE_URL=data/tokens.db # 数据库文件路径
export DEBUG=false           # 调试模式
```

##### Windows

```cmd
set PORT=8000
set HOST=0.0.0.0
set API_PASSWORD=yourpass
set DATABASE_URL=data/tokens.db
set DEBUG=false
```

## 使用方法

### 快速测试

```bash
# 测试代码是否能正常运行
python -c "import src.main; print('✅ 代码导入成功')"

# 启动服务器
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 详细步骤

1. 启动服务器后，访问 http://localhost:8000
2. 输入密码（默认：qwen123）
3. 使用以下任一方式获取 token：
   - 点击"OAuth 登录获取 Token"进行授权
   - 上传本地的 oauth_creds.json 文件
4. 在 API 测试区域测试功能

### 使用 Python 包安装

```bash
# 安装包
pip install -e .

# 运行服务器
qwen-api-server
```

## API 接口

### OpenAI 兼容接口

服务器完全兼容 OpenAI API 格式，可以直接用于各种 OpenAI 客户端。

#### 聊天完成 (Chat Completions)

```bash
# 标准格式
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer yourpassword" \
  -d '{
    "model": "qwen3-coder-plus",
    "messages": [{"role": "user", "content": "你好"}]
  }'

# 支持流式输出
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer yourpassword" \
  -d '{
    "model": "qwen3-coder-plus",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'
```

#### 模型列表 (Models)

```bash
# 获取可用模型列表
curl -X GET http://localhost:8000/v1/models \
  -H "Authorization: Bearer yourpassword"
```

#### 使用示例

```python
import openai

# 配置 OpenAI 客户端
client = openai.OpenAI(
    api_key="yourpassword",
    base_url="http://localhost:8000/v1"
)

# 聊天对话
response = client.chat.completions.create(
    model="qwen3-coder-plus",
    messages=[
        {"role": "user", "content": "你好，请写一个Python函数来计算斐波那契数列"}
    ]
)

print(response.choices[0].message.content)
```

### 原生 API 接口

```bash
# 登录
curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"password": "yourpassword"}'

# 上传 token
curl -X POST http://localhost:8000/api/upload-token \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer yourpassword" \
  -d '{
    "access_token": "...",
    "refresh_token": "..."
  }'

# 获取 token 状态
curl -X GET http://localhost:8000/api/token-status \
  -H "Authorization: Bearer yourpassword"

# 聊天
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer yourpassword" \
  -d '{
    "messages": [{"role": "user", "content": "你好"}],
    "model": "qwen3-coder-plus"
  }'
```

## 数据库

项目使用 SQLite 数据库存储 token 信息，数据库文件默认为 `data/tokens.db`。

数据库结构：
```sql
CREATE TABLE tokens (
    id TEXT PRIMARY KEY,           -- refresh_token 的前8位
    access_token TEXT NOT NULL,    -- 访问令牌
    refresh_token TEXT NOT NULL,   -- 刷新令牌
    expires_at INTEGER,            -- 过期时间戳
    uploaded_at INTEGER            -- 上传时间戳
);
```

## 项目结构

```
QwenAPI/
├── src/
│   ├── main.py              # 主应用入口
│   ├── api/                 # API 路由
│   │   ├── routes.py        # 原生 API 路由
│   │   └── openai_routes.py # OpenAI 兼容 API 路由
│   ├── auth/                # 认证模块
│   │   └── auth.py          # 密码认证
│   ├── config/              # 配置模块
│   │   └── settings.py      # 环境变量配置
│   ├── database/            # 数据库模块
│   │   └── token_db.py      # Token 数据库操作
│   ├── models/              # 数据模型
│   │   └── data_models.py   # 数据模型定义
│   ├── oauth/               # OAuth 模块
│   │   ├── oauth_manager.py # OAuth 管理
│   │   └── token_manager.py # Token 管理
│   ├── utils/               # 工具模块
│   │   └── helpers.py       # 辅助函数
│   └── web/                 # Web 界面
│       └── web_routes.py    # Web 路由
├── static/                  # 静态文件
│   ├── script.js           # JavaScript 文件
│   └── style.css           # CSS 文件
├── templates/              # 模板文件
│   └── index.html          # 主页面
├── data/                   # 数据目录
│   └── tokens.db           # SQLite 数据库
├── requirements.txt        # Python 依赖
├── setup.py               # 包安装配置
├── run.sh                 # Linux/macOS 启动脚本
├── run.bat                # Windows 启动脚本
└── README.md              # 项目说明
```

## 注意事项

- 请妥善保管 API 密码
- Token 数据存储在本地数据库中，请确保数据库文件安全
- 建议在生产环境中使用强密码并通过环境变量设置
- 确保 `data` 目录存在且可写，用于存储 SQLite 数据库
- 虚拟环境会自动创建和激活，无需手动操作

## 许可证

本项目采用 MIT 许可证。
