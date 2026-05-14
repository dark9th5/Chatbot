"""
Chat Schemas — Pydantic DTOs
Validate và serialize dữ liệu request/response cho Chatbot API
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date


class ChatRequest(BaseModel):
    """Request body cho endpoint /api/chat"""
    question: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="Câu hỏi của người dùng",
        examples=["Tin tức kinh tế Việt Nam hôm nay?"]
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Số kết quả trả về"
    )
    category: Optional[str] = Field(
        default=None,
        description="Lọc theo danh mục tin tức (VD: Thời sự, Kinh doanh, Giải trí, etc). None = tất cả danh mục"
    )
    from_date: Optional[date] = Field(
        default=None,
        description="Lọc tin tức từ ngày này trở đi (YYYY-MM-DD). None = không giới hạn"
    )
    to_date: Optional[date] = Field(
        default=None,
        description="Lọc tin tức đến ngày này (YYYY-MM-DD). None = hôm nay"
    )


class SearchResult(BaseModel):
    """Một kết quả tìm kiếm ngữ nghĩa"""
    chunk_text: str = Field(description="Đoạn văn bản liên quan")
    similarity_score: float = Field(description="Điểm tương đồng tổng hợp (Final Score)")
    vector_score: Optional[float] = Field(default=None, description="Điểm Vector (Semantic)")
    keyword_score: Optional[float] = Field(default=None, description="Điểm Keyword (Lexical)")
    article_title: str = Field(description="Tiêu đề bài viết nguồn")
    article_source: str = Field(description="Nguồn báo (VnExpress, Dân Trí)")
    article_link: str = Field(default="", description="Link bài viết gốc")


class ChatResponse(BaseModel):
    """Response body cho endpoint /api/chat"""
    question: str = Field(description="Câu hỏi gốc")
    answer: str = Field(description="Câu trả lời tổng hợp")
    confidence: float = Field(description="Độ tin cậy (0-1)")
    sources: List[SearchResult] = Field(description="Danh sách nguồn trích dẫn")
    total_chunks_searched: int = Field(description="Tổng số chunks đã tìm kiếm")


class HealthResponse(BaseModel):
    """Response cho health check"""
    status: str
    service: str
    model_loaded: bool
    total_chunks: int


class CategoriesResponse(BaseModel):
    """Response cho endpoint danh sách danh mục."""
    categories: List[str]
    count: int
