# iFlow-Cli API Server

🚀 **iFlow-Cli API Server** - FastAPI-based Qwen model API server, fully compatible with OpenAI API format

[中文版本](README.md) | English Version

## ✨ Features

- 🔐 **Password Protected Access** - Environment variable configurable access control
- 🔑 **OAuth2 Authorization Code Flow** - Complete OAuth2 authorization code flow support
- 👤 **User Information Management** - Automatic user info retrieval and storage with username display
- 💬 **OpenAI Compatible API** - 100% compatible with OpenAI clients, supports multiple models
- 🔄 **Smart Token Management** - Automatic token refresh and status monitoring, prioritizes API Key usage
- 📊 **Real-time Usage Statistics** - API call statistics and usage tracking by date
- 🐳 **Dockerized Deployment** - Support for Docker and Docker Compose with auto build and release
- 🌐 **Web Management Interface** - Intuitive token management interface with user info viewing
- 🏗️ **Modular Architecture** - Clear code structure, easy to extend
- 📈 **Performance Optimization** - Streaming response deduplication, reduced bandwidth usage
- 🎯 **Multi-Model Support** - Supports Qwen, DeepSeek, Kimi, GLM and other models

## 🚀 Quick Start

### Method 1: One-click Start (Recommended)

```bash
# Clone the project
git clone https://github.com/Water008/QwenAPI.git
cd QwenAPI

# One-click start (auto creates virtual environment)
./run.sh          # Linux/macOS
run.bat           # Windows
```

### Method 2: Docker Deployment

```bash
# Using Docker Compose (Recommended)
docker-compose up -d

# Or using Docker command
docker run -d \
  --name qwen-api \
  -p 8000:8000 \
  -e API_PASSWORD=your_secure_password \
  -e OAUTH2_CLIENT_ID=your_client_id \
  -v $(pwd)/data:/app/data \
  ghcr.io/coulsontl/qwenapi:iflow
```

### Method 3: Manual Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Start service
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## ⚙️ Configuration

### Environment Variables

Create `.env` file (recommended):

```bash
cp .env.example .env
```

Edit `.env` file:
```bash
# Server Configuration
PORT=8000                    # Service port
HOST=0.0.0.0                # Listen address
API_PASSWORD=qwen123        # Access password (must change)
DATABASE_URL=data/tokens.db # Database path
DEBUG=false                 # Debug mode

# iFlow API Configuration
API_ENDPOINT=https://apis.iflow.cn/v1/chat/completions

# OAuth2 Configuration
OAUTH2_CLIENT_ID=your_client_id           # OAuth client ID (required)
OAUTH2_CLIENT_SECRET=your_client_secret   # OAuth client secret (required, used to generate Basic Authorization header)
OAUTH2_VERIFICATION_URI=https://iflow.cn/oauth
OAUTH2_TOKEN_ENDPOINT=https://iflow.cn/oauth/token
OAUTH2_CALLBACK_URL=http://localhost:8000/oauth2callback

# User Info Configuration
USER_INFO_ENDPOINT=https://iflow.cn/api/oauth/getUserInfo

# Token refresh threshold (seconds, default 2 hours = 7200 seconds)
# When the remaining validity period of the token is greater than this value, the refresh will be skipped
TOKEN_REFRESH_THRESHOLD_SECONDS=7200
```

## 📖 Usage Guide

### 1. Get Access

Visit http://localhost:8000 and enter your configured password to login.

### 2. Get Token

**Method A: OAuth2 Authorization Code Flow (Recommended)**
1. Click "OAuth Login to Get Token"
2. System generates authorization link
3. Complete authorization in browser
4. System automatically gets token and user info

**Method B: Manual Upload**
1. Prepare oauth_creds.json file
2. Upload file in web interface
3. System automatically parses and saves

**Method C: API Get Token**
```bash
# Get token and API key
curl -X GET "http://localhost:8000/v1/iflow/token" \
  -H "Authorization: Bearer yourpassword"
```

### 3. Test API

#### Using OpenAI Client

```python
import openai

client = openai.OpenAI(
    api_key="yourpassword",
    base_url="http://localhost:8000/v1"
)

# Chat conversation
response = client.chat.completions.create(
    model="qwen3-coder",
    messages=[
        {"role": "user", "content": "Please write a Python quicksort algorithm"}
    ]
)
print(response.choices[0].message.content)

# Streaming output
response = client.chat.completions.create(
    model="qwen3-coder",
    messages=[{"role": "user", "content": "Tell me a joke"}],
    stream=True
)
for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

#### Native API Calls

```bash
# Get token status
curl -X GET http://localhost:8000/api/token-status \
  -H "Authorization: Bearer yourpassword"

# Chat API
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer yourpassword" \
  -d '{
    "messages": [{"role": "user", "content": "Hello"}],
    "model": "qwen3-coder"
  }'

# Streaming chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer yourpassword" \
  -d '{
    "messages": [{"role": "user", "content": "Hello"}],
    "model": "qwen3-coder",
    "stream": true
  }'
```

## 📊 API Documentation

### OpenAI Compatible Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/v1/chat/completions` | POST | Chat completions |
| `/v1/models` | GET | Get available models |
| `/v1/iflow/token` | GET | Get token and API key |

### OAuth2 Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/oauth-init` | POST | Initialize OAuth2 authorization |
| `/oauth2callback` | GET | OAuth2 callback handling |
| `/poll-oauth-status` | GET | Poll OAuth status |

### Native API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/login` | POST | User login |
| `/api/upload-token` | POST | Upload token |
| `/api/token-status` | GET | Token status |
| `/api/refresh-token` | POST | Refresh all tokens |
| `/api/chat` | POST | Chat API |
| `/api/health` | GET | Health check |
| `/api/metrics` | GET | Performance metrics |

### Supported Models

- **Qwen Series**: qwen3-coder, qwen3-max-preview, qwen3-32b, qwen3-235b, etc.
- **DeepSeek Series**: deepseek-v3.1, deepseek-r1, deepseek-v3
- **Kimi Series**: kimi-k2-0905, kimi-k2
- **GLM Series**: glm-4.5
- **TStars Series**: tstars2.0

## 🐳 Docker Usage

### Using Pre-built Image (Recommended)

```bash
# Run pre-built image directly
docker run -d \
  --name qwen-api \
  -p 8000:8000 \
  -e API_PASSWORD=your_secure_password \
  -e OAUTH2_CLIENT_ID=your_client_id \
  -v $(pwd)/data:/app/data \
  ghcr.io/water008/qwenapi:iflow

# Using Docker Compose
docker-compose up -d
```

### Local Build (Optional)

```bash
# Build image locally
docker build -t qwen-api .

# Run locally built image
docker run -d \
  --name qwen-api \
  -p 8000:8000 \
  -e API_PASSWORD=yourpassword \
  -v $(pwd)/data:/app/data \
  qwen-api
```

## 🔧 Development Guide

### Project Structure

```
QwenAPI/
├── src/
│   ├── main.py              # Main application entry
│   ├── api/                 # API routes
│   ├── auth/                # Authentication module
│   ├── config/              # Configuration management
│   ├── database/            # Database operations
│   ├── models/              # Data models
│   ├── oauth/               # OAuth authentication
│   ├── utils/               # Utility functions
│   └── web/                 # Web interface
├── static/                  # Static resources
├── templates/               # HTML templates
├── data/                    # Data storage
├── requirements.txt         # Dependencies list
├── Dockerfile              # Docker configuration
├── docker-compose.yml      # Docker Compose configuration
├── run.sh                  # Linux startup script
├── run.bat                 # Windows startup script
└── .env.example            # Environment variables example
```

### Development Environment

```bash
# Install development dependencies
pip install -r requirements.txt

# Run development server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Code check
find src -name "*.py" -exec python -m py_compile {} \;
```

## 🚨 Important Notes

- **Security First**: Always change the default password
- **Data Backup**: Regularly backup `data/tokens.db` database
- **Environment Isolation**: Use Docker for production deployment
- **Log Monitoring**: Monitor application logs and performance metrics
- **Token Security**: Token information is encrypted and stored, do not leak

## 🤝 Contributing

1. Fork this project
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Create Pull Request

## 📄 License

This project is licensed under the MIT License

## 🙋‍♂️ Support & Feedback

- **Issues**: [GitHub Issues](https://github.com/Water008/QwenAPI/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Water008/QwenAPI/discussions)

---

**⭐ If this project helps you, please give it a star!**