"""
Chat Schemas — Pydantic DTOs
Validate và serialize dữ liệu request/response cho Chatbot API
"""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional
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
    data_source: Literal["news"] = Field(
        default="news",
        description="Nguồn dữ liệu: chỉ hỗ trợ 'news' (bài báo đã cào)"
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
    conversation_context: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Câu hỏi trước đó cần giữ lại khi người dùng đang trả lời câu hỏi làm rõ"
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
    published_date: Optional[date] = Field(default=None, description="Ngày xuất bản của nguồn")


class ChatResponse(BaseModel):
    """Response body cho endpoint /api/chat"""
    question: str = Field(description="Câu hỏi gốc")
    answer: str = Field(description="Câu trả lời tổng hợp")
    sources: List[SearchResult] = Field(description="Danh sách nguồn trích dẫn")
    total_chunks_searched: int = Field(description="Tổng số chunks đã tìm kiếm")
    needs_clarification: bool = Field(
        default=False,
        description="Có cần giữ ngữ cảnh để người dùng trả lời tiếp hay không"
    )


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
