import math
import re
from typing import List, Dict

class TextRankSummarizer:
    """
    Thuật toán Tóm tắt văn bản dùng phương pháp Extractive (TextRank).
    Tự code hoàn toàn bằng Python Toán học (Không dùng Machine Learning model để tiết kiệm RAM).
    Ý tưởng: Dựng đồ thị các câu, tính độ tương đồng bằng TF-IDF/Overlap, sau đó lặp PageRank.
    """
    
    # Khởi tạo bộ tóm tắt văn bản với các tham số cho thuật toán PageRank
    def __init__(self, damping_factor: float = 0.85, max_iter: int = 50, tolerance: float = 1e-4):
        self.d = damping_factor
        self.max_iter = max_iter
        self.tolerance = tolerance

    # Tách văn bản thành danh sách các câu
    def _split_sentences(self, text: str) -> List[str]:
        """Tách câu đơn giản bằng regex."""
        # Tách câu: chấm/hỏi/than theo sau bởi khoảng trắng hoặc cuối chuỗi
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 15] # Bỏ câu quá ngắn

    # Tính toán độ tương đồng giữa hai câu dựa trên các từ chung
    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """Tính điểm tương đồng giữa 2 câu bằng Word Overlap (Jaccard-like)."""
        words1 = set(s1.lower().split())
        words2 = set(s2.lower().split())
        
        if not words1 or not words2:
            return 0.0
            
        overlap = len(words1.intersection(words2))
        
        # Áp dụng log normalization để tránh thiên vị câu quá dài
        denominator = math.log(len(words1) + 1) + math.log(len(words2) + 1)
        if denominator == 0:
            return 0.0
            
        return overlap / denominator

    # Xây dựng ma trận tương đồng giữa tất cả các cặp câu
    def _build_similarity_matrix(self, sentences: List[str]) -> List[List[float]]:
        """Dựng ma trận kề (đồ thị) cho các câu."""
        n = len(sentences)
        matrix = [[0.0] * n for _ in range(n)]
        
        for i in range(n):
            for j in range(n):
                if i != j:
                    matrix[i][j] = self._calculate_similarity(sentences[i], sentences[j])
                    
        return matrix

    # Thực hiện tóm tắt văn bản và lấy ra k câu quan trọng nhất
    def summarize(self, text: str, top_k: int = 3) -> str:
        """
        Thực thi thuật toán TextRank để rút trích top_k câu quan trọng nhất.
        """
        if not text:
            return ""
            
        sentences = self._split_sentences(text)
        n = len(sentences)
        
        if n <= top_k:
            return ". ".join(sentences) + "."
            
        matrix = self._build_similarity_matrix(sentences)
        
        # Khởi tạo điểm TextRank bằng nhau cho mọi node
        scores = [1.0 / n] * n
        
        # Tính tổng trọng số các cạnh đi ra từ mỗi node
        out_sums = [sum(row) for row in matrix]
        
        # Vòng lặp tính PageRank
        for _ in range(self.max_iter):
            prev_scores = list(scores)
            
            for i in range(n):
                sum_in = 0.0
                for j in range(n):
                    if i != j and matrix[j][i] > 0 and out_sums[j] > 0:
                        sum_in += (matrix[j][i] / out_sums[j]) * prev_scores[j]
                        
                scores[i] = (1 - self.d) + self.d * sum_in
                
            # Kiểm tra hội tụ
            diff = sum(abs(scores[i] - prev_scores[i]) for i in range(n))
            if diff < self.tolerance:
                break
                
        # Gắn điểm với câu gốc và giữ nguyên thứ tự thời gian (để đọc cho mượt)
        ranked_sentences = sorted(((scores[i], i, sentences[i]) for i in range(n)), reverse=True)
        
        # Chọn top_k câu
        top_sentences = sorted(ranked_sentences[:top_k], key=lambda x: x[1])
        
        summary = ". ".join([s[2] for s in top_sentences]) + "."
        return summary
