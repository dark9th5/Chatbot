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
    get_graph_search_service
)


router = APIRouter(prefix="/api", tags=["Chatbot API"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Hỏi đáp với Chatbot",
    description="Gửi câu hỏi và nhận câu trả lời dựa trên Đồ thị Tri thức (Knowledge Graph)."
)
# Xử lý yêu cầu chat từ người dùng và trả về câu trả lời từ AI
def chat(
    request: ChatRequest,
    service: ChatbotService = Depends(get_chatbot_service)
) -> ChatResponse:
    """
    Endpoint chính của chatbot (Knowledge Graph Version).
    """
    return service.get_answer(
        question=request.question,
        top_k=request.top_k,
        data_source=request.data_source,
        category=request.category,
        from_date=request.from_date,
        to_date=request.to_date,
        conversation_context=request.conversation_context,
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Kiểm tra trạng thái Chatbot API"
)
# Kiểm tra trạng thái sức khỏe của dịch vụ Chatbot
def chatbot_health(
    graph_service=Depends(get_graph_search_service)
) -> HealthResponse:
    """Health check cho chatbot service (Graph Version)"""
    return HealthResponse(
        status="healthy",
        service="Chatbot API (Knowledge Graph)",
        model_loaded=True, # No more AI models to load for search
        total_chunks=0 # Graph based
    )


@router.get(
    "/categories",
    response_model=CategoriesResponse,
    summary="Lấy danh sách danh mục"
)
# Lấy danh sách các danh mục tin tức từ MySQL
def list_categories() -> CategoriesResponse:
    """Danh sách danh mục lấy trực tiếp từ MySQL articles."""
    categories = set()
    try:
        from web_admin.utils.db import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Chỉ lấy danh mục tin tức, không trộn lẫn file upload.
        cursor.execute(
            "SELECT DISTINCT category FROM articles "
            "WHERE category IS NOT NULL AND link NOT LIKE %s",
            ("upload://%",),
        )
        rows = cursor.fetchall()
        for row in rows:
            if row['category'] and row['category'] != 'Tài liệu':
                categories.add(row['category'])
            
        conn.close()
    except Exception as e:
        print(f"Error fetching categories: {e}")
    
    final_list = sorted(list(categories))
    return CategoriesResponse(categories=final_list, count=len(final_list))

