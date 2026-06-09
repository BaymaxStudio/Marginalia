"""AI 适配器抽象基类

定义统一接口，底层可切换不同模型供应商：
  - ClaudeAdapter    (Anthropic Messages API)
  - DeepSeekAdapter   (OpenAI 兼容格式)
  - OpenAICompatAdapter (OpenAI Chat Completions)
"""

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel


class WordLookupRequest(BaseModel):
    word: str
    sentence: str
    paragraph: str
    dictionary_entries: list[dict]
    mode: str = "context"  # "context" | "expand"


class WordLookupResponse(BaseModel):
    selected_index: int
    explanation: str
    is_technical_term: bool
    domain: Optional[str] = None
    memory_hint: Optional[str] = None
    confusion_note: Optional[str] = None


class CommentaryRequest(BaseModel):
    document_title: str
    chapter_title: str
    previous_paragraph: Optional[str] = None
    current_paragraph: str
    next_paragraph: Optional[str] = None
    excluded_personas: list[str] = []


class PersonaComment(BaseModel):
    persona: str
    comment: str


class CommentaryResponse(BaseModel):
    selected_personas: list[str]
    comments: list[PersonaComment]


class ChapterReviewRequest(BaseModel):
    document_title: str
    chapter_title: str
    chapter_number: int
    total_chapters: int
    previous_chapter_title: Optional[str] = None
    next_chapter_title: Optional[str] = None
    chapter_content: str


class ChapterReviewResponse(BaseModel):
    main_argument: str
    key_takeaways: list[str]
    connection_to_previous: str
    preview_next: str


class AIAdapter(ABC):
    """AI 供应商适配器抽象基类"""

    @abstractmethod
    async def word_lookup(self, request: WordLookupRequest) -> WordLookupResponse:
        ...

    @abstractmethod
    async def paragraph_commentary(self, request: CommentaryRequest) -> CommentaryResponse:
        ...

    @abstractmethod
    async def chapter_review(self, request: ChapterReviewRequest) -> ChapterReviewResponse:
        ...

    async def summarize_chapter(self, chapter_title: str, content: str,
                                max_length: int = 1500) -> str:
        """将超长章节内容压缩为中文摘要。子类可覆盖此默认实现。"""
        raise NotImplementedError

    async def recognize_structure(self, first_pages_text: str,
                                  total_pages: int) -> list[dict]:
        """AI 兜底结构识别：返回 [{"title": "...", "location_hint": "..."}, ...]。"""
        raise NotImplementedError
