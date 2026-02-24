from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from typing import List, Dict
from .models import Article
from .rss_parser import CustomRSSParser
from .extractors import ExtractorFactory
from .loader import DatabaseLoader
from .deduplicator import JaccardDeduplicator
from .text_summarizer import TextRankSummarizer

class AsyncNewsCrawler:
    """
    Crawler tin tức bất đồng bộ (Multi-threading).
    Quy trình: Fetch RSS -> Parse XML -> Fetch Full Content (Async) -> Save DB.
    """
    
    # Cấu hình nguồn tin (Copy từ rss_collector_full.py)
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

    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.parser = CustomRSSParser()
        self.loader = DatabaseLoader()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        # Khởi tạo bộ Deduplication lọc n-gram (Copy)
        self.deduplicator = JaccardDeduplicator(threshold=0.85)
        self.summarizer = TextRankSummarizer()

    def process_article_content(self, article: Article) -> Article:
        """Task chạy trong thread: Lấy nội dung đầy đủ"""
        try:
            extractor = ExtractorFactory.get_extractor(article.link)
            if extractor:
                full_content = extractor.extract(article.link)
                if full_content:
                    article.content = full_content
                    # Tự động tóm tắt 3 câu cốt lõi (TextRank)
                    article.summary = self.summarizer.summarize(full_content, top_k=3)
        except Exception as e:
            print(f"  ⚠ Error extracting content for {article.link}: {e}")
        return article

    def crawl_feed(self, url: str, source_name: str, category: str, limit: int = 10) -> List[Article]:
        """Crawl một RSS feed"""
        print(f"📡 Fetching RSS: {url}...")
        
        # 1. Parse RSS (Sequential - nhẹ)
        raw_articles = self.parser.parse(url, source_name, category)
        
        # Limit số lượng bài mới để crawl content (tránh spam)
        target_articles = raw_articles[:limit]
        
        print(f"  ✓ Found {len(raw_articles)} items. Processing {len(target_articles)} items...")
        
        # 2. Extract Full Content (Concurrent - nặng I/O)
        final_articles = []
        futures = []
        
        for article in target_articles:
            # Submit task vào thread pool
            future = self.executor.submit(self.process_article_content, article)
            futures.append(future)
            
        # Thu thập kết quả
        for future in as_completed(futures):
            try:
                res = future.result()
                
                # Check Data Deduplication trước khi save
                if not self.deduplicator.is_duplicate(res):
                    final_articles.append(res)
                    
            except Exception as e:
                print(f"  ✗ Task error: {e}")
                
        return final_articles

    def run(self):
        """Chạy toàn bộ quy trình Crawl"""
        print(f"🚀 Starting Async Crawler (Workers={self.max_workers})...")
        start_time = time.time()
        total_collected = 0

        for source_key, source_info in self.RSS_SOURCES.items():
            source_name = source_info['name']
            
            for category, urls in source_info['categories'].items():
                for url in urls:
                    articles = self.crawl_feed(url, source_name, category)
                    
                    if articles:
                        # 3. Save to DB (Bulk Insert)
                        self.loader.save_articles(articles)
                        total_collected += len(articles)
                        
        duration = time.time() - start_time
        print("\n" + "="*60)
        print(f"✅ Crawling Completed in {duration:.2f}s")
        print(f"📦 Total Articles: {total_collected}")
        print("="*60)
        return total_collected

    def shutdown(self):
        self.executor.shutdown(wait=True)
