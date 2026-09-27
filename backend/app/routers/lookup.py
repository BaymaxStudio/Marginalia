"""词义查询接口

GET  /api/dictionary/{word}     纯本地词典查询（毫秒级）
POST /api/lookup/ai             AI 语境解释（异步）
"""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, HTTPException

from app.logger import get_logger
from app.models import LookupRequest, LookupResponse, DictionaryEntry, AIContext, AIExpand
from app.services.dictionary import query as dict_query, lemmatize
from app.services.ai_adapter import NoAPIKeyError, create_adapter
from app.services.ai_adapter.base import WordLookupRequest as AIWordLookupRequest
from app.services.cache import get_cached, set_cache
from app.services.settings_service import get_ai_config

router = APIRouter(tags=["lookup"])
logger = get_logger("ai_adapter")


@router.get("/dictionary/{word:path}")
async def dictionary_lookup(word: str):
    """本地词典查询，毫秒级返回。"""
    entries, phonetic = dict_query(word)
    lemma = lemmatize(word)

    if not entries:
        return {
            "word_lemma": lemma,
            "phonetic": None,
            "dictionary_entries": [],
            "found": False,
        }

    return {
        "word_lemma": entries[0].get("_word", lemma) if entries else lemma,
        "phonetic": phonetic,
        "dictionary_entries": [
            {"index": e["index"], "pos": e.get("pos", ""),
             "en": e.get("en", ""), "zh": e.get("zh", "")}
            for e in entries
        ],
        "found": True,
    }


@router.post("/lookup/ai")
async def ai_lookup(body: LookupRequest):
    """AI 语境解释，异步返回。"""
    # 1. 词典查询
    entries, phonetic = dict_query(body.word)
    if not entries:
        return LookupResponse(
            word_lemma=lemmatize(body.word),
            phonetic=None,
            dictionary_entries=[],
            ai_context=None,
            from_cache=False,
        )

    dict_entries = [
        {"index": e["index"], "pos": e.get("pos", ""),
         "en": e.get("en", ""), "zh": e.get("zh", "")}
        for e in entries
    ]

    # 2. 查缓存
    lemma = lemmatize(body.word)
    # 同一段落可能多次使用同一个词；语境和展开模式必须分别缓存。
    cache_key = (body.document_id, body.paragraph_id, lemma, body.sentence, body.mode)
    cached = get_cached("word_lookup", *cache_key)
    if cached:
        t_cache = time.time()
        data = json.loads(cached)
        ai_context = AIContext(**data["ai_context"])
        _add_to_vocabulary(body, lemma, phonetic, dict_entries, ai_context)
        logger.info("word_lookup word=%s cache=hit latency=%.3fs",
                    lemma, time.time() - t_cache)
        return LookupResponse(
            word_lemma=lemma, phonetic=phonetic,
            dictionary_entries=[DictionaryEntry(**d) for d in dict_entries],
            ai_context=ai_context,
            ai_expand=AIExpand(**data["ai_expand"]) if data.get("ai_expand") else None,
            from_cache=True,
        )

    # 3. AI 调用
    try:
        ai_cfg = get_ai_config()
        logger.info("word_lookup provider=%s model=%s word=%s cache=miss",
                    ai_cfg["provider"],
                    ai_cfg.get("lookup_model") or ai_cfg.get("model", "unknown"),
                    lemma)
        adapter = create_adapter()
        ai_req = AIWordLookupRequest(
            word=lemma,
            sentence=body.sentence,
            paragraph="",  # 仅句子足够
            dictionary_entries=dict_entries,
            mode=body.mode,
        )
        ai_resp = await adapter.word_lookup(ai_req)

        ai_context = AIContext(
            selected_index=ai_resp.selected_index,
            explanation=ai_resp.explanation,
            is_technical_term=ai_resp.is_technical_term,
            domain=ai_resp.domain,
        )

        ai_expand = None
        if body.mode == "expand" and ai_resp.memory_hint:
            ai_expand = AIExpand(
                memory_hint=ai_resp.memory_hint,
                confusion_note=ai_resp.confusion_note,
            )

        # 4. 写缓存
        cache_data = {
            "ai_context": {
                "selected_index": ai_resp.selected_index,
                "explanation": ai_resp.explanation,
                "is_technical_term": ai_resp.is_technical_term,
                "domain": ai_resp.domain,
            },
            "ai_expand": {
                "memory_hint": ai_resp.memory_hint,
                "confusion_note": ai_resp.confusion_note,
            } if ai_expand else None,
        }
        set_cache("word_lookup", json.dumps(cache_data), *cache_key)

        # 5. 写入生词本
        _add_to_vocabulary(body, lemma, phonetic, dict_entries, ai_resp)

        return LookupResponse(
            word_lemma=lemma, phonetic=phonetic,
            dictionary_entries=[DictionaryEntry(**d) for d in dict_entries],
            ai_context=ai_context,
            ai_expand=ai_expand,
            from_cache=False,
        )

    except Exception as e:
        # AI 调用失败时仍返回词典数据，并把原因交给前端显示
        if isinstance(e, NoAPIKeyError):
            ai_error = str(e)
        else:
            logger.warning("word_lookup failed word=%s error=%r", lemma, e)
            ai_error = "AI 解释暂时不可用，请稍后重试。"
        return LookupResponse(
            word_lemma=lemma, phonetic=phonetic,
            dictionary_entries=[DictionaryEntry(**d) for d in dict_entries],
            ai_context=None,
            ai_error=ai_error,
            from_cache=False,
        )


def _add_to_vocabulary(body, lemma, phonetic, dict_entries, ai_resp):
    """写入生词本。"""
    import uuid
    from app.database import get_connection

    conn = get_connection()
    existing = conn.execute(
        "SELECT id, lookup_count FROM vocabulary WHERE document_id = ? AND word_lemma = ?",
        (body.document_id, lemma),
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE vocabulary SET lookup_count = ?, last_lookup_time = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (existing["lookup_count"] + 1, existing["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO vocabulary
               (id, document_id, paragraph_id, word_original, word_lemma,
                sentence, phonetic, dictionary_entries, ai_explanation,
                selected_index, is_technical_term, domain)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                uuid.uuid4().hex[:12],
                body.document_id,
                body.paragraph_id,
                body.word,
                lemma,
                body.sentence,
                phonetic,
                json.dumps(dict_entries, ensure_ascii=False),
                ai_resp.explanation,
                ai_resp.selected_index,
                ai_resp.is_technical_term,
                ai_resp.domain,
            ),
        )
    conn.commit()
    conn.close()
