"""
Dependencies — Dependency Injection Wiring
Khai báo và quản lý singleton instances cho toàn bộ ứng dụng.

Design Pattern: Dependency Injection (FastAPI built-in DI)

Configuration via Environment Variables:
- LLM_PROVIDER: 'gemini', 'openai', 'llama_cpp', 'ollama' (default: 'ollama')
- GEMINI_API_KEY: Google Gemini API key
- OPENAI_API_KEY: OpenAI API key  
- LLAMA_CPP_MODEL_PATH: Path to GGUF model file
"""

import os
import logging
from functools import lru_cache
from fastapi import HTTPException
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from chatbot_api.repositories.chunk_repository import ChunkRepository
from chatbot_api.repositories.article_repository import ArticleRepository
from chatbot_api.services.embedding_service import EmbeddingService
from chatbot_api.services.qdrant_service import QdrantService
from chatbot_api.services.chatbot_service import ChatbotService
from chatbot_api.services.llm_service import (
    LLMService, GroqProvider, HuggingFaceProvider, FallbackLLMProvider
)


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
    
    Configuration từ environment variables:
    - GROQ_API_KEY: Groq API key (bắt buộc)
    - GROQ_MODEL: Model name (mặc định: mixtral-8x7b-32768)
    """
    llm_provider = os.getenv("LLM_PROVIDER", "groq").lower()

    try:
        # Primary: Groq
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        primary = GroqProvider(api_key=groq_key, model_name=groq_model)

        # Fallback: HuggingFace (optional)
        hf_key = os.getenv("HUGGINGFACE_API_KEY")
        fallback = None
        if hf_key:
            hf_model = os.getenv("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
            fallback = HuggingFaceProvider(api_key=hf_key, model_name=hf_model)

        provider = FallbackLLMProvider(primary=primary, fallback=fallback)

    except (ValueError, ImportError) as e:
        import logging
        logging.error(f"Failed to initialize LLM provider: {str(e)}")
        raise

    llm_service = LLMService(provider)
    query_expansion_service = QueryExpansionService(llm_service)

    return ChatbotService(
        embedding_service=get_embedding_service(),
        qdrant_service=get_qdrant_service(),
        article_repository=get_article_repository(),
        llm_service=llm_service,
        query_expansion_service=query_expansion_service
    )
