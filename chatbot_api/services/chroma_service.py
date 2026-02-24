"""
ChromaDB Service - Vector Database Wrapper
Quản lý việc lưu trữ và tìm kiếm vector sử dụng ChromaDB.
Hoạt động ở chế độ Persistent Client (lưu file local, không cần server).
"""

import chromadb
from chromadb.config import Settings
import os
from typing import List, Dict, Optional, Any
import uuid

class ChromaService:
    """
    Service wrapper cho ChromaDB.
    Singleton Pattern: Nên được khởi tạo một lần và tái sử dụng.
    """
    
    def __init__(self, persist_path: str = "data/chroma_db"):
        """
        Khởi tạo Chroma Client.
        
        Args:
            persist_path: Đường dẫn thư mục lưu dữ liệu ChromaDB
        """
        self.persist_path = persist_path
        
        # Tạo thư mục nếu chưa có
        os.makedirs(persist_path, exist_ok=True)
        
        print(f"⏳ [ChromaService] Connecting to ChromaDB at {persist_path}...")
        
        # Khởi tạo Client
        self.client = chromadb.PersistentClient(path=persist_path)
        
        # Lấy hoặc tạo collection
        self.collection_name = "news_articles"
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"} # Sử dụng Cosine Similarity
        )
        
        print(f"✓ [ChromaService] Connected! Collection: {self.collection_name}")
        print(f"  Existing items: {self.collection.count()}")

    def add_chunks(self, 
                   chunks: List[str], 
                   embeddings: List[List[float]], 
                   metadatas: List[Dict[str, Any]]):
        """
        Thêm danh sách các chunks và vector vào DB.
        
        Args:
            chunks: Danh sách nội dung văn bản
            embeddings: Danh sách vector tương ứng
            metadatas: Danh sách thông tin đi kèm (title, source, link...)
        """
        if not chunks:
            return
            
        # Tạo IDs ngẫu nhiên (UUID)
        ids = [str(uuid.uuid4()) for _ in chunks]
        
        # Thêm vào collection
        self.collection.add(
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        # print(f"      + Added {len(chunks)} chunks to ChromaDB")

    def search(self, 
               query_embedding: List[float], 
               n_results: int = 5,
               metadata_filter: Optional[Dict] = None) -> List[Dict]:
        """
        Tìm kiếm vector tương đồng.
        
        Args:
            query_embedding: Vector câu hỏi
            n_results: Số lượng kết quả trả về
            metadata_filter: Bộ lọc metadata (ví dụ: tìm theo nguồn, ngày...)
            
        Returns:
            Danh sách các documents kèm metadata và score
        """
        if not query_embedding:
            return []
            
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=metadata_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        # Format lại kết quả cho dễ dùng
        output = []
        if results['ids']:
            for i in range(len(results['ids'][0])):
                item = {
                    'id': results['ids'][0][i],
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'score': 1 - results['distances'][0][i] # Convert distance to similarity
                }
                output.append(item)
                
        return output

    def count(self) -> int:
        """Đếm tổng số chunk trong DB"""
        return self.collection.count()

    def delete_old_data(self):
        """Xóa toàn bộ dữ liệu (Dùng khi muốn reset)"""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        print("✓ [ChromaService] Collection cleared!")
