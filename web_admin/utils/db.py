"""
Database utilities for Web Admin — MySQL Version
"""

import pymysql
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from pipeline.config import MYSQL_CONFIG


CATEGORY_ALIASES = {
    'Công nghệ': 'Số hóa',
    'Thời tiết Hà Nội': 'Thời tiết Việt Nam',
}


def _normalize_category_value(category: Optional[str]) -> Optional[str]:
    if not category:
        return category

    cleaned = category.strip()
    return CATEGORY_ALIASES.get(cleaned, cleaned)


def get_db_connection():
    """Tạo kết nối đến MySQL database"""
    return pymysql.connect(
        **MYSQL_CONFIG,
        cursorclass=pymysql.cursors.DictCursor
    )


def init_documents_table():
    """Khởi tạo bảng documents nếu chưa tồn tại"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INT AUTO_INCREMENT PRIMARY KEY,
            filename VARCHAR(500) NOT NULL,
            file_type VARCHAR(20) NOT NULL,
            content LONGTEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed TINYINT DEFAULT 0,
            chunks_count INT DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')

    conn.commit()
    conn.close()


def _table_exists(table_name: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SHOW TABLES LIKE %s', (table_name,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def _column_exists(table_name: str, column_name: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE %s", (column_name,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def ensure_articles_schema():
    """Đảm bảo bảng articles có các cột/index mới để tránh lỗi 500 khi query."""
    if not _table_exists('articles'):
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if not _column_exists('articles', 'category'):
            cursor.execute('ALTER TABLE articles ADD COLUMN category VARCHAR(100) NULL')

        if not _column_exists('articles', 'created_at'):
            cursor.execute('ALTER TABLE articles ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')

        cursor.execute("SHOW INDEX FROM articles WHERE Key_name = 'idx_category'")
        if cursor.fetchone() is None:
            cursor.execute('CREATE INDEX idx_category ON articles(category)')

        cursor.execute("SHOW INDEX FROM articles WHERE Key_name = 'idx_created_at'")
        if cursor.fetchone() is None:
            cursor.execute('CREATE INDEX idx_created_at ON articles(created_at)')

        cursor.execute("SHOW INDEX FROM articles WHERE Key_name = 'idx_published_date'")
        if cursor.fetchone() is None:
            cursor.execute('CREATE INDEX idx_published_date ON articles(published_date)')

        cursor.execute("SHOW INDEX FROM articles WHERE Key_name = 'idx_source'")
        if cursor.fetchone() is None:
            cursor.execute('CREATE INDEX idx_source ON articles(source)')

        # Backfill category cho dữ liệu cũ trước khi fallback về "Chưa phân loại"
        cursor.execute('''
            UPDATE articles
            SET category = CASE
                WHEN source LIKE '%Weather%' OR source LIKE '%Thời Tiết%' THEN 'Thời tiết Việt Nam'
                WHEN link LIKE '%/thoi-su/%' THEN 'Thời sự'
                WHEN link LIKE '%/the-gioi/%' THEN 'Thế giới'
                WHEN link LIKE '%/kinh-doanh/%' THEN 'Kinh doanh'
                WHEN link LIKE '%/giai-tri/%' THEN 'Giải trí'
                WHEN link LIKE '%/the-thao/%' THEN 'Thể thao'
                WHEN link LIKE '%/phap-luat/%' THEN 'Pháp luật'
                WHEN link LIKE '%/giao-duc/%' THEN 'Giáo dục'
                WHEN link LIKE '%/suc-khoe/%' THEN 'Sức khỏe'
                WHEN link LIKE '%/gia-dinh/%' THEN 'Đời sống'
                WHEN link LIKE '%/du-lich/%' THEN 'Du lịch'
                WHEN link LIKE '%/khoa-hoc/%' THEN 'Khoa học'
                WHEN link LIKE '%/so-hoa/%' OR link LIKE '%/suc-manh-so/%' THEN 'Số hóa'
                WHEN link LIKE '%/oto-xe-may/%' OR link LIKE '%/xe/%' THEN 'Xe'
                WHEN link LIKE '%/xa-hoi/%' THEN 'Xã hội'
                WHEN link LIKE '%/van-hoa/%' THEN 'Văn hóa'
                ELSE category
            END
            WHERE category IS NULL OR category = '' OR category = 'Chưa phân loại'
        ''')

        cursor.execute("UPDATE articles SET category = 'Số hóa' WHERE category = 'Công nghệ'")
        cursor.execute("UPDATE articles SET category = 'Thời tiết Việt Nam' WHERE category = 'Thời tiết Hà Nội'")

        cursor.execute('''
            UPDATE articles
            SET category = CASE
                WHEN title REGEXP 'thời tiết|mưa|nắng|bão|áp thấp|nhiệt độ' THEN 'Thời tiết Việt Nam'
                WHEN title REGEXP 'Ukraine|Nga|Mỹ|Trung Quốc|Israel|Gaza|NATO|EU|Triều Tiên|Iran|quốc tế' THEN 'Thế giới'
                WHEN title REGEXP 'Hà Nội|TP HCM|thành phố|tỉnh|Quốc hội|Chính phủ|Bộ trưởng' THEN 'Thời sự'
                WHEN title REGEXP 'kinh doanh|kinh tế|thị trường|chứng khoán|đầu tư|ngân hàng|giá vàng|bất động sản' THEN 'Kinh doanh'
                WHEN title REGEXP 'sức khỏe|bệnh|y tế|bệnh viện|khám' THEN 'Sức khỏe'
                WHEN title REGEXP 'thể thao|bóng đá|V-League|U23|vô địch|Olympic' THEN 'Thể thao'
                WHEN title REGEXP 'giải trí|showbiz|ca sĩ|diễn viên|phim|âm nhạc' THEN 'Giải trí'
                ELSE category
            END
            WHERE category = 'Chưa phân loại'
        ''')

        cursor.execute("UPDATE articles SET category = 'Chưa phân loại' WHERE category IS NULL OR category = ''")
        conn.commit()
    finally:
        conn.close()


def get_all_news(limit: int = 20, offset: int = 0, category: str = None) -> Tuple[List[Dict], int]:
    conn = get_db_connection()
    cursor = conn.cursor()
    has_category = _column_exists('articles', 'category')
    category = _normalize_category_value(category)

    category_select = 'category,' if has_category else "'Chưa phân loại' as category,"

    if category and has_category:
        # Khi chọn danh mục cụ thể (bao gồm cả 'Tài liệu')
        cursor.execute('SELECT COUNT(*) as cnt FROM articles WHERE category = %s', (category,))
        total = cursor.fetchone()['cnt']

        cursor.execute('''
            SELECT id, title, link, summary, source, ''' + category_select + ''' published_date, 
                   CHAR_LENGTH(content) as content_length
            FROM articles 
            WHERE category = %s
            ORDER BY published_date DESC 
            LIMIT %s OFFSET %s
        ''', (category, limit, offset))
    else:
        # Mặc định (hoặc không dùng bộ lọc): Loại bỏ danh mục 'Tài liệu'
        where_clause = "WHERE category != 'Tài liệu'" if has_category else ""
        
        cursor.execute(f'SELECT COUNT(*) as cnt FROM articles {where_clause}')
        total = cursor.fetchone()['cnt']

        cursor.execute(f'''
            SELECT id, title, link, summary, source, {category_select} published_date, 
                   CHAR_LENGTH(content) as content_length
            FROM articles 
            {where_clause}
            ORDER BY published_date DESC 
            LIMIT %s OFFSET %s
        ''', (limit, offset))

    news = cursor.fetchall()
    conn.close()

    return news, total


def get_news_by_id(news_id: int) -> Optional[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM articles WHERE id = %s', (news_id,))

    row = cursor.fetchone()
    conn.close()

    return row


def search_news(query: str, limit: int = 20) -> List[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()

    search_pattern = f'%{query}%'
    cursor.execute('''
        SELECT id, title, link, summary, source, published_date,
               CHAR_LENGTH(content) as content_length
        FROM articles 
        WHERE title LIKE %s OR summary LIKE %s OR content LIKE %s
        ORDER BY published_date DESC 
        LIMIT %s
    ''', (search_pattern, search_pattern, search_pattern, limit))

    news = cursor.fetchall()
    conn.close()

    return news


def save_document(filename: str, content: str, file_type: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO documents (filename, file_type, content)
        VALUES (%s, %s, %s)
    ''', (filename, file_type, content))

    doc_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return doc_id


def get_all_documents(limit: int = 50) -> List[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, filename, file_type, uploaded_at,
               CHAR_LENGTH(content) as content_length,
               processed, chunks_count
        FROM documents 
        ORDER BY uploaded_at DESC 
        LIMIT %s
    ''', (limit,))

    documents = cursor.fetchall()
    conn.close()

    return documents


def get_document_by_id(doc_id: int) -> Optional[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM documents WHERE id = %s', (doc_id,))

    row = cursor.fetchone()
    conn.close()

    return row


def get_statistics() -> Dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    has_category = _column_exists('articles', 'category')

    cursor.execute('SELECT COUNT(*) as cnt FROM articles')
    total_news = cursor.fetchone()['cnt']

    cursor.execute('SELECT COUNT(*) as cnt FROM documents')
    total_docs = cursor.fetchone()['cnt']

    cursor.execute('SELECT source, COUNT(*) as count FROM articles GROUP BY source')
    news_by_source = {row['source']: row['count'] for row in cursor.fetchall()}
    
    if has_category:
        cursor.execute('SELECT category, COUNT(*) as count FROM articles GROUP BY category ORDER BY count DESC')
        news_by_category = {}
        for row in cursor.fetchall():
            normalized_category = _normalize_category_value(row['category'])
            news_by_category[normalized_category] = news_by_category.get(normalized_category, 0) + row['count']
    else:
        news_by_category = {}

    conn.close()

    return {
        'total_news': total_news,
        'total_documents': total_docs,
        'news_by_source': news_by_source,
        'news_by_category': news_by_category
    }


def delete_article(article_id: int) -> bool:
    """Xóa bài báo khỏi MySQL"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Lấy link để phục vụ việc xóa ở Qdrant nếu cần
        cursor.execute('SELECT link FROM articles WHERE id = %s', (article_id,))
        row = cursor.fetchone()
        
        cursor.execute('DELETE FROM articles WHERE id = %s', (article_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Delete article error: {e}")
        return False
    finally:
        conn.close()


def delete_document(doc_id: int) -> Optional[str]:
    """Xóa tài liệu và trả về tên file để xóa file vật lý"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT filename FROM documents WHERE id = %s', (doc_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        filename = row['filename']
        
        # Xóa bài báo liên quan (nếu có)
        cursor.execute('DELETE FROM articles WHERE link = %s', (f"upload://{filename}",))
        
        # Xóa record document
        cursor.execute('DELETE FROM documents WHERE id = %s', (doc_id,))
        conn.commit()
        return filename
    except Exception as e:
        print(f"Delete document error: {e}")
        return None
    finally:
        conn.close()


def get_categories_list() -> List[str]:
    """Lấy danh sách tất cả các danh mục để app Android hiển thị"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Lấy tất cả category khác rỗng
        cursor.execute('''
            SELECT DISTINCT category 
            FROM articles 
            WHERE category IS NOT NULL AND category != '' 
            ORDER BY category ASC
        ''')
        categories = [row['category'] for row in cursor.fetchall()]
        
        # Đảm bảo có 'Tài liệu' nếu nó chưa xuất hiện
        if 'Tài liệu' not in categories:
            # Kiểm tra xem có tài liệu nào đã nạp chưa
            cursor.execute("SELECT COUNT(*) as cnt FROM articles WHERE category = 'Tài liệu'")
            if cursor.fetchone()['cnt'] > 0:
                categories.append('Tài liệu')
        
        return sorted(list(set(categories)))
    except Exception as e:
        print(f"Get categories list error: {e}")
        return []
    finally:
        conn.close()


def initialize_db():
    """Khởi tạo toàn bộ cấu trúc database cần thiết cho Web Admin"""
    print("[DB] Initializing database schema...")
    init_documents_table()
    ensure_articles_schema()
    print("[DB] Database initialization complete.")
