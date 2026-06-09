"""DeepSeek 适配器（OpenAI 兼容格式）"""

from __future__ import annotations

import json
import re
import time

from openai import AsyncOpenAI

from app.logger import get_logger

from app.services.ai_adapter.base import (
    AIAdapter,
    WordLookupRequest,
    WordLookupResponse,
    CommentaryRequest,
    CommentaryResponse,
    ChapterReviewRequest,
    ChapterReviewResponse,
    PersonaComment,
)
from app.prompts.word_lookup import SYSTEM_PROMPT as WL_SYSTEM, USER_PROMPT as WL_USER, EXPAND_APPEND
from app.prompts.paragraph_commentary import (
    SYSTEM_PROMPT as PC_SYSTEM,
    USER_PROMPT as PC_USER,
    EXCLUDED_SECTION,
)
from app.prompts.chapter_review import (
    SYSTEM_PROMPT as CR_SYSTEM,
    USER_PROMPT as CR_USER,
)
from app.prompts.chapter_summary import (
    SYSTEM_PROMPT as CS_SYSTEM,
    USER_PROMPT as CS_USER,
)
from app.prompts.structure_recognition import (
    SYSTEM_PROMPT as SR_SYSTEM,
    USER_PROMPT as SR_USER,
)

logger = get_logger("ai_adapter")


def _extract_json_ds(text: str) -> dict:
    """从 DeepSeek 返回文本中提取 JSON 对象。"""
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    return json.loads(text)


class DeepSeekAdapter(AIAdapter):
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        self.model = model

    async def word_lookup(self, request: WordLookupRequest) -> WordLookupResponse:
        entries_formatted = "\n".join(
            f"[{e['index']}] {e.get('pos','')} {e.get('en','')} | {e.get('zh','')}"
            for e in request.dictionary_entries
        )

        user_prompt = WL_USER.format(
            word_lemma=request.word,
            word_original=request.word,
            sentence=request.sentence,
            paragraph=request.paragraph,
            dictionary_entries_formatted=entries_formatted,
        )
        if request.mode == "expand":
            user_prompt += "\n" + EXPAND_APPEND

        t0 = time.time()
        logger.debug("word_lookup prompt: %s...", user_prompt[:500])
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": WL_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=512,
                temperature=0.3,
            )
        except Exception as e:
            logger.warning("word_lookup failed provider=deepseek model=%s word=%s error=%r",
                           self.model, request.word, str(e))
            raise

        latency = time.time() - t0
        tokens_in = getattr(resp.usage, "prompt_tokens", 0) if resp.usage else 0
        tokens_out = getattr(resp.usage, "completion_tokens", 0) if resp.usage else 0
        logger.info("word_lookup completed latency=%.1fs tokens_in=%d tokens_out=%d",
                    latency, tokens_in, tokens_out)

        content = resp.choices[0].message.content or "{}"
        logger.debug("word_lookup response: %s", content[:500])
        data = _extract_json_ds(content)

        return WordLookupResponse(
            selected_index=data.get("selected_index", 0),
            explanation=data.get("explanation", ""),
            is_technical_term=data.get("is_technical_term", False),
            domain=data.get("domain"),
            memory_hint=data.get("memory_hint"),
            confusion_note=data.get("confusion_note"),
        )

    async def paragraph_commentary(
        self, request: CommentaryRequest
    ) -> CommentaryResponse:
        excluded_section = ""
        if request.excluded_personas:
            excluded_section = EXCLUDED_SECTION.format(
                excluded_personas_list=", ".join(request.excluded_personas)
            )

        user_prompt = PC_USER.format(
            document_title=request.document_title,
            chapter_title=request.chapter_title,
            previous_paragraph=request.previous_paragraph or "（无）",
            current_paragraph=request.current_paragraph,
            next_paragraph=request.next_paragraph or "（无）",
            excluded_section=excluded_section,
        )

        t0 = time.time()
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": PC_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=2048,
                temperature=0.7,
            )
        except Exception as e:
            logger.warning("paragraph_commentary failed provider=deepseek model=%s error=%r",
                           self.model, str(e))
            raise

        latency = time.time() - t0
        tokens_in = getattr(resp.usage, "prompt_tokens", 0) if resp.usage else 0
        tokens_out = getattr(resp.usage, "completion_tokens", 0) if resp.usage else 0

        content = resp.choices[0].message.content or "{}"
        data = _extract_json_ds(content)
        personas = data.get("selected_personas", [])

        logger.info("paragraph_commentary completed latency=%.1fs tokens_in=%d tokens_out=%d personas=%s",
                    latency, tokens_in, tokens_out, personas)

        return CommentaryResponse(
            selected_personas=personas,
            comments=[
                PersonaComment(persona=c["persona"], comment=c["comment"])
                for c in data.get("comments", [])
            ],
        )

    async def chapter_review(
        self, request: ChapterReviewRequest
    ) -> ChapterReviewResponse:
        user_prompt = CR_USER.format(
            document_title=request.document_title,
            chapter_title=request.chapter_title,
            chapter_number=request.chapter_number,
            total_chapters=request.total_chapters,
            previous_chapter_title_or_none=request.previous_chapter_title or "（无，这是第一章）",
            next_chapter_title_or_none=request.next_chapter_title or "（无，这是最后一章）",
            chapter_content_or_summary=request.chapter_content,
        )

        t0 = time.time()
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": CR_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=2048,
                temperature=0.7,
            )
        except Exception as e:
            logger.warning("chapter_review failed provider=deepseek model=%s error=%r",
                           self.model, str(e))
            raise

        latency = time.time() - t0
        tokens_in = getattr(resp.usage, "prompt_tokens", 0) if resp.usage else 0
        tokens_out = getattr(resp.usage, "completion_tokens", 0) if resp.usage else 0
        logger.info("chapter_review completed latency=%.1fs tokens_in=%d tokens_out=%d",
                    latency, tokens_in, tokens_out)

        content = resp.choices[0].message.content or "{}"
        data = _extract_json_ds(content)

        return ChapterReviewResponse(
            main_argument=data.get("main_argument", ""),
            key_takeaways=data.get("key_takeaways", []),
            connection_to_previous=data.get("connection_to_previous", ""),
            preview_next=data.get("preview_next", ""),
        )

    async def summarize_chapter(self, chapter_title: str, content: str,
                                max_length: int = 1500) -> str:
        chars = len(content)
        logger.info("summarize_chapter chapter=%r chars=%d",
                    chapter_title[:60], chars)
        user_prompt = CS_USER.format(
            chapter_title=chapter_title,
            chapter_content=content[:15000],
        )
        t0 = time.time()
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": CS_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1024,
                temperature=0.3,
            )
        except Exception as e:
            logger.warning("summarize_chapter failed provider=deepseek model=%s error=%r",
                           self.model, str(e))
            raise
        latency = time.time() - t0
        logger.info("summarize_chapter completed latency=%.1fs", latency)
        return resp.choices[0].message.content or ""

    async def recognize_structure(self, first_pages_text: str,
                                  total_pages: int) -> list[dict]:
        logger.info("recognize_structure pages=%d", total_pages)
        user_prompt = SR_USER.format(
            total_pages=total_pages,
            first_pages_text=first_pages_text[:5000],
        )
        t0 = time.time()
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SR_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1024,
                temperature=0.3,
            )
        except Exception as e:
            logger.warning("recognize_structure failed provider=deepseek model=%s error=%r",
                           self.model, str(e))
            raise
        latency = time.time() - t0
        content = resp.choices[0].message.content or "{}"
        data = _extract_json_ds(content)
        chapters = data.get("chapters", [])
        logger.info("recognize_structure completed latency=%.1fs returned=%d chapters",
                    latency, len(chapters))
        return chapters
