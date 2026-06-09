"""AI 请求缓存服务

缓存键策略（按 spec 4.4）：
  - 词义查询：  (document_id, paragraph_id, word_lemma)
  - 段评：      (document_id, paragraph_id, persona_set)
  - 章评：      (document_id, chapter_id)
"""

from __future__ import annotations

import hashlib
import json
from typing import Optional

from app.database import get_connection


def _make_key(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def get_cached(cache_type: str, *key_parts: str) -> Optional[str]:
    """查询缓存，命中返回 JSON 字符串，未命中返回 None。"""
    key = _make_key(cache_type, *key_parts)
    conn = get_connection()
    row = conn.execute(
        "SELECT response_json FROM cache WHERE cache_key = ? AND cache_type = ?",
        (key, cache_type),
    ).fetchone()
    conn.close()
    return row["response_json"] if row else None


def set_cache(cache_type: str, data: str, *key_parts: str) -> None:
    """写入缓存。"""
    key = _make_key(cache_type, *key_parts)
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO cache (cache_key, cache_type, response_json)
           VALUES (?, ?, ?)""",
        (key, cache_type, data),
    )
    conn.commit()
    conn.close()
