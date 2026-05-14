"""
NLP Processor - Tiền xử lý văn bản tiếng Việt (Bước 3)
Sử dụng Underthesea để: chuẩn hóa Unicode, tách từ, loại bỏ stop words
"""

import re
import pymysql
import unicodedata
from typing import Optional, List, Dict

from underthesea import word_tokenize
from bs4 import BeautifulSoup
from pipeline.config import MYSQL_CONFIG


def _get_connection():
    return pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)


# ============================================================
# DANH SÁCH STOP WORDS TIẾNG VIỆT
# ============================================================
VIETNAMESE_STOP_WORDS = {
    # Đại từ nhân xưng
    'tôi', 'tao', 'mình', 'ta', 'chúng_tôi', 'chúng_ta', 'bạn', 'các_bạn',
    'anh', 'chị', 'em', 'ông', 'bà', 'nó', 'họ', 'chúng_nó',
    
    # Từ chỉ định / Mạo từ
    'này', 'kia', 'đó', 'ấy', 'đây', 'nọ', 'thế',
    'một', 'các', 'những', 'mọi', 'mỗi', 'từng',
    
    # Giới từ
    'của', 'cho', 'với', 'trong', 'ngoài', 'trên', 'dưới',
    'về', 'từ', 'đến', 'tới', 'bởi', 'theo', 'qua',
    'vào', 'ra', 'lên', 'xuống', 'tại', 'ở',
    
    # Liên từ
    'và', 'hoặc', 'hay', 'nhưng', 'mà', 'nên', 'vì',
    'nếu', 'thì', 'do', 'bởi_vì', 'cho_nên', 'tuy', 'dù',
    'vì_vậy', 'tuy_nhiên', 'mặc_dù',
    
    # Trợ từ / Từ đệm
    'là', 'có', 'được', 'bị', 'đã', 'đang', 'sẽ', 'vẫn',
    'cũng', 'còn', 'rồi', 'lại', 'rất', 'quá', 'hơn',
    'nhất', 'chỉ', 'cùng', 'ngay', 'chính', 'thật',
    'không', 'chưa', 'chẳng', 'chả', 'đừng',
    
    # Từ nối câu / Phụ từ
    'thì', 'mới', 'liền', 'ngay', 'đều', 'luôn', 'suốt',
    'nữa', 'thôi', 'vậy', 'thế', 'nhé', 'nhỉ', 'ạ',
    'hả', 'ư', 'sao', 'nào', 'gì',
    
    # Từ chỉ mức độ / Số lượng
    'rất', 'lắm', 'quá', 'hết_sức', 'vô_cùng', 'khá',
    'nhiều', 'ít', 'vài', 'bao_nhiêu', 'bấy_nhiêu',
    
    # Từ chỉ thời gian phổ biến (không mang nghĩa cụ thể)
    'khi', 'lúc', 'lần', 'sau', 'trước', 'đồng_thời',
    
    # Từ khác
    'như', 'để', 'nhằm', 'bằng', 'cách', 'việc', 'điều',
    'người', 'cái', 'con', 'chiếc', 'bức', 'thanh',
    'thì', 'sang', 'sự', 'cuộc', 'phải', 'nơi',
}


import os

def load_custom_stopwords():
    try:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(base_dir, "data", "vietnamese-stopwords.txt")
        with open(path, "r", encoding="utf-8") as f:
            return set(line.strip().lower() for line in f if line.strip())
    except Exception:
        return VIETNAMESE_STOP_WORDS

CUSTOM_STOP_WORDS = load_custom_stopwords()

def clean_query(query: str) -> str:
    """Làm sạch câu hỏi: Xóa stopwords thừa để tăng độ chính xác tìm kiếm từ khóa."""
    if not query:
        return ""
    
    # Chuẩn hóa và tách từ bằng underthesea
    query = normalize_unicode(query).lower()
    words = word_tokenize(query) # Trả về list các từ (có thể chứa dấu gạch dưới _ hoặc dấu cách tùy format)
    
    # Lọc stop words
    cleaned = [w.replace('_', ' ') for w in words if w.lower().replace(' ', '_') not in CUSTOM_STOP_WORDS]
    
    text = " ".join(cleaned)
    return re.sub(r'\s+', ' ', text).strip()



# ============================================================
# HÀM TIỀN XỬ LÝ VĂN BẢN
# ============================================================

def normalize_unicode(text: str) -> str:
    """Chuẩn hóa Unicode về dạng NFC"""
    return unicodedata.normalize('NFC', text)


def remove_html_tags(text: str) -> str:
    """Loại bỏ tất cả thẻ HTML"""
    soup = BeautifulSoup(text, 'html.parser')
    return soup.get_text(separator=' ', strip=True)


def remove_emoji(text: str) -> str:
    """Loại bỏ emoji và ký tự đặc biệt Unicode"""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # Emoticons
        "\U0001F300-\U0001F5FF"  # Symbols & Pictographs
        "\U0001F680-\U0001F6FF"  # Transport & Map
        "\U0001F1E0-\U0001F1FF"  # Flags
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251"  # Enclosed characters
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub('', text)


def remove_special_characters(text: str) -> str:
    """Loại bỏ ký tự đặc biệt nhưng giữ lại tiếng Việt và dấu câu cơ bản"""
    # Giữ lại: chữ cái (bao gồm tiếng Việt), số, dấu câu cơ bản, khoảng trắng
    text = re.sub(r'[^\w\s.,;:!?\-()àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ]', ' ', text)
    # Loại bỏ khoảng trắng thừa
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def remove_urls(text: str) -> str:
    """Loại bỏ các URL"""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    return text


def word_segment(text: str) -> str:
    """Tách từ tiếng Việt sử dụng Underthesea"""
    try:
        return word_tokenize(text, format='text')
    except Exception as e:
        print(f"  ⚠ Word segmentation error: {e}")
        return text


def remove_stopwords(text: str, stop_words: set = None) -> str:
    """Loại bỏ stop words tiếng Việt"""
    if stop_words is None:
        stop_words = VIETNAMESE_STOP_WORDS
    
    words = text.split()
    filtered = [w for w in words if w.lower() not in stop_words]
    return ' '.join(filtered)


def clean_text(text: str, remove_stops: bool = True) -> Optional[str]:
    """
    Hàm chính: Tiền xử lý toàn diện văn bản tiếng Việt
    
    Pipeline:
    1. Chuẩn hóa Unicode (NFC)
    2. Loại bỏ URL
    3. Loại bỏ thẻ HTML
    4. Loại bỏ emoji
    5. Loại bỏ ký tự đặc biệt
    6. Tách từ (Word Segmentation) bằng Underthesea
    7. Loại bỏ stop words (tùy chọn)
    
    Args:
        text: Văn bản gốc cần xử lý
        remove_stops: Có loại bỏ stop words hay không
        
    Returns:
        str: Văn bản đã được tiền xử lý
    """
    if not text or not text.strip():
        return None
    
    # Bước 1: Chuẩn hóa Unicode
    text = normalize_unicode(text)
    
    # Bước 2: Loại bỏ URL
    text = remove_urls(text)
    
    # Bước 3: Loại bỏ HTML
    text = remove_html_tags(text)
    
    # Bước 4: Loại bỏ emoji
    text = remove_emoji(text)
    
    # Bước 5: Loại bỏ ký tự đặc biệt
    text = remove_special_characters(text)
    
    # Bước 6: Chuyển về chữ thường
    text = text.lower()
    
    # Bước 7: Tách từ tiếng Việt
    text = word_segment(text)
    
    # Bước 8: Loại bỏ stop words (tùy chọn)
    if remove_stops:
        text = remove_stopwords(text)
    
    # Loại bỏ khoảng trắng thừa cuối cùng
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text if text else None


# ============================================================
# XỬ LÝ DỮ LIỆU TỪ DATABASE
# ============================================================

def add_cleaned_column(db_path: str = None):
    """Thêm cột cleaned_content vào bảng articles nếu chưa có"""
    conn = _get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('ALTER TABLE articles ADD COLUMN cleaned_content LONGTEXT')
        print("✓ Đã thêm cột 'cleaned_content' vào bảng articles")
    except Exception:
        pass
    
    conn.commit()
    conn.close()


def process_all_articles(db_path: str = None):
    """
    Xử lý toàn bộ bài báo trong database
    Tiền xử lý cleaned_content = clean_text(content)
    """
    print("\n🔧 BẮT ĐẦU TIỀN XỬ LÝ VĂN BẢN TIẾNG VIỆT")
    print("=" * 60)
    
    add_cleaned_column()
    
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, title, content, source FROM articles')
    articles = cursor.fetchall()
    
    total = len(articles)
    success = 0
    failed = 0
    
    print(f"📊 Tổng số bài viết cần xử lý: {total}\n")
    
    for idx, article in enumerate(articles, 1):
        article_id = article['id']
        title = article['title']
        content = article['content']
        source = article['source']
        
        print(f"  [{idx}/{total}] {title[:50]}...")
        
        if not content:
            print(f"      ⚠ Không có nội dung, bỏ qua")
            failed += 1
            continue
        
        cleaned = clean_text(content, remove_stops=True)
        
        if cleaned:
            cursor.execute(
                'UPDATE articles SET cleaned_content = %s WHERE id = %s',
                (cleaned, article_id)
            )
            
            original_len = len(content)
            cleaned_len = len(cleaned)
            reduction = round((1 - cleaned_len / original_len) * 100, 1)
            
            print(f"      ✓ Gốc: {original_len} → Sau xử lý: {cleaned_len} ký tự (giảm {reduction}%)")
            success += 1
        else:
            print(f"      ✗ Lỗi xử lý")
            failed += 1
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 60)
    print("📊 KẾT QUẢ TIỀN XỬ LÝ")
    print("=" * 60)
    print(f"  ✓ Thành công: {success}/{total}")
    print(f"  ✗ Thất bại:   {failed}/{total}")
    print(f"  📁 Database:   MySQL")
    print("=" * 60)


def preview_results(db_path: str = None, limit: int = 3):
    """Xem trước kết quả tiền xử lý"""
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT title, content, cleaned_content, source 
        FROM articles 
        WHERE cleaned_content IS NOT NULL
        LIMIT %s
    ''', (limit,))
    
    articles = cursor.fetchall()
    conn.close()
    
    print("\n📖 XEM TRƯỚC KẾT QUẢ TIỀN XỬ LÝ")
    print("=" * 60)
    
    for idx, article in enumerate(articles, 1):
        print(f"\n{'─' * 60}")
        print(f"📰 Bài {idx}: {article['title'][:60]}")
        print(f"🔖 Nguồn: {article['source']}")
        print(f"\n📝 NỘI DUNG GỐC (200 ký tự đầu):")
        print(f"   {article['content'][:200]}...")
        print(f"\n✅ SAU TIỀN XỬ LÝ (200 ký tự đầu):")
        print(f"   {article['cleaned_content'][:200]}...")
    
    print(f"\n{'─' * 60}")


# ============================================================
# MAIN
# ============================================================

def main():
    """Hàm chính"""
    print("\n🤖 NLP Processor - Tiền xử lý văn bản tiếng Việt")
    print("   Thư viện: Underthesea (Word Segmentation)")
    print("   Database: MySQL\n")
    
    # Bước 1: Xử lý toàn bộ bài báo
    process_all_articles()
    
    # Bước 2: Xem trước kết quả
    preview_results(limit=3)
    
    print("\n✅ Tiền xử lý hoàn tất!\n")


if __name__ == '__main__':
    main()
