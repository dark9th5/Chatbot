"""
Chatbot Service — Business Logic Layer (RAG Architecture - Qdrant)
Xử lý logic RAG: Tìm kiếm ngữ nghĩa với Qdrant + Sinh câu trả lời bằng LLM.

Design Pattern: Service Layer + Dependency Injection
"""

import numpy as np
import re
from typing import List, Optional
from datetime import date, datetime, timedelta

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
        """Khởi tạo đối tượng và chuẩn bị các phụ thuộc cần dùng."""
        self._graph_service = graph_search_service
        self._article_repo = article_repository
        self._llm_service = llm_service
        self._query_expansion_service = query_expansion_service

    # Xử lý câu hỏi của người dùng và trả về câu trả lời tối ưu nhất
    def get_answer(
        self,
        question: str,
        top_k: int = 3,
        data_source: str = "news",
        category: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        conversation_context: Optional[str] = None,
    ) -> ChatResponse:
        """
        Xử lý câu hỏi theo quy trình RAG (Graph Retrieval).
        """
        # Documents feature removed — always query news
        data_source = "news"
        source_label = "các bài báo"

        # Nếu không còn bộ lọc thủ công, lấy mốc thời gian trực tiếp từ câu hỏi tự nhiên.
        # Bước 0: Gắn ngữ cảnh danh mục vào truy vấn (nếu có)
        effective_question = question
        if conversation_context and conversation_context.strip():
            effective_question = f"{conversation_context.strip()}. {question}"

        explicit_date = self._extract_explicit_date(effective_question)
        inferred_from_date, inferred_to_date = (
            self._extract_date_range(effective_question)
            if data_source == "news"
            else (None, None)
        )
        # Ngày tương đối như "hôm nay" hợp với lọc theo ngày xuất bản. Ngày tuyệt
        # đối như "16/5" thường là ngày được nhắc trong nội dung (đặc biệt bài dự
        # báo đăng tối hôm trước), nên dùng làm tín hiệu mềm thay vì cắt cứng theo
        # `published_date`.
        if explicit_date is not None and from_date is None and to_date is None:
            effective_from_date = None
            effective_to_date = None
        else:
            effective_from_date = from_date or inferred_from_date
            effective_to_date = to_date or inferred_to_date

        expanded_query = effective_question
        if category and str(category).strip():
            expanded_query = f"{str(category).strip()}. {effective_question}"

        # Nếu câu hỏi rất chung chung, ưu tiên hỏi làm rõ thay vì truy hồi bừa
        try:
            pre_analysis = self._graph_service.ner.analyze_query(expanded_query)
            entities = pre_analysis.get("entities", {}) or {}
            intents = set(pre_analysis.get("question_intents", []) or [])
            normalized_category = str(category or "").casefold()

            is_travel = "du lịch" in normalized_category or "travel" in normalized_category
            is_where_question = "WHERE" in intents
            has_loc = bool(entities.get("LOC"))

            is_weatherish = bool(entities.get("DATE") or entities.get("TIME")) and (
                bool(entities.get("TEMPERATURE"))
                or any(term in {"nóng", "lạnh"} for term in (entities.get("STATE") or []))
            )

            if data_source == "news" and is_travel and is_where_question and not has_loc and not conversation_context:
                return self._empty_response(
                    question,
                    message=(
                        "Bạn muốn đi chơi ở khu vực nào (tỉnh/thành hoặc quận/huyện)? "
                        "Đi trong ngày hay 2-3 ngày, và bạn thích kiểu biển/núi/ăn uống?"
                    ),
                    needs_clarification=True,
                )

            if data_source == "news" and is_weatherish and not has_loc:
                return self._empty_response(
                    question,
                    message="Bạn muốn hỏi thời tiết ngày mai ở khu vực nào (tỉnh/thành hoặc quận/huyện)?",
                    needs_clarification=True,
                )
        except Exception as e:
            print(f"[Warning] Pre-check query analysis failed: {e}")
        
        # Bước 1: Tìm kiếm trên Đồ thị thực thể (Graph Search)
        print("[*] Searching Graph...")
        search_limit = max(top_k * 4, top_k) if explicit_date is not None else top_k
        valid_results = self._graph_service.search(
            query=expanded_query,
            limit=search_limit,
            data_source=data_source,
            category=category,
            from_date=effective_from_date,
            to_date=effective_to_date,
        )
        if explicit_date is not None and data_source == "news":
            explicit_date_results = self._graph_service.search_explicit_date_mentions(
                query=expanded_query,
                explicit_date=explicit_date,
                limit=search_limit,
                data_source=data_source,
            )
            valid_results = self._graph_service._merge_results(
                explicit_date_results,
                valid_results,
            )
            valid_results = self._prefer_explicit_date_results(valid_results, explicit_date)
        valid_results = valid_results[:top_k]

        # LOGGING
        print(f"[*] Graph Search complete. Found {len(valid_results)} candidates.")

        if not valid_results:
            analysis = getattr(self._graph_service, "last_query_analysis", {}) or {}
            if analysis.get("requires_clarification"):
                entities = analysis.get("entities", {}) or {}
                intents = set(analysis.get("question_intents", []) or [])

                if (entities.get("DATE") or entities.get("TIME")) and (
                    entities.get("TEMPERATURE") or entities.get("STATE")
                ):
                    return self._empty_response(
                        question,
                        message="Bạn muốn hỏi thời tiết ở khu vực nào (tỉnh/thành hoặc quận/huyện)?",
                        needs_clarification=True,
                    )

                if "WHERE" in intents:
                    return self._empty_response(
                        question,
                        message="Bạn đang muốn hỏi ở khu vực nào (tỉnh/thành hoặc quận/huyện)?",
                        needs_clarification=True,
                    )

                return self._empty_response(
                    question,
                    message=(
                        "Câu hỏi này còn chung chung. Bạn hãy thêm đối tượng cần hỏi, ví dụ: "
                        "“giá vàng đang tăng mạnh không?” hoặc “mưa lớn còn kéo dài không?”"
                    ),
                    needs_clarification=True,
                )
            return self._empty_response(
                question,
                message=f"Xin lỗi, tôi chưa tìm thấy thông tin phù hợp trong {source_label} để trả lời câu hỏi này."
            )

        # Bước 2: Xây dựng Context cho LLM (Sử dụng Micro-chunking & Entity/Keyword Scoring)
        print("[*] Building prompt context from Graph nodes (Micro-chunking enabled)...")
        context_text, sources = self._build_context(
            valid_results,
            effective_question,
            data_source=data_source,
        )
        if not context_text.strip() or not sources:
            return self._empty_response(
                question,
                message=f"Xin lỗi, tôi chưa tìm thấy thông tin phù hợp trong {source_label} để trả lời câu hỏi này."
            )

        # Bước 3: Gửi cho LLM sinh câu trả lời
        print(f"[*] Generating answer using {self._llm_service.provider.provider_name}...")
        explicit_date_label = self._extract_explicit_date_label(effective_question)
        llm_response = self._llm_service.generate_answer(
            context_text,
            effective_question,
            source_label=source_label,
            reference_date=explicit_date_label,
        )
        llm_response = self._anchor_answer_to_explicit_date(
            llm_response,
            explicit_date_label,
        )
        if self._answer_indicates_no_info(llm_response):
            sources = []
        print("[*] Answer generated successfully.")

        return ChatResponse(
            question=question,
            answer=llm_response,
            sources=sources,
            total_chunks_searched=0, # Không dùng chunking ở DB nữa, tự micro-chunk ở bộ nhớ
            needs_clarification=False,
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

    @staticmethod
    def _answer_indicates_no_info(answer: str) -> bool:
        """Xử lý một phần nghiệp vụ của module theo tham số đầu vào."""
        lowered = (answer or "").casefold()
        return any(
            marker in lowered
            for marker in (
                "không tìm thấy thông tin",
                "không tìm thấy dữ liệu",
                "chưa tìm thấy thông tin",
                "không có thông tin",
                "không nhắc tới",
                "không nhắc đến",
                "không đề cập",
                "không tìm thấy",
                "chưa có thông tin",
                "i could not find",
                "cannot find",
            )
        )

    def _extract_focus_terms(self, question: str) -> List[str]:
        """Lấy các từ/cụm trọng tâm để giảm nguồn nhiễu khi dựng context."""
        generic_terms = {
            "việt nam",
            "vn",
            "thế giới",
            "quốc tế",
            "tình hình",
            "hiện nay",
            "hôm nay",
            "hôm qua",
            "ngày mai",
        }

        try:
            analysis = self._graph_service.ner.analyze_query(question)
            candidates = (
                list(analysis.get("anchor_terms", []))
                + list(analysis.get("supporting_terms", []))
                + list(analysis.get("residual_keywords", []))
            )
        except Exception:
            candidates = clean_query(question).split()

        terms: List[str] = []
        seen = set()
        for raw_term in candidates:
            term = raw_term.strip().lower()
            if len(term) < 3 or term in generic_terms or term in seen:
                continue
            seen.add(term)
            terms.append(term)
        return terms

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
    def _build_context(
        self,
        results: List[dict],
        question: str,
        data_source: str,
    ) -> tuple[str, List[SearchResult]]:
        """
        Sử dụng Micro-chunking & Entity/Keyword Scoring để chọn các đoạn tối ưu nhất:
        1. Chia bài viết thành các chunk nhỏ gọn (50-120 từ).
        2. Chấm điểm và trích chọn top 1-2 chunks liên quan nhất đến câu hỏi.
        """
        # Trích xuất thực thể + tín hiệu ngữ nghĩa từ câu hỏi
        query_entities = []
        try:
            analysis = self._graph_service.ner.analyze_query(question)
            query_entities.extend(
                term.lower().strip()
                for term in analysis.get("search_terms", [])
                if len(term) > 2
            )
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

        focus_terms = self._extract_focus_terms(question)

        context_parts = []
        sources = []
        seen_articles = set()

        for item in results:
            content = item.get('content', '')
            metadata = item.get('metadata', {})
            score = item.get('score', 0)

            title = metadata.get('title', 'Không rõ tiêu đề')
            source_name = metadata.get('source', 'Nguồn tin tức')
            published_date = self._normalize_source_date(metadata.get('published_date'))
            article_id = item.get('id')

            if data_source == "news" and focus_terms:
                haystack = f"{title}\n{content}".casefold()
                if not any(term in haystack for term in focus_terms):
                    continue

            # Bước A: Chia nhỏ văn bản thành các micro-chunks
            chunks = self.split_to_micro_chunks(content, max_words=120, overlap_words=20)
            
            if not chunks:
                continue

            # Bước B: Tính điểm liên quan cho từng chunk
            scored_chunks = []
            for index, chunk in enumerate(chunks):
                chunk_score = self._score_chunk(chunk, query_entities, keywords)
                scored_chunks.append((index, chunk, chunk_score))

            # Sắp xếp theo điểm giảm dần
            scored_chunks.sort(key=lambda x: x[2], reverse=True)

            # Chỉ giữ lại bài viết nếu có ít nhất 1 micro-chunk có điểm > 0
            if scored_chunks[0][2] <= 0:
                continue

            # Lấy top 1 hoặc 2 chunk có điểm cao nhất (điểm > 0)
            selected_indices: List[int] = []
            selected_indices.append(scored_chunks[0][0])
            if len(scored_chunks) > 1 and scored_chunks[1][2] > 0:
                selected_indices.append(scored_chunks[1][0])

            top_chunks = [chunks[index] for index in selected_indices]

            # Ghép nội dung các top chunks được chọn
            trimmed_text = "\n...\n".join(top_chunks)

            source_date_text = f"\nNgày nguồn: {published_date.isoformat()}" if published_date else ""
            context_parts.append(
                f"Nguồn: {source_name} - {title}{source_date_text}\nNội dung: {trimmed_text}"
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
                    article_link=metadata.get('link', ''),
                    published_date=published_date,
                ))

        full_context = "\n\n".join(context_parts)
        return full_context, sources

    # Tạo phản hồi mặc định khi không tìm thấy thông tin phù hợp
    def _empty_response(
        self,
        question: str,
        message: str = "",
        needs_clarification: bool = False,
    ) -> ChatResponse:
        """Trả về response rỗng khi không tìm thấy tin."""
        if not message:
            message = "Xin lỗi, hiện tại tôi không tìm thấy thông tin liên quan trong dữ liệu."

        return ChatResponse(
            question=question,
            answer=message,
            sources=[],
            total_chunks_searched=0,
            needs_clarification=needs_clarification,
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
        Hỗ trợ: ngày cụ thể dạng 16/5, 16-05-2026, 'hôm nay', 'hôm qua',
        'X ngày qua', 'tuần này'.
        """
        today = date.today()
        q = question.lower()

        explicit_date = self._extract_explicit_date(question)
        if explicit_date is not None:
            return explicit_date, explicit_date

        # 1. Hôm nay
        if "hôm nay" in q or "trong ngày" in q:
            return today, today
        
        # 2. Hôm qua
        if "hôm qua" in q:
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday

        # 3. Ngày mai
        if "ngày mai" in q:
            tomorrow = today + timedelta(days=1)
            return tomorrow, tomorrow
            
        # 4. X ngày qua / X ngày gần đây
        match_days = re.search(r'(\d+)\s+ngày\s+(qua|gần\s+đây)', q)
        if match_days:
            days = int(match_days.group(1))
            start_date = today - timedelta(days=days)
            return start_date, today

        # 5. Tuần này
        if "tuần này" in q:
            start_of_week = today - timedelta(days=today.weekday())
            return start_of_week, today

        # 6. Mới nhất / Gần đây / Mới có (Mặc định 3 ngày qua để ưu tiên tin mới)
        if "mới nhất" in q or "gần đây" in q or "mới có" in q:
            start_date = today - timedelta(days=3)
            return start_date, today

        return None, None

    def _extract_explicit_date(self, question: str) -> Optional[date]:
        """
        Lấy ngày tuyệt đối nếu câu hỏi chứa mẫu như 16/5, 16-05 hoặc 16/05/2026.
        Nếu thiếu năm, mặc định dùng năm hiện tại của server.
        """
        match = re.search(
            r"(?:ngày\s+)?(?P<day>\d{1,2})[/-](?P<month>\d{1,2})(?:[/-](?P<year>\d{2,4}))?",
            question,
            flags=re.IGNORECASE,
        )
        if not match:
            return None

        try:
            day = int(match.group("day"))
            month = int(match.group("month"))
            raw_year = match.group("year")
            year = int(raw_year) if raw_year else date.today().year
            if raw_year and len(raw_year) == 2:
                year += 2000
            return date(year, month, day)
        except ValueError:
            return None

    def _extract_explicit_date_label(self, question: str) -> Optional[str]:
        """Trích xuất dữ liệu nội bộ phục vụ phân tích."""
        explicit_date = self._extract_explicit_date(question)
        if explicit_date is None:
            return None

        return f"ngày {explicit_date.day}/{explicit_date.month}/{explicit_date.year}"

    @staticmethod
    def _date_text_variants(target_date: date) -> tuple[str, ...]:
        """Xử lý một phần nghiệp vụ của module theo tham số đầu vào."""
        day = target_date.day
        month = target_date.month
        year = target_date.year
        return (
            f"{day}/{month}",
            f"{day:02d}/{month:02d}",
            f"{day}.{month}",
            f"{day:02d}.{month:02d}",
            f"{day}-{month}",
            f"{day:02d}-{month:02d}",
            f"ngày {day}/{month}",
            f"ngày {day:02d}/{month:02d}",
            f"{day}/{month}/{year}",
            f"{day:02d}/{month:02d}/{year}",
        )

    def _prefer_explicit_date_results(
        self,
        results: List[dict],
        explicit_date: date,
    ) -> List[dict]:
        """
        Với câu hỏi có ngày tuyệt đối, ưu tiên bài thật sự nhắc tới ngày đó trong
        tiêu đề/nội dung. Điều này giữ được các bài dự báo đăng tối hôm trước
        nhưng nói về thời tiết của ngày hôm sau.
        """
        variants = self._date_text_variants(explicit_date)
        matching: List[dict] = []
        others: List[dict] = []

        for item in results:
            metadata = item.get("metadata", {}) or {}
            haystack = f"{metadata.get('title', '')}\n{item.get('content', '')}".casefold()
            bucket = matching if any(variant in haystack for variant in variants) else others
            bucket.append(item)

        return matching + others if matching else results

    @staticmethod
    def _normalize_source_date(value) -> Optional[date]:
        """
        Chuẩn hóa published_date từ MySQL về date thuần.
        Dữ liệu hiện có trong DB lẫn cả datetime object lẫn chuỗi 'YYYY-MM-DD HH:MM:SS'.
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            for parser in (
                lambda text: datetime.fromisoformat(text).date(),
                lambda text: date.fromisoformat(text[:10]),
            ):
                try:
                    return parser(raw)
                except ValueError:
                    continue
        return None



    @staticmethod
    def _anchor_answer_to_explicit_date(answer: str, explicit_date_label: Optional[str]) -> str:
        """
        Chặn lỗi ngôn ngữ kiểu nguồn cũ có chữ 'hôm nay' nhưng người dùng đang hỏi ngày lịch sử.
        """
        if not explicit_date_label:
            return answer

        return re.sub(
            r"\bhôm nay\b",
            explicit_date_label,
            answer,
            flags=re.IGNORECASE,
        )
