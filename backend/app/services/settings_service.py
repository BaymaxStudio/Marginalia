"""用户设置读写服务

API Key 使用 Fernet 对称加密存储（密钥存储在 data/.fernet_key）。
若密钥文件不存在则自动生成。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.fernet import Fernet

from app.database import get_connection

DATA_DIR = Path(__file__).parent.parent.parent / "data"
KEY_FILE = DATA_DIR / ".fernet_key"

# API Key 相关字段名（前缀匹配）
_KEY_FIELDS = ("api_key_",)


def _get_fernet() -> Fernet:
    """获取或创建 Fernet 加密实例。"""
    if not KEY_FILE.exists():
        key = Fernet.generate_key()
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        os.chmod(KEY_FILE, 0o600)
    else:
        with open(KEY_FILE, "rb") as f:
            key = f.read()
    return Fernet(key)


def _is_key_field(name: str) -> bool:
    return any(name.startswith(prefix) for prefix in _KEY_FIELDS)


def get_all_safe() -> dict[str, str]:
    """获取所有设置的原始值（不解密），启动时安全读取。"""
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def get_all() -> dict[str, str]:
    """获取所有设置。API Key 字段会自动解密。"""
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()

    fernet = _get_fernet()
    result = {}
    for r in rows:
        value = r["value"]
        if _is_key_field(r["key"]) and value:
            try:
                value = fernet.decrypt(value.encode()).decode()
            except Exception:
                pass  # 旧明文数据或解密失败，返回原值
        result[r["key"]] = value
    return result


def get_ai_config() -> dict:
    """获取 AI 供应商完整配置（含解密后的 API Key）。"""
    settings = get_all()
    provider = settings.get("ai_provider", "claude")

    if provider == "claude":
        return {
            "provider": "claude",
            "api_key": settings.get("api_key_claude", ""),
            "lookup_model": settings.get("model_word_lookup", "claude-haiku-4-5-20251001"),
            "commentary_model": settings.get("model_commentary", "claude-sonnet-4-6"),
            "base_url": settings.get("anthropic_base_url", ""),
        }
    elif provider == "deepseek":
        return {
            "provider": "deepseek",
            "api_key": settings.get("api_key_deepseek", ""),
            "model": "deepseek-chat",
        }
    else:
        return {
            "provider": "openai_compat",
            "api_key": settings.get("api_key_openai_compat", ""),
            "base_url": settings.get("openai_compat_base_url", ""),
            "model": settings.get("openai_compat_model_name", "gpt-4o"),
        }


def get_reading_prefs() -> dict:
    settings = get_all()
    return {
        "font_size": int(settings.get("font_size", "18")),
        "line_height": float(settings.get("line_height", "1.8")),
        "theme": settings.get("theme", "light"),
    }


def update_setting(key: str, value: str) -> None:
    """更新设置。API Key 字段会自动加密后存储。"""
    if _is_key_field(key) and value:
        fernet = _get_fernet()
        stored_value = fernet.encrypt(value.encode()).decode()
    else:
        stored_value = value

    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, stored_value),
    )
    conn.commit()
    conn.close()
