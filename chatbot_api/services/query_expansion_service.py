from .llm_service import LLMService
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

class QueryExpansionService:
    """
    Service mở rộng truy vấn (Query Expansion) bằng LLM.
    Mục đích: Viết lại câu hỏi của người dùng để rõ nghĩa hơn và bao gồm các từ khóa liên quan.
    """

    # Khởi tạo dịch vụ mở rộng truy vấn với LLM Service
    def __init__(self, llm_service: LLMService):
        """Khởi tạo đối tượng và chuẩn bị các phụ thuộc cần dùng."""
        self.llm_service = llm_service

    # Viết lại câu hỏi gốc để rõ nghĩa và hiệu quả hơn khi tìm kiếm
    def expand_query(self, original_query: str, timeout_seconds: float = 4.0) -> str:
        """
        Mở rộng câu hỏi gốc.
        Ví dụ: "giá vàng" -> "Giá vàng hôm nay tại Việt Nam biến động như thế nào?"
        """
        # Nếu câu hỏi quá ngắn, mới cần expand
        if len(original_query.split()) > 10:
            return original_query

        prompt = f"""
        Bạn là một trợ lý ảo tìm kiếm tin tức.
        Nhiệm vụ: Viết lại câu hỏi sau của người dùng để rõ nghĩa hơn, đầy đủ chủ ngữ vị ngữ và bao gồm các từ khóa liên quan để tìm kiếm hiệu quả hơn.
        
        Câu hỏi gốc: '{original_query}'
        
        Chỉ trả về câu hỏi đã viết lại, không giải thích gì thêm.
        Câu hỏi viết lại:
        """
        
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    self.llm_service.generate_answer,
                    context="",
                    question=prompt,
                )
                expanded_query = future.result(timeout=timeout_seconds)

            # Clean up response (remove potential quotes or prefixes)
            expanded_query = expanded_query.strip().strip('"').strip("'")
            
            # Nếu LLM trả về quá dài hoặc linh tinh, dùng lại câu gốc
            if len(expanded_query) > 200: 
                return original_query
                
            print(f"[Query Expansion] '{original_query}' -> '{expanded_query}'")
            return expanded_query
        except FutureTimeoutError:
            print(f"[Query Expansion] Timeout after {timeout_seconds}s, use original query.")
            return original_query
        except Exception as e:
            print(f"[Query Expansion] Error: {e}")
            return original_query
