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
    HealthResponse
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
    description="Gửi câu hỏi và nhận câu trả lời dựa trên tin tức đã thu thập"
)
async def chat(
    request: ChatRequest,
    service: ChatbotService = Depends(get_chatbot_service)
) -> ChatResponse:
    """
    Endpoint chính của chatbot.
    
    - Nhận câu hỏi từ user
    - Tìm kiếm ngữ nghĩa trong Qdrant
    - Trả về câu trả lời + nguồn trích dẫn
    """
    return service.get_answer(
        question=request.question,
        top_k=request.top_k
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

