"""
Embedding Service — Singleton Pattern
Tải model Sentence-Transformers MỘT LẦN DUY NHẤT và cung cấp
method encode_query() cho toàn bộ ứng dụng.

Design Pattern: Singleton (thông qua module-level instance)
"""

import numpy as np
from typing import List

from sentence_transformers import SentenceTransformer


class EmbeddingService:
    """
    Service xử lý vector hóa văn bản.
    
    Singleton Pattern: Chỉ tạo 1 instance duy nhất trong dependencies.py.
    Model được tải lên bộ nhớ 1 lần và tái sử dụng cho mọi request.
    """

    MODEL_NAME = "bkai-foundation-models/vietnamese-bi-encoder"

    def __init__(self):
        """Tải model khi khởi tạo (chỉ gọi 1 lần)"""
        print(f"[EmbeddingService] Dang tai model: {self.MODEL_NAME}")
        # device='cpu' để đảm bảo chạy ổn định trên máy không GPU
        self._model = SentenceTransformer(self.MODEL_NAME)
        self._dimension = self._model.get_sentence_embedding_dimension()
        print(f"[EmbeddingService] Tai model thanh cong! Dimension: {self._dimension}")

    @property
    def dimension(self) -> int:
        """Số chiều của vector embedding"""
        return self._dimension

    @property
    def is_loaded(self) -> bool:
        """Kiểm tra model đã được tải chưa"""
        return self._model is not None

    def encode_query(self, text: str) -> np.ndarray:
        """
        Chuyển câu hỏi thành vector embedding.
        
        Args:
            text: Câu hỏi của user
            
        Returns:
            np.ndarray: Vector embedding (1 x dimension)
        """
        return self._model.encode(text, convert_to_numpy=True)

    def encode_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Chuyển nhiều văn bản thành vectors (batch processing).
        
        Args:
            texts: Danh sách văn bản
            batch_size: Kích thước batch
            
        Returns:
            np.ndarray: Ma trận embeddings (N x dimension)
        """
        return self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True
        )

    @staticmethod
    def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """
        Tính Cosine Similarity giữa 2 vectors.
        
        Returns:
            float: Giá trị từ -1 đến 1 (1 = giống hoàn toàn)
        """
        dot_product = np.dot(vec_a, vec_b)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))
