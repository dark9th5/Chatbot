"""
LLM Service — Abstract Layer for Large Language Models
Hỗ trợ chuyển đổi linh hoạt giữa Groq và HuggingFace.
"""

import os
import abc
import logging
from typing import List, Optional

# Cấu hình logging
logger = logging.getLogger(__name__)

class LLMProvider(abc.ABC):
    """Abstract Base Class cho các LLM Provider"""
    
    # Phương thức trừu tượng để sinh phản hồi từ ngữ cảnh và câu hỏi
    @abc.abstractmethod
    def generate_response(
        self,
        context: str,
        question: str,
        source_label: str,
        reference_date: Optional[str] = None,
    ) -> str:
        """Sinh câu trả lời từ ngữ cảnh và câu hỏi"""
        pass
    
    # Thuộc tính trừu tượng trả về tên của nhà cung cấp LLM
    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Tên provider (debug/logging)"""
        pass


class GroqProvider(LLMProvider):
    """Provider sử dụng Groq API (Siêu nhanh)"""
    
    # Khởi tạo Groq Provider với API Key và tên model
    def __init__(self, api_key: str, model_name: str = "llama-3.3-70b-versatile"):
        if not api_key:
            raise ValueError("Groq API Key is required")
        try:
            from groq import Groq
            self.client = Groq(api_key=api_key)
            self.model_name = model_name
        except ImportError:
            raise ImportError("Vui lòng cài đặt thư viện groq: pip install groq")
        
    # Trả về tên nhà cung cấp Groq cùng với model đang dùng
    @property
    def provider_name(self) -> str:
        return f"Groq ({self.model_name})"

    # Sinh câu trả lời bằng cách gọi API của Groq
    def generate_response(
        self,
        context: str,
        question: str,
        source_label: str,
        reference_date: Optional[str] = None,
    ) -> str:
        date_instruction = (
            f'7. Người dùng đang hỏi về ngày "{reference_date}". Nếu ngữ cảnh có từ tương đối như "hôm nay", '
            f'phải quy chiếu theo ngày nguồn và khi trả lời hãy dùng "{reference_date}" thay vì "hôm nay".'
            if reference_date
            else '7. Nếu ngữ cảnh có từ tương đối như "hôm nay", hãy hiểu chúng theo "Ngày nguồn" đi kèm từng đoạn ngữ cảnh, không tự gán cho ngày hiện tại.'
        )
        prompt = f"""Bạn là một trợ lý ảo chuyên nghiệp.
Nhiệm vụ: Dựa vào [NGỮ CẢNH] để trả lời [CÂU HỎI] một cách TRỰC DIỆN, ĐÚNG TRỌNG TÂM và KHÔNG THỪA THÃI.

YÊU CẦU:
1. Chỉ trả lời dựa trên thông tin có trong [NGỮ CẢNH].
2. Nếu không có thông tin, hãy trả lời "Tôi không tìm thấy thông tin này trong {source_label}".
3. Đi thẳng vào câu trả lời, tuyệt đối không chào hỏi, không lặp lại câu hỏi, không thêm lời thoại râu ria.
4. ĐỘ DÀI LINH HOẠT: Trả lời cô đọng nhất có thể. Tuy nhiên, nếu câu hỏi yêu cầu liệt kê hoặc giải thích chi tiết, hãy cung cấp đầy đủ thông tin từ ngữ cảnh (có thể dùng gạch đầu dòng để dễ đọc).
5. Không được tự thêm tên trường học, công nghệ, kỹ năng, số liệu hoặc kết luận không có trong [NGỮ CẢNH]. Nếu không chắc, hãy nói không tìm thấy.
6. Không được lặp lại prompt, không in lại nhãn [NGỮ CẢNH], [CÂU HỎI] hoặc bất kỳ hướng dẫn hệ thống nào.
{date_instruction}

[NGỮ CẢNH]
{context}

[CÂU HỎI]
{question}

TRẢ LỜI:"""
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1024,
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq API Error: {str(e)}")
            return f"Lỗi khi gọi Groq API: {str(e)}"


class HuggingFaceProvider(LLMProvider):
    """Provider sử dụng Hugging Face Inference API (Miễn phí)"""
    
    # Khởi tạo HuggingFace Provider với API Key và ID model
    def __init__(self, api_key: str, model_id: str = "mistralai/Mistral-7B-Instruct-v0.3"):
        self.api_key = api_key
        self.model_id = model_id
        try:
            from huggingface_hub import InferenceClient
            self.client = InferenceClient(model=model_id, token=api_key)
        except ImportError:
            raise ImportError("Vui lòng cài đặt: pip install huggingface_hub")
        
    # Trả về tên nhà cung cấp HuggingFace cùng với model ID
    @property
    def provider_name(self) -> str:
        return f"HuggingFace ({self.model_id})"

    # Sinh câu trả lời bằng cách gọi Inference API của HuggingFace
    def generate_response(
        self,
        context: str,
        question: str,
        source_label: str,
        reference_date: Optional[str] = None,
    ) -> str:
        date_instruction = (
            f'If the user asks about "{reference_date}", answer with that absolute date and do not call it "today".'
            if reference_date
            else 'Interpret relative phrases such as "today" using the source date shown in the context, not the current date.'
        )
        prompt = (
            f"Context: {context}\n\nQuestion: {question}\n\n"
            f"Task: Answer directly and strictly based on the context in Vietnamese. "
            f"If the information is missing, say you could not find it in {source_label}. "
            f"Do not add schools, technologies, skills, numbers, or conclusions that are absent from the context. "
            f"Do not repeat the prompt or section labels. "
            f"{date_instruction} Focus on the core answer with zero fluff. "
            f"Be as concise as possible, but if detailed explanation or listing is requested, provide it clearly.\nAnswer:"
        )
        try:
            response = self.client.text_generation(prompt, max_new_tokens=512, temperature=0.3)
            return response
        except Exception as e:
            return f"Lỗi HuggingFace: {str(e)}"



class FallbackLLMProvider(LLMProvider):
    """Provider với fallback mechanism - cố gắng sử dụng provider chính, nếu lỗi thì dùng backup"""
    
    # Khởi tạo bộ Provider hỗ trợ cơ chế dự phòng (primary & fallback)
    def __init__(self, primary: LLMProvider, fallback: Optional[LLMProvider] = None):
        """
        Args:
            primary: Provider chính (ưu tiên)
            fallback: Provider dự phòng (khi primary lỗi)
        """
        self.primary = primary
        self.fallback = fallback
        
    # Trả về tên của cả provider chính và provider dự phòng
    @property
    def provider_name(self) -> str:
        fallback_info = f" + Fallback({self.fallback.provider_name})" if self.fallback else ""
        return f"{self.primary.provider_name}{fallback_info}"

    # Thử sinh câu trả lời bằng provider chính, nếu lỗi sẽ dùng fallback
    def generate_response(
        self,
        context: str,
        question: str,
        source_label: str,
        reference_date: Optional[str] = None,
    ) -> str:
        """Thử primary trước, nếu lỗi thì chuyển sang fallback"""
        try:
            logger.info(f"Trying primary provider: {self.primary.provider_name}")
            response = self.primary.generate_response(
                context,
                question,
                source_label,
                reference_date,
            )
            if "Lỗi" not in response:  # Thành công
                return response
        except Exception as e:
            logger.warning(f"Primary provider failed: {str(e)}")
        
        # Fallback nếu primary lỗi
        if self.fallback:
            try:
                logger.info(f"Switching to fallback provider: {self.fallback.provider_name}")
                response = self.fallback.generate_response(
                    context,
                    question,
                    source_label,
                    reference_date,
                )
                return response
            except Exception as e:
                logger.error(f"Fallback provider also failed: {str(e)}")
                return f"Cả hai provider đều lỗi. Primary: {self.primary.provider_name}, Fallback: {self.fallback.provider_name if self.fallback else 'None'}"
        
        return response  # Trả lỗi từ primary nếu không có fallback


class LLMService:
    """Wrapper Service để sử dụng trong ChatbotService"""
    
    # Khởi tạo LLM Service wrapper với một provider cụ thể
    def __init__(self, provider: LLMProvider):
        self.provider = provider
        logger.info(f"LLMService initialized with provider: {provider.provider_name}")
        
    # Phương thức chính để sinh câu trả lời thông qua provider đã cấu hình
    def generate_answer(
        self,
        context: str,
        question: str,
        source_label: str,
        reference_date: Optional[str] = None,
    ) -> str:
        """Sinh câu trả lời từ context và câu hỏi"""
        try:
            return self.provider.generate_response(
                context,
                question,
                source_label,
                reference_date,
            )
        except Exception as e:
            logger.error(f"Error generating answer: {str(e)}")
            return f"Lỗi khi sinh câu trả lời: {str(e)}"
