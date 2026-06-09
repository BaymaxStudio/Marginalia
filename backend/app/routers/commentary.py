"""评论生成接口

POST /api/commentary/paragraph   段评（六角色选 2-3 位）
POST /api/commentary/chapter     章评（领读学长主讲）
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.logger import get_logger
from app.models import (
    CommentaryRequest,
    CommentaryResponse,
    PersonaComment,
    ChapterReviewRequest,
    ChapterReviewResponse,
)
from app.services.ai_adapter import create_adapter
from app.services.ai_adapter.base import (
    CommentaryRequest as AICommentaryRequest,
    ChapterReviewRequest as AIChapterReviewRequest,
)
from app.services.cache import get_cached, set_cache
from app.services.settings_service import get_ai_config
from app.database import get_connection

router = APIRouter(prefix="/commentary", tags=["commentary"])
logger = get_logger("ai_adapter")

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"


def _load_structure(doc_id: str) -> dict:
    conn = get_connection()
    row = conn.execute("SELECT json_path FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "文档不存在")
    json_path = Path(row["json_path"])
    if not json_path.exists():
        raise HTTPException(404, "文档结构文件缺失")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _find_paragraph_context(structure: dict, paragraph_id: str) -> dict | None:
    """在文档结构中查找段落及其上下文（前后段 + 章节标题）。"""
    chapters = structure.get("chapters", [])
    all_paragraphs = []
    for ch in chapters:
        for sec in ch.get("sections", []):
            for p in sec.get("paragraphs", []):
                all_paragraphs.append({
                    "paragraph": p,
                    "chapter_title": ch["title"],
                    "chapter_id": ch["id"],
                })

    for i, item in enumerate(all_paragraphs):
        if item["paragraph"]["id"] == paragraph_id:
            prev_text = all_paragraphs[i - 1]["paragraph"]["text"] if i > 0 else None
            next_text = all_paragraphs[i + 1]["paragraph"]["text"] if i + 1 < len(all_paragraphs) else None
            return {
                "current_paragraph": item["paragraph"]["text"],
                "previous_paragraph": prev_text,
                "next_paragraph": next_text,
                "chapter_title": item["chapter_title"],
                "chapter_id": item["chapter_id"],
                "document_title": structure.get("title", ""),
            }
    return None


# ---- 段评 ----

@router.post("/paragraph")
async def paragraph_commentary(body: CommentaryRequest):
    structure = _load_structure(body.document_id)
    ctx = _find_paragraph_context(structure, body.paragraph_id)
    if not ctx:
        raise HTTPException(404, f"段落 {body.paragraph_id} 不存在")

    # 查缓存
    excluded_key = ",".join(sorted(body.excluded_personas)) if body.excluded_personas else "none"
    cache_key = (body.document_id, body.paragraph_id, excluded_key)
    cached = get_cached("paragraph_commentary", *cache_key)
    ai_cfg = get_ai_config()
    if cached:
        t_cache = time.time()
        data = json.loads(cached)
        logger.info("paragraph_commentary para=%s cache=hit latency=%.3fs",
                    body.paragraph_id, time.time() - t_cache)
        return CommentaryResponse(
            selected_personas=data["selected_personas"],
            comments=[PersonaComment(**c) for c in data["comments"]],
            from_cache=True,
        )

    # AI 调用
    logger.info("paragraph_commentary provider=%s model=%s para=%s cache=miss",
                ai_cfg["provider"],
                ai_cfg.get("commentary_model") or ai_cfg.get("model", "unknown"),
                body.paragraph_id)
    adapter = create_adapter()
    ai_req = AICommentaryRequest(
        document_title=ctx["document_title"],
        chapter_title=ctx["chapter_title"],
        previous_paragraph=ctx["previous_paragraph"],
        current_paragraph=ctx["current_paragraph"],
        next_paragraph=ctx["next_paragraph"],
        excluded_personas=body.excluded_personas,
    )
    ai_resp = await adapter.paragraph_commentary(ai_req)

    # 写缓存
    cache_data = {
        "selected_personas": ai_resp.selected_personas,
        "comments": [c.model_dump() for c in ai_resp.comments],
    }
    set_cache("paragraph_commentary", json.dumps(cache_data, ensure_ascii=False), *cache_key)

    return CommentaryResponse(
        selected_personas=ai_resp.selected_personas,
        comments=[
            PersonaComment(
                persona=c.persona,
                avatar={
                    "领读学长": "guide",
                    "术语侦探": "detective",
                    "批判者": "critic",
                    "联想家": "connector",
                    "文化翻译官": "translator",
                    "历史档案员": "archivist",
                }.get(c.persona, "default"),
                comment=c.comment,
            )
            for c in ai_resp.comments
        ],
        from_cache=False,
    )


# ---- 章评 ----

SUMMARY_THRESHOLD = 12000


@router.post("/chapter")
async def chapter_review(body: ChapterReviewRequest):
    structure = _load_structure(body.document_id)
    chapters = structure.get("chapters", [])

    chapter = next((ch for ch in chapters if ch["id"] == body.chapter_id), None)
    if not chapter:
        raise HTTPException(404, f"章节 {body.chapter_id} 不存在")

    # 组装章节全文
    chapter_text_parts = []
    for sec in chapter.get("sections", []):
        if sec.get("title"):
            chapter_text_parts.append(f"## {sec['title']}")
        for p in sec.get("paragraphs", []):
            chapter_text_parts.append(p["text"])

    chapter_content = "\n\n".join(chapter_text_parts)

    # 查缓存（包含 summarized 标记在键中，截断和摘要不共享缓存）
    needs_summary = len(chapter_content) > SUMMARY_THRESHOLD
    cache_suffix = "_summary" if needs_summary else "_full"
    cached = get_cached("chapter_review", body.document_id, body.chapter_id + cache_suffix)
    ai_cfg = get_ai_config()
    if cached:
        t_cache = time.time()
        data = json.loads(cached)
        logger.info("chapter_review chapter=%s cache=hit latency=%.3fs",
                    body.chapter_id, time.time() - t_cache)
        return ChapterReviewResponse(**data, from_cache=True)

    logger.info("chapter_review provider=%s model=%s chapter=%s cache=miss",
                ai_cfg["provider"],
                ai_cfg.get("commentary_model") or ai_cfg.get("model", "unknown"),
                body.chapter_id)

    # 找前/后章标题
    ch_idx = chapters.index(chapter)
    prev_title = chapters[ch_idx - 1]["title"] if ch_idx > 0 else None
    next_title = chapters[ch_idx + 1]["title"] if ch_idx + 1 < len(chapters) else None

    adapter = create_adapter()
    summarized = False

    # 超长章节：先摘要压缩
    if needs_summary:
        try:
            chapter_content = await adapter.summarize_chapter(
                chapter_title=chapter["title"],
                content=chapter_content,
            )
            summarized = True
        except NotImplementedError:
            chapter_content = chapter_content[:SUMMARY_THRESHOLD]
        except Exception:
            chapter_content = chapter_content[:SUMMARY_THRESHOLD]

    ai_req = AIChapterReviewRequest(
        document_title=structure.get("title", ""),
        chapter_title=chapter["title"],
        chapter_number=ch_idx + 1,
        total_chapters=len(chapters),
        previous_chapter_title=prev_title,
        next_chapter_title=next_title,
        chapter_content=chapter_content,
    )
    ai_resp = await adapter.chapter_review(ai_req)

    # 写缓存
    cache_data = {
        "persona": "领读学长",
        "main_argument": ai_resp.main_argument,
        "key_takeaways": ai_resp.key_takeaways,
        "connection_to_previous": ai_resp.connection_to_previous,
        "preview_next": ai_resp.preview_next,
        "summarized": summarized,
    }
    set_cache("chapter_review", json.dumps(cache_data, ensure_ascii=False),
              body.document_id, body.chapter_id + cache_suffix)

    return ChapterReviewResponse(
        persona="领读学长",
        main_argument=ai_resp.main_argument,
        key_takeaways=ai_resp.key_takeaways,
        connection_to_previous=ai_resp.connection_to_previous,
        preview_next=ai_resp.preview_next,
        summarized=summarized,
        from_cache=False,
    )
