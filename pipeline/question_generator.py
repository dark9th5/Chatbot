"""
Question Generator - Bước 6
Sinh câu hỏi theo mẫu 5W1H dựa trên thực thể đã nhận diện
Who (Ai), What (Cái gì), Where (Ở đâu), When (Khi nào), Why (Tại sao), How (Như thế nào)
"""

import pymysql
import json
import numpy as np
import re
from typing import List, Dict, Tuple
from collections import defaultdict
from sentence_transformers import SentenceTransformer

from pipeline.config import MYSQL_CONFIG


def _get_connection():
    return pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)


# ============================================================
# TEMPLATE 5W1H
# ============================================================

QUESTION_TEMPLATES = {
    'PERSON': [
        "{entity} có vai trò gì trong bài \"{title}\"?",
        "Trong bài \"{title}\", {entity} được nhắc tới với hoạt động nào?",
        "Điểm đáng chú ý liên quan đến {entity} trong bài \"{title}\" là gì?",
    ],
    'ORG': [
        "Theo bài \"{title}\", {entity} đã thực hiện hoặc công bố điều gì?",
        "Vai trò của {entity} trong bài \"{title}\" là gì?",
        "Thông tin chính về {entity} được nêu trong bài \"{title}\" là gì?",
    ],
    'LOC': [
        "Sự việc gì diễn ra tại {entity} trong bài \"{title}\"?",
        "Theo bài \"{title}\", địa điểm {entity} liên quan đến sự kiện nào?",
        "Điểm nổi bật xảy ra ở {entity} là gì?",
    ],
    'TIME': [
        "Vào {entity}, sự kiện chính nào được đề cập trong bài \"{title}\"?",
        "Mốc thời gian {entity} gắn với diễn biến gì trong bài \"{title}\"?",
        "Theo bài \"{title}\", chuyện gì xảy ra vào {entity}?",
    ],
    'DATE': [
        "Vào {entity}, sự kiện chính nào được đề cập trong bài \"{title}\"?",
        "Mốc ngày {entity} gắn với diễn biến gì trong bài \"{title}\"?",
        "Theo bài \"{title}\", chuyện gì xảy ra vào {entity}?",
    ],
    'EVENT': [
        "Sự kiện {entity} được nhắc đến như thế nào trong bài \"{title}\"?",
        "Theo bài \"{title}\", điểm đáng chú ý của {entity} là gì?",
        "{entity} liên quan tới diễn biến nào trong bài \"{title}\"?",
    ],
    'PRODUCT': [
        "Bài \"{title}\" nêu thông tin gì về {entity}?",
        "{entity} được đề cập với điểm nổi bật nào trong bài \"{title}\"?",
        "Theo bài \"{title}\", diễn biến chính liên quan đến {entity} là gì?",
    ],
    'LAW': [
        "Bài \"{title}\" nói gì về {entity}?",
        "{entity} liên quan tới thay đổi nào trong bài \"{title}\"?",
        "Theo bài \"{title}\", nội dung đáng chú ý của {entity} là gì?",
    ],
    'TOPIC': [
        "Bài \"{title}\" cập nhật điều gì về {entity}?",
        "Diễn biến chính của {entity} trong bài \"{title}\" là gì?",
        "Theo bài \"{title}\", điểm đáng chú ý về {entity} là gì?",
    ],
}

_semantic_model = None


def _get_semantic_model() -> SentenceTransformer:
    global _semantic_model
    if _semantic_model is None:
        _semantic_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return _semantic_model


# ============================================================
# SINH CÂU HỎI TỪ THỰC THỂ
# ============================================================

def generate_questions_from_entities(
    entities: Dict[str, List[str]],
    context: str,
    title: str,
    max_questions_per_type: int = 2
) -> List[Dict]:
    qa_pairs = []

    for entity_type, values in entities.items():
        if entity_type not in QUESTION_TEMPLATES:
            continue

        templates = QUESTION_TEMPLATES[entity_type]

        for value in values[:max_questions_per_type]:
            template = templates[len(qa_pairs) % len(templates)]
            question = template.format(entity=value, title=title[:80])
            answer = find_relevant_sentence(context, value, title=title)

            qa_pairs.append({
                'question': question,
                'answer': answer,
                'entity_type': entity_type,
                'entity_value': value
            })

    return qa_pairs


def find_relevant_sentence(text: str, entity: str, title: str = "") -> str:
    sentences = [
        re.sub(r'\s+', ' ', s).strip()
        for s in re.split(r'(?<=[.!?])\s+|\n+', text)
    ]
    sentences = [s for s in sentences if len(s) >= 25]

    if not sentences:
        base = text[:220].strip()
        return base + ("..." if len(text) > 220 else "")

    model = _get_semantic_model()
    query = f"{entity}. {title}".strip()

    query_vec = model.encode(query, convert_to_numpy=True)
    sent_vecs = model.encode(sentences[:30], convert_to_numpy=True)

    best_sentence = sentences[0]
    best_score = -1.0
    for sentence, vec in zip(sentences[:30], sent_vecs):
        score = float(np.dot(query_vec, vec) / (np.linalg.norm(query_vec) * np.linalg.norm(vec)))
        if score > best_score:
            best_score = score
            best_sentence = sentence

    if len(best_sentence) > 240:
        best_sentence = best_sentence[:240].rstrip() + "..."

    return best_sentence


def generate_general_questions(context: str, title: str) -> List[Dict]:
    general_templates = [
        {"question": f"Thông tin chính trong bài \"{title[:80]}\" là gì?", "type": "WHAT"},
        {"question": f"Diễn biến đáng chú ý nhất trong bài \"{title[:80]}\" là gì?", "type": "HOW"},
    ]

    qa_pairs = []
    summary = find_relevant_sentence(context, title, title=title)

    for template in general_templates:
        qa_pairs.append({
            'question': template['question'],
            'answer': summary,
            'entity_type': template['type'],
            'entity_value': 'general'
        })

    return qa_pairs


# ============================================================
# XỬ LÝ DATABASE (MySQL)
# ============================================================

def init_qa_table(db_path: str = None):
    """Tạo bảng question_answers trong MySQL"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS question_answers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            article_id INT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            entity_type VARCHAR(50),
            entity_value TEXT,
            INDEX idx_qa_article (article_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')

    conn.commit()
    conn.close()
    print("✓ Bảng 'question_answers' đã sẵn sàng (MySQL)")


def process_all_articles(db_path: str = None):
    """Sinh câu hỏi 5W1H cho toàn bộ bài báo"""
    print("\n🔧 BẮT ĐẦU SINH CÂU HỎI 5W1H")
    print("=" * 60)

    init_qa_table()

    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM question_answers')
    conn.commit()

    cursor.execute('SELECT id, title, content FROM articles WHERE content IS NOT NULL')
    articles = cursor.fetchall()

    total = len(articles)
    total_qa = 0
    type_stats = defaultdict(int)

    print(f"📊 Tổng số bài viết: {total}\n")

    for idx, article in enumerate(articles, 1):
        article_id = article['id']
        title = article['title']
        content = article['content']

        print(f"  [{idx}/{total}] {title[:50]}...")

        cursor.execute(
            'SELECT entity_type, entity_value FROM entities WHERE article_id = %s',
            (article_id,)
        )
        entity_rows = cursor.fetchall()

        entities = defaultdict(list)
        for row in entity_rows:
            if row['entity_value'] not in entities[row['entity_type']]:
                entities[row['entity_type']].append(row['entity_value'])

        qa_pairs = generate_questions_from_entities(dict(entities), content, title=title)
        qa_pairs.extend(generate_general_questions(content, title=title))

        for qa in qa_pairs:
            cursor.execute('''
                INSERT INTO question_answers (article_id, question, answer, entity_type, entity_value)
                VALUES (%s, %s, %s, %s, %s)
            ''', (article_id, qa['question'], qa['answer'], qa['entity_type'], qa['entity_value']))
            type_stats[qa['entity_type']] += 1

        total_qa += len(qa_pairs)
        print(f"      ✓ {len(qa_pairs)} câu hỏi")

    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print("📊 KẾT QUẢ SINH CÂU HỎI 5W1H")
    print("=" * 60)
    print(f"  📰 Bài viết:       {total}")
    print(f"  ❓ Tổng câu hỏi:   {total_qa}")
    print(f"  📊 Phân loại:")
    for qtype, count in sorted(type_stats.items()):
        print(f"     - {qtype}: {count} câu hỏi")
    print("=" * 60)


def preview_results(db_path: str = None, limit: int = 3):
    """Xem trước cặp Q&A"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) as cnt FROM question_answers')
    total = cursor.fetchone()['cnt']

    print(f"\n📖 XEM TRƯỚC KẾT QUẢ ({total} cặp Q&A)")

    cursor.execute('''
        SELECT qa.question, qa.answer, qa.entity_type, qa.entity_value, a.title
        FROM question_answers qa
        JOIN articles a ON qa.article_id = a.id
        ORDER BY qa.article_id
        LIMIT %s
    ''', (limit * 3,))

    rows = cursor.fetchall()
    conn.close()

    current_title = None
    for row in rows:
        if row['title'] != current_title:
            current_title = row['title']
            print(f"\n{'─' * 60}")
            print(f"📰 {current_title[:60]}")

        print(f"\n   ❓ Q [{row['entity_type']}]: {row['question']}")
        print(f"   💬 A: {row['answer'][:120]}...")


def export_qa_json(db_path: str = None, output_path: str = 'data/qa_dataset.json'):
    """Xuất toàn bộ Q&A ra file JSON"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT qa.question, qa.answer, qa.entity_type, qa.entity_value, 
               a.title, a.source, a.link
        FROM question_answers qa
        JOIN articles a ON qa.article_id = a.id
        ORDER BY qa.article_id
    ''')

    rows = cursor.fetchall()
    conn.close()

    dataset = []
    for row in rows:
        dataset.append({
            'question': row['question'],
            'answer': row['answer'],
            'entity_type': row['entity_type'],
            'entity_value': row['entity_value'],
            'source_title': row['title'],
            'source': row['source'],
            'source_link': row['link']
        })

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Đã xuất {len(dataset)} cặp Q&A → {output_path}")


# ============================================================
# MAIN
# ============================================================

def main():
    """Hàm chính"""
    print("\n🤖 Question Generator - Sinh câu hỏi 5W1H")
    print("   Dựa trên thực thể đã nhận diện từ NER")
    print("   Database: MySQL\n")

    process_all_articles()
    preview_results(limit=3)
    export_qa_json()

    print("\n✅ Sinh câu hỏi 5W1H hoàn tất!\n")


if __name__ == '__main__':
    main()
