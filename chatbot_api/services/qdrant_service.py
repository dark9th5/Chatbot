"""
Qdrant Service - Vector Database Wrapper (Local Mode)
Quản lý lưu trữ và tìm kiếm vector sử dụng Qdrant.
Chạy ở chế độ Local (lưu file trên ổ cứng, không cần Docker).
"""

import os
import uuid
from typing import List, Dict, Optional, Any
from datetime import date, datetime

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue, Range
)


class QdrantService:
    """
    Service wrapper cho Qdrant (Local Mode).
    Singleton Pattern: Nên khởi tạo 1 lần duy nhất trong dependencies.py.
    """

    COLLECTION_NAME = "news_articles"
    CACHE_COLLECTION = "semantic_cache"
    CATEGORY_ALIASES = {
        "Công nghệ": "Số hóa",
        "Thời tiết Hà Nội": "Thời tiết Việt Nam",
    }

    def __init__(self, persist_path: str = "data/qdrant_db", vector_size: int = 768):
        """
        Khởi tạo Qdrant Client ở chế độ Local.

        Args:
            persist_path: Thư mục lưu dữ liệu
            vector_size: Số chiều vector (phụ thuộc vào model embedding)
        """
        self.persist_path = persist_path
        self.vector_size = vector_size

        os.makedirs(persist_path, exist_ok=True)

        print(f"[QdrantService] Connecting to Qdrant at {persist_path}...")
        self.client = QdrantClient(path=persist_path)

        # Tạo collection nếu chưa có
        self._ensure_collection()
        self._ensure_cache_collection()
        print(f"OK [QdrantService] Connected! Collection: {self.COLLECTION_NAME}")
        print(f"  Existing items: {self.count()}")

    def _ensure_collection(self):
        """Tạo collection nếu chưa tồn tại."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.COLLECTION_NAME for c in collections)

        if not exists:
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                )
            )
            print(f"  OK Created new collection: {self.COLLECTION_NAME}")

    def _ensure_cache_collection(self):
        """Tạo collection cache nếu chưa tồn tại."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.CACHE_COLLECTION for c in collections)

        if not exists:
            self.client.create_collection(
                collection_name=self.CACHE_COLLECTION,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                )
            )
            print(f"  OK Created new cache collection: {self.CACHE_COLLECTION}")

    def add_chunks(
        self,
        chunks: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]]
    ):
        """
        Thêm danh sách chunks và vectors vào DB.

        Args:
            chunks: Nội dung văn bản
            embeddings: Vector tương ứng
            metadatas: Thông tin đi kèm (title, source, link...)
        """
        if not chunks:
            return

        points = []
        for i, (chunk, embedding, metadata) in enumerate(zip(chunks, embeddings, metadatas)):
            # Thêm nội dung chunk vào metadata để trả về khi search
            payload = {**metadata, "content": chunk}

            # Chuyển embedding sang list nếu cần
            vec = embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)

            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload=payload
            ))

        self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=points
        )

    def _normalize_category(self, category: Optional[str]) -> Optional[str]:
        if not category:
            return None

        cleaned = category.strip()
        return self.CATEGORY_ALIASES.get(cleaned, cleaned)

    def _parse_published_date(self, value: Any) -> Optional[date]:
        if not value:
            return None

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        text = str(value).strip()
        if not text:
            return None

        # Handle YYYY-MM-DD HH:MM:SS format from MySQL str()
        if " " in text:
            text = text.split(" ")[0]

        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue

        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            return None

    def search(
        self,
        query_embedding,
        n_results: int = 5,
        source_filter: Optional[str] = None,
        category: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> List[Dict]:
        """
        Tìm kiếm vector tương đồng với hỗ trợ bộ lọc.

        Args:
            query_embedding: Vector câu hỏi (numpy array hoặc list)
            n_results: Số kết quả trả về
            source_filter: Lọc theo nguồn tin (VnExpress, Dân Trí...)
            category: Lọc theo danh mục (Thời sự, Kinh doanh, etc)
            from_date: Lọc từ ngày (YYYY-MM-DD)
            to_date: Lọc đến ngày (YYYY-MM-DD)

        Returns:
            List[Dict]: Kết quả gồm content, metadata, score
        """
        # Chuyển sang list nếu là numpy
        vec = query_embedding.tolist() if hasattr(query_embedding, 'tolist') else list(query_embedding)
        category = self._normalize_category(category)

        # Tạo bộ lọc
        must_conditions = []
        
        if source_filter:
            must_conditions.append(
                FieldCondition(key="source", match=MatchValue(value=source_filter))
            )
        
        if category:
            must_conditions.append(
                FieldCondition(key="category", match=MatchValue(value=category))
            )
        
        if from_date:
            from_int = int(from_date.strftime("%Y%m%d"))
            must_conditions.append(
                FieldCondition(key="pub_date_int", range=Range(gte=from_int))
            )
        
        if to_date:
            to_int = int(to_date.strftime("%Y%m%d"))
            must_conditions.append(
                FieldCondition(key="pub_date_int", range=Range(lte=to_int))
            )

        query_filter = None
        if must_conditions:
            query_filter = Filter(must=must_conditions)

        # Với Native Filter, chúng ta không cần post-filtering nữa. 
        # Tuy nhiên vẫn lấy nhiều hơn chút để Rerank tốt hơn.
        search_limit = n_results * 5 if (from_date or to_date) else n_results

        results = self.client.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=vec,
            limit=search_limit,
            query_filter=query_filter
        )

        output = []
        for hit in results:
            payload = hit.payload or {}

            # Native Filter đã xử lý rồi, không cần post-filtering logic cũ nữa
            output.append({
                'id': hit.id,
                'content': payload.get('content', ''),
                'metadata': {
                    'article_id': payload.get('article_id'),
                    'title': payload.get('title', ''),
                    'source': payload.get('source', ''),
                    'link': payload.get('link', ''),
                    'published_date': payload.get('published_date', ''),
                    'category': payload.get('category', ''),
                },
                'score': hit.score
            })

            if len(output) >= n_results:
                break

        return output

    def search_cache(self, query_embedding, threshold: float = 0.90) -> Optional[str]:
        """Tìm câu trả lời trong cache với ngưỡng tương đồng cao."""
        vec = query_embedding.tolist() if hasattr(query_embedding, 'tolist') else list(query_embedding)
        
        results = self.client.search(
            collection_name=self.CACHE_COLLECTION,
            query_vector=vec,
            limit=1,
            score_threshold=threshold
        )
        
        if results:
            hit = results[0]
            print(f"CACHE HIT! Score: {hit.score:.4f}")
            return hit.payload.get('answer', '')
        return None

    def add_to_cache(self, question: str, answer: str, embedding):
        """Lưu câu hỏi và câu trả lời vào cache."""
        vec = embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
        
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={
                "question": question,
                "answer": answer
            }
        )
        
        self.client.upsert(
            collection_name=self.CACHE_COLLECTION,
            points=[point]
        )

    def count(self) -> int:
        """Đếm tổng số chunk trong DB."""
        try:
            info = self.client.get_collection(self.COLLECTION_NAME)
            return info.points_count
        except Exception:
            return 0

    def delete_all(self):
        """Xóa toàn bộ dữ liệu (reset)."""
        self.client.delete_collection(self.COLLECTION_NAME)
        self._ensure_collection()
        print("Done [QdrantService] Collection cleared!")

    def get_all_categories(self) -> set:
        """[DEBUG] Lấy tất cả danh mục duy nhất có trong DB."""
        categories = set()
        offset = None
        
        while True:
            result = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            points, offset = result
            
            for p in points:
                cat = p.payload.get('category', 'N/A')
                categories.add(cat)
            
            if offset is None:
                break
        
        return categories

    def get_normalized_categories(self) -> List[str]:
        """Lấy danh sách danh mục đã chuẩn hóa, bỏ giá trị rỗng/không hợp lệ."""
        raw_categories = self.get_all_categories()
        normalized = set()

        for category in raw_categories:
            if category is None:
                continue

            text = str(category).strip()
            if not text or text.upper() == "N/A":
                continue

            mapped = self._normalize_category(text)
            if mapped:
                normalized.add(mapped)

        return sorted(normalized)
