"""AI 适配器工厂"""

from __future__ import annotations

from app.services.ai_adapter.base import AIAdapter
from app.services.ai_adapter.claude import ClaudeAdapter
from app.services.ai_adapter.deepseek import DeepSeekAdapter
from app.services.ai_adapter.openai_compat import OpenAICompatAdapter
from app.services.settings_service import get_ai_config


class NoAPIKeyError(Exception):
    """未配置 API Key"""


def create_adapter() -> AIAdapter:
    """根据用户设置创建对应的 AI 适配器实例。"""
    config = get_ai_config()
    provider = config["provider"]
    api_key = config.get("api_key", "")

    if not api_key:
        raise NoAPIKeyError(
            f"未配置 {provider} 的 API Key。请在设置页面填入 API Key 后再试。"
        )

    if provider == "deepseek":
        return DeepSeekAdapter(api_key=api_key, model=config.get("model", "deepseek-chat"))
    elif provider == "openai_compat":
        return OpenAICompatAdapter(
            api_key=api_key,
            base_url=config["base_url"],
            model_name=config["model"],
        )
    else:
        return ClaudeAdapter(
            api_key=api_key,
            lookup_model=config.get("lookup_model", "claude-haiku-4-5-20251001"),
            commentary_model=config.get("commentary_model", "claude-sonnet-4-6"),
            base_url=config.get("base_url"),
        )
