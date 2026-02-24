from abc import ABC, abstractmethod
import requests
from bs4 import BeautifulSoup
import re
from typing import Optional

class BaseExtractor(ABC):
    """Abstract Base Class cho việc trích xuất nội dung bài viết"""
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    @abstractmethod
    def extract(self, url: str) -> Optional[str]:
        pass

    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """Helper để lấy BeautifulSoup object từ URL"""
        try:
            response = requests.get(url, headers=self.HEADERS, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            print(f"  ✗ Error fetching {url}: {e}")
            return None

    def _clean_text(self, text: str) -> str:
        """Helper để làm sạch văn bản"""
        if not text:
            return ""
        # Chuẩn hóa khoảng trắng và dòng mới
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        return text.strip()


class VnExpressExtractor(BaseExtractor):
    def extract(self, url: str) -> Optional[str]:
        soup = self._get_soup(url)
        if not soup:
            return None

        try:
            # VnExpress: nội dung nằm trong class 'fck_detail'
            content_div = soup.find('article', class_='fck_detail')
            if not content_div:
                content_div = soup.find('div', class_='fck_detail')

            if content_div:
                # Loại bỏ rác
                for tag in content_div.find_all(['script', 'style', 'iframe', 'ins']):
                    tag.decompose()

                # Ưu tiên lấy từ thẻ p.Normal
                paragraphs = content_div.find_all('p', class_='Normal')
                if paragraphs:
                    content = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                else:
                    content = content_div.get_text(separator='\n', strip=True)
                
                return self._clean_text(content)
        except Exception as e:
            print(f"  ✗ Error parsing VnExpress {url}: {e}")
        
        return None


class DantriExtractor(BaseExtractor):
    def extract(self, url: str) -> Optional[str]:
        soup = self._get_soup(url)
        if not soup:
            return None

        try:
            # Dân Trí: nội dung nằm trong class 'singular-content'
            content_div = soup.find('div', class_='singular-content')
            if not content_div:
                content_div = soup.find('div', class_='detail-content')

            if content_div:
                # Loại bỏ rác
                for tag in content_div.find_all(['script', 'style', 'iframe', 'ins', 'figure']):
                    tag.decompose()

                # Lấy text
                paragraphs = content_div.find_all('p')
                if paragraphs:
                    content = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                else:
                    content = content_div.get_text(separator='\n', strip=True)
                
                return self._clean_text(content)
        except Exception as e:
            print(f"  ✗ Error parsing Dân Trí {url}: {e}")
            
        return None

class ExtractorFactory:
    """Factory để lấy Extractor phù hợp dựa trên URL/Source"""
    
    @staticmethod
    def get_extractor(url: str) -> Optional[BaseExtractor]:
        if 'vnexpress.net' in url:
            return VnExpressExtractor()
        elif 'dantri.com.vn' in url:
            return DantriExtractor()
        return None
