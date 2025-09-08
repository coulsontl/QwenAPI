"""
Database management for Qwen Code API Server
"""
import sqlite3
import time
from typing import Dict
from ..models import TokenData
import os
from ..config import DATABASE_URL, DATABASE_TABLE_NAME

class TokenDatabase:
    
    def __init__(self, db_path: str = DATABASE_URL):
        self.db_path = db_path
        self._ensure_directory_exists()
        self.init_db()
        self._migrate_db()
        self._cache = {}
        self._cache_ttl = 60
    
    def _ensure_directory_exists(self):
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    def _migrate_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='token_usage_stats'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(token_usage_stats)")
                columns = [info[1] for info in cursor.fetchall()]
                if 'call_count' not in columns:
                    cursor.execute("ALTER TABLE token_usage_stats ADD COLUMN call_count INTEGER DEFAULT 0")
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_versions'")
            if not cursor.fetchone():
                cursor.execute('''
                    CREATE TABLE app_versions (
                        key TEXT PRIMARY KEY,
                        version TEXT NOT NULL,
                        updated_at INTEGER NOT NULL
                    )
                ''')
            conn.commit()

    def init_db(self):
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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS token_usage_stats (
                    date TEXT,
                    model_name TEXT,
                    total_tokens INTEGER,
                    call_count INTEGER DEFAULT 0,
                    PRIMARY KEY (date, model_name)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS app_versions (
                    key TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            ''')
            conn.commit()
    
    def _get_cache_key(self, method: str, *args) -> str:
        return f"{method}:{':'.join(str(arg) for arg in args)}"
    
    def _get_cached_result(self, key: str):
        if key in self._cache:
            cached = self._cache[key]
            if time.time() - cached['timestamp'] < self._cache_ttl:
                return cached['data']
            del self._cache[key]
        return None
    
    def _cache_result(self, key: str, result):
        self._cache[key] = {'data': result, 'timestamp': time.time()}
    
    def _invalidate_cache(self):
        self._cache.clear()

    def save_token(self, token_id: str, token_data: TokenData) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                INSERT OR REPLACE INTO {DATABASE_TABLE_NAME} 
                (id, access_token, refresh_token, expires_at, uploaded_at, usage_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (token_id, token_data.access_token, token_data.refresh_token, 
                  token_data.expires_at, token_data.uploaded_at, token_data.usage_count))
            conn.commit()
        self._invalidate_cache()

    def load_all_tokens(self) -> Dict[str, TokenData]:
        cache_key = self._get_cache_key("load_all_tokens")
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached
        
        tokens = {}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'SELECT * FROM {DATABASE_TABLE_NAME}')
            for row in cursor.fetchall():
                token_id, access_token, refresh_token, expires_at, uploaded_at, usage_count = row
                tokens[token_id] = TokenData(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    uploaded_at=uploaded_at,
                    usage_count=usage_count
                )
        
        self._cache_result(cache_key, tokens)
        return tokens

    def delete_token(self, token_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'DELETE FROM {DATABASE_TABLE_NAME} WHERE id = ?', (token_id,))
            conn.commit()
        self._invalidate_cache()

    def delete_all_tokens(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'DELETE FROM {DATABASE_TABLE_NAME}')
            conn.commit()
        self._invalidate_cache()

    def update_token_usage(self, date: str, model_name: str, tokens: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO token_usage_stats (date, model_name, total_tokens, call_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(date, model_name) DO UPDATE SET 
                    total_tokens = total_tokens + excluded.total_tokens,
                    call_count = call_count + 1
            ''', (date, model_name, tokens))
            conn.commit()
        self._invalidate_cache()

    def get_usage_stats(self, date: str) -> Dict:
        cache_key = self._get_cache_key("get_usage_stats", date)
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM token_usage_stats WHERE date = ?', (date,))
            rows = cursor.fetchall()
            
            total_tokens = sum(row[2] for row in rows)
            total_calls = sum(row[3] for row in rows)
            models = {row[1]: {"total_tokens": row[2], "call_count": row[3]} for row in rows}
            
            result = {
                "date": date,
                "total_tokens_today": total_tokens,
                "total_calls_today": total_calls,
                "models": models
            }
            
            self._cache_result(cache_key, result)
            return result

    def delete_usage_stats(self, date: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM token_usage_stats WHERE date = ?', (date,))
            deleted_count = cursor.rowcount
            conn.commit()
        self._invalidate_cache()
        return deleted_count

    def increment_token_usage_count(self, token_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE {DATABASE_TABLE_NAME} SET usage_count = usage_count + 1 WHERE id = ?", (token_id,))
            conn.commit()

    def get_available_dates(self) -> list:
        cache_key = self._get_cache_key("get_available_dates")
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT date FROM token_usage_stats ORDER BY date DESC')
            dates = [row[0] for row in cursor.fetchall()]
            
            self._cache_result(cache_key, dates)
            return dates

    def save_app_version(self, version: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO app_versions (key, version, updated_at)
                VALUES (?, ?, ?)
            ''', ('qwen_code', version, int(time.time() * 1000)))
            conn.commit()
        self._invalidate_cache()

    def get_app_version(self) -> str:
        cache_key = self._get_cache_key("get_app_version")
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT version FROM app_versions WHERE key = ?', ('qwen_code',))
            row = cursor.fetchone()
            version = row[0] if row else None
            
            if version:
                self._cache_result(cache_key, version)
            return version