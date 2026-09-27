"""Pydantic 数据模型

按产品技术规格第四章 4.3 节 AI 适配器接口定义的 Request/Response 模型，
以及第六章 API 接口规格定义的请求/响应模型。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ---- 词义查询 ----

class LookupRequest(BaseModel):
    document_id: str
    paragraph_id: str
    word: str
    sentence: str
    mode: str = "context"  # "context" | "expand"


class DictionaryEntry(BaseModel):
    index: int
    pos: str
    en: str
    zh: str


class AIContext(BaseModel):
    selected_index: int
    explanation: str
    is_technical_term: bool
    domain: Optional[str] = None


class AIExpand(BaseModel):
    memory_hint: Optional[str] = None
    confusion_note: Optional[str] = None


class LookupResponse(BaseModel):
    word_lemma: str
    phonetic: Optional[str] = None
    dictionary_entries: list[DictionaryEntry] = []
    ai_context: Optional[AIContext] = None
    ai_expand: Optional[AIExpand] = None
    from_cache: bool = False


# ---- 评论生成 ----

class CommentaryRequest(BaseModel):
    document_id: str
    paragraph_id: str
    excluded_personas: list[str] = []


class PersonaComment(BaseModel):
    persona: str
    avatar: str
    comment: str


class CommentaryResponse(BaseModel):
    selected_personas: list[str]
    comments: list[PersonaComment]
    from_cache: bool = False


class ChapterReviewRequest(BaseModel):
    document_id: str
    chapter_id: str


class ChapterReviewResponse(BaseModel):
    persona: str = "领读学长"
    main_argument: str
    key_takeaways: list[str]
    connection_to_previous: str
    preview_next: str
    summarized: bool = False
    from_cache: bool = False


# ---- 文档管理 ----

class DocumentInfo(BaseModel):
    id: str
    title: str
    filename: str
    upload_time: str
    total_chapters: int
    reading_progress_percent: float


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]


class ChapterItem(BaseModel):
    id: str
    title: str
    sections: Optional[list] = None


class DocumentStructure(BaseModel):
    id: str
    title: str
    chapters: list


class SectionContent(BaseModel):
    id: str
    title: Optional[str] = None
    paragraphs: list


class ImageRef(BaseModel):
    id: str
    url: str
    after_paragraph: str


class ChapterContent(BaseModel):
    chapter_id: str
    title: str
    sections: list[SectionContent]
    images: list[ImageRef]


# ---- 生词本 ----

class VocabularyItem(BaseModel):
    id: str
    word_lemma: str
    phonetic: Optional[str] = None
    sentence: str
    selected_meaning: Optional[str] = None
    ai_explanation: Optional[str] = None
    domain: Optional[str] = None
    lookup_count: int
    last_lookup_time: str


class VocabularyListResponse(BaseModel):
    total: int
    words: list[VocabularyItem]


# ---- 阅读进度 ----

class ProgressUpdateRequest(BaseModel):
    last_paragraph_id: str
    chapter_status: dict[str, str]


class ProgressResponse(BaseModel):
    last_paragraph_id: str
    last_read_time: Optional[str] = None
    chapter_status: dict[str, str]


# ---- 用户设置 ----

class SettingsResponse(BaseModel):
    ai_provider: str
    has_api_key: bool
    api_keys_configured: dict[str, bool] = {}
    openai_compat_base_url: str = ""
    openai_compat_model_name: str = ""
    font_size: int
    line_height: float
    theme: str
    log_level: str = "INFO"


class SettingsUpdateRequest(BaseModel):
    ai_provider: Optional[str] = None
    api_key_claude: Optional[str] = None
    api_key_deepseek: Optional[str] = None
    api_key_openai_compat: Optional[str] = None
    openai_compat_base_url: Optional[str] = None
    openai_compat_model_name: Optional[str] = None
    model_word_lookup: Optional[str] = None
    model_commentary: Optional[str] = None
    font_size: Optional[int] = None
    line_height: Optional[float] = None
    theme: Optional[str] = None
    log_level: Optional[str] = None
