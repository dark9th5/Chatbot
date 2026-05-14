import pymysql
from typing import List
from .models import Article
import sys

class DatabaseLoader:
    """Class chịu trách nhiệm Load dữ liệu vào MySQL"""

    def __init__(self):
        self._init_database()

    def _get_connection(self):
        """Tạo kết nối MySQL"""
        from pipeline.config import MYSQL_CONFIG
        return pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)

    def _init_database(self):
        """Khởi tạo bảng articles nếu chưa có"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS articles (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(500) NOT NULL,
                    link VARCHAR(1000),
                    summary TEXT,
                    content LONGTEXT,
                    published_date VARCHAR(50),
                    source VARCHAR(100),
                    category VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_link (link(500)),
                    INDEX idx_category (category),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"✗ Database initialization error: {e}")
            sys.exit(1)

    def save_articles(self, articles: List[Article]):
        """Lưu danh sách bài báo vào DB"""
        if not articles:
            return

        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            inserted = 0
            updated = 0
            
            for article in articles:
                try:
                    cursor.execute('''
                        INSERT INTO articles (title, link, summary, content, published_date, source, category)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            content = VALUES(content),
                            summary = VALUES(summary),
                            category = CASE
                                WHEN category IS NULL OR category = '' OR category = 'Chưa phân loại'
                                    THEN VALUES(category)
                                ELSE category
                            END
                    ''', (
                        article.title,
                        article.link,
                        article.summary,
                        article.content,
                        article.published_date,
                        article.source,
                        article.category
                    ))

                    if cursor.rowcount == 1:
                        inserted += 1
                    elif cursor.rowcount == 2:
                        updated += 1
                except Exception as e:
                    # Ignore duplicate errors or data errors
                    continue
            
            conn.commit()
            conn.close()
            
            print(f"✓ Saved batch to DB: {inserted} new, {updated} updated")
            
        except Exception as e:
            print(f"✗ Database save error: {e}")
