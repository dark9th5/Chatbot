"""
Chunking & Vectorization - Upgrade (Qdrant + Vietnamese Bi-Encoder)
Chia văn bản thành các đoạn nhỏ (Semantic Chunking) và tính Vector Embedding.
Lưu trữ vào Qdrant Local Mode thay vì MySQL.
"""

import pymysql
import time
import re
from typing import List, Optional

from sentence_transformers import SentenceTransformer
# from langchain_text_splitters import RecursiveCharacterTextSplitter # Replaced by custom implementation

from db_config import MYSQL_CONFIG
from chatbot_api.services.qdrant_service import QdrantService
from etl.ner_extractor import NERExtractor


def _get_connection():
    return pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)


# ============================================================
# SEMANTIC CHUNKING
# ============================================================

class VietnameseTextSplitter:
    """
    Custom Text Splitter cho tiếng Việt.
    - Tách câu dựa trên dấu câu (. ! ?) nhưng bỏ qua các từ viết tắt phổ biến (Tp., Mr.,...)
    - Gom nhóm câu thành chunk theo sliding window (kích thước & overlap).
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []

        # 1. Tách câu thông minh
        sentences = self._split_sentences(text)

        # 2. Gom nhóm thành chunks
        chunks = []
        current_chunk = []
        current_length = 0

        for sentence in sentences:
            sentence_len = len(sentence)

            # Nếu thêm câu này vào mà vượt quá chunk_size thì lưu chunk hiện tại
            if current_length + sentence_len > self.chunk_size and current_chunk:
                # Lưu chunk hiện tại
                full_chunk = " ".join(current_chunk)
                chunks.append(full_chunk)

                # Reset chunk mới, nhưng giữ lại phần overlap từ cuối chunk trước
                overlap_len = 0
                new_chunk = []
                
                # Lấy ngược từ cuối lên để đủ overlap
                for s in reversed(current_chunk):
                    if overlap_len + len(s) <= self.chunk_overlap:
                        new_chunk.insert(0, s)
                        overlap_len += len(s)
                    else:
                        break
                
                current_chunk = new_chunk
                current_length = overlap_len

            current_chunk.append(sentence)
            current_length += sentence_len

        # Lưu chunk cuối cùng nếu còn
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """
        Tách câu sử dụng Regex lookbehind để tránh tách nhầm từ viết tắt.
        """
        # Danh sách từ viết tắt phổ biến cần bảo vệ (Tp., ThS., v.v...)
        abbreviations = r"(?<!Tp\.)(?<!ThS\.)(?<!TS\.)(?<!GS\.)(?<!Mr\.)(?<!Ms\.)(?<!Dr\.)"
        
        # Regex giải thích:
        # Tách khi gặp dấu chấm/chấm than/hỏi chấm
        # Theo sau là khoảng trắng hoặc cuối dòng
        # VÀ không nằm sau các từ viết tắt
        pattern = fr"{abbreviations}(?<=[\.\!\?])\s+"
        
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]


def semantic_chunking(text: str, chunk_size: int = 500, chunk_overlap: int = 100) -> List[str]:
    """
    Chia văn bản sử dụng Custom VietnameseTextSplitter.
    Design Pattern: Strategy Pattern (Thay thế algorithm cũ).
    """
    if not text or not text.strip():
        return []

    splitter = VietnameseTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_text(text)


# ============================================================
# VECTOR EMBEDDING
# ============================================================

class TextVectorizer:
    """Lớp xử lý vector hóa văn bản (Vietnamese Optimized)"""

    def __init__(self, model_name: str = 'bkai-foundation-models/vietnamese-bi-encoder'):
        print(f"⏳ Đang tải model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self._dim = self.model.get_sentence_embedding_dimension()
        print(f"✓ Model sẵn sàng! Dimension: {self._dim}")

    @property
    def dimension(self) -> int:
        return self._dim

    def encode(self, texts: List[str], batch_size: int = 32):
        """Encode danh sách văn bản thành vectors."""
        return self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True
        )


# ============================================================
# XỬ LÝ CHÍNH
# ============================================================

def process_all_articles(incremental: bool = True, qdrant_service: Optional[QdrantService] = None):
    """
    Xử lý bài báo: Semantic Chunking → Vectorization → Qdrant
    """
    print("\n🔧 BẮT ĐẦU CHUNKING & VECTOR HÓA (QDRANT)")
    print("=" * 60)

    # 1. Tải model trước để biết vector dimension
    vectorizer = TextVectorizer()

    # 2. Kết nối Qdrant
    # Ưu tiên dùng singleton QdrantService của ứng dụng để tránh lock file khi chạy song song với API.
    if qdrant_service is not None:
        qdrant = qdrant_service
    else:
        try:
            from chatbot_api.dependencies import get_qdrant_service
            qdrant = get_qdrant_service()
        except Exception:
            qdrant = QdrantService(vector_size=vectorizer.dimension)
    
    # Khởi tạo NER Extractor
    ner_extractor = NERExtractor()

    # 3. Kiểm tra bài đã xử lý (incremental)
    processed_ids = set()
    if incremental:
        print("⏳ Đang kiểm tra dữ liệu đã có trong Qdrant...")
        try:
            # Scroll qua tất cả points để lấy article_id
            offset = None
            while True:
                result = qdrant.client.scroll(
                    collection_name=QdrantService.COLLECTION_NAME,
                    limit=1000,
                    offset=offset,
                    with_payload=["article_id"],
                    with_vectors=False
                )
                points, offset = result
                for p in points:
                    if p.payload and 'article_id' in p.payload:
                        processed_ids.add(p.payload['article_id'])
                if offset is None:
                    break
            print(f"✓ Đã tìm thấy {len(processed_ids)} bài viết đã xử lý.")
        except Exception as e:
            print(f"⚠ Không thể check data cũ: {e}")
    else:
        print("⚠ Chế độ Full Refresh: Xóa toàn bộ dữ liệu cũ...")
        qdrant.delete_all()

    # 4. Lấy bài viết từ MySQL
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, title, content, source, published_date, link '
        'FROM articles WHERE content IS NOT NULL'
    )
    articles = cursor.fetchall()
    conn.close()

    # Lọc bài chưa xử lý
    new_articles = [a for a in articles if a['id'] not in processed_ids]
    total = len(new_articles)

    if total == 0:
        print("\n✅ Không có bài viết mới cần xử lý.")
        return

    print(f"\n📊 Tổng số bài viết mới: {total}")
    print(f"⚙️ Chunking: Recursive Character (Size=500, Overlap=100)")
    print(f"🧠 Model: bkai-foundation-models/vietnamese-bi-encoder\n")

    total_chunks = 0
    start_time = time.time()

    for idx, article in enumerate(new_articles, 1):
        article_id = article['id']
        title = article['title']
        content = article['content']
        source = article['source']
        link = article['link']

        # 1. Chunking
        chunks = semantic_chunking(content, chunk_size=500, chunk_overlap=100)

        if not chunks:
            continue

        # 2. Vectorization
        embeddings = vectorizer.encode(chunks)

        # 3. Tra cứu NER & Xây dựng Metadata
        metadatas = []
        for chunk in chunks:
            entities = ner_extractor.extract_entities(chunk)
            metadatas.append({
                "article_id": article_id,
                "title": title,
                "source": source,
                "link": link or "",
                "published_date": str(article['published_date'] or ""),
                "entities": entities  # Lưu vào Qdrant payload
            })

        qdrant.add_chunks(chunks, embeddings, metadatas)
        total_chunks += len(chunks)

        if idx % 10 == 0:
            print(f"  ✓ Đã xử lý {idx}/{total} bài ({total_chunks} chunks)")

    duration = time.time() - start_time

    print("\n" + "=" * 60)
    print("📊 KẾT QUẢ XỬ LÝ")
    print("=" * 60)
    print(f"  📰 Bài viết mới:      {total}")
    print(f"  📦 Tổng số chunks:    {total_chunks}")
    print(f"  ⏱️ Thời gian:         {duration:.2f}s ({duration/total:.2f}s/bài)")
    print(f"  📁 Database:          Qdrant (Local Persistent)")
    print("=" * 60)


def demo_search():
    """Demo tìm kiếm với Qdrant."""
    print("\n🔍 DEMO: TÌM KIẾM NGỮ NGHĨA (QDRANT)")
    print("=" * 60)

    vectorizer = TextVectorizer()
    qdrant = QdrantService(vector_size=vectorizer.dimension)

    if qdrant.count() == 0:
        print("⚠ DB trống. Hãy chạy process_all_articles() trước.")
        return

    queries = [
        "kinh tế Việt Nam dự báo tăng trưởng",
        "trí tuệ nhân tạo AI thay đổi thế giới",
        "dự báo thời tiết Hà Nội hôm nay"
    ]

    for query in queries:
        print(f"\n❓ Câu hỏi: \"{query}\"")

        query_vec = vectorizer.encode([query])[0]
        results = qdrant.search(query_vec, n_results=3)

        print("   📋 Kết quả:")
        for res in results:
            meta = res['metadata']
            score = res['score']
            print(f"   [{score:.4f}] [{meta['source']}] {meta['title'][:50]}")
            print(f"      → {res['content'][:100]}...")

    print("\n" + "=" * 60)


def main():
    print("\n🚀 RAG PIPELINE (Qdrant + Vietnamese Bi-Encoder)")
    process_all_articles(incremental=True)
    demo_search()
    print("\n✅ Hoàn tất!\n")


if __name__ == '__main__':
    main()
