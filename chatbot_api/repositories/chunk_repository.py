"""
Chunk Repository — Data Access cho bảng chunks
Truy vấn các đoạn văn bản đã chunking + embedding vectors
"""

import numpy as np
from typing import List, Dict, Tuple

from chatbot_api.repositories.base import BaseRepository


class ChunkRepository(BaseRepository):
    """Repository truy vấn bảng chunks (đoạn văn bản + vector embedding)"""

    def get_all_with_embeddings(self) -> List[Dict]:
        """
        Lấy tất cả chunks kèm embedding vectors.

        Returns:
            List[Dict]: Mỗi dict chứa: id, article_id, chunk_text, embedding (bytes)
        """
        query = '''
            SELECT c.id, c.article_id, c.chunk_index, c.chunk_text, c.embedding
            FROM chunks c
            ORDER BY c.article_id, c.chunk_index
        '''
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)

            results = []
            for row in cursor.fetchall():
                embedding_array = np.frombuffer(
                    row['embedding'], dtype=np.float32
                )
                results.append({
                    'id': row['id'],
                    'article_id': row['article_id'],
                    'chunk_index': row['chunk_index'],
                    'chunk_text': row['chunk_text'],
                    'embedding': embedding_array
                })

            return results

    def get_by_article_id(self, article_id: int) -> List[Dict]:
        """Lấy tất cả chunks của một bài viết"""
        return self._fetch_all(
            'SELECT id, chunk_index, chunk_text FROM chunks WHERE article_id = %s',
            (article_id,)
        )

    def count(self) -> int:
        """Đếm tổng số chunks"""
        result = self._fetch_one('SELECT COUNT(*) as total FROM chunks')
        return result['total'] if result else 0
