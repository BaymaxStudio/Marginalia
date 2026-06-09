"""ECDICT 词典查询服务

本地 SQLite 数据库，约 340 万词条（含变形），MIT 协议
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from nltk.stem import WordNetLemmatizer

from app.logger import get_logger

logger = get_logger("dictionary")

DB_PATH = Path(__file__).parent.parent.parent / "data" / "ecdict.db"

_lemmatizer = WordNetLemmatizer()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def lemmatize(word: str, pos: str = "n") -> str:
    """词形还原：economies → economy, running → run

    pos 可选: 'n' (名词), 'v' (动词), 'a' (形容词), 'r' (副词)
    先尝试所有可能词性，取还原后不同的结果。
    """
    candidates = set()
    for tag in ("n", "v", "a", "r"):
        lemma = _lemmatizer.lemmatize(word, pos=tag)
        candidates.add(lemma)

    # 如果所有词性返回相同结果且不等于原词，返回它
    # 否则返回小写原词作为fallback
    for lemma in candidates:
        if lemma != word:
            return lemma
    return word.lower()


def query(word: str) -> tuple[list[dict], str | None]:
    """查询词典，返回 (义项列表, 音标)。若查不到返回 (空列表, None)。"""
    conn = _get_conn()
    cursor = conn.cursor()

    # 先查原词，再查小写，再查 lemma
    for candidate in (word, word.lower(), lemmatize(word)):
        cursor.execute(
            "SELECT word, phonetic, definition, translation, pos FROM stardict WHERE word = ?",
            (candidate,),
        )
        row = cursor.fetchone()
        if row:
            break

    conn.close()

    if not row:
        logger.info("lookup word=%s lemma=%s found=no -> AI-only mode",
                    word, lemmatize(word))
        return [], None

    logger.debug("lookup word=%s lemma=%s found=yes entries=%d",
                 word, row["word"], len((row["definition"] or "").split("\n")))

    # 解析义项
    defs_en = (row["definition"] or "").split("\n")
    defs_zh = (row["translation"] or "").split("\n")
    pos_str = row["pos"] or ""

    # 解析词性（pos 字段格式如 "n:100,v:50" 或 "n."）
    pos_list = []
    raw_pos = pos_str.split(",") if pos_str else []
    for p in raw_pos:
        p = p.split(":")[0].strip()
        if p and not p.endswith("."):
            p = p + "."
        if p:
            pos_list.append(p)

    entries = []
    for i in range(max(len(defs_en), len(defs_zh))):
        entries.append({
            "index": i,
            "pos": pos_list[min(i, len(pos_list) - 1)] if pos_list else "",
            "en": defs_en[i].strip() if i < len(defs_en) else "",
            "zh": defs_zh[i].strip() if i < len(defs_zh) else "",
        })

    return entries, row["phonetic"]


def query_raw(word: str) -> dict | None:
    """返回完整词典行（用于查不到时的诊断）。"""
    conn = _get_conn()
    cursor = conn.cursor()
    for candidate in (word, word.lower(), lemmatize(word)):
        cursor.execute("SELECT * FROM stardict WHERE word = ?", (candidate,))
        row = cursor.fetchone()
        if row:
            conn.close()
            return dict(row)
    conn.close()
    return None
