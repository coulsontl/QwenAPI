# Qwen API Server

FastAPI server providing Qwen model API interface, compatible with OpenAI API format.

[English Version](README_en.md) | [中文版本](README.md)

## Features

- 🔐 Password-protected access
- 📁 Support for uploading oauth_creds.json files
- 🔑 OAuth device code authorization login
- 💬 OpenAI-compatible API interface
- 🔄 Automatic token refresh
- 📊 Token status management
- 💾 SQLite persistent storage
- 🌐 Web management interface
- 🏗️ Modular architecture design
- 🐳 Docker deployment support
- 🌍 Multi-timezone support

## System Requirements

- Python 3.8+
- pip package manager

## Installation and Running

### Method 1: Using Run Scripts (Recommended)

#### Linux/macOS

```bash
# Clone or download the project
cd QwenAPI

# Run the script
./run.sh
```

#### Windows

```cmd
# Clone or download the project
cd QwenAPI

# Run the script
run.bat
```

### Method 2: Manual Installation

```bash
# 1. Create virtual environment
python3 -m venv venv

# Activate virtual environment on Linux/macOS
source venv/bin/activate

# Activate virtual environment on Windows
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Method 3: Using Docker (Recommended)

```bash
# Use pre-built image
docker run -d \
  --name qwen-api \
  -p 8000:8000 \
  -e API_PASSWORD=your_secure_password \
  ghcr.io/water008/qwenapi:latest

# Or use docker-compose
docker-compose up -d
```

Docker image URL: `ghcr.io/water008/qwenapi:latest`

### Environment Variable Configuration

Two methods are supported for configuring environment variables:

#### Method 1: Using .env file (Recommended)

1. Copy the example file:
```bash
cp .env.example .env
```

2. Edit the `.env` file:
```bash
# Server configuration
PORT=8000
HOST=0.0.0.0
API_PASSWORD=your_secure_password
DATABASE_URL=data/tokens.db
DEBUG=false

# OAuth2 configuration
QWEN_OAUTH_BASE_URL=https://chat.qwen.ai
QWEN_OAUTH_CLIENT_ID=f0304373b74a44d2b584a3fb70ca9e56
QWEN_OAUTH_SCOPE=openid profile email model.completion
QWEN_API_ENDPOINT=https://portal.qwen.ai/v1/chat/completions

# Timezone configuration
TZ=UTC
```

#### Method 2: Direct Environment Variable Setting

##### Linux/macOS

```bash
export PORT=8000              # Server port
export HOST=0.0.0.0          # Listening address
export API_PASSWORD=yourpass  # Access password
export DATABASE_URL=data/tokens.db # Database file path
export DEBUG=false           # Debug mode
export TZ=UTC                # Timezone setting
```

##### Windows

```cmd
set PORT=8000
set HOST=0.0.0.0
set API_PASSWORD=yourpass
set DATABASE_URL=data/tokens.db
set DEBUG=false
set TZ=UTC
```

## Usage

### Quick Test

```bash
# Test if the code runs properly
python -c "import src.main; print('✅ Code import successful')"

# Start the server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Detailed Steps

1. After starting the server, visit http://localhost:8000
2. Enter the password (default: qwen123)
3. Use either of the following methods to get a token:
   - Click "OAuth Login to Get Token" for authorization
   - Upload the local oauth_creds.json file
4. Test functionality in the API test area

### Using Python Package Installation

```bash
# Install the package
pip install -e .

# Run the server
qwen-api-server
```

## API Endpoints

### OpenAI Compatible Interface

The server is fully compatible with OpenAI API format and can be directly used with various OpenAI clients.

#### Chat Completions

```bash
# Standard format
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer yourpassword" \
  -d '{
    "model": "qwen3-coder-plus",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# Support for streaming output
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer yourpassword" \
  -d '{
    "model": "qwen3-coder-plus",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true
  }'
```

#### Models

```bash
# Get available model list
curl -X GET http://localhost:8000/v1/models \
  -H "Authorization: Bearer yourpassword"
```

#### Usage Example

```python
import openai

# Configure OpenAI client
client = openai.OpenAI(
    api_key="yourpassword",
    base_url="http://localhost:8000/v1"
)

# Chat conversation
response = client.chat.completions.create(
    model="qwen3-coder-plus",
    messages=[
        {"role": "user", "content": "Hello, please write a Python function to calculate Fibonacci sequence"}
    ]
)

print(response.choices[0].message.content)
```

### Native API Endpoints

```bash
# Login
curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"password": "yourpassword"}'

# Upload token
curl -X POST http://localhost:8000/api/upload-token \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer yourpassword" \
  -d '{
    "access_token": "...",
    "refresh_token": "..."
  }'

# Get token status
curl -X GET http://localhost:8000/api/token-status \
  -H "Authorization: Bearer yourpassword"

# Chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer yourpassword" \
  -d '{
    "messages": [{"role": "user", "content": "Hello"}],
    "model": "qwen3-coder-plus"
  }'
```

## Database

The project uses SQLite database to store token information, with the default database file being `data/tokens.db`.

Database structure:
```sql
CREATE TABLE tokens (
    id TEXT PRIMARY KEY,           -- First 8 characters of refresh_token
    access_token TEXT NOT NULL,    -- Access token
    refresh_token TEXT NOT NULL,   -- Refresh token
    expires_at INTEGER,            -- Expiration timestamp
    uploaded_at INTEGER            -- Upload timestamp
);
```

## Project Structure

```
QwenAPI/
├── src/
│   ├── main.py              # Main application entry point
│   ├── api/                 # API routes
│   │   ├── routes.py        # Native API routes
│   │   └── openai_routes.py # OpenAI compatible API routes
│   ├── auth/                # Authentication module
│   │   └── auth.py          # Password authentication
│   ├── config/              # Configuration module
│   │   └── settings.py      # Environment variable configuration
│   ├── database/            # Database module
│   │   └── token_db.py      # Token database operations
│   ├── models/              # Data models
│   │   └── data_models.py   # Data model definitions
│   ├── oauth/               # OAuth module
│   │   ├── oauth_manager.py # OAuth management
│   │   └── token_manager.py # Token management
│   ├── utils/               # Utility module
│   │   ├── helpers.py       # Helper functions
│   │   └── timezone_utils.py # Timezone utility functions
│   └── web/                 # Web interface
│       └── web_routes.py    # Web routes
├── static/                  # Static files
│   ├── script.js           # JavaScript files
│   └── style.css           # CSS files
├── templates/              # Template files
│   └── index.html          # Main page
├── data/                   # Data directory
│   └── tokens.db           # SQLite database
├── requirements.txt        # Python dependencies
├── setup.py               # Package installation configuration
├── docker-compose.yml     # Docker Compose configuration
├── run.sh                 # Linux/macOS startup script
├── run.bat                # Windows startup script
├── README.md              # Project documentation (Chinese)
└── README_en.md           # Project documentation (English)
```

## Notes

- Please keep your API password secure
- Token data is stored in the local database, please ensure the database file is secure
- It is recommended to use strong passwords and set them through environment variables in production environments
- Ensure the `data` directory exists and is writable for storing the SQLite database
- Virtual environment will be created and activated automatically, no manual operation required

## License

This project is licensed under the MIT License.