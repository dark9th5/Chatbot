"""
Knowledge Graph Builder - REPLACING CHUNKING & VECTORIZATION
Xây dựng đồ thị tri thức từ bài báo dựa trên thực thể (Entities).
Sử dụng 100% kỹ thuật tự code (Regex, Dictionary, Set Theory).
"""

import pymysql
import time
import re
import sys
from typing import List, Dict, Set

# Ensure UTF-8 for console logging on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
from pipeline.config import MYSQL_CONFIG
from etl.ner_extractor import NERExtractor

class KnowledgeGraphBuilder:
    def __init__(self):
        self.ner = NERExtractor()
        self.conn = pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)

    def _get_cursor(self):
        if not self.conn.open:
            self.conn.ping(reconnect=True)
        return self.conn.cursor()

    def build_graph(self):
        """Quét toàn bộ bài báo và xây dựng quan hệ thực thể."""
        print("\n[Graph] BẮT ĐẦU XÂY DỰNG ĐỒ THỊ TRI THỨC (KNOWLEDGE GRAPH)")
        print("=" * 60)
        
        cursor = self._get_cursor()
        
        # 1. Lấy bài báo chưa được đánh index đồ thị (Có thể tối ưu bằng flag sau)
        cursor.execute("SELECT id, title, content FROM articles WHERE content IS NOT NULL")
        articles = cursor.fetchall()
        
        print(f"[Info] Đang xử lý {len(articles)} bài báo...")
        
        total_entities_found = 0
        start_time = time.time()

        for idx, article in enumerate(articles, 1):
            article_id = article['id']
            # Kết hợp Tiêu đề + Nội dung để trích xuất thực thể mạnh hơn
            full_text = f"{article['title']}. {article['content']}"
            
            # 2. Trích xuất thực thể bằng NER thuần Regex
            entities_dict = self.ner.extract_entities(full_text)
            
            # Gom tất cả các loại thực thể lại thành một tập hợp duy nhất
            unique_entities = set()
            for entity_type, names in entities_dict.items():
                for name in names:
                    # Chuẩn hóa tên: viết thường để đồng nhất (hoặc giữ nguyên nếu muốn phân biệt)
                    name_clean = name.strip().lower()
                    if len(name_clean) > 2: # Bỏ qua rác quá ngắn
                        unique_entities.add((name_clean, entity_type))

            # 3. Lưu vào Database
            for name, e_type in unique_entities:
                # 3.1. Insert entity nếu chưa có
                cursor.execute(
                    "INSERT IGNORE INTO graph_entities (name, type) VALUES (%s, %s)",
                    (name, e_type)
                )
                
                # 3.2. Lấy ID của entity
                cursor.execute("SELECT id FROM graph_entities WHERE name = %s", (name,))
                entity_id = cursor.fetchone()['id']
                
                # 3.3. Tạo mối liên kết (Edge)
                cursor.execute(
                    "INSERT IGNORE INTO article_graph (article_id, entity_id) VALUES (%s, %s)",
                    (article_id, entity_id)
                )
                total_entities_found += 1

            if idx % 50 == 0:
                print(f"  [OK] Đã xử lý {idx}/{len(articles)} bài báo...")
                self.conn.commit() # Commit định kỳ

        self.conn.commit()
        duration = time.time() - start_time
        
        print("\n" + "=" * 60)
        print("--- KẾT QUẢ XÂY DỰNG ĐỒ THỊ ---")
        print(f"  Tổng số bài báo:   {len(articles)}")
        print(f"  Thực thể tìm thấy: {total_entities_found}")
        print(f"  Thời gian chạy:    {duration:.2f}s")
        print("=" * 60)

    def close(self):
        self.conn.close()

if __name__ == "__main__":
    builder = KnowledgeGraphBuilder()
    try:
        builder.build_graph()
    finally:
        builder.close()
