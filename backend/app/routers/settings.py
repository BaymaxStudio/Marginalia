"""设置接口

GET /api/settings    获取当前设置（API Key 仅返回是否已配置）
PUT /api/settings    更新设置（部分更新）
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException

from app.models import SettingsResponse, SettingsUpdateRequest
from app.services.settings_service import get_all, get_reading_prefs, update_setting

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_settings():
    try:
        all_settings = get_all()
        prefs = get_reading_prefs()

        provider = all_settings.get("ai_provider", "claude")
        has_api_key = bool(all_settings.get(f"api_key_{provider}", ""))

        return {
            "ai_provider": provider,
            "has_api_key": has_api_key,
            "font_size": prefs["font_size"],
            "line_height": prefs["line_height"],
            "theme": prefs["theme"],
            "log_level": all_settings.get("log_level", "INFO"),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.put("")
async def update_settings(body: SettingsUpdateRequest):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "没有需要更新的字段")

    for key, value in updates.items():
        update_setting(key, str(value) if not isinstance(value, str) else value)

    # 如果更新了 log_level，动态调整日志级别
    if "log_level" in updates and updates["log_level"] in ("INFO", "DEBUG"):
        logging.getLogger("marginalia").setLevel(
            getattr(logging, updates["log_level"].upper(), logging.INFO)
        )

    return {"status": "saved"}
