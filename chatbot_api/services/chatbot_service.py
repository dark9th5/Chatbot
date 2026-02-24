"""
Chatbot Service — Business Logic Layer (RAG Architecture - Qdrant)
Xử lý logic RAG: Tìm kiếm ngữ nghĩa với Qdrant + Sinh câu trả lời bằng LLM.

Design Pattern: Service Layer + Dependency Injection
"""

import numpy as np
from typing import List

from chatbot_api.schemas.chat import ChatResponse, SearchResult
from chatbot_api.services.qdrant_service import QdrantService
from chatbot_api.repositories.article_repository import ArticleRepository
from chatbot_api.services.embedding_service import EmbeddingService
from chatbot_api.services.llm_service import LLMService
from nlp_processor import clean_query


from chatbot_api.services.query_expansion_service import QueryExpansionService

class ChatbotService:
    """
    Service chính của chatbot (RAG Version - Qdrant).

    Flow:
    1. User Question -> Query Expansion (Optional)
    2. Vector (EmbeddingService)
    3. Search Qdrant -> Top Chunks (Context)
    4. Context + Question -> LLM -> Answer
    """

    MIN_CONFIDENCE_SCORE = 0.40

    def __init__(
        self,
        embedding_service: EmbeddingService,
        qdrant_service: QdrantService,
        article_repository: ArticleRepository,
        llm_service: LLMService,
        query_expansion_service: QueryExpansionService
    ):
        self._embedding_service = embedding_service
        self._qdrant_service = qdrant_service
        self._article_repo = article_repository
        self._llm_service = llm_service
        self._query_expansion_service = query_expansion_service

    def get_answer(self, question: str, top_k: int = 3) -> ChatResponse:
        """
        Xử lý câu hỏi theo quy trình RAG.
        """
        # Bước 0: Mở rộng truy vấn (Query Expansion) nếu câu hỏi ngắn
        expanded_query = self._query_expansion_service.expand_query(question)
        
        # Bước 1: Vector hóa câu hỏi (Dùng Expanded Query để tìm kiếm tốt hơn)
        query_vector = self._embedding_service.encode_query(expanded_query)

        # [SEMANTIC CACHE CHECK]
        cached_answer = self._qdrant_service.search_cache(query_vector)
        if cached_answer:
            print(f"⚡ [Cache Hit] Trả về câu trả lời đã lưu.")
            return ChatResponse(
                question=question,
                answer=cached_answer,
                confidence=1.0,
                sources=[],
                total_chunks_searched=0
            )

        # Bước 2: Tìm kiếm ngữ nghĩa trong Qdrant
        # Lấy nhiều kết quả hơn để Rerank (Hybrid Search)
        search_results = self._qdrant_service.search(
            query_embedding=query_vector,
            n_results=top_k * 5  # Lấy top 15-20 để lọc lại
        )

        # RERANKING LOGIC (Vector 70% + Keyword 30%)
        reranked_results = []
        for res in search_results:
            content = res.get('content', '')
            vector_score = res['score']
            
            # Tính điểm từ khóa
            keyword_score = self._calculate_keyword_score(question, content)
            
            # Tính điểm tổng hợp
            final_score = (vector_score * 0.7) + (keyword_score * 0.3)
            
            res['original_score'] = vector_score
            res['keyword_score'] = keyword_score
            res['score'] = final_score
            
            reranked_results.append(res)
            
        # Sắp xếp lại theo final_score
        reranked_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Lấy top_k kết quả tốt nhất
        final_results = reranked_results[:top_k]

        # Filter theo ngưỡng tự tin (thấp hơn xíu vì score bị chia lại)
        valid_results = [
            res for res in final_results
            if res['score'] >= 0.35 # Giảm threshold chút vì công thức mới
        ]

        # LOGGING ĐỂ DBG
        print(f"\n🔍 [Hybrid Search] Top {len(valid_results)} candidates:")
        for i, res in enumerate(valid_results):
            print(f"   {i+1}. {res['metadata'].get('title', '')[:50]}...")
            print(f"      Vec: {res['original_score']:.4f} | Key: {res['keyword_score']:.4f} | Final: {res['score']:.4f}")

        if not valid_results:
            return self._empty_response(
                question,
                message="Xin lỗi, tôi chưa có thông tin về vấn đề này trong cơ sở dữ liệu."
            )

        # Bước 3: Xây dựng Context cho LLM
        context_text, sources = self._build_context(valid_results)

        # Bước 4: Gửi cho LLM sinh câu trả lời
        print(f"--- Gửi Prompt cho {self._llm_service.provider.provider_name} ---")
        llm_response = self._llm_service.generate_answer(context_text, question)

        # [SEMANTIC CACHE SAVE]
        # Chỉ lưu nếu có kết quả tốt (confidence cao)
        if valid_results[0]['score'] >= 0.6: # Ngưỡng tin cậy để cache
            self._qdrant_service.add_to_cache(question, llm_response, query_vector)
            print(f"💾 [Cache Saved] Đã lưu câu hỏi vào cache.")

        return ChatResponse(
            question=question,
            answer=llm_response,
            confidence=round(valid_results[0]['score'], 4),
            sources=sources,
            total_chunks_searched=self._qdrant_service.count()
        )

    def _build_context(self, results: List[dict]) -> tuple[str, List[SearchResult]]:
        """Gộp các chunk thành đoạn văn context và danh sách nguồn."""
        context_parts = []
        sources = []
        seen_articles = set()

        for item in results:
            content = item.get('content', '')
            metadata = item.get('metadata', {})
            score = item.get('score', 0)

            title = metadata.get('title', 'Không rõ tiêu đề')
            source_name = metadata.get('source', 'Nguồn tin tức')
            article_id = metadata.get('article_id')

            trimmed_text = content[:1000]
            context_parts.append(
                f"Nguồn: {source_name} - {title}\nNội dung: {trimmed_text}"
            )

            if article_id and article_id not in seen_articles:
                seen_articles.add(article_id)
                sources.append(SearchResult(
                    chunk_text=content[:200] + "...",
                    similarity_score=round(score, 4),
                    vector_score=round(item.get('original_score', 0), 4),
                    keyword_score=round(item.get('keyword_score', 0), 4),
                    article_title=title,
                    article_source=source_name,
                    article_link=metadata.get('link', '')
                ))

        full_context = "\n\n".join(context_parts)
        return full_context, sources

    def _empty_response(self, question: str, message: str = "") -> ChatResponse:
        """Trả về response rỗng khi không tìm thấy tin."""
        if not message:
            message = "Xin lỗi, hiện tại tôi không tìm thấy thông tin liên quan trong dữ liệu."

        return ChatResponse(
            question=question,
            answer=message,
            confidence=0.0,
            sources=[],
            total_chunks_searched=0
        )

    def _calculate_keyword_score(self, query: str, content: str) -> float:
        """
        Tính điểm khớp từ khóa (Simple Overlap) sau khi lọc Stopwords.
        """
        if not query or not content:
            return 0.0

        # Làm sạch query (Lọc từ rác)
        cleaned_query = clean_query(query)
        
        # Normalization (Lowercase)
        query_tokens = set(cleaned_query.lower().split())
        content_lower = content.lower()
        
        if not query_tokens:
            return 0.0
            
        matched_count = 0
        for token in query_tokens:
            if token in content_lower:
                matched_count += 1
                
        return matched_count / len(query_tokens)
