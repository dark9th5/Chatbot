"""
Graph Search Service - REPLACING QDRANT SEARCH
Tìm kiếm thông tin dựa trên Đồ thị thực thể (MySQL).
100% Custom logic, không dùng Vector, không dùng AI Search.
"""

import pymysql
import re
from typing import List, Dict, Any
from pipeline.config import MYSQL_CONFIG
from etl.ner_extractor import NERExtractor

class GraphSearchService:
    def __init__(self):
        self.ner = NERExtractor()
        # Sử dụng lazy connection để tránh lỗi timeout
        self._conn = None

    @property
    def conn(self):
        if self._conn is None or not self._conn.open:
            self._conn = pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        return self._conn

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Thuật toán tìm kiếm trên đồ thị:
        1. Trích xuất thực thể từ câu hỏi.
        2. Tìm các bài báo chứa các thực thể đó.
        3. Tính điểm (Score) dựa trên số lượng thực thể trùng khớp.
        """
        # 1. Trích xuất thực thể từ câu hỏi (Custom NER)
        query_entities_dict = self.ner.extract_entities(query)
        query_entities = []
        for names in query_entities_dict.values():
            query_entities.extend([n.lower().strip() for n in names if len(n) > 2])
        
        # Nếu không tìm thấy thực thể cụ thể, dùng từ khóa đơn giản (Simple Tokenizer)
        if not query_entities:
            # Tách từ đơn giản bằng khoảng trắng, bỏ qua từ ngắn
            query_entities = [w.lower() for w in query.split() if len(w) > 3]

        if not query_entities:
            return []

        cursor = self.conn.cursor()
        
        # 2. Xây dựng câu truy vấn SQL để tìm bài báo có nhiều thực thể trùng khớp nhất
        # Đây là thuật toán "Intersection over Graph Nodes"
        format_strings = ','.join(['%s'] * len(query_entities))
        sql = f"""
            SELECT 
                a.id, 
                a.title, 
                a.content, 
                a.source, 
                a.link,
                COUNT(ag.entity_id) as match_count
            FROM articles a
            JOIN article_graph ag ON a.id = ag.article_id
            JOIN graph_entities ge ON ag.entity_id = ge.id
            WHERE LOWER(ge.name) IN ({format_strings})
            GROUP BY a.id
            ORDER BY match_count DESC, a.published_date DESC
            LIMIT %s
        """
        
        params = tuple(query_entities) + (limit,)
        cursor.execute(sql, params)
        results = cursor.fetchall()

        # 3. Định dạng kết quả giống với Qdrant kết quả cũ để dễ tích hợp
        formatted_results = []
        for res in results:
            formatted_results.append({
                "id": res['id'],
                "content": res['content'],
                "score": float(res['match_count']), # Dùng số lượng thực thể làm điểm số
                "metadata": {
                    "title": res['title'],
                    "source": res['source'],
                    "link": res['link']
                }
            })

        return formatted_results

    def close(self):
        if self._conn:
            self._conn.close()
