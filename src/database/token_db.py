"""
Database management for Qwen Code API Server
"""
import sqlite3
import os
from typing import Dict, Optional
from ..models import TokenData
from ..config import DATABASE_URL, DATABASE_TABLE_NAME


class TokenDatabase:
    """SQLite database manager for token storage"""
    
    def __init__(self, db_path: str = DATABASE_URL):
        self.db_path = db_path
        self._ensure_directory_exists()
        self.init_db()
    
    def _ensure_directory_exists(self):
        """确保数据库文件的目录存在"""
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    
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
                    uploaded_at INTEGER
                )
            ''')
            conn.commit()
    
    def save_token(self, token_id: str, token_data: TokenData):
        """保存token到数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                INSERT OR REPLACE INTO {DATABASE_TABLE_NAME} (id, access_token, refresh_token, expires_at, uploaded_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                token_id,
                token_data.access_token,
                token_data.refresh_token,
                token_data.expires_at,
                token_data.uploaded_at
            ))
            conn.commit()
    
    def load_all_tokens(self) -> Dict[str, TokenData]:
        """从数据库加载所有token"""
        tokens = {}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'SELECT id, access_token, refresh_token, expires_at, uploaded_at FROM {DATABASE_TABLE_NAME}')
            for row in cursor.fetchall():
                token_id, access_token, refresh_token, expires_at, uploaded_at = row
                tokens[token_id] = TokenData(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    uploaded_at=uploaded_at
                )
        return tokens
    
    def delete_token(self, token_id: str):
        """删除单个token"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'DELETE FROM {DATABASE_TABLE_NAME} WHERE id = ?', (token_id,))
            conn.commit()
    
    def delete_all_tokens(self):
        """删除所有token"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'DELETE FROM {DATABASE_TABLE_NAME}')
            conn.commit()