"""
Database utilities for Web Admin — MySQL Version
"""

import pymysql
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from etl.content_cleaner import strip_article_boilerplate
from pipeline.config import MYSQL_CONFIG


CATEGORY_ALIASES = {
    'Công nghệ': 'Số hóa',
    'Thời tiết Hà Nội': 'Thời tiết Việt Nam',
}

UPLOAD_LINK_PATTERN = 'upload://%'

VI_ENTITY_TYPE_MAP = {
    'PERSON': 'NHÂN_VẬT',
    'ORG': 'TỔ_CHỨC',
    'LOC': 'ĐỊA_ĐIỂM',
    'MONEY': 'TIỀN_TỆ',
    'DATE': 'NGÀY_THÁNG',
    'TIME': 'THỜI_GIAN',
    'JOB': 'CHỨC_DANH',
    'EVENT': 'SỰ_KIỆN',
    'PRODUCT': 'SẢN_PHẨM',
    'LAW': 'LUẬT_PHÁP',
    'PERCENT': 'PHẦN_TRĂM',
    'PHONE': 'ĐIỆN_THOẠI',
    'EMAIL': 'EMAIL',
    'URL': 'LIÊN_KẾT',
    'AGE': 'TUỔI_TÁC',
    'TEMPERATURE': 'NHIỆT_ĐỘ',
    'QUANTITY': 'SỐ_LƯỢNG',
    'SCORE': 'TỶ_SỐ',
    'FACILITY': 'CƠ_SỞ_HẠ_TẦNG',
    'VEHICLE': 'PHƯƠNG_TIỆN',
    'AWARD': 'GIẢI_THƯỞNG',
    'DISEASE': 'DỊCH_BỆNH',
    'SPORT_TEAM': 'ĐỘI_BÓNG',
    'WORK_OF_ART': 'TÁC_PHẨM',
    'LANGUAGE': 'NGÔN_NGỮ',
    'NATIONALITY': 'QUỐC_TỊCH',
    'CRYPTO': 'TIỀN_ẢO',
    'ADDRESS': 'ĐỊA_CHỈ',
    'IDENTIFIER': 'MÃ_ĐỊNH_DANH',
    'STOCK_TICKER': 'MÃ_CỔ_PHIẾU',
    'INDEX': 'CHỈ_SỐ',
    'ORDINAL': 'SỐ_THỨ_TỰ',
    'CARDINAL': 'SỐ_ĐẾM',
    'DURATION': 'KHOẢNG_THỜI_GIAN',
    'HASHTAG': 'HASHTAG',
    'USERNAME': 'TÊN_TÀI_KHOẢN',
    'TOPIC': 'CHỦ_ĐỀ',
    'ACTION': 'HÀNH_ĐỘNG',
    'TREND': 'XU_HƯỚNG',
    'STATE': 'TRẠNG_THÁI',
}

VI_ATTRIBUTE_KEY_MAP = {
    'TREND': 'XU_HƯỚNG',
    'STATE': 'TRẠNG_THÁI',
}


def _normalize_category_value(category: Optional[str]) -> Optional[str]:
    """Chuẩn hóa tên danh mục cũ về tên tiếng Việt đang dùng."""
    if not category:
        return category

    cleaned = category.strip()
    return CATEGORY_ALIASES.get(cleaned, cleaned)


def _to_vi_entity_type(entity_type: Optional[str]) -> str:
    """Đổi mã loại thực thể tiếng Anh trong DB cũ sang nhãn tiếng Việt."""
    if not entity_type:
        return 'CHƯA_XÁC_ĐỊNH'
    normalized = str(entity_type).upper().strip()
    return VI_ENTITY_TYPE_MAP.get(normalized, str(entity_type).strip())


def _to_vi_attribute_key(attribute_key: Optional[str]) -> str:
    """Đổi mã thuộc tính tiếng Anh trong DB cũ sang nhãn tiếng Việt."""
    if not attribute_key:
        return 'THUỘC_TÍNH'
    normalized = str(attribute_key).upper().strip()
    return VI_ATTRIBUTE_KEY_MAP.get(normalized, _to_vi_entity_type(normalized))


def get_db_connection():
    """Tạo kết nối đến MySQL database"""
    return pymysql.connect(
        **MYSQL_CONFIG,
        cursorclass=pymysql.cursors.DictCursor
    )


def _table_exists(table_name: str) -> bool:
    """Kiểm tra bảng MySQL có tồn tại trước khi đọc dữ liệu phụ trợ."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SHOW TABLES LIKE %s', (table_name,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def _column_exists(table_name: str, column_name: str) -> bool:
    """Kiểm tra cột MySQL có tồn tại trước khi chạy truy vấn hoặc migration."""
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


def get_all_news(limit: int = 20, offset: int = 0, category: str = None, has_relations: bool = False) -> Tuple[List[Dict], int]:
    """Lấy danh sách bài báo theo trang và trả về tổng số bản ghi."""
    conn = get_db_connection()
    cursor = conn.cursor()
    has_category = _column_exists('articles', 'category')
    category = _normalize_category_value(category)

    category_select = 'a.category,' if has_category else "'Chưa phân loại' as category,"

    if category and has_category:
        count_sql = 'SELECT COUNT(*) as cnt FROM articles a WHERE a.link NOT LIKE %s AND a.category = %s'
        params = [UPLOAD_LINK_PATTERN, category]
        if has_relations:
            count_sql += ' AND EXISTS (SELECT 1 FROM entity_relations WHERE article_id = a.id)'
            
        cursor.execute(count_sql, tuple(params))
        total = cursor.fetchone()['cnt']

        select_sql = f'''
            SELECT a.id, a.title, a.link, a.summary, a.source, {category_select} a.published_date, 
                   CHAR_LENGTH(a.content) as content_length,
                   (SELECT COUNT(*) FROM entity_relations WHERE article_id = a.id) as relation_count,
                   (SELECT COUNT(*) FROM article_graph WHERE article_id = a.id) as entity_count
            FROM articles a 
            WHERE a.link NOT LIKE %s AND a.category = %s
        '''
        if has_relations:
            select_sql += ' AND EXISTS (SELECT 1 FROM entity_relations WHERE article_id = a.id)'
        select_sql += ' ORDER BY a.published_date DESC LIMIT %s OFFSET %s'
        
        cursor.execute(select_sql, tuple(params + [limit, offset]))
    else:
        count_sql = 'SELECT COUNT(*) as cnt FROM articles a WHERE a.link NOT LIKE %s'
        params = [UPLOAD_LINK_PATTERN]
        if has_relations:
            count_sql += ' AND EXISTS (SELECT 1 FROM entity_relations WHERE article_id = a.id)'
            
        cursor.execute(count_sql, tuple(params))
        total = cursor.fetchone()['cnt']

        select_sql = f'''
            SELECT a.id, a.title, a.link, a.summary, a.source, {category_select} a.published_date, 
                   CHAR_LENGTH(a.content) as content_length,
                   (SELECT COUNT(*) FROM entity_relations WHERE article_id = a.id) as relation_count,
                   (SELECT COUNT(*) FROM article_graph WHERE article_id = a.id) as entity_count
            FROM articles a 
            WHERE a.link NOT LIKE %s
        '''
        if has_relations:
            select_sql += ' AND EXISTS (SELECT 1 FROM entity_relations WHERE article_id = a.id)'
        select_sql += ' ORDER BY a.published_date DESC LIMIT %s OFFSET %s'
        
        cursor.execute(select_sql, tuple(params + [limit, offset]))

    news = cursor.fetchall()
    conn.close()

    return news, total


def get_news_by_id(news_id: int) -> Optional[Dict]:
    """Lấy đầy đủ nội dung một bài báo theo mã bài viết."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        'SELECT * FROM articles WHERE id = %s AND link NOT LIKE %s',
        (news_id, UPLOAD_LINK_PATTERN),
    )

    row = cursor.fetchone()
    conn.close()

    if row and row.get('content'):
        row['content'] = strip_article_boilerplate(row.get('content') or '', row.get('source'))

    return row


def search_news(query: str, limit: int = 20, has_relations: bool = False) -> List[Dict]:
    """Tìm bài báo theo tiêu đề, tóm tắt hoặc nội dung."""
    conn = get_db_connection()
    cursor = conn.cursor()
    has_category = _column_exists('articles', 'category')
    category_select = 'a.category,' if has_category else "'Chưa phân loại' as category,"

    search_pattern = f'%{query}%'
    select_sql = f'''
        SELECT a.id, a.title, a.link, a.summary, a.source, {category_select} a.published_date,
               CHAR_LENGTH(a.content) as content_length,
               (SELECT COUNT(*) FROM entity_relations WHERE article_id = a.id) as relation_count,
               (SELECT COUNT(*) FROM article_graph WHERE article_id = a.id) as entity_count
        FROM articles a 
        WHERE a.link NOT LIKE %s
          AND (a.title LIKE %s OR a.summary LIKE %s OR a.content LIKE %s)
    '''
    if has_relations:
        select_sql += ' AND EXISTS (SELECT 1 FROM entity_relations WHERE article_id = a.id)'
        
    select_sql += ' ORDER BY a.published_date DESC LIMIT %s'
    
    cursor.execute(select_sql, (UPLOAD_LINK_PATTERN, search_pattern, search_pattern, search_pattern, limit))

    news = cursor.fetchall()
    conn.close()

    return news


def get_statistics() -> Dict:
    """Tổng hợp số lượng bài báo theo nguồn và danh mục."""
    conn = get_db_connection()
    cursor = conn.cursor()
    has_category = _column_exists('articles', 'category')

    cursor.execute(
        'SELECT COUNT(*) as cnt FROM articles WHERE link NOT LIKE %s',
        (UPLOAD_LINK_PATTERN,),
    )
    total_news = cursor.fetchone()['cnt']


    cursor.execute(
        'SELECT source, COUNT(*) as count FROM articles WHERE link NOT LIKE %s GROUP BY source',
        (UPLOAD_LINK_PATTERN,),
    )
    news_by_source = {row['source']: row['count'] for row in cursor.fetchall()}
    
    if has_category:
        cursor.execute(
            '''
            SELECT category, COUNT(*) as count
            FROM articles
            WHERE link NOT LIKE %s
            GROUP BY category
            ORDER BY count DESC
            ''',
            (UPLOAD_LINK_PATTERN,),
        )
        news_by_category = {}
        for row in cursor.fetchall():
            normalized_category = _normalize_category_value(row['category'])
            news_by_category[normalized_category] = news_by_category.get(normalized_category, 0) + row['count']
    else:
        news_by_category = {}

    conn.close()

    return {
        'total_news': total_news,
        'news_by_source': news_by_source,
        'news_by_category': news_by_category
    }


def get_article_entities(article_id: int, limit: int = 300) -> List[Dict]:
    """Lấy nhanh danh sách thực thể đã liên kết với một bài báo."""
    if not _table_exists('article_graph') or not _table_exists('graph_entities'):
        return []

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''
            SELECT e.name, e.type
            FROM article_graph ag
            JOIN graph_entities e ON ag.entity_id = e.id
            WHERE ag.article_id = %s
            ORDER BY e.type ASC, e.name ASC
            LIMIT %s
            ''',
            (article_id, limit),
        )
        entities = []
        seen = set()
        for row in cursor.fetchall():
            entity_type = _to_vi_entity_type(row.get('type'))
            key = (str(row['name']).casefold(), entity_type)
            if key in seen:
                continue
            seen.add(key)
            entities.append({
                'name': row['name'],
                'type': entity_type,
            })
        return entities
    finally:
        conn.close()


def get_article_relations(article_id: int, limit: int = 100) -> List[Dict]:
    """Lấy nhanh các quan hệ thực thể đã lưu sẵn của một bài báo."""
    if (
        not _table_exists('entity_relations')
        or not _table_exists('graph_entities')
    ):
        return []

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''
            SELECT
                s.name AS subject,
                s.type AS subject_type,
                r.relation_type AS relation,
                o.name AS object,
                o.type AS object_type
            FROM entity_relations r
            JOIN graph_entities s ON r.subject_id = s.id
            JOIN graph_entities o ON r.object_id = o.id
            WHERE r.article_id = %s
            ORDER BY r.id DESC
            LIMIT %s
            ''',
            (article_id, limit),
        )
        relations = []
        seen = set()
        for row in cursor.fetchall():
            item = {
                'subject': row['subject'],
                'subject_type': _to_vi_entity_type(row.get('subject_type')),
                'relation': str(row['relation']).replace(' ', '_').upper(),
                'object': row['object'],
                'object_type': _to_vi_entity_type(row.get('object_type')),
            }
            key = (
                str(item['subject']).casefold(),
                item['subject_type'],
                item['relation'],
                str(item['object']).casefold(),
                item['object_type'],
            )
            if key in seen:
                continue
            seen.add(key)
            relations.append(item)
        return relations
    finally:
        conn.close()


def get_article_attributes(article_id: int, limit: int = 100) -> List[Dict]:
    """Lấy nhanh các thuộc tính thực thể đã lưu sẵn của một bài báo."""
    if (
        not _table_exists('entity_attributes')
        or not _table_exists('graph_entities')
    ):
        return []

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''
            SELECT
                e.name AS entity,
                e.type AS entity_type,
                ea.attribute_key,
                ea.attribute_value
            FROM entity_attributes ea
            JOIN graph_entities e ON ea.entity_id = e.id
            WHERE ea.article_id = %s
            ORDER BY ea.id DESC
            LIMIT %s
            ''',
            (article_id, limit),
        )
        return [
            {
                'entity': row['entity'],
                'entity_type': _to_vi_entity_type(row.get('entity_type')),
                'attribute_key': _to_vi_attribute_key(row.get('attribute_key')),
                'attribute_value': row['attribute_value'],
            }
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


def delete_article(article_id: int) -> bool:
    """Xóa bài báo khỏi MySQL"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Lấy link để phục vụ việc xóa ở Qdrant nếu cần
        cursor.execute('SELECT link FROM articles WHERE id = %s', (article_id,))
        row = cursor.fetchone()
        
        cursor.execute(
            'DELETE FROM articles WHERE id = %s AND link NOT LIKE %s',
            (article_id, UPLOAD_LINK_PATTERN),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Delete article error: {e}")
        return False
    finally:
        conn.close()


def get_categories_list() -> List[str]:
    """Lấy danh mục tin tức."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT DISTINCT category 
            FROM articles 
            WHERE category IS NOT NULL
              AND category != ''
              AND link NOT LIKE %s
            ORDER BY category ASC
        ''', (UPLOAD_LINK_PATTERN,))
        categories = [
            row['category']
            for row in cursor.fetchall()
        ]
        
        return sorted(list(set(categories)))
    except Exception as e:
        print(f"Get categories list error: {e}")
        return []
    finally:
        conn.close()


def initialize_db():
    """Khởi tạo toàn bộ cấu trúc database cần thiết cho Web Admin
    Note: documents feature disabled — do not create documents table.
    """
    print("[DB] Initializing database schema (documents disabled)...")
    ensure_articles_schema()
    from web_admin.utils.auth import ensure_seed_admin_user
    ensure_seed_admin_user()
    print("[DB] Database initialization complete.")
