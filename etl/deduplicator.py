import re
from typing import Set, List
from .models import Article

class JaccardDeduplicator:
    """
    Module loại bỏ bài viết trùng lặp (Data Deduplication) sử dụng Jaccard Similarity.
    Kỹ thuật: Biến đổi văn bản thành tập hợp các từ (hoặc N-grams) và đo tỷ lệ giao/hợp.
    Giúp loại bỏ các bài báo "đạo văn" hoặc xào bài giữa các trang báo.
    """
    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold
        # Lưu trữ signature (set of words) của các bài đã quét trong session
        self.processed_signatures: List[Set[str]] = []

    def _get_ngrams(self, text: str, n: int = 2) -> Set[str]:
        """Chuyển văn bản thành set các N-grams để so sánh."""
        if not text:
            return set()
            
        # Làm sạch cơ bản
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        words = text.split()
        
        if len(words) < n:
            return set(words)
            
        # Tạo N-grams (ví dụ 2-grams: "xin chào", "chào bạn")
        ngrams = set()
        for i in range(len(words) - n + 1):
            ngram = " ".join(words[i:i+n])
            ngrams.add(ngram)
            
        return ngrams

    def is_duplicate(self, article: Article) -> bool:
        """Kiểm tra xem bài báo này có bị trùng lặp với các bài trước đó không."""
        # Chỉ check trùng lặp nếu có nội dung
        content_to_check = article.content if article.content else article.title
        
        # Dùng 3-grams để tăng độ mẫn cảm với "cụm từ chép y nguyên"
        current_signature = self._get_ngrams(content_to_check, n=3)
        
        if not current_signature:
            return False

        for past_signature in self.processed_signatures:
            # Tính Jaccard Similarity = Giao / Hợp
            intersection = len(current_signature.intersection(past_signature))
            union = len(current_signature.union(past_signature))
            
            if union == 0:
                continue
                
            similarity = intersection / union
            
            if similarity >= self.threshold:
                print(f"      [Deduplicator] Phái hiện bài copy (Độ giống: {similarity*100:.1f}%) -> {article.title[:40]}...")
                return True
                
        # Nếu không trùng, lưu signature lại để so sánh với các bài đến sau
        self.processed_signatures.append(current_signature)
        return False
