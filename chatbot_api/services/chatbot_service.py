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
from chatbot_api.services.graph_search_service import GraphSearchService
from chatbot_api.repositories.article_repository import ArticleRepository
from chatbot_api.services.llm_service import LLMService
from pipeline.nlp_processor import clean_query


from chatbot_api.services.query_expansion_service import QueryExpansionService

class ChatbotService:
    """
    Service chính của chatbot (Knowledge Graph Version).

    Flow:
    1. User Question -> Custom NER (GraphSearchService)
    2. Search Graph (MySQL) -> Top Related Articles (Context)
    3. Context + Question -> LLM -> Answer
    """

    # Khởi tạo Chatbot Service với các dependency cần thiết
    def __init__(
        self,
        graph_search_service: GraphSearchService,
        article_repository: ArticleRepository,
        llm_service: LLMService,
        query_expansion_service: QueryExpansionService
    ):
        self._graph_service = graph_search_service
        self._article_repo = article_repository
        self._llm_service = llm_service
        self._query_expansion_service = query_expansion_service

    # Xử lý câu hỏi của người dùng và trả về câu trả lời tối ưu nhất
    def get_answer(
        self,
        question: str,
        top_k: int = 3,
        category: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> ChatResponse:
        """
        Xử lý câu hỏi theo quy trình RAG (Graph Retrieval).
        """
        # Bước 0: Mở rộng truy vấn (ĐÃ TẮT ĐỂ ĐẢM BẢO 100% KHÔNG DÙNG AI TRONG TÌM KIẾM)
        expanded_query = question
        
        # Bước 1: Tìm kiếm trên Đồ thị thực thể (Graph Search)
        print(f"[*] Searching Graph for: '{expanded_query}'...")
        valid_results = self._graph_service.search(
            query=expanded_query,
            limit=top_k
        )

        # LOGGING
        print(f"[*] Graph Search complete. Found {len(valid_results)} candidates.")

        if not valid_results:
            return self._empty_response(
                question,
                message="Xin lỗi, tôi chưa tìm thấy mối liên hệ nào trong đồ thị tri thức để trả lời câu hỏi này."
            )

        # Bước 2: Xây dựng Context cho LLM (Sử dụng Micro-chunking & Entity/Keyword Scoring)
        print("[*] Building prompt context from Graph nodes (Micro-chunking enabled)...")
        context_text, sources = self._build_context(valid_results, question)

        # Bước 3: Gửi cho LLM sinh câu trả lời
        print(f"[*] Generating answer using {self._llm_service.provider.provider_name}...")
        llm_response = self._llm_service.generate_answer(context_text, question)
        print("[*] Answer generated successfully.")

        return ChatResponse(
            question=question,
            answer=llm_response,
            confidence=round(valid_results[0]['score'], 4) if valid_results else 0.0,
            sources=sources,
            total_chunks_searched=0 # Không dùng chunking ở DB nữa, tự micro-chunk ở bộ nhớ
        )

    def split_to_micro_chunks(self, text: str, max_words: int = 120, overlap_words: int = 20) -> List[str]:
        """
        Chia văn bản tiếng Việt thành các micro-chunks (đoạn nhỏ) dựa trên số lượng từ.
        Đảm bảo giữ nguyên các câu trọn vẹn nếu có thể.
        """
        if not text:
            return []
        
        # Tách văn bản thành các câu bằng các dấu câu phổ biến (. ! ?)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk_words = []
        current_word_count = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            sentence_words = sentence.split()
            sentence_word_count = len(sentence_words)
            
            # Nếu câu đơn lẻ quá dài, cắt nhỏ trực tiếp
            if sentence_word_count > max_words:
                if current_chunk_words:
                    chunks.append(" ".join(current_chunk_words))
                    current_chunk_words = []
                    current_word_count = 0
                
                for i in range(0, sentence_word_count, max_words - overlap_words):
                    sub_chunk = " ".join(sentence_words[i:i + max_words])
                    chunks.append(sub_chunk)
                continue
                
            if current_word_count + sentence_word_count > max_words:
                chunks.append(" ".join(current_chunk_words))
                # Lấy overlap từ cuối current_chunk_words
                overlap_list = current_chunk_words[-overlap_words:] if len(current_chunk_words) > overlap_words else current_chunk_words
                current_chunk_words = list(overlap_list) + sentence_words
                current_word_count = len(current_chunk_words)
            else:
                current_chunk_words.extend(sentence_words)
                current_word_count += sentence_word_count
                
        if current_chunk_words:
            chunks.append(" ".join(current_chunk_words))
            
        return [c.strip() for c in chunks if c.strip()]

    def _score_chunk(self, chunk: str, query_entities: List[str], keywords: set) -> float:
        """Tính điểm phù hợp của chunk dựa trên thực thể và từ khóa trùng khớp."""
        chunk_lower = chunk.lower()
        score = 0.0
        
        # 1. Điểm trùng khớp Thực thể (Độ ưu tiên cao nhất)
        for entity in query_entities:
            if entity in chunk_lower:
                score += 3.0
                
        # 2. Điểm trùng khớp Từ khóa
        for kw in keywords:
            if kw in chunk_lower:
                score += 1.0
                
        return score

    # Xác định xem có nên mở rộng câu truy vấn để tăng độ chính xác hay không
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

    # Xây dựng ngữ cảnh từ các kết quả tìm kiếm để gửi cho LLM
    def _build_context(self, results: List[dict], question: str) -> tuple[str, List[SearchResult]]:
        """
        Sử dụng Micro-chunking & Entity/Keyword Scoring để chọn các đoạn tối ưu nhất:
        1. Chia bài viết thành các chunk nhỏ gọn (50-120 từ).
        2. Chấm điểm và trích chọn top 1-2 chunks liên quan nhất đến câu hỏi.
        """
        # Trích xuất thực thể từ câu hỏi
        query_entities = []
        try:
            query_entities_dict = self._graph_service.ner.extract_entities(question)
            for names in query_entities_dict.values():
                query_entities.extend([n.lower().strip() for n in names if len(n) > 2])
        except Exception as e:
            print(f"[Warning] Error extracting entities for micro-chunk scoring: {e}")

        # Trích xuất từ khóa từ câu hỏi
        keywords = set()
        try:
            cleaned = clean_query(question)
            if cleaned:
                keywords = set(cleaned.lower().split())
        except Exception as e:
            print(f"[Warning] Error cleaning query for micro-chunk scoring: {e}")

        context_parts = []
        sources = []
        seen_articles = set()

        for item in results:
            content = item.get('content', '')
            metadata = item.get('metadata', {})
            score = item.get('score', 0)

            title = metadata.get('title', 'Không rõ tiêu đề')
            source_name = metadata.get('source', 'Nguồn tin tức')
            article_id = item.get('id')

            # Bước A: Chia nhỏ văn bản thành các micro-chunks
            chunks = self.split_to_micro_chunks(content, max_words=120, overlap_words=20)
            
            if not chunks:
                continue

            # Bước B: Tính điểm liên quan cho từng chunk
            scored_chunks = []
            for chunk in chunks:
                chunk_score = self._score_chunk(chunk, query_entities, keywords)
                scored_chunks.append((chunk, chunk_score))

            # Sắp xếp theo điểm giảm dần
            scored_chunks.sort(key=lambda x: x[1], reverse=True)

            # Lấy top 1 hoặc 2 chunk có điểm cao nhất (điểm > 0)
            top_chunks = []
            if scored_chunks[0][1] > 0:
                top_chunks.append(scored_chunks[0][0])
                if len(scored_chunks) > 1 and scored_chunks[1][1] > 0:
                    top_chunks.append(scored_chunks[1][0])
            else:
                top_chunks.append(scored_chunks[0][0])

            # Ghép nội dung các top chunks được chọn
            trimmed_text = "\n...\n".join(top_chunks)

            context_parts.append(
                f"Nguồn: {source_name} - {title}\nNội dung: {trimmed_text}"
            )

            if article_id and article_id not in seen_articles:
                seen_articles.add(article_id)
                
                # Hiển thị chunk khớp tốt nhất trong phần "Nguồn tham khảo" của UI
                source_preview = top_chunks[0][:200] + "..." if len(top_chunks[0]) > 200 else top_chunks[0]
                
                sources.append(SearchResult(
                    chunk_text=source_preview,
                    similarity_score=round(score, 4),
                    vector_score=round(item.get('original_score', 0), 4),
                    keyword_score=round(item.get('keyword_score', 0), 4),
                    article_title=title,
                    article_source=source_name,
                    article_link=metadata.get('link', '')
                ))

        full_context = "\n\n".join(context_parts)
        return full_context, sources

    # Tạo phản hồi mặc định khi không tìm thấy thông tin phù hợp
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

    # Tính điểm dựa trên sự xuất hiện của các từ khóa trong nội dung
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

    # Trích xuất thông tin về khoảng thời gian từ câu hỏi tự nhiên
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
