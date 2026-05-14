"""
Chatbot Service — Business Logic Layer (RAG Architecture - Qdrant)
Xử lý logic RAG: Tìm kiếm ngữ nghĩa với Qdrant + Sinh câu trả lời bằng LLM.

Design Pattern: Service Layer + Dependency Injection
"""

import numpy as np
import re
from typing import List, Optional
from datetime import date

from chatbot_api.schemas.chat import ChatResponse, SearchResult
from chatbot_api.services.qdrant_service import QdrantService
from chatbot_api.repositories.article_repository import ArticleRepository
from chatbot_api.services.embedding_service import EmbeddingService
from chatbot_api.services.llm_service import LLMService
from pipeline.nlp_processor import clean_query


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

    def get_answer(
        self,
        question: str,
        top_k: int = 3,
        category: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> ChatResponse:
        """
        Xử lý câu hỏi theo quy trình RAG.
        
        Parameters:
            question: Câu hỏi của người dùng
            top_k: Số kết quả trả về
            category: Lọc theo danh mục (Optional)
            from_date: Lọc từ ngày (Optional)
            to_date: Lọc đến ngày (Optional)
        """
        # Bước -1: Tự động trích xuất thời gian từ câu hỏi nếu user không chọn filter
        if from_date is None and to_date is None:
            try:
                print(f"[*] Analyzing time constraints for: '{question}'...")
            except UnicodeEncodeError:
                print(f"[*] Analyzing time constraints for query (encoding error)...")
                
            extracted_from, extracted_to = self._extract_date_range(question)
            if extracted_from or extracted_to:
                from_date = extracted_from
                to_date = extracted_to
                print(f"[Time Extraction] Found range - From: {from_date}, To: {to_date}")

        # Bước 0: Mở rộng truy vấn (Query Expansion) có điều kiện để tránh tăng độ trễ không cần thiết.
        should_expand_query = self._should_expand_query(
            question=question,
            category=category,
            from_date=from_date,
            to_date=to_date,
        )
        expanded_query = (
            self._query_expansion_service.expand_query(question)
            if should_expand_query
            else question
        )
        
        # Bước 1: Vector hóa câu hỏi
        print(f"[*] Encoding query (Expansion: {'ON' if should_expand_query else 'OFF'})...")
        query_vector = self._embedding_service.encode_query(expanded_query)

        # [SEMANTIC CACHE CHECK] (Bỏ qua cache nếu có dùng bộ lọc)
        if category is None and from_date is None and to_date is None:
            cached_answer = self._qdrant_service.search_cache(query_vector)
            if cached_answer:
                print(f"[Cache Hit] Tra ve cau tra loi da luu.")
                return ChatResponse(
                    question=question,
                    answer=cached_answer,
                    confidence=1.0,
                    sources=[],
                    total_chunks_searched=0
                )

        # Bước 2: Tìm kiếm ngữ nghĩa trong Qdrant với filters
        print(f"[*] Searching Qdrant (Category={category}, DateRange={from_date} to {to_date})...")
        search_results = self._qdrant_service.search(
            query_embedding=query_vector,
            n_results=top_k * 5,  # Lấy top 15-20 để lọc lại
            category=category,
            from_date=from_date,
            to_date=to_date
        )

        # Bước 3: RERANKING LOGIC (Vector 70% + Keyword 30%)
        # Tối ưu: Làm sạch query 1 lần duy nhất trước khi lặp
        print(f"[*] Starting reranking process for {len(search_results)} candidates...")
        cleaned_query = clean_query(question)
        
        reranked_results = []
        for res in search_results:
            content = res.get('content', '')
            vector_score = res['score']
            
            # Tính điểm từ khóa (Truyền cleaned_query đã xử lý)
            keyword_score = self._calculate_keyword_score_fast(cleaned_query, content)
            
            # Tính điểm tổng hợp
            final_score = (vector_score * 0.7) + (keyword_score * 0.3)
            
            res['original_score'] = vector_score
            res['keyword_score'] = keyword_score
            res['score'] = final_score
            
            reranked_results.append(res)
            
        # Sắp xếp lại theo final_score
        reranked_results.sort(key=lambda x: x['score'], reverse=True)
        print(f"[*] Reranking complete. Found {len(reranked_results)} potential matches.")
        
        # Lấy top_k kết quả tốt nhất
        final_results = reranked_results[:top_k]

        # Filter theo ngưỡng tự tin
        # Nếu có bộ lọc (ngày/danh mục), giảm ngưỡng xuống để ưu tiên hiển thị kết quả đúng tiêu chí
        min_score = 0.25 if (from_date or to_date or category) else 0.35
        
        valid_results = [
            res for res in final_results
            if res['score'] >= min_score
        ]

        # LOGGING DE DBG
        try:
            print(f"\n[Hybrid Search] Top {len(valid_results)} candidates:")
            for i, res in enumerate(valid_results):
                try:
                    title = res['metadata'].get('title', '')[:50]
                    print(f"   {i+1}. {title}...")
                except UnicodeEncodeError:
                    print(f"   {i+1}. [Title encoding error]")
                print(f"      Vec: {res['original_score']:.4f} | Key: {res['keyword_score']:.4f} | Final: {res['score']:.4f}")
        except Exception:
            print(f"\n[Hybrid Search] Found {len(valid_results)} candidates (Encoding error in console log)")

        if not valid_results:
            return self._empty_response(
                question,
                message="Xin lỗi, tôi chưa có thông tin về vấn đề này trong cơ sở dữ liệu."
            )

        # Bước 4: Xây dựng Context cho LLM
        print("[*] Building prompt context...")
        context_text, sources = self._build_context(valid_results)

        # Bước 5: Gửi cho LLM sinh câu trả lời
        print(f"[*] Generating answer using {self._llm_service.provider.provider_name}...")
        llm_response = self._llm_service.generate_answer(context_text, question)
        print("[*] Answer generated successfully.")

        # [SEMANTIC CACHE SAVE]
        # Chỉ lưu nếu có kết quả tốt (confidence cao) và không dùng bộ lọc
        if valid_results[0]['score'] >= 0.6 and category is None and from_date is None and to_date is None:
            self._qdrant_service.add_to_cache(question, llm_response, query_vector)
            print(f"[Cache Saved] Da luu cau hoi vao cache.")

        return ChatResponse(
            question=question,
            answer=llm_response,
            confidence=round(valid_results[0]['score'], 4),
            sources=sources,
            total_chunks_searched=self._qdrant_service.count()
        )

    def _should_expand_query(
        self,
        question: str,
        category: Optional[str],
        from_date: Optional[date],
        to_date: Optional[date],
    ) -> bool:
        """
        Chỉ mở rộng truy vấn khi thực sự cần.

        - Nếu người dùng đã áp dụng bộ lọc rõ ràng, bỏ qua để giảm độ trễ.
        - Nếu câu hỏi đủ dài (đã rõ nghĩa), không cần mở rộng.
        """
        if category is not None or from_date is not None or to_date is not None:
            return False

        return len(question.split()) <= 10

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

    def _calculate_keyword_score_fast(self, cleaned_query: str, content: str) -> float:
        """
        Tính điểm khớp từ khóa (Simple Overlap) với query đã được làm sạch trước đó.
        """
        if not cleaned_query or not content:
            return 0.0
            
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

    def _extract_date_range(self, question: str) -> tuple[Optional[date], Optional[date]]:
        """
        Trích xuất khoảng thời gian từ câu hỏi tiếng Việt.
        Hỗ trợ: 'hôm nay', 'hôm qua', 'X ngày qua', 'tuần này'.
        """
        from datetime import timedelta
        today = date.today()
        q = question.lower()

        # 1. Hôm nay
        if "hôm nay" in q or "trong ngày" in q:
            return today, today
        
        # 2. Hôm qua
        if "hôm qua" in q:
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
            
        # 3. X ngày qua / X ngày gần đây
        match_days = re.search(r'(\d+)\s+ngày\s+(qua|gần\s+đây)', q)
        if match_days:
            days = int(match_days.group(1))
            start_date = today - timedelta(days=days)
            return start_date, today

        # 4. Tuần này
        if "tuần này" in q:
            start_of_week = today - timedelta(days=today.weekday())
            return start_of_week, today

        # 5. Mới nhất / Gần đây / Mới có (Mặc định 3 ngày qua để ưu tiên tin mới)
        if "mới nhất" in q or "gần đây" in q or "mới có" in q:
            start_date = today - timedelta(days=3)
            return start_date, today

        return None, None
