from abc import ABC, abstractmethod
import requests
from bs4 import BeautifulSoup, Comment
import re
from typing import Optional
import time
import random

from etl.content_cleaner import strip_article_boilerplate

class BaseExtractor(ABC):
    """Abstract Base Class cho việc trích xuất nội dung bài viết"""
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    @abstractmethod
    def extract(self, url: str) -> Optional[str]:
        """Xử lý một phần nghiệp vụ của module theo tham số đầu vào."""
        pass

    def _get_soup(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        """Lấy dữ liệu nội bộ phục vụ xử lý trong module."""
        for i in range(retries):
            try:
                time.sleep(random.uniform(1.0, 3.0))
                response = requests.get(url, headers=self.HEADERS, timeout=15)
                
                if response.status_code == 429:
                    wait_time = (2 ** i) + random.random()
                    print(f"  [Wait] 429 Too Many Requests. Waiting {wait_time:.2f}s before retry...")
                    time.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                return BeautifulSoup(response.content, 'html.parser')
                
            except Exception as e:
                if i == retries - 1:
                    print(f"  ✗ Error fetching {url}: {e}")
                else:
                    time.sleep(1)
        return None

    def _clean_text(self, text: str) -> str:
        """Làm sạch nội bộ cho dữ liệu văn bản."""
        if not text: return ""
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        return strip_article_boilerplate(text)

    def _remove_noise(self, soup: BeautifulSoup):
        """Xóa các thẻ rác khỏi cây HTML chung"""
        for element in soup.find_all(['script', 'style', 'iframe', 'ins', 'nav', 'footer', 'header', 'aside', 'form', 'button']):
            element.decompose()
        # Xóa comment HTML
        for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
            comment.extract()


class VnExpressExtractor(BaseExtractor):
    def extract(self, url: str) -> Optional[str]:
        """Xử lý một phần nghiệp vụ của module theo tham số đầu vào."""
        soup = self._get_soup(url)
        if not soup: return None
        try:
            content_div = soup.find('article', class_='fck_detail') or soup.find('div', class_='fck_detail')
            if content_div:
                self._remove_noise(content_div)
                paragraphs = content_div.find_all('p', class_='Normal')
                content = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]) if paragraphs else content_div.get_text(separator='\n', strip=True)
                return self._clean_text(content)
        except Exception: pass
        return None


class DantriExtractor(BaseExtractor):
    def extract(self, url: str) -> Optional[str]:
        """Xử lý một phần nghiệp vụ của module theo tham số đầu vào."""
        soup = self._get_soup(url)
        if not soup: return None
        try:
            content_div = soup.find('div', class_='singular-content') or soup.find('div', class_='detail-content')
            if content_div:
                self._remove_noise(content_div)
                paragraphs = content_div.find_all('p')
                content = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]) if paragraphs else content_div.get_text(separator='\n', strip=True)
                return self._clean_text(content)
        except Exception: pass
        return None


class GenericReadabilityExtractor(BaseExtractor):
    """
    Thuật toán trích xuất tự động (Readability/Text Density).
    Dành cho TẤT CẢ các website mà không cần hardcode class.
    Thuật toán: Tìm khối thẻ <div>, <article> có tỷ lệ text / tag cao nhất.
    """
    def extract(self, url: str) -> Optional[str]:
        """Xử lý một phần nghiệp vụ của module theo tham số đầu vào."""
        soup = self._get_soup(url)
        if not soup: return None
        
        try:
            self._remove_noise(soup)
            # Quét tất cả thẻ p, div, article, section
            candidates = soup.find_all(['div', 'article', 'section'])
            best_candidate = None
            highest_score = 0
            
            for candidate in candidates:
                text_length = len(candidate.get_text(strip=True))
                tags_count = len(candidate.find_all())
                
                # Bỏ qua những khối quá ít chữ
                if text_length < 200: continue
                
                # Text density score (Mật độ chữ càng cao càng dễ là nội dung chính)
                score = text_length / (tags_count + 1)
                
                # Thưởng thêm nếu là thẻ <article>
                if candidate.name == 'article': score *= 1.5
                
                if score > highest_score:
                    highest_score = score
                    best_candidate = candidate
                    
            if best_candidate:
                paragraphs = best_candidate.find_all('p')
                content = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30])
                
                # Nếu không dùng thẻ <p>, lấy text trực tiếp
                if not content:
                    content = best_candidate.get_text(separator='\n', strip=True)
                
                return self._clean_text(content)
                
        except Exception as e:
            print(f"  ✗ Error in GenericExtractor {url}: {e}")
            
        return None


class ExtractorFactory:
    """Factory để lấy Extractor phù hợp dựa trên URL/Source"""
    @staticmethod
    def get_extractor(url: str) -> Optional[BaseExtractor]:
        """Lấy dữ liệu cần thiết cho luồng xử lý."""
        if 'vnexpress.net' in url:
            return VnExpressExtractor()
        elif 'dantri.com.vn' in url:
            return DantriExtractor()
        
        # Nếu website lạ -> Dùng thuật toán Readability đa năng
        return GenericReadabilityExtractor()
