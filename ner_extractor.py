"""
NER Extractor - Bước 5
Nhận diện thực thể (Named Entity Recognition) từ văn bản tiếng Việt
Sử dụng: Underthesea NER
"""

import pymysql
import json
from typing import List, Dict, Optional
from collections import defaultdict

from underthesea import ner
from db_config import MYSQL_CONFIG


def _get_connection():
    return pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)


# ============================================================
# MAPPING NER TAGS
# ============================================================

ENTITY_LABELS = {
    'PER': 'Người',
    'ORG': 'Tổ chức',
    'LOC': 'Địa điểm',
}


# ============================================================
# TRÍCH XUẤT THỰC THỂ
# ============================================================

def extract_entities(text: str) -> Dict[str, List[str]]:
    entities = defaultdict(list)

    if not text or not text.strip():
        return dict(entities)

    try:
        sentences = split_into_sentences(text)

        for sentence in sentences:
            if not sentence.strip():
                continue

            ner_results = ner(sentence)

            current_entity = []
            current_label = None

            for token_info in ner_results:
                word = token_info[0]
                tag = token_info[3] if len(token_info) > 3 else 'O'

                if tag.startswith('B-'):
                    if current_entity and current_label:
                        entity_text = ' '.join(current_entity)
                        if entity_text not in entities[current_label]:
                            entities[current_label].append(entity_text)

                    current_label = tag[2:]
                    current_entity = [word]

                elif tag.startswith('I-') and current_label == tag[2:]:
                    current_entity.append(word)

                else:
                    if current_entity and current_label:
                        entity_text = ' '.join(current_entity)
                        if entity_text not in entities[current_label]:
                            entities[current_label].append(entity_text)
                    current_entity = []
                    current_label = None

            if current_entity and current_label:
                entity_text = ' '.join(current_entity)
                if entity_text not in entities[current_label]:
                    entities[current_label].append(entity_text)

    except Exception as e:
        print(f"  ⚠ NER error: {e}")

    return dict(entities)


def split_into_sentences(text: str) -> List[str]:
    import re
    sentences = re.split(r'[.!?\n]+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def extract_time_entities(text: str) -> List[str]:
    import re

    time_patterns = [
        r'ngày\s+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
        r'ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}',
        r'ngày\s+\d{1,2}\s+tháng\s+\d{1,2}',
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
        r'tháng\s+\d{1,2}\s+năm\s+\d{4}',
        r'tháng\s+\d{1,2}[/-]\d{4}',
        r'năm\s+\d{4}',
        r'hôm\s+nay',
        r'hôm\s+qua',
        r'ngày\s+mai',
        r'tuần\s+(?:trước|sau|này|tới)',
        r'tháng\s+(?:trước|sau|này|tới)',
        r'năm\s+(?:trước|sau|này|tới|ngoái)',
        r'quý\s+[IViv1-4]+\s+năm\s+\d{4}',
        r'quý\s+[IViv1-4]+[/-]\d{4}',
    ]

    times = []
    for pattern in time_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            if m not in times:
                times.append(m)

    return times


def extract_all_entities(text: str) -> Dict[str, List[str]]:
    entities = extract_entities(text)
    times = extract_time_entities(text)
    if times:
        entities['TIME'] = times
    return entities


# ============================================================
# XỬ LÝ DATABASE (MySQL)
# ============================================================

def init_entities_table(db_path: str = None):
    """Tạo bảng entities trong MySQL"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entities (
            id INT AUTO_INCREMENT PRIMARY KEY,
            article_id INT NOT NULL,
            entity_type VARCHAR(50) NOT NULL,
            entity_value TEXT NOT NULL,
            INDEX idx_entity_type (entity_type),
            INDEX idx_entity_article (article_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')

    conn.commit()
    conn.close()
    print("✓ Bảng 'entities' đã sẵn sàng (MySQL)")


def process_all_articles(db_path: str = None):
    """Trích xuất thực thể từ toàn bộ bài báo"""
    print("\n🔧 BẮT ĐẦU NHẬN DIỆN THỰC THỂ (NER)")
    print("=" * 60)

    init_entities_table()

    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM entities')
    conn.commit()

    cursor.execute('SELECT id, title, content, source FROM articles WHERE content IS NOT NULL')
    articles = cursor.fetchall()

    total = len(articles)
    total_entities = 0
    stats = defaultdict(int)

    print(f"📊 Tổng số bài viết: {total}\n")

    for idx, article in enumerate(articles, 1):
        article_id = article['id']
        title = article['title']
        content = article['content']

        print(f"  [{idx}/{total}] {title[:50]}...")

        entities = extract_all_entities(content)

        entity_count = 0
        for entity_type, values in entities.items():
            for value in values:
                cursor.execute(
                    'INSERT INTO entities (article_id, entity_type, entity_value) VALUES (%s, %s, %s)',
                    (article_id, entity_type, value)
                )
                entity_count += 1
                stats[entity_type] += 1

        total_entities += entity_count

        entity_summary = ', '.join([f"{k}: {len(v)}" for k, v in entities.items()])
        if entity_summary:
            print(f"      ✓ {entity_summary}")
        else:
            print(f"      ⚠ Không tìm thấy thực thể")

    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print("📊 KẾT QUẢ NER")
    print("=" * 60)
    print(f"  📰 Bài viết đã xử lý: {total}")
    print(f"  🏷️ Tổng số thực thể:  {total_entities}")
    for etype, count in sorted(stats.items()):
        label = ENTITY_LABELS.get(etype, etype)
        print(f"     - {label} ({etype}): {count}")
    print("=" * 60)


def preview_results(db_path: str = None, limit: int = 3):
    """Xem trước kết quả NER"""
    conn = _get_connection()
    cursor = conn.cursor()

    print(f"\n📖 XEM TRƯỚC KẾT QUẢ NER")

    cursor.execute('''
        SELECT a.title, e.entity_type, GROUP_CONCAT(DISTINCT e.entity_value SEPARATOR ', ') as entity_vals
        FROM entities e
        JOIN articles a ON e.article_id = a.id
        GROUP BY a.id, e.entity_type
        ORDER BY a.id
        LIMIT %s
    ''', (limit * 4,))

    rows = cursor.fetchall()
    conn.close()

    current_title = None
    for row in rows:
        if row['title'] != current_title:
            current_title = row['title']
            print(f"\n{'─' * 60}")
            print(f"📰 {current_title[:60]}")

        label = ENTITY_LABELS.get(row['entity_type'], row['entity_type'])
        print(f"   🏷️ {label}: {row['entity_vals']}")

    print(f"\n{'─' * 60}")


# ============================================================
# MAIN
# ============================================================

def main():
    """Hàm chính"""
    print("\n🤖 NER Extractor - Nhận diện Thực thể tiếng Việt")
    print("   Thư viện: Underthesea NER + Regex (Time)")
    print("   Database: MySQL\n")

    process_all_articles()
    preview_results(limit=3)

    print("\n✅ NER hoàn tất!\n")


if __name__ == '__main__':
    main()
