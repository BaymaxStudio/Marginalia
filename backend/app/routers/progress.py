"""阅读进度接口

GET /api/progress/{doc_id}   获取阅读进度
PUT /api/progress/{doc_id}   更新阅读进度
"""

import json

from fastapi import APIRouter, HTTPException

from app.logger import get_logger
from app.models import ProgressUpdateRequest, ProgressResponse
from app.database import get_connection

router = APIRouter(prefix="/progress", tags=["progress"])
logger = get_logger("progress")


@router.get("/{doc_id}")
async def get_progress(doc_id: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM reading_progress WHERE document_id = ?",
        (doc_id,),
    ).fetchone()
    conn.close()

    if not row:
        return {
            "last_paragraph_id": None,
            "last_read_time": None,
            "chapter_status": {},
        }

    return {
        "last_paragraph_id": row["last_paragraph_id"],
        "last_read_time": row["last_read_time"],
        "chapter_status": json.loads(row["chapter_status"] or "{}"),
    }


@router.put("/{doc_id}")
async def update_progress(doc_id: str, body: ProgressUpdateRequest):
    conn = get_connection()

    # 验证文档存在
    doc = conn.execute("SELECT id FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        conn.close()
        raise HTTPException(404, "文档不存在")

    conn.execute(
        """INSERT OR REPLACE INTO reading_progress
           (document_id, last_paragraph_id, last_read_time, chapter_status)
           VALUES (?, ?, CURRENT_TIMESTAMP, ?)""",
        (doc_id, body.last_paragraph_id, json.dumps(body.chapter_status, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()

    status_summary = ",".join(
        f"{k}={v}" for k, v in sorted(body.chapter_status.items())
        if v != "unread"
    ) or "all_unread"
    logger.debug("save doc=%s para=%s chapter_status=[%s]",
                 doc_id, body.last_paragraph_id, status_summary)

    return {"status": "saved"}
