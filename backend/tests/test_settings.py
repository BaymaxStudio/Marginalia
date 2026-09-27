"""使用临时数据库验证设置保存不会清空已存的 API Key。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import database
from app.models import SettingsUpdateRequest
from app.routers import settings
from app.services import settings_service


class SettingsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for target, name, value in (
            (database, "DB_DIR", root),
            (database, "DB_PATH", root / "test.db"),
            (settings_service, "DATA_DIR", root),
            (settings_service, "KEY_FILE", root / ".fernet_key"),
        ):
            patcher = patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        database.init_db()

    async def test_saving_form_with_blank_keys_keeps_stored_values(self):
        await settings.update_settings(SettingsUpdateRequest(
            ai_provider="openai_compat",
            api_key_openai_compat="sk-test",
            openai_compat_base_url="https://example.test/v1",
            openai_compat_model_name="test-model",
        ))

        # 设置页的表单形状：GET 不回传 Key 原文，所以 Key 字段是空串
        loaded = await settings.get_settings()
        await settings.update_settings(SettingsUpdateRequest(
            ai_provider=loaded["ai_provider"],
            api_key_claude="",
            api_key_deepseek="",
            api_key_openai_compat="",
            openai_compat_base_url=loaded["openai_compat_base_url"],
            openai_compat_model_name=loaded["openai_compat_model_name"],
            font_size=20,
        ))

        stored = settings_service.get_all()
        self.assertEqual(stored["api_key_openai_compat"], "sk-test")
        self.assertEqual(stored["openai_compat_base_url"], "https://example.test/v1")
        self.assertEqual(stored["openai_compat_model_name"], "test-model")

        after = await settings.get_settings()
        self.assertTrue(after["has_api_key"])
        self.assertEqual(after["font_size"], 20)
        self.assertEqual(after["api_keys_configured"],
                         {"claude": False, "deepseek": False, "openai_compat": True})


if __name__ == "__main__":
    unittest.main()
