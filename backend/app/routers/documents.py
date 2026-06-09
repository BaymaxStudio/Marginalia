"""文档管理接口

POST   /api/documents/upload          上传 PDF
GET    /api/documents                  文档列表
GET    /api/documents/{id}/structure   文档目录结构
GET    /api/documents/{id}/chapters/{ch_id}  章节内容
DELETE /api/documents/{id}             删除文档
GET    /api/documents/{id}/images/{filename} 图片资源
"""

import json
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.database import get_connection

router = APIRouter(prefix="/documents", tags=["documents"])

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"

# ---- 辅助函数 ----

def _doc_exists(doc_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _get_progress_percent(doc_id: str) -> float:
    conn = get_connection()
    row = conn.execute(
        "SELECT chapter_status FROM reading_progress WHERE document_id = ?",
        (doc_id,),
    ).fetchone()
    conn.close()
    if not row:
        return 0.0
    try:
        status = json.loads(row["chapter_status"])
        completed = sum(1 for v in status.values() if v == "completed")
        return round(completed / max(len(status), 1) * 100, 1)
    except (json.JSONDecodeError, ZeroDivisionError):
        return 0.0


# ---- 上传 ----

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "请提供文件名")

    file_bytes = await file.read()

    from app.services.pdf_parser import ValidationError, parse_pdf

    try:
        result = await parse_pdf(file_bytes, file.filename)
    except ValidationError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(422, f"PDF 解析失败：{e}")

    return {
        "document_id": result["doc_id"],
        "title": result["title"],
        "total_chapters": result["total_chapters"],
        "total_pages": result["total_pages"],
        "status": "ready",
    }


# ---- 列表 ----

@router.get("")
async def list_documents():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, title, filename, upload_time, total_chapters FROM documents ORDER BY upload_time DESC"
    ).fetchall()
    conn.close()

    documents = []
    for row in rows:
        d = dict(row)
        d["reading_progress_percent"] = _get_progress_percent(d["id"])
        documents.append(d)

    return {"documents": documents}


# ---- 目录结构 ----

@router.get("/{doc_id}/structure")
async def get_structure(doc_id: str):
    doc = _doc_exists(doc_id)
    if not doc:
        raise HTTPException(404, "文档不存在")

    json_path = Path(doc["json_path"])
    if not json_path.exists():
        raise HTTPException(404, "文档结构文件缺失")

    with open(json_path, "r", encoding="utf-8") as f:
        structure = json.load(f)

    return {
        "id": structure["id"],
        "title": structure["title"],
        "chapters": [
            {
                "id": ch["id"],
                "title": ch["title"],
                "sections": [
                    {"id": sec["id"], "title": sec.get("title", "")}
                    for sec in ch.get("sections", [])
                ],
            }
            for ch in structure.get("chapters", [])
        ],
    }


# ---- 章节内容 ----

@router.get("/{doc_id}/chapters/{chapter_id}")
async def get_chapter(doc_id: str, chapter_id: str):
    doc = _doc_exists(doc_id)
    if not doc:
        raise HTTPException(404, "文档不存在")

    json_path = Path(doc["json_path"])
    if not json_path.exists():
        raise HTTPException(404, "文档结构文件缺失")

    with open(json_path, "r", encoding="utf-8") as f:
        structure = json.load(f)

    chapter = next(
        (ch for ch in structure.get("chapters", []) if ch["id"] == chapter_id),
        None,
    )
    if not chapter:
        raise HTTPException(404, f"章节 {chapter_id} 不存在")

    # 筛选属于该章节的图片
    chapter_images = []
    for img in structure.get("images", []):
        # 按 after_paragraph 段落所属章来判断
        for sec in chapter.get("sections", []):
            for p in sec.get("paragraphs", []):
                if p["id"] == img.get("after_paragraph"):
                    chapter_images.append({
                        "id": img["id"],
                        "url": f"/api/documents/{doc_id}/images/{img['filename']}",
                        "after_paragraph": img["after_paragraph"],
                        "caption": img.get("caption", ""),
                    })
                    break

    return {
        "chapter_id": chapter["id"],
        "title": chapter["title"],
        "sections": [
            {
                "id": sec["id"],
                "title": sec.get("title", ""),
                "paragraphs": sec.get("paragraphs", []),
            }
            for sec in chapter.get("sections", [])
        ],
        "images": chapter_images,
    }


# ---- 图片资源 ----

@router.get("/{doc_id}/images/{filename}")
async def serve_image(doc_id: str, filename: str):
    doc = _doc_exists(doc_id)
    if not doc:
        raise HTTPException(404, "文档不存在")

    filepath = DOCUMENTS_DIR / doc_id / "images" / filename
    if not filepath.exists():
        raise HTTPException(404, "图片不存在")

    return FileResponse(str(filepath))


# ---- 删除 ----

@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    doc = _doc_exists(doc_id)
    if not doc:
        raise HTTPException(404, "文档不存在")

    # 删除文件
    doc_dir = DOCUMENTS_DIR / doc_id
    if doc_dir.exists():
        shutil.rmtree(doc_dir)

    # 删除数据库记录（CASCADE 自动清理 vocabulary / progress）
    conn = get_connection()
    conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()

    return {"status": "deleted"}
