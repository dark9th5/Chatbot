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

from chatbot_api.repositories.article_repository import ArticleRepository
from chatbot_api.services.graph_search_service import GraphSearchService
from chatbot_api.services.chatbot_service import ChatbotService
from chatbot_api.services.llm_service import (
    LLMService, GroqProvider, HuggingFaceProvider, FallbackLLMProvider
)


# ============================================================
# SINGLETON INSTANCES
# ============================================================


# Lấy singleton instance của ArticleRepository
@lru_cache(maxsize=1)
def get_article_repository() -> ArticleRepository:
    """Singleton ArticleRepository"""
    return ArticleRepository()


# Lấy singleton instance của GraphSearchService (Thay thế Qdrant)
@lru_cache(maxsize=1)
def get_graph_search_service() -> GraphSearchService:
    """Singleton GraphSearchService (MySQL Graph)"""
    return GraphSearchService()


from chatbot_api.services.query_expansion_service import QueryExpansionService

# Lấy singleton instance của ChatbotService với đầy đủ các dependency được inject
@lru_cache(maxsize=1)
def get_chatbot_service() -> ChatbotService:
    """
    Singleton ChatbotService.
    Inject: GraphSearchService, ArticleRepository, LLMService, QueryExpansionService.
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
        fallback = None
        hf_key = os.getenv("HUGGINGFACE_API_KEY")
        if hf_key:
            try:
                hf_model = os.getenv("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
                fallback = HuggingFaceProvider(api_key=hf_key, model_id=hf_model)
            except (ImportError, Exception) as e:
                logging.warning(f"Could not initialize HuggingFace fallback: {e}")

        provider = FallbackLLMProvider(primary=primary, fallback=fallback)

    except (ValueError, ImportError, Exception) as e:
        logging.error(f"Failed to initialize primary LLM provider: {str(e)}")
        raise

    llm_service = LLMService(provider)
    query_expansion_service = QueryExpansionService(llm_service)

    return ChatbotService(
        graph_search_service=get_graph_search_service(),
        article_repository=get_article_repository(),
        llm_service=llm_service,
        query_expansion_service=query_expansion_service
    )

def clear_service_caches():
    """
    Xóa cache của các singleton service để ép buộc nạp lại từ điển (lexicons)
    và các thay đổi mà không cần khởi động lại server.
    """
    get_article_repository.cache_clear()
    get_graph_search_service.cache_clear()
    get_chatbot_service.cache_clear()
    logging.info("Service caches cleared successfully.")
