"""SQLite 数据库初始化与连接

按产品技术规格第五章数据模型建表：
  - documents       文档元数据
  - vocabulary      生词本
  - reading_progress 阅读进度
  - settings        用户设置
  - cache           AI 请求缓存
"""

import sqlite3
import os
from pathlib import Path

DB_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DB_DIR / "app.db"


def get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """初始化数据库：创建所有表（若不存在）"""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id              TEXT PRIMARY KEY,
            title           TEXT NOT NULL,
            filename        TEXT NOT NULL,
            upload_time     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_pages     INTEGER,
            total_chapters  INTEGER,
            json_path       TEXT NOT NULL,
            pdf_path        TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS vocabulary (
            id                  TEXT PRIMARY KEY,
            document_id         TEXT NOT NULL,
            paragraph_id        TEXT NOT NULL,
            word_original       TEXT NOT NULL,
            word_lemma           TEXT NOT NULL,
            sentence            TEXT NOT NULL,
            phonetic            TEXT,
            dictionary_entries  TEXT NOT NULL,
            ai_explanation      TEXT,
            selected_index      INTEGER,
            is_technical_term   BOOLEAN DEFAULT FALSE,
            domain              TEXT,
            lookup_count        INTEGER DEFAULT 1,
            first_lookup_time   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_lookup_time    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS reading_progress (
            document_id         TEXT PRIMARY KEY,
            last_paragraph_id   TEXT NOT NULL,
            last_read_time      TIMESTAMP,
            chapter_status      TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS settings (
            key     TEXT PRIMARY KEY,
            value   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS cache (
            cache_key       TEXT PRIMARY KEY,
            cache_type      TEXT NOT NULL,
            response_json   TEXT NOT NULL,
            created_time    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 写入默认设置（仅当不存在时）
    defaults = {
        "ai_provider": "claude",
        "api_key_claude": "",
        "api_key_deepseek": "",
        "api_key_openai_compat": "",
        "openai_compat_base_url": "",
        "openai_compat_model_name": "",
        "model_word_lookup": "claude-haiku-4-5-20251001",
        "model_commentary": "claude-sonnet-4-6",
        "font_size": "18",
        "line_height": "1.8",
        "theme": "light",
    }
    for k, v in defaults.items():
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (k, v),
        )

    conn.commit()
    conn.close()
