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
    GRAPH_INDEX_TYPES = set(NERExtractor.TYPE_ORDER) - NERExtractor.WEAK_SIGNAL_TYPES

    def __init__(self):
        self.ner = NERExtractor()
        self.conn = pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)

    def _check_graph_entities_schema(self):
        """
        Check `graph_entities.type` column for restrictive ENUM definitions and
        print a recommended ALTER TABLE statement if it's too narrow.
        """
        try:
            cursor = self._get_cursor()
            cursor.execute(
                """
                SELECT COLUMN_TYPE, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'graph_entities' AND COLUMN_NAME = 'type'
                """,
                (MYSQL_CONFIG.get('db'),),
            )
            row = cursor.fetchone()
            if row and row.get('COLUMN_TYPE') and 'enum' in row.get('COLUMN_TYPE').lower():
                print("[Warning] `graph_entities.type` is an ENUM. This may limit stored entity types.")
                print("Recommended SQL to widen the column:")
                print("ALTER TABLE graph_entities MODIFY COLUMN `type` VARCHAR(50) NOT NULL;")
        except Exception as e:
            print(f"[Info] Could not check graph_entities schema: {e}")

    def _get_cursor(self):
        if not self.conn.open:
            self.conn.ping(reconnect=True)
        return self.conn.cursor()

    def build_graph(self):
        """Quét toàn bộ bài báo và xây dựng quan hệ thực thể."""
        print("\n[Graph] BẮT ĐẦU XÂY DỰNG ĐỒ THỊ TRI THỨC (KNOWLEDGE GRAPH)")
        print("=" * 60)
        
        cursor = self._get_cursor()
        # Check schema compatibility early and warn if `type` column is restrictive.
        self._check_graph_entities_schema()
        
        # 1. Lấy bài báo chưa được đánh index đồ thị (Có thể tối ưu bằng flag sau)
        cursor.execute("SELECT id, title, content FROM articles WHERE content IS NOT NULL")
        articles = cursor.fetchall()
        
        print(f"[Info] Đang xử lý {len(articles)} bài báo...")
        
        total_entities_found = 0
        inserted_type_counts = {}
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
                if entity_type not in self.GRAPH_INDEX_TYPES:
                    continue
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
                inserted_type_counts[e_type] = inserted_type_counts.get(e_type, 0) + 1
                
                # 3.2. Lấy ID của entity
                cursor.execute(
                    "SELECT id FROM graph_entities WHERE name = %s AND type = %s LIMIT 1",
                    (name, e_type),
                )
                entity_row = cursor.fetchone()
                if not entity_row:
                    # If not found, try to select by name+type was not present —
                    # in new schema we expect (name,type) uniqueness; attempt INSERT above
                    # should have created the row. If still missing, log and skip.
                    print(f"[GraphBuilder] Warning: entity not found after insert: {name} ({e_type})")
                    continue
                entity_id = entity_row['id']
                
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
        # Show a breakdown of inserted entity types to help diagnose DB mapping
        if inserted_type_counts:
            print("  Phân bố loại thực thể (tên loại: số lượng insert attempts):")
            for k, v in sorted(inserted_type_counts.items(), key=lambda x: -x[1]):
                print(f"    {k}: {v}")
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
