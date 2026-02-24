"""
LLM Service — Abstract Layer for Large Language Models
Hỗ trợ chuyển đổi linh hoạt giữa Google Gemini (API) và Ollama (Local).
"""

import os
import abc
from typing import List, Optional
import google.generativeai as genai
import ollama

class LLMProvider(abc.ABC):
    """Abstract Base Class cho các LLM Provider"""
    
    @abc.abstractmethod
    def generate_response(self, context: str, question: str) -> str:
        """Sinh câu trả lời từ ngữ cảnh và câu hỏi"""
        pass
    
    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Tên provider (debug/logging)"""
        pass


class GeminiProvider(LLMProvider):
    """Provider sử dụng Google Gemini API"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-pro"):
        if not api_key:
            raise ValueError("Gemini API Key is required")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        
    @property
    def provider_name(self) -> str:
        return "Google Gemini API"

    def generate_response(self, context: str, question: str) -> str:
        prompt = f"""Dựa vào thông tin được cung cấp dưới đây, hãy trả lời câu hỏi một cách chi tiết, tự nhiên và chính xác bằng tiếng Việt.
Nếu thông tin không có trong bài viết, hãy nói rõ là không tìm thấy thông tin.

[THÔNG TIN NGỮ CẢNH]
{context}

[CÂU HỎI]
{question}

TRẢ LỜI:"""
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Lỗi khi gọi Gemini API: {str(e)}"


class OllamaProvider(LLMProvider):
    """Provider sử dụng Ollama chạy Local"""
    
    def __init__(self, model_name: str = "qwen2.5:1.5b"):
        self.model_name = model_name
        
    @property
    def provider_name(self) -> str:
        return f"Ollama Local ({self.model_name})"

    def generate_response(self, context: str, question: str) -> str:
        # Prompt ngắn gọn cho model nhỏ
        prompt = f"""Trả lời ngắn gọn bằng tiếng Việt dựa trên văn bản:

{context}

Hỏi: {question}
Đáp:"""
        
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{
                    'role': 'user',
                    'content': prompt,
                }],
                options={
                    'num_predict': 256,     # Giới hạn output tokens
                    'temperature': 0.3,     # Giảm randomness -> nhanh hơn
                    'num_ctx': 2048,        # Giảm context window
                }
            )
            return response['message']['content']
        except Exception as e:
            return f"Lỗi khi gọi Ollama: {str(e)}. Hãy chắc chắn Ollama đang chạy."


class LLMService:
    """Wrapper Service để sử dụng trong ChatbotService"""
    
    def __init__(self, provider: LLMProvider):
        self.provider = provider
        
    def generate_answer(self, context: str, question: str) -> str:
        return self.provider.generate_response(context, question)
