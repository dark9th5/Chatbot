"""
Dependencies — Dependency Injection Wiring
Khai báo và quản lý singleton instances cho toàn bộ ứng dụng.

Design Pattern: Dependency Injection (FastAPI built-in DI)
"""

from functools import lru_cache
from fastapi import HTTPException

from chatbot_api.repositories.chunk_repository import ChunkRepository
from chatbot_api.repositories.article_repository import ArticleRepository
from chatbot_api.services.embedding_service import EmbeddingService
from chatbot_api.services.qdrant_service import QdrantService
from chatbot_api.services.chatbot_service import ChatbotService
from chatbot_api.services.llm_service import LLMService, GeminiProvider, OllamaProvider


# ============================================================
# SINGLETON INSTANCES
# ============================================================

@lru_cache(maxsize=1)
def get_chunk_repository() -> ChunkRepository:
    """Singleton ChunkRepository (giữ lại cho backward compat)"""
    return ChunkRepository()


@lru_cache(maxsize=1)
def get_article_repository() -> ArticleRepository:
    """Singleton ArticleRepository"""
    return ArticleRepository()


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """
    Singleton EmbeddingService.
    Model chỉ được tải 1 lần duy nhất khi ứng dụng khởi động.
    """
    return EmbeddingService()


@lru_cache(maxsize=1)
def get_qdrant_service() -> QdrantService:
    """
    Singleton QdrantService.
    Vector size phải khớp với EmbeddingService dimension.
    """
    embedding = get_embedding_service()
    try:
        return QdrantService(vector_size=embedding.dimension)
    except RuntimeError as exc:
        if "already accessed by another instance" in str(exc):
            raise HTTPException(
                status_code=503,
                detail="Qdrant đang bận do tiến trình đồng bộ dữ liệu. Vui lòng thử lại sau ít phút."
            )
        raise


from chatbot_api.services.query_expansion_service import QueryExpansionService

@lru_cache(maxsize=1)
def get_chatbot_service() -> ChatbotService:
    """
    Singleton ChatbotService.
    Inject: EmbeddingService, QdrantService, ArticleRepository, LLMService, QueryExpansionService.
    """
    llm_type = "ollama"

    if llm_type == "gemini":
        api_key = "YOUR_GEMINI_API_KEY"
        provider = GeminiProvider(api_key=api_key)
    else:
        provider = OllamaProvider(model_name="qwen2.5:1.5b")

    llm_service = LLMService(provider)
    query_expansion_service = QueryExpansionService(llm_service)

    return ChatbotService(
        embedding_service=get_embedding_service(),
        qdrant_service=get_qdrant_service(),
        article_repository=get_article_repository(),
        llm_service=llm_service,
        query_expansion_service=query_expansion_service
    )
