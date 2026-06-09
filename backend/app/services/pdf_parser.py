"""PDF 解析管线

处理流程：文件校验 → 文本提取 → 图表截取 → 结构识别 → 清洗修正 → 组装存储
"""

from __future__ import annotations

import io
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from app.logger import get_logger

logger = get_logger("pdf_parser")

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
SCAN_THRESHOLD = 50  # chars/page avg


# ---------------------------------------------------------------------------
# 步骤 1：文件校验
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """文件校验失败"""


def validate_pdf(file_bytes: bytes, filename: str) -> None:
    """校验上传文件：格式魔数、大小、加密、扫描版。不通过则抛 ValidationError。"""
    if not filename.lower().endswith(".pdf"):
        raise ValidationError("仅支持 PDF 格式，请上传 .pdf 文件")

    if len(file_bytes) < 5 or file_bytes[:5] != b"%PDF-":
        raise ValidationError("文件格式无效：非 PDF 文件")

    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValidationError(f"文件过大（{len(file_bytes) / 1024 / 1024:.1f}MB），上限 50MB")

    doc = fitz.open(stream=file_bytes, filetype="pdf")

    if doc.is_encrypted:
        doc.close()
        raise ValidationError("请上传未加密的 PDF，不支持需要密码的文档")

    total_chars = 0
    pages_to_check = min(5, len(doc))
    for i in range(pages_to_check):
        total_chars += len(doc[i].get_text())

    doc.close()

    avg_chars_per_page = total_chars / pages_to_check if pages_to_check > 0 else 0
    if avg_chars_per_page < SCAN_THRESHOLD:
        raise ValidationError(
            f"暂不支持扫描版 PDF（平均每页 {avg_chars_per_page:.0f} 字符）。"
            "请使用数字版 PDF（由文字处理器生成的文档）。"
        )


# ---------------------------------------------------------------------------
# 步骤 2：文本提取（pymupdf4llm）
# ---------------------------------------------------------------------------

def extract_markdown(pdf_path: str) -> str:
    """从 PDF 文件路径提取 Markdown 文本。pymupdf4llm 要求传入文件路径或 PyMuPDF Document。"""
    return __import__("pymupdf4llm").to_markdown(pdf_path)


# ---------------------------------------------------------------------------
# 步骤 3：图表截取
# ---------------------------------------------------------------------------

def extract_images(pdf_path: str, doc_id: str) -> list[dict]:
    """提取 PDF 中嵌入的图片，保存为 PNG，返回图片信息列表。

    每条：{"id": "img_xxx", "filename": "img_001.png", "page": 3, "y": 450.0}
    """
    doc = fitz.open(pdf_path)
    img_dir = DOCUMENTS_DIR / doc_id / "images"
    os.makedirs(img_dir, exist_ok=True)

    images = []
    img_counter = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)

        for img in image_list:
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
            except Exception:
                continue

            if pix.n >= 5:
                pix = fitz.Pixmap(fitz.csRGB, pix)

            img_counter += 1
            filename = f"img_{page_num + 1:03d}_{img_counter:04d}.png"
            filepath = img_dir / filename

            if pix.alpha:
                pix = fitz.Pixmap(pix, 0)  # 去除 alpha 通道

            pix.save(str(filepath))

            # 获取图片在页面中的位置
            img_rect = page.get_image_rects(img)
            y_pos = img_rect[0][1] if img_rect else 0

            images.append({
                "id": f"img_ch_{page_num + 1}_{img_counter:03d}",
                "filename": filename,
                "page": page_num + 1,
                "y": y_pos,
            })

    doc.close()
    return images


# ---------------------------------------------------------------------------
# 步骤 4 & 5：结构识别 + 文本清洗
# ---------------------------------------------------------------------------

def _extract_headers_footers(pdf_path: str) -> tuple[set[str], set[str]]:
    """从 PDF 各页首尾提取跨页重复行作为候选页眉/页脚。"""
    doc = fitz.open(pdf_path)
    page_count = len(doc)
    if page_count < 3:
        doc.close()
        return set(), set()

    top_lines: list[set[str]] = []
    bottom_lines: list[set[str]] = []

    for page_num in range(page_count):
        blocks = doc[page_num].get_text("blocks")
        blocks.sort(key=lambda b: b[1])

        page_height = doc[page_num].rect.height
        top_set = set()
        bottom_set = set()

        for b in blocks:
            text = b[4].strip()
            if not text:
                continue
            y0 = b[1]
            if y0 < page_height * 0.12:
                clean = re.sub(r"\s+", " ", text).strip()
                if len(clean) < 120:
                    top_set.add(clean)
            if y0 > page_height * 0.88:
                clean = re.sub(r"\s+", " ", text).strip()
                if len(clean) < 120:
                    bottom_set.add(clean)

        top_lines.append(top_set)
        bottom_lines.append(bottom_set)

    doc.close()

    # 出现在 >= 60% 页面的行视为页眉/页脚
    threshold = max(2, int(page_count * 0.6))
    header_candidates = set()
    footer_candidates = set()

    all_top = [line for s in top_lines for line in s]
    all_bottom = [line for s in bottom_lines for line in s]

    for line in set(all_top):
        if sum(1 for s in top_lines if line in s) >= threshold:
            header_candidates.add(line)

    for line in set(all_bottom):
        if sum(1 for s in bottom_lines if line in s) >= threshold:
            footer_candidates.add(line)

    return header_candidates, footer_candidates


def _detect_headings_and_paragraphs(
    md_text: str,
    headers: set[str],
    footers: set[str],
) -> list[dict]:
    """将 Markdown 文本解析为章节-段落层级结构。

    返回列表，每项为 {"type": "heading", "level": n, "text": "..."} 或
    {"type": "paragraph", "id": "para_x_y_zzz", "text": "..."} 或
    {"type": "image_placeholder", "id": "img_xxx"}。
    """
    lines = md_text.split("\n")
    elements: list[dict] = []

    # 章节/节计数器
    ch_num = 0
    sec_num = 0
    para_in_sec = 0

    # 段落缓冲区
    para_lines: list[str] = []

    def flush_paragraph():
        nonlocal para_in_sec
        text = " ".join(para_lines)
        text = re.sub(r"\s{2,}", " ", text).strip()

        # 跳过空段落和仅含页眉/页脚文本的段落
        if not text or len(text) < 5:
            para_lines.clear()
            return
        if text in headers or text in footers:
            para_lines.clear()
            return
        # 跳过纯页码
        if re.match(r"^\d{1,4}$", text):
            para_lines.clear()
            return

        if ch_num == 0:
            ch_num_ = 1
            sec_num_ = 1
        else:
            ch_num_ = ch_num
            sec_num_ = max(sec_num, 1)

        para_in_sec += 1
        pid = f"para_{ch_num_}_{sec_num_}_{para_in_sec:03d}"
        elements.append({"type": "paragraph", "id": pid, "text": text})
        para_lines.clear()

    # TOC 状态机：IN_TOC 状态下 ## 标题降级为段落
    _TOC_NORMAL = 0
    _TOC_INSIDE = 1
    toc_state = _TOC_NORMAL

    for line in lines:
        stripped = line.strip()

        # 跳过页眉/页脚行
        if stripped in headers or stripped in footers:
            continue
        if re.match(r"^\d{1,4}$", stripped):  # 纯页码
            continue

        # 退出条件 B：在 IN_TOC 状态下遇到长段落（正文特征）
        if toc_state == _TOC_INSIDE and len(stripped) > 200:
            toc_state = _TOC_NORMAL
            logger.debug("TOC filter: exited by long paragraph (%d chars)", len(stripped))

        # 检测 Markdown 标题
        heading_match = re.match(r"^(#{1,4})\s+(.+)", stripped)
        if heading_match:
            flush_paragraph()

            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            title = re.sub(r"\s+", " ", title)

            # 若二级标题包含 CHAPTER 标记，提升为一级（章节级）
            if level == 2 and re.match(r"^(?:Chapter|CHAPTER|C H A P T E R)\s*\d+", title):
                level = 1

            # --- TOC 状态机：仅在 ## 级标题（level==2）上工作 ---
            if level == 2:
                if toc_state == _TOC_NORMAL:
                    # 入口条件：检测到 Contents / Table of Contents
                    if re.match(r'^(?:contents|table\s+of\s+contents|目录)$',
                                title.strip().lower()):
                        toc_state = _TOC_INSIDE
                        logger.debug("TOC filter: entered at '%s'", title)

                elif toc_state == _TOC_INSIDE:
                    # 退出条件 A：首章标题白名单
                    if re.match(
                        r'^(?:chapter\s+\d|CHAPTER\s+\d|part\s+[ivxlcdm\d]|'
                        r'introduction|preface|foreword|prologue|'
                        r'第[一二三四五六七八九十\d]+[章篇])',
                        title, re.IGNORECASE
                    ):
                        toc_state = _TOC_NORMAL
                        logger.debug("TOC filter: exited at '%s'", title)
                        # 当前标题按正常标题处理（不降级）
                    else:
                        # 降级：标题 → 段落
                        logger.debug("TOC filter: demoting '## %s' to paragraph", title)
                        elements.append({"type": "paragraph",
                                         "id": f"para_toc_{len(elements):04d}",
                                         "text": title})
                        continue
            # --------------------------------------------------------

            if level == 1:
                ch_num += 1
                sec_num = 0
                para_in_sec = 0
            elif level == 2:
                if ch_num == 0:
                    ch_num = 1
                sec_num += 1
                para_in_sec = 0
            elif level >= 3:
                if ch_num == 0:
                    ch_num = 1
                if sec_num == 0:
                    sec_num = 1
                para_in_sec = 0

            elements.append({"type": "heading", "level": level, "text": title})
            continue

        # 检测 "Chapter N" / "CHAPTER N" 等模式（非 Markdown 标题时）
        chapter_match = re.match(
            r"^(?:Chapter|CHAPTER|第)\s*(\d+|[A-Z]+)(?:[\s\.:：].*)?$",
            stripped,
        )
        if chapter_match and len(stripped) < 200:
            flush_paragraph()
            ch_num += 1
            sec_num = 0
            para_in_sec = 0
            elements.append({"type": "heading", "level": 1, "text": stripped})
            continue

        # 检测 "Part N" 模式
        part_match = re.match(r"^(?:Part|PART)\s+(\d+|[IVX]+)(?:[\s\.:：].*)?$", stripped)
        if part_match and len(stripped) < 60:
            flush_paragraph()
            ch_num += 1
            sec_num = 0
            para_in_sec = 0
            elements.append({"type": "heading", "level": 1, "text": stripped})
            continue

        # 空行 == 段落分隔
        if stripped == "":
            flush_paragraph()
        else:
            para_lines.append(stripped)

    flush_paragraph()
    return elements


def _fix_hyphenation(text: str) -> str:
    """修复英文连字符断行：interna-\ntional → international"""
    return re.sub(r"(\w+)-\s+(\w+)", lambda m: m.group(1) + m.group(2), text)


def _merge_cross_page_paragraphs(elements: list[dict]) -> list[dict]:
    """合并跨页段落：前一段不以句号结束，后一段以小写开头 → 合并。"""
    merged = []
    for i, el in enumerate(elements):
        if el["type"] != "paragraph":
            merged.append(el)
            continue

        if i > 0 and merged and merged[-1]["type"] == "paragraph":
            prev = merged[-1]
            if prev["text"] and not prev["text"].endswith((".", "!", "?", ":", '"', "'", ")", "]")) :
                if el["text"] and el["text"][0].islower():
                    prev["text"] = prev["text"] + " " + el["text"]
                    continue

        merged.append(el)

    return merged


def _strip_markdown_format(text: str) -> str:
    """移除 Markdown 粗体/斜体标记和多余空白。"""
    text = re.sub(r"\*{1,3}([^*]+?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+?)_{1,3}", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _fix_all_paragraphs(elements: list[dict]) -> list[dict]:
    """对所有段落和标题文本执行清洗。"""
    for el in elements:
        if el["type"] in ("paragraph", "heading"):
            el["text"] = _fix_hyphenation(el["text"])
            el["text"] = _strip_markdown_format(el["text"])
    return elements


# ---------------------------------------------------------------------------
# 步骤 6：组装 JSON
# ---------------------------------------------------------------------------

def _find_first_real_heading(elements: list[dict]) -> int:
    """找到第一个非元数据标题的索引。跳过 Authors, Acknowledgements 等。"""
    _meta_headings = {"authors", "acknowledgements", "acknowledgments",
                      "preface", "abstract", "about the author", "disclaimer",
                      "copyright", "published", "date", "version", "contents",
                      "table of contents", "dedication",
                      "cover", "title page", "also by", "notes", "index"}
    for i, el in enumerate(elements):
        if el["type"] == "heading":
            if el["text"].strip().lower() not in _meta_headings:
                return i
    # 如果所有标题都是元数据类型，返回第一个标题位置
    for i, el in enumerate(elements):
        if el["type"] == "heading":
            return i
    return len(elements)


def _build_structure(elements: list[dict], images: list[dict]) -> dict:
    """将元素列表组装为规范定义的层级 JSON 结构。

    改进处理：
    - 跳过首页元数据（日期、作者行等）
    - 当所有标题均为同级时，自动提升部分标题为章节级
    - 合并内容过少的小节
    """
    doc_title = "Untitled"
    chapters = []
    current_chapter = None
    current_section = None
    ch_idx = 0
    sec_idx = 0

    has_headings = any(el["type"] == "heading" for el in elements)

    if not has_headings:
        all_paragraphs = [el for el in elements if el["type"] == "paragraph"]
        if all_paragraphs:
            doc_title = _guess_title(all_paragraphs)
            chapters = [{
                "id": "ch_1", "title": doc_title,
                "page_start": 1, "page_end": 1,
                "sections": [{
                    "id": "sec_1_1", "title": "",
                    "paragraphs": [
                        {"id": p["id"], "text": p["text"], "page": 1}
                        for p in all_paragraphs
                    ],
                }],
            }]
        return {"id": "", "title": doc_title, "chapters": chapters}

    # 找到第一个非元数据标题用作文档标题
    _meta_headings = {"authors", "acknowledgements", "acknowledgments", "preface",
                      "abstract", "about the author", "disclaimer", "copyright",
                      "published", "date", "version", "contents",
                      "table of contents", "dedication", "cover",
                      "title page", "also by", "notes", "index"}
    for el in elements:
        if el["type"] == "heading":
            if el["text"].strip().lower() not in _meta_headings:
                doc_title = el["text"]
                break
    if doc_title == "Untitled":
        all_paras = [el for el in elements if el["type"] == "paragraph"]
        doc_title = _guess_title(all_paras)

    # 跳过首页元数据：第一个"实质"标题（非 Authors/Acknowledgements）之前的段落
    first_real_heading_idx = _find_first_real_heading(elements)
    metadata_patterns = [
        r"^Published\s", r"^January|February|March|April|May|June|July|August",
        r"^September|October|November|December", r"^\d{4}$", r"^\*Lead",
        r"^Our sincere thanks", r"^\*Lead authors?", r"^Author[s]?$",
        r"^By\s", r"^With\s", r"^©", r"^All rights reserved",
        r"^https?://", r"^DOI:", r"^arXiv:",
        r"^[\w.-]+@[\w.]+$",
        r"^Equal contribution", r"^Work done at",
        r"^Permission to (copy|make|reproduce)",
    ]
    skip_ids = set()
    for i in range(first_real_heading_idx):
        el = elements[i]
        if el["type"] == "paragraph":
            text = el["text"].strip()
            is_meta = any(re.match(pat, text) for pat in metadata_patterns)
            if is_meta and len(text) < 250:
                skip_ids.add(el["id"])

    # 额外：跳过包含 2+ 个 email 地址的行（作者行）
    for i in range(first_real_heading_idx):
        if i < len(elements) and elements[i]["type"] == "paragraph":
            text = elements[i]["text"]
            emails = re.findall(r"[\w.-]+@[\w.]+", text)
            if len(emails) >= 2 or len(text) < 10:
                skip_ids.add(elements[i]["id"])
                # 也跳过紧接着的一两段（通常也是作者信息）
                if i + 1 < len(elements) and elements[i + 1]["type"] == "paragraph":
                    if len(elements[i + 1]["text"]) < 200:
                        skip_ids.add(elements[i + 1]["id"])

    for el in elements:
        if el["type"] == "heading":
            if el["level"] == 1:
                if current_section and current_chapter:
                    current_chapter["sections"].append(current_section)
                if current_chapter:
                    chapters.append(current_chapter)

                ch_idx += 1
                sec_idx = 0
                current_chapter = {
                    "id": f"ch_{ch_idx}", "title": el["text"],
                    "page_start": 1, "page_end": 1, "sections": [],
                }
                current_section = None

            elif el["level"] >= 2:
                if current_chapter is None:
                    ch_idx += 1
                    current_chapter = {
                        "id": f"ch_{ch_idx}", "title": doc_title,
                        "page_start": 1, "page_end": 1, "sections": [],
                    }
                if current_section:
                    current_chapter["sections"].append(current_section)
                sec_idx += 1
                current_section = {
                    "id": f"sec_{ch_idx}_{sec_idx}",
                    "title": el["text"],
                    "paragraphs": [],
                }

        elif el["type"] == "paragraph":
            if el["id"] in skip_ids:
                continue
            if current_chapter is None:
                ch_idx += 1
                current_chapter = {
                    "id": f"ch_{ch_idx}", "title": doc_title,
                    "page_start": 1, "page_end": 1, "sections": [],
                }
            if current_section is None:
                sec_idx += 1
                current_section = {
                    "id": f"sec_{ch_idx}_{sec_idx}",
                    "title": "",
                    "paragraphs": [],
                }
            current_section["paragraphs"].append({
                "id": el["id"],
                "text": el["text"],
                "page": 1,
            })

    # 收尾
    if current_section and current_chapter:
        current_chapter["sections"].append(current_section)
    if current_chapter:
        chapters.append(current_chapter)

    # 清除空章节 + 合并内容少的小节，然后重新编号
    chapters = _postprocess_chapters(chapters)
    chapters = _strip_author_sections(chapters)
    chapters = _separate_back_matter(chapters)
    chapters = _renumber_chapters(chapters)

    return {"id": "", "title": doc_title, "chapters": chapters}


def _strip_author_sections(chapters: list[dict]) -> list[dict]:
    """移除作者/机构元数据 section：无标题且段落含 email 或过短。"""
    for ch in chapters:
        clean_sections = []
        for sec in ch.get("sections", []):
            if sec.get("title", "").strip():
                clean_sections.append(sec)
                continue
            # 无标题 section：检查是否全是作者/元数据行
            paras = sec.get("paragraphs", [])
            total_emails = sum(len(re.findall(r"[\w.-]+@[\w.]+", p["text"])) for p in paras)
            total_chars = sum(len(p["text"]) for p in paras)
            if total_emails >= 2 or total_chars < 30:
                continue
            clean_sections.append(sec)
        ch["sections"] = clean_sections
    return chapters


def _renumber_chapters(chapters: list[dict]) -> list[dict]:
    """重新编号章节和段落，确保 ID 连续。"""
    for ch_idx, ch in enumerate(chapters, 1):
        ch["id"] = f"ch_{ch_idx}"
        for sec_idx, sec in enumerate(ch.get("sections", []), 1):
            old_sec_id = sec["id"]
            sec["id"] = f"sec_{ch_idx}_{sec_idx}"
            for p_idx, p in enumerate(sec.get("paragraphs", []), 1):
                p["id"] = f"para_{ch_idx}_{sec_idx}_{p_idx:03d}"
    return chapters


_BACK_MATTER_PATTERNS = [
    r'^acknowledg', r'^bibliograph', r'^references$', r'^index$',
    r'^glossary$', r'^copyright', r'^about\s+the\s+author',
    r'^also\s+by\b', r'^further\s+reading', r'^notes$', r'^appendix',
]


def _is_back_matter(title: str) -> bool:
    title_lower = title.strip().lower()
    return any(re.match(p, title_lower) for p in _BACK_MATTER_PATTERNS)


def _separate_back_matter(chapters: list[dict]) -> list[dict]:
    """从最后一章中分离后置内容（致谢/索引/版权等）为独立附录章节。"""
    if len(chapters) < 2:
        return chapters

    last = chapters[-1]
    sections = last.get("sections", [])
    if len(sections) < 2:
        return chapters

    # 从后往前扫描，找连续的后置内容块
    split_idx = None
    for i in range(len(sections) - 1, -1, -1):
        if _is_back_matter(sections[i].get("title", "")):
            split_idx = i
        else:
            break

    if split_idx is None:
        return chapters

    back_sections = sections[split_idx:]
    logger.debug("Back matter: separating %d section(s) from '%s'",
                 len(back_sections), last.get("title", ""))
    last["sections"] = sections[:split_idx]

    # 如果原章节变成空的，移除它
    if not last["sections"]:
        chapters.pop()

    appendix = {
        "id": f"ch_{len(chapters) + 1}",
        "title": "附录 / Back Matter",
        "page_start": 1,
        "page_end": 1,
        "sections": back_sections,
    }
    chapters.append(appendix)
    return chapters


def _postprocess_chapters(chapters: list[dict]) -> list[dict]:
    """后处理：移除空章节，合并内容过少的小节。"""
    cleaned = []
    for ch in chapters:
        valid_sections = [
            s for s in ch.get("sections", [])
            if s.get("paragraphs")
        ]
        if not valid_sections:
            continue

        # 合并小节
        merged = []
        for sec in valid_sections:
            if merged and len(merged[-1].get("paragraphs", [])) < 3:
                merged[-1]["paragraphs"].extend(sec.get("paragraphs", []))
                if sec.get("title") and not merged[-1].get("title"):
                    merged[-1]["title"] = sec["title"]
                continue
            merged.append(sec)

        ch["sections"] = merged
        cleaned.append(ch)

    # 合并总段落极少的章节（< 3 段即视为 frontmatter 并入下一章）
    if len(cleaned) > 1:
        final = []
        pending_merge_sections = []
        for ch in cleaned:
            n_paras = sum(len(s.get("paragraphs", [])) for s in ch.get("sections", []))
            if n_paras < 3:
                pending_merge_sections.extend(ch["sections"])
                continue
            if pending_merge_sections:
                ch["sections"] = pending_merge_sections + ch["sections"]
                pending_merge_sections = []
            final.append(ch)
        # 如果所有章节都 < 3 段（不太可能），全部保留
        if not final:
            final = cleaned
        # 如果最后有悬挂的 merge sections，合并到最后一个章节
        elif pending_merge_sections and final:
            final[-1]["sections"] = final[-1].get("sections", []) + pending_merge_sections
        cleaned = final

    return cleaned


def _guess_title(paragraphs: list[dict]) -> str:
    """从首段推测文档标题。"""
    for p in paragraphs:
        text = p.get("text", "")
        if len(text) > 10:
            # 取前 80 字符作为标题
            title = text[:80].strip()
            if len(title) > 80:
                title = title[:77] + "..."
            return title
    return "Untitled"


def _map_images_to_structure(images: list[dict], chapters: list[dict]) -> list[dict]:
    """将图片按页码映射到对应章节的 after_paragraph。"""
    # 简化实现：每张图片挂在对应页的首段之后
    img_entries = []
    for img in images:
        img_page = img.get("page", 1)
        # 找该页第一个段落
        found = None
        for ch in chapters:
            for sec in ch.get("sections", []):
                for para in sec.get("paragraphs", []):
                    if para.get("page", 1) >= img_page:
                        found = para["id"]
                        break
                if found:
                    break
            if found:
                break

        img_entries.append({
            "id": img["id"],
            "filename": img["filename"],
            "after_paragraph": found or "para_1_1_001",
            "page": img_page,
            "caption": "",
        })
    return img_entries


# ---------------------------------------------------------------------------
# AI 结构识别兜底
# ---------------------------------------------------------------------------

_REASONABLE_FIRST_CHAPTER = [
    r'^chapter\s+[1i]', r'^CHAPTER\s+[1I]', r'^part\s+[1i]',
    r'^introduction', r'^preface', r'^foreword', r'^prologue',
    r'^第[一1]?[章篇]', r'^\d+[\.\s]', r'^(I|1)[\.\s:：]',
]


def _needs_ai_fallback(chapters: list, total_pages: int) -> bool:
    """判断是否需要 AI 兜底结构识别。"""
    # 条件 1（原有）：章节数量过少
    if total_pages > 5 and len(chapters) <= 1:
        return True
    if total_pages > 30 and len(chapters) < 3:
        return True

    # 条件 2（新增）：首章标题质量检测（>50页的书）
    if len(chapters) > 0 and total_pages > 50:
        first_title = chapters[0].get("title", "").strip()
        if not _is_reasonable_first_chapter(first_title):
            return True

    return False


def _is_reasonable_first_chapter(title: str) -> bool:
    """判断首章标题是否看起来像一个正常的第一章。"""
    title_lower = title.strip().lower()
    for pat in _REASONABLE_FIRST_CHAPTER:
        if re.match(pat, title_lower):
            return True
    return False


async def _ai_structure_recognition(md_text: str, total_pages: int,
                                     raw_md: str) -> list[dict] | None:
    """调用 AI 识别章节结构（异步）。成功返回章节标题列表，失败返回 None。"""
    import re as _re

    # 提取前 5000 字符（约前 3-5 页）
    first_pages = md_text[:5000]

    try:
        from app.services.ai_adapter import create_adapter
        adapter = create_adapter()
        chapters = await adapter.recognize_structure(first_pages, total_pages)
        if not chapters:
            return None
        return chapters
    except Exception:
        return None


def _apply_ai_structure(md_text: str, ai_chapters: list[dict]) -> str:
    """根据 AI 返回的章节标题在 Markdown 文本中定位并插入 `#` 标题标记。"""
    import difflib

    lines = md_text.split("\n")
    result_lines = []
    applied = set()

    for ch in ai_chapters:
        title = ch.get("title", "").strip()
        if not title or title in applied:
            continue

        # 在全文行中模糊匹配标题
        best_ratio = 0.0
        best_idx = -1
        for i, line in enumerate(lines):
            clean = line.strip().lstrip("#").strip()
            ratio = difflib.SequenceMatcher(None, title.lower(), clean.lower()).ratio()
            if ratio > best_ratio and ratio > 0.6:
                best_ratio = ratio
                best_idx = i

        if best_idx >= 0 and lines[best_idx].strip() == lines[best_idx].strip():
            # 在该行前插入 `# ` 标记
            line = lines[best_idx]
            stripped = line.strip()
            if not stripped.startswith("# "):
                indent = line[:len(line) - len(line.lstrip())]
                lines[best_idx] = f"{indent}# {stripped.lstrip('#').strip()}"
            applied.add(title)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

async def parse_pdf(file_bytes: bytes, filename: str, doc_id: str | None = None) -> dict:
    """完整解析流程入口。"""
    t_start = time.time()
    if doc_id is None:
        doc_id = uuid.uuid4().hex[:12]

    # 1. 校验
    t0 = time.time()
    validate_pdf(file_bytes, filename)
    size_mb = len(file_bytes) / 1024 / 1024

    # 2. 创建文档目录 + 获取总页数
    doc_dir = DOCUMENTS_DIR / doc_id
    os.makedirs(doc_dir / "images", exist_ok=True)

    pdf_path = doc_dir / "original.pdf"
    with open(pdf_path, "wb") as f:
        f.write(file_bytes)

    doc_tmp = fitz.open(str(pdf_path))
    total_pages = len(doc_tmp)
    doc_tmp.close()

    logger.info("Step 1/6 validate: %s (%.1fMB, %d pages) passed in %.1fs",
                filename, size_mb, total_pages, time.time() - t0)

    # 3. 文本提取
    t0 = time.time()
    md_text = extract_markdown(str(pdf_path))

    raw_path = doc_dir / "raw.md"
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(md_text)

    raw_size_kb = raw_path.stat().st_size / 1024
    logger.info("Step 2/6 text_extraction: completed in %.1fs (raw.md: %.0fKB)",
                time.time() - t0, raw_size_kb)

    # 4. 图表截取
    t0 = time.time()
    images = extract_images(str(pdf_path), doc_id)
    logger.info("Step 3/6 image_extraction: %d images extracted in %.1fs",
                len(images), time.time() - t0)

    # 5. 提取页眉/页脚候选
    t0 = time.time()
    headers, footers = _extract_headers_footers(str(pdf_path))
    logger.debug("Headers/footers: %d header candidates, %d footer candidates",
                 len(headers), len(footers))

    # 6. 结构识别 + 段落切分
    t0_sr = time.time()
    elements = _detect_headings_and_paragraphs(md_text, headers, footers)

    # 7. 文本清洗
    elements = _fix_all_paragraphs(elements)
    elements = _merge_cross_page_paragraphs(elements)

    # 8. 组装 JSON
    structure = _build_structure(elements, images)
    n_ch = len(structure.get("chapters", []))
    n_sec = sum(len(ch.get("sections", [])) for ch in structure.get("chapters", []))
    n_para = sum(
        sum(len(s.get("paragraphs", [])) for s in ch.get("sections", []))
        for ch in structure.get("chapters", [])
    )

    # TOC 过滤计数
    toc_demoted = sum(
        1 for el in elements
        if el["type"] == "paragraph" and el.get("id", "").startswith("para_toc_")
    )

    # 8.5 AI 结构识别兜底
    ai_fallback_used = False
    if _needs_ai_fallback(structure.get("chapters", []), total_pages):
        reason = _fallback_reason(structure.get("chapters", []), total_pages)
        logger.info("Step 4/6 structure_recognition: AI fallback triggered (%s)", reason)
        ai_chapters = await _ai_structure_recognition(md_text, total_pages, md_text)
        if ai_chapters:
            logger.info("AI fallback: recognized %d chapters, re-parsing...", len(ai_chapters))
            enhanced_md = _apply_ai_structure(md_text, ai_chapters)
            elements2 = _detect_headings_and_paragraphs(enhanced_md, headers, footers)
            elements2 = _fix_all_paragraphs(elements2)
            elements2 = _merge_cross_page_paragraphs(elements2)
            structure = _build_structure(elements2, images)
            structure["_ai_structure_fallback"] = True
            ai_fallback_used = True
            n_ch = len(structure.get("chapters", []))
            n_sec = sum(len(ch.get("sections", [])) for ch in structure.get("chapters", []))
            n_para = sum(
                sum(len(s.get("paragraphs", [])) for s in ch.get("sections", []))
                for ch in structure.get("chapters", [])
            )

    sr_time = time.time() - t0_sr
    logger.info(
        "Step 4/6 structure_recognition: L1+L2 → %dch/%dsec/%dpara "
        "TOC_filter=%s(%d) AI_fallback=%s in %.1fs",
        n_ch, n_sec, n_para,
        "yes" if toc_demoted > 0 else "no", toc_demoted,
        "yes" if ai_fallback_used else "no",
        sr_time,
    )

    # 文件名兜底标题
    t0 = time.time()
    _meta_titles = {"authors", "acknowledgements", "acknowledgments", "preface",
                    "abstract", "published", "untitled", "contents"}
    _looks_like_chapter_number = bool(re.match(r"^\d+[½¼¾]?\s", structure["title"].strip()))
    _looks_like_section_title = bool(re.match(
        r'^(?:introduction|chapter\s|preface|foreword|prologue|part\s)',
        structure["title"].strip().lower()))
    if (structure["title"].strip().lower() in _meta_titles
            or len(structure["title"].strip()) < 5
            or _looks_like_chapter_number
            or _looks_like_section_title):
        base = filename.rsplit(".", 1)[0]
        base = base.replace("-", " ").replace("_", " ").strip()
        if len(base) > 3:
            structure["title"] = base

    # 更新 doc_id 和图片信息
    structure["id"] = doc_id
    for ch in structure["chapters"]:
        orig_images = ch.pop("images", None)
    structure["images"] = _map_images_to_structure(images, structure["chapters"])

    # 9. 存储 structure.json
    json_path = doc_dir / "structure.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)

    # 10. 写入数据库元数据
    from app.database import get_connection

    conn = get_connection()
    conn.execute(
        """INSERT INTO documents (id, title, filename, total_pages, total_chapters, json_path, pdf_path)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            doc_id,
            structure["title"],
            filename,
            total_pages,
            len(structure["chapters"]),
            str(json_path),
            str(pdf_path),
        ),
    )
    conn.commit()
    conn.close()

    total_time = time.time() - t_start
    logger.info(
        "Parse complete: %s → %dch/%dsec/%dpara/%dimg in %.1fs",
        filename, n_ch, n_sec, n_para, len(images), total_time,
    )

    return {
        "doc_id": doc_id,
        "title": structure["title"],
        "total_pages": total_pages,
        "total_chapters": len(structure["chapters"]),
        "images_count": len(images),
    }


def _fallback_reason(chapters: list, total_pages: int) -> str:
    """返回触发 AI 兜底的原因描述。"""
    if total_pages > 5 and len(chapters) <= 1:
        return f"single chapter for {total_pages}-page doc"
    if total_pages > 30 and len(chapters) < 3:
        return f"only {len(chapters)} chapters for {total_pages}-page doc"
    if len(chapters) > 0 and total_pages > 50:
        return f"suspicious first chapter title: '{chapters[0].get('title', '')}'"
    return "unknown"
