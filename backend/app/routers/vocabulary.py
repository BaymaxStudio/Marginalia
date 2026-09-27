"""生词本接口

GET /api/vocabulary   按文档分组、支持排序的词汇列表
"""

import json

from fastapi import APIRouter, Query

from app.database import get_connection

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])

SORT_MAP = {
    "time_desc": "last_lookup_time DESC",
    "time_asc": "last_lookup_time ASC",
    "alpha_asc": "word_lemma ASC",
    "alpha_desc": "word_lemma DESC",
}


@router.get("")
async def list_vocabulary(
    document_id: str = Query(None),
    sort: str = Query("time_desc"),
):
    order = SORT_MAP.get(sort, "last_lookup_time DESC")
    conn = get_connection()

    if document_id:
        rows = conn.execute(
            f"""SELECT * FROM vocabulary
                WHERE document_id = ?
                ORDER BY {order}""",
            (document_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT * FROM vocabulary ORDER BY {order}"
        ).fetchall()

    conn.close()

    words = []
    for r in rows:
        r = dict(r)
        entries = json.loads(r.get("dictionary_entries", "[]"))
        words.append({
            "id": r["id"],
            "document_id": r.get("document_id"),
            "paragraph_id": r.get("paragraph_id"),
            "word_lemma": r["word_lemma"],
            "phonetic": r.get("phonetic"),
            "sentence": r.get("sentence", ""),
            "selected_meaning": entries[r["selected_index"]].get("zh", "")
                if entries and r.get("selected_index") is not None
                and 0 <= r["selected_index"] < len(entries) else None,
            "ai_explanation": r.get("ai_explanation"),
            "domain": r.get("domain"),
            "lookup_count": r.get("lookup_count", 1),
            "last_lookup_time": str(r.get("last_lookup_time", "")),
        })

    return {"total": len(words), "words": words}
