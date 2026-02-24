"""
Qdrant Service - Vector Database Wrapper (Local Mode)
Quản lý lưu trữ và tìm kiếm vector sử dụng Qdrant.
Chạy ở chế độ Local (lưu file trên ổ cứng, không cần Docker).
"""

import os
import uuid
from typing import List, Dict, Optional, Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue
)


class QdrantService:
    """
    Service wrapper cho Qdrant (Local Mode).
    Singleton Pattern: Nên khởi tạo 1 lần duy nhất trong dependencies.py.
    """

    COLLECTION_NAME = "news_articles"
    CACHE_COLLECTION = "semantic_cache"

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

        print(f"⏳ [QdrantService] Connecting to Qdrant at {persist_path}...")
        self.client = QdrantClient(path=persist_path)

        # Tạo collection nếu chưa có
        self._ensure_collection()
        self._ensure_cache_collection()
        print(f"✓ [QdrantService] Connected! Collection: {self.COLLECTION_NAME}")
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
            print(f"  ✓ Created new collection: {self.COLLECTION_NAME}")

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
            print(f"  ✓ Created new cache collection: {self.CACHE_COLLECTION}")

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

    def search(
        self,
        query_embedding,
        n_results: int = 5,
        source_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Tìm kiếm vector tương đồng.

        Args:
            query_embedding: Vector câu hỏi (numpy array hoặc list)
            n_results: Số kết quả trả về
            source_filter: Lọc theo nguồn tin (VnExpress, Dân Trí...)

        Returns:
            List[Dict]: Kết quả gồm content, metadata, score
        """
        # Chuyển sang list nếu là numpy
        vec = query_embedding.tolist() if hasattr(query_embedding, 'tolist') else list(query_embedding)

        # Tạo filter nếu cần
        query_filter = None
        if source_filter:
            query_filter = Filter(
                must=[FieldCondition(key="source", match=MatchValue(value=source_filter))]
            )

        results = self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=vec,
            limit=n_results,
            query_filter=query_filter
        ).points

        output = []
        for hit in results:
            payload = hit.payload or {}
            output.append({
                'id': hit.id,
                'content': payload.get('content', ''),
                'metadata': {
                    'article_id': payload.get('article_id'),
                    'title': payload.get('title', ''),
                    'source': payload.get('source', ''),
                    'link': payload.get('link', ''),
                    'published_date': payload.get('published_date', ''),
                },
                'score': hit.score
            })

        return output

    def search_cache(self, query_embedding, threshold: float = 0.90) -> Optional[str]:
        """Tìm câu trả lời trong cache với ngưỡng tương đồng cao."""
        vec = query_embedding.tolist() if hasattr(query_embedding, 'tolist') else list(query_embedding)
        
        results = self.client.query_points(
            collection_name=self.CACHE_COLLECTION,
            query=vec,
            limit=1,
            score_threshold=threshold
        ).points
        
        if results:
            hit = results[0]
            print(f"🔥 CACHE HIT! Score: {hit.score:.4f}")
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
        print("✓ [QdrantService] Collection cleared!")
