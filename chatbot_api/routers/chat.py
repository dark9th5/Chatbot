"""
Chat Router — API Endpoints (Thin Controller)
Chỉ chịu trách nhiệm: nhận request, gọi service, trả response.
Không chứa business logic.

Design Pattern: Thin Controller
"""

from fastapi import APIRouter, Depends

from chatbot_api.schemas.chat import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    CategoriesResponse,
)
from chatbot_api.services.chatbot_service import ChatbotService
from chatbot_api.dependencies import (
    get_chatbot_service,
    get_qdrant_service,
    get_embedding_service
)


router = APIRouter(prefix="/api", tags=["Chatbot API"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Hỏi đáp với Chatbot",
    description="Gửi câu hỏi và nhận câu trả lời dựa trên tin tức đã thu thập. Hỗ trợ lọc theo danh mục và ngày tháng năm."
)
async def chat(
    request: ChatRequest,
    service: ChatbotService = Depends(get_chatbot_service)
) -> ChatResponse:
    """
    Endpoint chính của chatbot.
    
    - Nhận câu hỏi từ user
    - Lọc theo danh mục (nếu có)
    - Lọc theo khoảng ngày (nếu có)
    - Tìm kiếm ngữ nghĩa trong Qdrant
    - Trả về câu trả lời + nguồn trích dẫn
    """
    return service.get_answer(
        question=request.question,
        top_k=request.top_k,
        category=request.category,
        from_date=request.from_date,
        to_date=request.to_date
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Kiểm tra trạng thái Chatbot API"
)
async def chatbot_health(
    embedding_service=Depends(get_embedding_service),
    qdrant_service=Depends(get_qdrant_service)
) -> HealthResponse:
    """Health check cho chatbot service"""
    return HealthResponse(
        status="healthy",
        service="Chatbot API",
        model_loaded=embedding_service.is_loaded,
        total_chunks=qdrant_service.count()
    )


@router.get(
    "/categories",
    response_model=CategoriesResponse,
    summary="Lấy danh sách danh mục"
)
async def list_categories(
    qdrant_service=Depends(get_qdrant_service)
) -> CategoriesResponse:
    """Danh sách danh mục dùng cho UI filter (Android/Web)."""
    categories = qdrant_service.get_normalized_categories()
    return CategoriesResponse(categories=categories, count=len(categories))


@router.get(
    "/_debug/categories",
    tags=["Debug"]
)
async def debug_categories(
    qdrant_service=Depends(get_qdrant_service)
) -> dict:
    """[DEBUG] Lấy danh sách danh mục trong DB"""
    categories = qdrant_service.get_all_categories()
    return {
        "categories": sorted(list(categories)),
        "count": len(categories)
    }

