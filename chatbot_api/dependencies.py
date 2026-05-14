"""
Dependencies — Dependency Injection Wiring
Khai báo và quản lý singleton instances cho toàn bộ ứng dụng.

Design Pattern: Dependency Injection (FastAPI built-in DI)
<<<<<<< HEAD
"""

=======

Configuration via Environment Variables:
- LLM_PROVIDER: 'gemini', 'openai', 'llama_cpp', 'ollama' (default: 'ollama')
- GEMINI_API_KEY: Google Gemini API key
- OPENAI_API_KEY: OpenAI API key  
- LLAMA_CPP_MODEL_PATH: Path to GGUF model file
"""

import os
import logging
>>>>>>> c1d95b9 (Initial commit)
from functools import lru_cache
from fastapi import HTTPException

from chatbot_api.repositories.chunk_repository import ChunkRepository
from chatbot_api.repositories.article_repository import ArticleRepository
from chatbot_api.services.embedding_service import EmbeddingService
from chatbot_api.services.qdrant_service import QdrantService
from chatbot_api.services.chatbot_service import ChatbotService
<<<<<<< HEAD
from chatbot_api.services.llm_service import LLMService, GeminiProvider, OllamaProvider
=======
from chatbot_api.services.llm_service import (
    LLMService, GeminiProvider, OllamaProvider, OpenAIProvider, 
    LlamaCppProvider, FallbackLLMProvider
)
>>>>>>> c1d95b9 (Initial commit)


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
<<<<<<< HEAD
    """
    llm_type = "ollama"

    if llm_type == "gemini":
        api_key = "YOUR_GEMINI_API_KEY"
        provider = GeminiProvider(api_key=api_key)
    else:
=======
    
    Configuration từ environment variables:
    - LLM_PROVIDER: 'gemini', 'openai', 'llama_cpp', 'ollama', hoặc 'gemini_fallback_openai' (mặc định: ollama)
    - GEMINI_API_KEY: Google Gemini API key
    - OPENAI_API_KEY: OpenAI API key
    - LLAMA_CPP_MODEL_PATH: Đường dẫn tệp GGUF model
    """
    llm_provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    
    try:
        if llm_provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY environment variable not set")
            provider = GeminiProvider(api_key=api_key)
            
        elif llm_provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            provider = OpenAIProvider(api_key=api_key, model_name="gpt-3.5-turbo")
            
        elif llm_provider == "llama_cpp":
            model_path = os.getenv("LLAMA_CPP_MODEL_PATH", "models/qwen2.5-1.5b.gguf")
            provider = LlamaCppProvider(model_path=model_path)
            
        elif llm_provider == "gemini_fallback_openai":
            # Primary: Gemini, Fallback: OpenAI
            gemini_key = os.getenv("GEMINI_API_KEY")
            openai_key = os.getenv("OPENAI_API_KEY")
            if not gemini_key or not openai_key:
                raise ValueError("Both GEMINI_API_KEY and OPENAI_API_KEY must be set")
            primary = GeminiProvider(api_key=gemini_key)
            fallback = OpenAIProvider(api_key=openai_key)
            provider = FallbackLLMProvider(primary=primary, fallback=fallback)
            
        else:  # ollama (default)
            provider = OllamaProvider(model_name="qwen2.5:1.5b")
            
    except (ValueError, ImportError) as e:
        # Fallback to Ollama nếu cấu hình lỗi
        import logging
        logging.warning(f"Failed to initialize {llm_provider} provider: {str(e)}. Falling back to Ollama.")
>>>>>>> c1d95b9 (Initial commit)
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
