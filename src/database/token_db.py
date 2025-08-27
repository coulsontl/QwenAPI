"""
Database management for Qwen Code API Server
"""
import sqlite3
import os
from typing import Dict
from ..models import TokenData
from ..config import DATABASE_URL, DATABASE_TABLE_NAME


class TokenDatabase:
    """SQLite database manager for token storage"""
    
    def __init__(self, db_path: str = DATABASE_URL):
        self.db_path = db_path
        self._ensure_directory_exists()
        self.init_db()
        self._migrate_db() # Add migration logic
    
    def _ensure_directory_exists(self):
        """确保数据库文件的目录存在"""
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    def _migrate_db(self):
        """检查并更新数据库结构"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Migrate token_usage_stats table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='token_usage_stats'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(token_usage_stats)")
                columns = [info[1] for info in cursor.fetchall()]
                if 'call_count' not in columns:
                    cursor.execute("ALTER TABLE token_usage_stats ADD COLUMN call_count INTEGER DEFAULT 0")

            # Migrate tokens table
            cursor.execute(f"PRAGMA table_info({DATABASE_TABLE_NAME})")
            columns = [info[1] for info in cursor.fetchall()]
            if 'usage_count' not in columns:
                cursor.execute(f"ALTER TABLE {DATABASE_TABLE_NAME} ADD COLUMN usage_count INTEGER NOT NULL DEFAULT 0")

            conn.commit()
    
    def init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {DATABASE_TABLE_NAME} (
                    id TEXT PRIMARY KEY,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,
                    expires_at INTEGER,
                    uploaded_at INTEGER,
                    usage_count INTEGER NOT NULL DEFAULT 0
                )
            ''')
            # Add a new table for token usage statistics
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS token_usage_stats (
                    date TEXT,
                    model_name TEXT,
                    total_tokens INTEGER,
                    call_count INTEGER DEFAULT 0,
                    PRIMARY KEY (date, model_name)
                )
            ''')
            conn.commit()
    
    def save_token(self, token_id: str, token_data: TokenData) -> None:
        """保存token到数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                INSERT OR REPLACE INTO {DATABASE_TABLE_NAME} (id, access_token, refresh_token, expires_at, uploaded_at, usage_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                token_id,
                token_data.access_token,
                token_data.refresh_token,
                token_data.expires_at,
                token_data.uploaded_at,
                token_data.usage_count
            ))
            conn.commit()
    
    def load_all_tokens(self) -> Dict[str, TokenData]:
        """从数据库加载所有token"""
        tokens = {}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'SELECT id, access_token, refresh_token, expires_at, uploaded_at, usage_count FROM {DATABASE_TABLE_NAME}')
            for row in cursor.fetchall():
                token_id, access_token, refresh_token, expires_at, uploaded_at, usage_count = row
                tokens[token_id] = TokenData(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    uploaded_at=uploaded_at,
                    usage_count=usage_count
                )
        return tokens
    
    def delete_token(self, token_id: str) -> None:
        """删除单个token"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'DELETE FROM {DATABASE_TABLE_NAME} WHERE id = ?', (token_id,))
            conn.commit()
    
    def delete_all_tokens(self) -> None:
        """删除所有token"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'DELETE FROM {DATABASE_TABLE_NAME}')
            conn.commit()

    def update_token_usage(self, date: str, model_name: str, tokens: int):
        """更新或插入token使用量和调用次数"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO token_usage_stats (date, model_name, total_tokens, call_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(date, model_name) DO UPDATE SET 
                    total_tokens = total_tokens + excluded.total_tokens,
                    call_count = call_count + 1;
            ''', (date, model_name, tokens))
            conn.commit()

    def get_usage_stats(self, date: str) -> Dict:
        """获取指定日期的token使用统计"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT model_name, total_tokens, call_count FROM token_usage_stats WHERE date = ?', (date,))
            rows = cursor.fetchall()
            
            total_tokens_today = sum(row[1] for row in rows)
            total_calls_today = sum(row[2] for row in rows)
            models = {row[0]: {"total_tokens": row[1], "call_count": row[2]} for row in rows}
            
            return {
                "date": date,
                "total_tokens_today": total_tokens_today,
                "total_calls_today": total_calls_today,
                "models": models
            }

    def increment_token_usage_count(self, token_id: str):
        """Increments the usage count for a specific token."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE {DATABASE_TABLE_NAME} SET usage_count = usage_count + 1 WHERE id = ?", (token_id,))
            conn.commit()

    def delete_usage_stats(self, date: str):
        """删除指定日期的用量统计数据"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM token_usage_stats WHERE date = ?', (date,))
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count