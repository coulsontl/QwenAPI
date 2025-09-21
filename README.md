# iFlow-Cli API Server

🚀 **iFlow-Cli API Server** - 基于FastAPI的Qwen模型API服务器，完全兼容OpenAI API格式

[English Version](README_en.md) | 中文版本

## ✨ 功能特性

- 🔐 **密码保护访问** - 支持环境变量配置的访问控制
- 🔑 **OAuth2授权码流程** - 支持完整的OAuth2授权码流程
- 👤 **用户信息管理** - 自动获取和存储用户信息，支持用户名显示
- 💬 **OpenAI兼容API** - 100%兼容OpenAI客户端，支持多种模型
- 🔄 **智能Token管理** - 自动Token刷新和状态监控，优先使用API Key
- 📊 **实时用量统计** - 按日期统计API调用量和使用情况
- 🐳 **Docker化部署** - 支持Docker和Docker Compose，自动构建发布
- 🌐 **Web管理界面** - 直观的Token管理界面，支持用户信息查看
- 🏗️ **模块化架构** - 清晰的代码结构，易于扩展
- 📈 **性能优化** - 流式响应去重，减少带宽消耗
- 🎯 **多模型支持** - 支持通义千问、DeepSeek、Kimi、GLM等多种模型

## 🚀 快速开始

### 方式一：一键启动（推荐）

```bash
# 克隆项目
git clone https://github.com/Water008/QwenAPI.git
cd QwenAPI

# 一键启动（自动创建虚拟环境）
./run.sh          # Linux/macOS
run.bat           # Windows
```

### 方式二：Docker部署

```bash
# 使用Docker Compose（推荐）
docker-compose up -d

# 或使用Docker命令
docker run -d \
  --name qwen-api \
  -p 8000:8000 \
  -e API_PASSWORD=your_secure_password \
  -v $(pwd)/data:/app/data \
  ghcr.io/coulsontl/qwenapi:iflow
```

### 方式三：手动安装

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## ⚙️ 配置说明

### 环境变量配置

创建 `.env` 文件（推荐）：

```bash
cp .env.example .env
```

编辑 `.env` 文件：
```bash
# 服务器配置
PORT=8000                    # 服务端口
HOST=0.0.0.0                # 监听地址
API_PASSWORD=qwen123        # 访问密码（务必修改）
DATABASE_URL=data/tokens.db # 数据库路径
DEBUG=false                 # 调试模式

# iFlow API配置
API_ENDPOINT=https://apis.iflow.cn/v1/chat/completions

# OAuth2配置
OAUTH_CLIENT_ID=your_client_id           # OAuth客户端ID（必填）
OAUTH_CLIENT_SECRET=your_client_secret   # OAuth客户端密钥（可选）
OAUTH_VERIFICATION_URI=https://iflow.cn/oauth
OAUTH2_TOKEN_ENDPOINT=https://iflow.cn/oauth/token
OAUTH2_AUTHORIZATION_HEADER=your_auth_header  # 可选
OAUTH2_CALLBACK_URL=http://localhost:8000/oauth2callback

# 用户信息配置
USER_INFO_ENDPOINT=https://iflow.cn/api/oauth/getUserInfo

# Token刷新时间阈值（秒，默认2小时=7200秒）
# 当Token剩余有效期大于此值时，将跳过刷新
TOKEN_REFRESH_THRESHOLD_SECONDS=7200
```

## 📖 使用指南

### 1. 获取访问权限

访问 http://localhost:8000，输入配置的密码登录。

### 2. 获取Token

**方式A：OAuth2授权码流程（推荐）**
1. 点击"OAuth登录获取Token"
2. 系统生成授权链接
3. 在浏览器中完成授权
4. 系统自动获取Token和用户信息

**方式B：手动上传**
1. 准备oauth_creds.json文件
2. 在Web界面上传文件
3. 系统自动解析并保存

**方式C：API获取Token**
```bash
# 获取Token和API Key
curl -X GET "http://localhost:8000/v1/iflow/token" \
  -H "Authorization: Bearer yourpassword"
```

### 3. 测试API

#### OpenAI客户端使用

```python
import openai

client = openai.OpenAI(
    api_key="yourpassword",
    base_url="http://localhost:8000/v1"
)

# 聊天对话
response = client.chat.completions.create(
    model="qwen3-coder",
    messages=[
        {"role": "user", "content": "请写一个Python快速排序算法"}
    ]
)
print(response.choices[0].message.content)

# 流式输出
response = client.chat.completions.create(
    model="qwen3-coder",
    messages=[{"role": "user", "content": "讲个笑话"}],
    stream=True
)
for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

#### 原生API调用

```bash
# 获取Token状态
curl -X GET http://localhost:8000/api/token-status \
  -H "Authorization: Bearer yourpassword"

# 聊天API
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer yourpassword" \
  -d '{
    "messages": [{"role": "user", "content": "你好"}],
    "model": "qwen3-coder"
  }'

# 流式聊天
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer yourpassword" \
  -d '{
    "messages": [{"role": "user", "content": "你好"}],
    "model": "qwen3-coder",
    "stream": true
  }'
```

## 📊 API接口文档

### OpenAI兼容接口

| 端点 | 方法 | 描述 |
|---|---|---|
| `/v1/chat/completions` | POST | 聊天完成 |
| `/v1/models` | GET | 获取模型列表 |
| `/v1/iflow/token` | GET | 获取Token和API Key |

### OAuth2接口

| 端点 | 方法 | 描述 |
|---|---|---|
| `/oauth-init` | POST | 初始化OAuth2授权 |
| `/oauth2callback` | GET | OAuth2回调处理 |
| `/poll-oauth-status` | GET | 轮询OAuth状态 |

### 原生API接口

| 端点 | 方法 | 描述 |
|---|---|---|
| `/api/login` | POST | 用户登录 |
| `/api/upload-token` | POST | 上传Token |
| `/api/token-status` | GET | Token状态 |
| `/api/refresh-token` | POST | 刷新所有Token |
| `/api/chat` | POST | 聊天API |
| `/api/health` | GET | 健康检查 |
| `/api/metrics` | GET | 性能指标 |

### 支持的模型

- **通义千问系列**：qwen3-coder, qwen3-max-preview, qwen3-32b, qwen3-235b等
- **DeepSeek系列**：deepseek-v3.1, deepseek-r1, deepseek-v3
- **Kimi系列**：kimi-k2-0905, kimi-k2
- **GLM系列**：glm-4.5
- **TStars系列**：tstars2.0

## 🐳 Docker使用

### 使用预构建镜像（推荐）

```bash
# 直接运行预构建镜像
docker run -d \
  --name qwen-api \
  -p 8000:8000 \
  -e API_PASSWORD=your_secure_password \
  -e OAUTH_CLIENT_ID=your_client_id \
  -v $(pwd)/data:/app/data \
  ghcr.io/coulsontl/iflow-cli-api

# 使用Docker Compose
docker-compose up -d
```

### 本地构建（可选）

```bash
# 本地构建镜像
docker build -t qwen-api .

# 运行本地构建的镜像
docker run -d \
  --name qwen-api \
  -p 8000:8000 \
  -e API_PASSWORD=yourpassword \
  -v $(pwd)/data:/app/data \
  qwen-api
```

## 🔧 开发指南

### 项目结构

```
QwenAPI/
├── src/
│   ├── main.py              # 主应用入口
│   ├── api/                 # API路由
│   ├── auth/                # 认证模块
│   ├── config/              # 配置管理
│   ├── database/            # 数据库操作
│   ├── models/              # 数据模型
│   ├── oauth/               # OAuth认证
│   ├── utils/               # 工具函数
│   └── web/                 # Web界面
├── static/                  # 静态资源
├── templates/               # HTML模板
├── data/                    # 数据存储
├── requirements.txt         # 依赖列表
├── Dockerfile              # Docker配置
├── docker-compose.yml      # Docker Compose配置
├── run.sh                  # Linux启动脚本
├── run.bat                 # Windows启动脚本
└── .env.example            # 环境变量示例
```

### 开发环境

```bash
# 安装开发依赖
pip install -r requirements.txt

# 运行开发服务器
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 代码检查
find src -name "*.py" -exec python -m py_compile {} \;
```

## 🚨 注意事项

- **安全第一**：务必修改默认密码
- **数据备份**：定期备份`data/tokens.db`数据库
- **环境隔离**：生产环境使用Docker部署
- **日志监控**：关注应用日志和性能指标
- **Token安全**：Token信息加密存储，勿泄露

## 🤝 贡献指南

1. Fork本项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 📄 许可证

本项目采用 MIT 许可证

## 🙋‍♂️ 支持与反馈

- **Issues**: [GitHub Issues](https://github.com/Water008/QwenAPI/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Water008/QwenAPI/discussions)

---

**⭐ 如果这个项目对你有帮助，请给个Star支持一下！**