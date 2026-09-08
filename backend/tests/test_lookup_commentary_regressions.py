"""使用临时数据库和 AI 替身验证缓存与生词本行为。"""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app import database
from app.models import CommentaryRequest, LookupRequest
from app.routers import commentary, lookup, vocabulary
from app.services.ai_adapter.base import (
    CommentaryResponse,
    PersonaComment,
    WordLookupResponse,
)
from app.services.cache import set_cache


class RouterRegressionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name, value in (("DB_DIR", root), ("DB_PATH", root / "test.db")):
            patcher = patch.object(database, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        database.init_db()
        conn = database.get_connection()
        conn.execute(
            "INSERT INTO documents (id, title, filename, json_path, pdf_path) "
            "VALUES ('doc', 'Book', 'book.pdf', '', '')"
        )
        conn.commit()
        conn.close()

    async def test_paragraph_cache_preserves_avatar_and_handles_legacy_rows(self):
        response = CommentaryResponse(
            selected_personas=["领读学长"],
            comments=[PersonaComment(persona="领读学长", comment="A comment")],
        )
        adapter = SimpleNamespace(paragraph_commentary=AsyncMock(return_value=response))
        structure = {
            "title": "Book",
            "chapters": [{"id": "ch", "title": "Chapter", "sections": [
                {"paragraphs": [{"id": "p", "text": "Text"}]}]}],
        }
        body = CommentaryRequest(document_id="doc", paragraph_id="p")
        with patch.object(commentary, "_load_structure", return_value=structure), \
             patch.object(commentary, "get_ai_config", return_value={"provider": "mock"}), \
             patch.object(commentary, "create_adapter", return_value=adapter):
            first = await commentary.paragraph_commentary(body)
            second = await commentary.paragraph_commentary(body)
            self.assertEqual(first.comments, second.comments)
            self.assertEqual(second.comments[0].avatar, "guide")
            self.assertTrue(second.from_cache)
            adapter.paragraph_commentary.assert_awaited_once()

            set_cache("paragraph_commentary", response.model_dump_json(), "doc", "p", "none")
            legacy = await commentary.paragraph_commentary(body)
            self.assertEqual(legacy.comments[0].avatar, "guide")
            self.assertTrue(legacy.from_cache)

    async def test_lookup_cache_separates_mode_and_sentence_and_counts_hits(self):
        async def answer(request):
            return WordLookupResponse(
                selected_index=0, explanation=request.sentence,
                is_technical_term=False,
                memory_hint="Remember this" if request.mode == "expand" else None,
            )

        adapter = SimpleNamespace(word_lookup=AsyncMock(side_effect=answer))
        body = LookupRequest(document_id="doc", paragraph_id="p", word="bank", sentence="River bank")
        entries = [{"index": 0, "pos": "n", "en": "bank", "zh": "岸"}]
        with patch.object(lookup, "dict_query", return_value=(entries, None)), \
             patch.object(lookup, "lemmatize", return_value="bank"), \
             patch.object(lookup, "get_ai_config", return_value={"provider": "mock"}), \
             patch.object(lookup, "create_adapter", return_value=adapter):
            first = await lookup.ai_lookup(body)
            repeated = await lookup.ai_lookup(body)
            expanded = await lookup.ai_lookup(body.model_copy(update={"mode": "expand"}))
            different = await lookup.ai_lookup(body.model_copy(update={"sentence": "Central bank"}))
        self.assertFalse(first.from_cache)
        self.assertTrue(repeated.from_cache)
        self.assertIsNotNone(expanded.ai_expand)
        self.assertEqual(different.ai_context.explanation, "Central bank")
        self.assertEqual(adapter.word_lookup.await_count, 3)
        conn = database.get_connection()
        row = conn.execute("SELECT lookup_count FROM vocabulary").fetchone()
        conn.close()
        self.assertEqual(row["lookup_count"], 4)

    async def test_negative_meaning_index_does_not_select_last_entry(self):
        conn = database.get_connection()
        conn.execute(
            "INSERT INTO vocabulary (id, document_id, paragraph_id, word_original, "
            "word_lemma, sentence, dictionary_entries, selected_index) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("v", "doc", "p", "bank", "bank", "Text", json.dumps([{"zh": "岸"}]), -1),
        )
        conn.commit()
        conn.close()
        result = await vocabulary.list_vocabulary(document_id="doc", sort="time_desc")
        self.assertIsNone(result["words"][0]["selected_meaning"])


if __name__ == "__main__":
    unittest.main()
