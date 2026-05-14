import xml.etree.ElementTree as ET
import requests
from typing import List, Optional
from datetime import datetime
from email.utils import parsedate_to_datetime
from .models import Article

class CustomRSSParser:
    """
    Parser RSS tùy chỉnh sử dụng xml.etree.ElementTree.
    Thay thế cho thư viện feedparser để tối ưu hiệu năng và RAM.
    """

    def parse(self, url: str, source_name: str, category: str) -> List[Article]:
        try:
            # 1. Fetch XML Content
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            xml_content = response.content

            # 2. Parse XML
            root = ET.fromstring(xml_content)
            
            # 3. Extract Items
            articles = []
            # RSS 2.0: /rss/channel/item
            for item in root.findall('./channel/item'):
                try:
                    title = item.findtext('title', default='').strip()
                    link = item.findtext('link', default='').strip()
                    
                    # Mô tả (Summary)
                    summary = item.findtext('description', default='').strip()
                    # Clean HTML from summary/description
                    summary = self._clean_html(summary)

                    # Ngày xuất bản
                    pub_date_str = item.findtext('pubDate', default='')
                    published_date = self._parse_date(pub_date_str)

                    # Nội dung (Content)
                    # Một số feed có thẻ content:encoded, nhưng thường ta sẽ crawl lại full content sau
                    # nên ở bước này chỉ lấy placeholder hoặc summary
                    content = summary 

                    article = Article(
                        title=title,
                        link=link,
                        summary=summary,
                        content=content, # Sẽ được update sau bởi Extractor
                        published_date=published_date,
                        source=source_name,
                        category=category
                    )
                    articles.append(article)
                    
                except Exception as e:
                    print(f"  ⚠ Error parsing item: {e}")
                    continue
            
            return articles

        except Exception as e:
            print(f"✗ Error parsing RSS {url}: {e}")
            return []

    def _clean_html(self, raw_html: str) -> str:
        """Loại bỏ thẻ HTML và giải mã các thực thể (entities)."""
        if not raw_html:
            return ""
        import re
        import html
        cleanr = re.compile('<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});')
        cleantext = re.sub(r'<.*?>', '', raw_html)
        return html.unescape(cleantext).strip()


    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse chuẩn RFC 822 (example: 'Fri, 27 Aug 2021 08:00:00 +0700')"""
        if not date_str:
            return None
        try:
            # Sử dụng email.utils để parse RFC 822 chuẩn
            dt = parsedate_to_datetime(date_str)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return date_str # Return raw if fail
