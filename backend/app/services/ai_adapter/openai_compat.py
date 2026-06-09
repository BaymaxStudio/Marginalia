"""OpenAI 兼容适配器（通用 Chat Completions 格式）

用于接入任何 OpenAI API 兼容的模型供应商（用户自行配置 base_url + model_name）
"""

from app.services.ai_adapter.base import (
    AIAdapter,
    WordLookupRequest,
    WordLookupResponse,
    CommentaryRequest,
    CommentaryResponse,
    ChapterReviewRequest,
    ChapterReviewResponse,
)


class OpenAICompatAdapter(AIAdapter):
    def __init__(self, api_key: str, base_url: str, model_name: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name

    async def word_lookup(self, request: WordLookupRequest) -> WordLookupResponse:
        raise NotImplementedError

    async def paragraph_commentary(self, request: CommentaryRequest) -> CommentaryResponse:
        raise NotImplementedError

    async def chapter_review(self, request: ChapterReviewRequest) -> ChapterReviewResponse:
        raise NotImplementedError
