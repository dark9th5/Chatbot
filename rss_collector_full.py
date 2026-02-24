"""
RSS News Collector with Full Content Extraction
Thu thập tin tức từ VnExpress và Dân Trí với nội dung đầy đủ
Yêu cầu: pip install feedparser beautifulsoup4 requests
"""

import feedparser
import json
import pymysql
from datetime import datetime
from typing import List, Dict, Optional
import time
import sys
import requests
from bs4 import BeautifulSoup
import re


class RSSCollectorFull:
    """Class thu thập tin tức với nội dung đầy đủ từ các nguồn RSS"""
    
    # Danh sách các nguồn RSS với phân loại đề mục
    RSS_SOURCES = {
        'vnexpress': {
            'name': 'VnExpress',
            'categories': {
                'Thời sự': ['https://vnexpress.net/rss/thoi-su.rss'],
                'Thế giới': ['https://vnexpress.net/rss/the-gioi.rss'],
                'Kinh doanh': ['https://vnexpress.net/rss/kinh-doanh.rss'],
                'Giải trí': ['https://vnexpress.net/rss/giai-tri.rss'],
                'Thể thao': ['https://vnexpress.net/rss/the-thao.rss'],
                'Pháp luật': ['https://vnexpress.net/rss/phap-luat.rss'],
                'Giáo dục': ['https://vnexpress.net/rss/giao-duc.rss'],
                'Sức khỏe': ['https://vnexpress.net/rss/suc-khoe.rss'],
                'Đời sống': ['https://vnexpress.net/rss/gia-dinh.rss'],
                'Du lịch': ['https://vnexpress.net/rss/du-lich.rss'],
                'Khoa học': ['https://vnexpress.net/rss/khoa-hoc.rss'],
                'Số hóa': ['https://vnexpress.net/rss/so-hoa.rss'],
                'Xe': ['https://vnexpress.net/rss/oto-xe-may.rss'],
            }
        },
        'dantri': {
            'name': 'Dân Trí',
            'categories': {
                'Xã hội': ['https://dantri.com.vn/rss/xa-hoi.rss'],
                'Thế giới': ['https://dantri.com.vn/rss/the-gioi.rss'],
                'Kinh doanh': ['https://dantri.com.vn/rss/kinh-doanh.rss'],
                'Thể thao': ['https://dantri.com.vn/rss/the-thao.rss'],
                'Giải trí': ['https://dantri.com.vn/rss/giai-tri.rss'],
                'Sức khỏe': ['https://dantri.com.vn/rss/suc-khoe.rss'],
                'Văn hóa': ['https://dantri.com.vn/rss/van-hoa.rss'],
                'Giáo dục': ['https://dantri.com.vn/rss/giao-duc.rss'],
                'Số hóa': ['https://dantri.com.vn/rss/suc-manh-so.rss'],
                'Xe': ['https://dantri.com.vn/rss/xe.rss'],
            }
        },
        'weather': {
            'name': 'Google News Weather',
            'categories': {
                'Thời tiết Hà Nội': [
                    'https://news.google.com/rss/search?q=th%E1%BB%9Di+ti%E1%BA%BFt+H%C3%A0+N%E1%BB%99i&hl=vi&gl=VN&ceid=VN:vi'
                ],
                'Thời tiết Việt Nam': [
                    'https://news.google.com/rss/search?q=th%E1%BB%9Di+ti%E1%BA%BFt+Vi%E1%BB%87t+Nam&hl=vi&gl=VN&ceid=VN:vi',
                    'https://thoitiet24h.vn/rss/tin-tuc.xml'
                ]
            }
        }
    }
    
    def __init__(self, json_path: str = 'data/news_full.json'):
        """
        Khởi tạo RSS Collector với khả năng crawl nội dung đầy đủ
        
        Args:
            json_path: Đường dẫn file JSON để lưu dữ liệu
        """
        self.json_path = json_path
        self.articles: List[Dict] = []
        
        # Tạo thư mục data nếu chưa có
        import os
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        
        # Headers để giả lập trình duyệt
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Khởi tạo database
        self._init_database()
    
    def _get_connection(self):
        """Tạo kết nối MySQL"""
        from db_config import MYSQL_CONFIG
        return pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)
    
    def _init_database(self):
        """Khởi tạo bảng articles trong MySQL với category và created_at"""
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
            
            # Thêm cột category và created_at nếu bảng đã tồn tại
            try:
                cursor.execute('ALTER TABLE articles ADD COLUMN category VARCHAR(100)')
                cursor.execute('CREATE INDEX idx_category ON articles(category)')
            except:
                pass  # Cột đã tồn tại
            
            try:
                cursor.execute('ALTER TABLE articles ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
                cursor.execute('CREATE INDEX idx_created_at ON articles(created_at)')
            except:
                pass  # Cột đã tồn tại
            
            conn.commit()
            conn.close()
            print(f"✓ MySQL Database initialized with category and created_at columns")
            
        except Exception as e:
            print(f"✗ Database initialization error: {e}")
            sys.exit(1)
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Chuyển đổi ngày đăng sang định dạng chuẩn"""
        if not date_str:
            return None
        
        try:
            parsed_time = time.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
            return time.strftime("%Y-%m-%d %H:%M:%S", parsed_time)
        except:
            try:
                parsed_time = time.strptime(date_str, "%a, %d %b %Y %H:%M:%S GMT")
                return time.strftime("%Y-%m-%d %H:%M:%S", parsed_time)
            except:
                return date_str
    
    def _extract_vnexpress_content(self, url: str) -> Optional[str]:
        """
        Trích xuất nội dung từ bài viết VnExpress
        
        Args:
            url: URL của bài viết
            
        Returns:
            Nội dung bài viết hoặc None nếu lỗi
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # VnExpress: nội dung nằm trong class 'fck_detail'
            content_div = soup.find('article', class_='fck_detail')
            
            if not content_div:
                # Thử tìm với selector khác
                content_div = soup.find('div', class_='fck_detail')
            
            if content_div:
                # Loại bỏ các thẻ không cần thiết
                for tag in content_div.find_all(['script', 'style', 'iframe', 'ins']):
                    tag.decompose()
                
                # Lấy text và làm sạch
                paragraphs = content_div.find_all('p', class_='Normal')
                if paragraphs:
                    content = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                else:
                    content = content_div.get_text(separator='\n', strip=True)
                
                # Làm sạch khoảng trắng thừa
                content = re.sub(r'\n{3,}', '\n\n', content)
                content = re.sub(r' {2,}', ' ', content)
                
                return content if content else None
            
            return None
            
        except Exception as e:
            print(f"  ✗ Error extracting VnExpress content from {url}: {e}")
            return None
    
    def _extract_dantri_content(self, url: str) -> Optional[str]:
        """
        Trích xuất nội dung từ bài viết Dân Trí
        
        Args:
            url: URL của bài viết
            
        Returns:
            Nội dung bài viết hoặc None nếu lỗi
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Dân Trí: nội dung nằm trong class 'singular-content'
            content_div = soup.find('div', class_='singular-content')
            
            if not content_div:
                # Thử selector khác
                content_div = soup.find('div', class_='detail-content')
            
            if content_div:
                # Loại bỏ các thẻ không cần thiết
                for tag in content_div.find_all(['script', 'style', 'iframe', 'ins', 'figure']):
                    tag.decompose()
                
                # Lấy text
                paragraphs = content_div.find_all('p')
                if paragraphs:
                    content = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                else:
                    content = content_div.get_text(separator='\n', strip=True)
                
                # Làm sạch
                content = re.sub(r'\n{3,}', '\n\n', content)
                content = re.sub(r' {2,}', ' ', content)
                
                return content if content else None
            
            return None
            
        except Exception as e:
            print(f"  ✗ Error extracting Dân Trí content from {url}: {e}")
            return None
    
    def _extract_full_content(self, url: str, source: str) -> Optional[str]:
        """
        Trích xuất nội dung đầy đủ từ URL dựa vào nguồn
        
        Args:
            url: URL của bài viết
            source: Nguồn tin (VnExpress, Dân Trí)
            
        Returns:
            Nội dung đầy đủ hoặc None
        """
        if 'vnexpress' in source.lower():
            return self._extract_vnexpress_content(url)
        elif 'dân trí' in source.lower() or 'dantri' in source.lower():
            return self._extract_dantri_content(url)
        else:
            return None
    
    def fetch_rss(self, url: str, source_name: str, category: str, max_articles: int = 10) -> List[Dict]:
        """
        Thu thập tin tức từ một URL RSS với nội dung đầy đủ
        
        Args:
            url: URL của RSS feed
            source_name: Tên nguồn tin
            max_articles: Số bài viết tối đa để crawl (để tránh quá lâu)
            
        Returns:
            Danh sách các bài viết
        """
        articles = []
        
        try:
            print(f"Fetching from {source_name}: {url}")
            
            # Parse RSS feed
            feed = feedparser.parse(url)
            
            if feed.bozo:
                print(f"  ⚠ Warning: Feed parsing issue - {feed.get('bozo_exception', 'Unknown error')}")
            
            # Giới hạn số bài viết để crawl
            entries = feed.entries[:max_articles]
            
            for idx, entry in enumerate(entries, 1):
                try:
                    # Lấy thông tin cơ bản
                    published_date = None
                    if hasattr(entry, 'published'):
                        published_date = self._parse_date(entry.published)
                    elif hasattr(entry, 'updated'):
                        published_date = self._parse_date(entry.updated)
                    
                    summary = ''
                    if hasattr(entry, 'summary'):
                        # Loại bỏ HTML tags từ summary
                        summary = BeautifulSoup(entry.summary, 'html.parser').get_text(strip=True)
                    elif hasattr(entry, 'description'):
                        summary = BeautifulSoup(entry.description, 'html.parser').get_text(strip=True)
                    
                    link = entry.link if hasattr(entry, 'link') else ''
                    title = entry.title if hasattr(entry, 'title') else 'No title'
                    
                    # Crawl nội dung đầy đủ
                    print(f"  [{idx}/{len(entries)}] Crawling: {title[:50]}...")
                    content = self._extract_full_content(link, source_name)
                    
                    if content:
                        print(f"      ✓ Content extracted: {len(content)} characters")
                    else:
                        print(f"      ⚠ No content extracted, using summary only")
                    
                    article = {
                        'title': title,
                        'link': link,
                        'summary': summary,
                        'content': content if content else summary,  # Fallback to summary
                        'published_date': published_date,
                        'source': source_name,
                        'category': category
                    }
                    
                    articles.append(article)
                    
                    # Delay để tránh spam requests
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"  ✗ Error processing entry: {e}")
                    continue
            
            print(f"  ✓ Collected {len(articles)} articles with full content")
            
        except Exception as e:
            print(f"  ✗ Network error fetching {url}: {e}")
        
        return articles
    
    def collect_all(self, max_articles_per_feed: int = 5):
        """
        Thu thập tin tức từ tất cả các nguồn RSS theo danh mục
        
        Args:
            max_articles_per_feed: Số bài viết tối đa mỗi feed (để tránh quá lâu)
        """
        print("\n" + "="*60)
        print("Starting RSS Collection with Full Content Extraction")
        print("="*60 + "\n")
        
        self.articles = []
        
        for source_key, source_info in self.RSS_SOURCES.items():
            source_name = source_info['name']
            print(f"\n📰 Collecting from {source_name}...")
            
            for category, urls in source_info['categories'].items():
                print(f"\n  📂 Category: {category}")
                for url in urls:
                    articles = self.fetch_rss(url, source_name, category, max_articles_per_feed)
                    self.articles.extend(articles)
                    
                    # Delay giữa các feed
                    time.sleep(2)
        
        print(f"\n{'='*60}")
        print(f"Total articles collected: {len(self.articles)}")
        print(f"{'='*60}\n")
    
    def save_to_json(self):
        """Lưu dữ liệu vào file JSON"""
        try:
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(self.articles, f, ensure_ascii=False, indent=2)
            print(f"✓ Saved to JSON: {self.json_path} ({len(self.articles)} articles)")
        except Exception as e:
            print(f"✗ Error saving to JSON: {e}")
    
    def save_to_database(self):
        """Lưu dữ liệu vào MySQL database"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            inserted = 0
            updated = 0
            unchanged = 0
            
            for article in self.articles:
                try:
                    cursor.execute('''
                        INSERT INTO articles (title, link, summary, content, published_date, source, category)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            category = CASE
                                WHEN category IS NULL OR category = '' OR category = 'Chưa phân loại'
                                    THEN VALUES(category)
                                ELSE category
                            END
                    ''', (
                        article['title'],
                        article['link'],
                        article['summary'],
                        article['content'],
                        article['published_date'],
                        article['source'],
                        article.get('category', 'Chưa phân loại')
                    ))

                    if cursor.rowcount == 1:
                        inserted += 1
                    elif cursor.rowcount == 2:
                        updated += 1
                    else:
                        unchanged += 1
                except Exception:
                    unchanged += 1
                    continue
            
            conn.commit()
            conn.close()
            
            print(f"✓ Saved to MySQL Database")
            print(f"  - New articles: {inserted}")
            print(f"  - Existing articles recategorized: {updated}")
            print(f"  - Existing articles unchanged/skipped: {unchanged}")
            
        except Exception as e:
            print(f"✗ Database error: {e}")
    
    def get_statistics(self) -> Dict:
        """Lấy thống kê từ database"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) as cnt FROM articles')
            total = cursor.fetchone()['cnt']
            
            cursor.execute('SELECT source, COUNT(*) as cnt FROM articles GROUP BY source')
            by_source = {row['source']: row['cnt'] for row in cursor.fetchall()}
            
            cursor.execute('SELECT category, COUNT(*) as cnt FROM articles GROUP BY category ORDER BY cnt DESC')
            by_category = {row['category']: row['cnt'] for row in cursor.fetchall()}
            
            cursor.execute('SELECT COUNT(*) as cnt FROM articles WHERE content IS NOT NULL AND CHAR_LENGTH(content) > 100')
            with_content = cursor.fetchone()['cnt']
            
            cursor.execute('SELECT AVG(CHAR_LENGTH(content)) as avg_len FROM articles WHERE content IS NOT NULL')
            avg_length = cursor.fetchone()['avg_len']
            
            conn.close()
            
            return {
                'total_articles': total,
                'by_source': by_source,
                'by_category': by_category,
                'with_full_content': with_content,
                'avg_content_length': int(avg_length) if avg_length else 0
            }
        except Exception as e:
            print(f"✗ Error getting statistics: {e}")
            return {}
    
    def delete_old_articles(self, days: int = 30):
        """
        Xóa các bài viết cũ hơn số ngày chỉ định
        
        Args:
            days: Số ngày (mặc định 30 ngày = 1 tháng)
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Xóa tin cũ hơn X ngày
            cursor.execute('''
                DELETE FROM articles 
                WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
            ''', (days,))
            
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            print(f"✓ Deleted {deleted} articles older than {days} days")
            return deleted
            
        except Exception as e:
            print(f"✗ Error deleting old articles: {e}")
            return 0


def main():
    """Hàm chính để chạy script"""
    print("\n🤖 RSS News Collector with Full Content Extraction")
    print("Collecting from VnExpress and Dân Trí\n")
    
    # Khởi tạo collector
    collector = RSSCollectorFull(
        json_path='data/news_full.json'
    )
    
    # Thu thập tin tức (5 bài/feed để test nhanh, bạn có thể tăng lên)
    print("⚠️  Note: Collecting 5 articles per feed for testing.")
    print("    You can increase this number in the code.\n")
    collector.collect_all(max_articles_per_feed=5)
    
    # Lưu vào JSON
    collector.save_to_json()
    
    # Lưu vào Database
    collector.save_to_database()
    
    # Hiển thị thống kê
    print("\n" + "="*60)
    print("Database Statistics")
    print("="*60)
    stats = collector.get_statistics()
    print(f"Total articles: {stats.get('total_articles', 0)}")
    print(f"Articles with full content: {stats.get('with_full_content', 0)}")
    print(f"Average content length: {stats.get('avg_content_length', 0)} characters")
    print(f"\nBy source:")
    for source, count in stats.get('by_source', {}).items():
        print(f"  - {source}: {count} articles")
    print(f"\nBy category:")
    for category, count in stats.get('by_category', {}).items():
        print(f"  - {category}: {count} articles")
    print("="*60 + "\n")
    
    print("✅ Collection completed successfully!\n")


if __name__ == '__main__':
    main()
