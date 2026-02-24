"""
Article Repository — Data Access cho bảng articles
"""

from typing import List, Dict, Optional

from chatbot_api.repositories.base import BaseRepository


class ArticleRepository(BaseRepository):
    """Repository truy vấn bảng articles (bài viết gốc)"""

    def get_by_id(self, article_id: int) -> Optional[Dict]:
        return self._fetch_one(
            'SELECT id, title, link, source, summary, published_date FROM articles WHERE id = %s',
            (article_id,)
        )

    def get_by_ids(self, article_ids: List[int]) -> Dict[int, Dict]:
        if not article_ids:
            return {}

        placeholders = ','.join(['%s' for _ in article_ids])
        query = f'''
            SELECT id, title, link, source, summary, published_date 
            FROM articles 
            WHERE id IN ({placeholders})
        '''

        rows = self._fetch_all(query, tuple(article_ids))
        return {row['id']: row for row in rows}

    def count(self) -> int:
        result = self._fetch_one('SELECT COUNT(*) as total FROM articles')
        return result['total'] if result else 0
