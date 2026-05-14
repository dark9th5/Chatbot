"""
LLM Service — Abstract Layer for Large Language Models
<<<<<<< HEAD
Hỗ trợ chuyển đổi linh hoạt giữa Google Gemini (API) và Ollama (Local).
=======
Hỗ trợ chuyển đổi linh hoạt giữa Google Gemini (API), OpenAI, Ollama (Local), và llama.cpp (Local).

Giai đoạn 1: Tách phụ thuộc Ollama + Thêm các provider thay thế
- GeminiProvider: Google Gemini API
- OpenAIProvider: OpenAI GPT API
- LlamaCppProvider: Local inference với llama.cpp
- OllamaProvider: Ollama local (deprecated, giữ cho backward compat)
- FallbackLLMProvider: Fallback mechanism khi provider chính lỗi
>>>>>>> c1d95b9 (Initial commit)
"""

import os
import abc
<<<<<<< HEAD
from typing import List, Optional
import google.generativeai as genai
import ollama
=======
import logging
from typing import List, Optional
import google.generativeai as genai

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False

logger = logging.getLogger(__name__)
>>>>>>> c1d95b9 (Initial commit)

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


<<<<<<< HEAD
class OllamaProvider(LLMProvider):
    """Provider sử dụng Ollama chạy Local"""
    
    def __init__(self, model_name: str = "qwen2.5:1.5b"):
=======
class OpenAIProvider(LLMProvider):
    """Provider sử dụng OpenAI GPT API (GPT-4, GPT-3.5-turbo)"""
    
    def __init__(self, api_key: str, model_name: str = "gpt-3.5-turbo"):
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package is not installed. Install with: pip install openai")
        if not api_key:
            raise ValueError("OpenAI API Key is required")
        openai.api_key = api_key
        self.model_name = model_name
        
    @property
    def provider_name(self) -> str:
        return f"OpenAI {self.model_name}"

    def generate_response(self, context: str, question: str) -> str:
        prompt = f"""Dựa vào thông tin được cung cấp dưới đây, hãy trả lời câu hỏi một cách chi tiết, tự nhiên và chính xác bằng tiếng Việt.
Nếu thông tin không có trong bài viết, hãy nói rõ là không tìm thấy thông tin.

[THÔNG TIN NGỮ CẢNH]
{context}

[CÂU HỎI]
{question}

TRẢ LỜI:"""
        
        try:
            response = openai.ChatCompletion.create(
                model=self.model_name,
                messages=[{
                    'role': 'system',
                    'content': 'Bạn là một trợ lý thông minh và hữu ích. Trả lời bằng tiếng Việt.'
                }, {
                    'role': 'user',
                    'content': prompt
                }],
                temperature=0.3,
                max_tokens=512
            )
            return response['choices'][0]['message']['content']
        except Exception as e:
            return f"Lỗi khi gọi OpenAI API: {str(e)}"


class LlamaCppProvider(LLMProvider):
    """Provider sử dụng llama.cpp cho local inference với GGUF models"""
    
    def __init__(self, model_path: str, n_gpu_layers: int = -1, n_ctx: int = 2048):
        """
        Args:
            model_path: Đường dẫn đến tệp GGUF model (ví dụ: models/qwen2.5-1.5b.gguf)
            n_gpu_layers: Số layers chạy trên GPU (-1 = all available)
            n_ctx: Context window size (giảm để tiết kiệm RAM)
        """
        if not LLAMA_CPP_AVAILABLE:
            raise ImportError("llama-cpp-python package is not installed. Install with: pip install llama-cpp-python")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        try:
            self.model = Llama(
                model_path=model_path,
                n_gpu_layers=n_gpu_layers,
                n_ctx=n_ctx,
                verbose=False
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load llama.cpp model: {str(e)}")
        
    @property
    def provider_name(self) -> str:
        return "llama.cpp (Local GGUF)"

    def generate_response(self, context: str, question: str) -> str:
        prompt = f"""Trả lời bằng tiếng Việt dựa trên thông tin:

{context}

Hỏi: {question}
Đáp:"""
        
        try:
            response = self.model(
                prompt,
                max_tokens=256,
                temperature=0.3,
                top_p=0.9,
                stop=["Hỏi:"]
            )
            return response['choices'][0]['text'].strip()
        except Exception as e:
            return f"Lỗi khi gọi llama.cpp: {str(e)}"


class OllamaProvider(LLMProvider):
    """Provider sử dụng Ollama chạy Local (Deprecated - dùng LlamaCppProvider thay thế)"""
    
    def __init__(self, model_name: str = "qwen2.5:1.5b"):
        if not OLLAMA_AVAILABLE:
            raise ImportError("ollama package is not installed. Install with: pip install ollama")
>>>>>>> c1d95b9 (Initial commit)
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
<<<<<<< HEAD
            return f"Lỗi khi gọi Ollama: {str(e)}. Hãy chắc chắn Ollama đang chạy."
=======
            logger.error(f"Ollama error: {str(e)}")
            return f"Lỗi khi gọi Ollama: {str(e)}. Hãy chắc chắn Ollama đang chạy tại localhost:11434"


class FallbackLLMProvider(LLMProvider):
    """Provider với fallback mechanism - cố gắng sử dụng provider chính, nếu lỗi thì dùng backup"""
    
    def __init__(self, primary: LLMProvider, fallback: Optional[LLMProvider] = None):
        """
        Args:
            primary: Provider chính (ưu tiên)
            fallback: Provider dự phòng (khi primary lỗi)
        """
        self.primary = primary
        self.fallback = fallback
        
    @property
    def provider_name(self) -> str:
        fallback_info = f" + Fallback({self.fallback.provider_name})" if self.fallback else ""
        return f"{self.primary.provider_name}{fallback_info}"

    def generate_response(self, context: str, question: str) -> str:
        """Thử primary trước, nếu lỗi thì chuyển sang fallback"""
        try:
            logger.info(f"Trying primary provider: {self.primary.provider_name}")
            response = self.primary.generate_response(context, question)
            if "Lỗi" not in response:  # Thành công
                return response
        except Exception as e:
            logger.warning(f"Primary provider failed: {str(e)}")
        
        # Fallback nếu primary lỗi
        if self.fallback:
            try:
                logger.info(f"Switching to fallback provider: {self.fallback.provider_name}")
                response = self.fallback.generate_response(context, question)
                return response
            except Exception as e:
                logger.error(f"Fallback provider also failed: {str(e)}")
                return f"Cả hai provider đều lỗi. Primary: {self.primary.provider_name}, Fallback: {self.fallback.provider_name if self.fallback else 'None'}"
        
        return response  # Trả lỗi từ primary nếu không có fallback
>>>>>>> c1d95b9 (Initial commit)


class LLMService:
    """Wrapper Service để sử dụng trong ChatbotService"""
    
    def __init__(self, provider: LLMProvider):
        self.provider = provider
<<<<<<< HEAD
        
    def generate_answer(self, context: str, question: str) -> str:
        return self.provider.generate_response(context, question)
=======
        logger.info(f"LLMService initialized with provider: {provider.provider_name}")
        
    def generate_answer(self, context: str, question: str) -> str:
        """
        Sinh câu trả lời từ context và question
        
        Args:
            context: Văn bản ngữ cảnh từ RAG
            question: Câu hỏi người dùng
            
        Returns:
            Câu trả lời từ LLM
        """
        try:
            logger.debug(f"Generating answer with {self.provider.provider_name}")
            response = self.provider.generate_response(context, question)
            logger.debug(f"Answer generated successfully (length: {len(response)})")
            return response
        except Exception as e:
            logger.error(f"Error generating answer: {str(e)}")
            return f"Lỗi khi sinh câu trả lời: {str(e)}"
>>>>>>> c1d95b9 (Initial commit)
