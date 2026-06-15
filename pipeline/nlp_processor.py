"""
NLP Processor - Tiền xử lý văn bản tiếng Việt (Bước 3)
Sử dụng Underthesea để: chuẩn hóa Unicode, tách từ, loại bỏ stop words
"""

import re
import pymysql
import unicodedata
from typing import Optional, List, Dict

# Loại bỏ underthesea, thay bằng thuật toán tách từ custom
# from underthesea import word_tokenize # REMOVED AI LIBRARY
from bs4 import BeautifulSoup
from pipeline.config import MYSQL_CONFIG


# Tạo kết nối đến cơ sở dữ liệu MySQL dựa trên cấu hình đã thiết lập
def _get_connection():
    """Lấy dữ liệu nội bộ phục vụ xử lý trong module."""
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

# Tải danh sách các từ dừng (stop words) tùy chỉnh từ file văn bản
def load_custom_stopwords():
    """Nạp dữ liệu đầu vào phục vụ quá trình xử lý."""
    try:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(base_dir, "data", "vietnamese-stopwords.txt")
        with open(path, "r", encoding="utf-8") as f:
            return set(line.strip().lower() for line in f if line.strip())
    except Exception:
        return VIETNAMESE_STOP_WORDS

CUSTOM_STOP_WORDS = load_custom_stopwords()


# ============================================================
# CÁC HÀM TIỀN XỬ LÝ VÀ CHUẨN HÓA VĂN BẢN (100% CUSTOM CODE)
# ============================================================

def normalize_unicode(text: str) -> str:
    """Chuẩn hóa Unicode sang dạng NFC."""
    if not text:
        return ""
    return unicodedata.normalize("NFC", text)


def remove_urls(text: str) -> str:
    """Loại bỏ các đường dẫn URL khỏi văn bản."""
    if not text:
        return ""
    # Mẫu regex cho URL phổ biến
    url_pattern = re.compile(r'https?://\S+|www\.\S+', re.IGNORECASE)
    return url_pattern.sub('', text)


def remove_html_tags(text: str) -> str:
    """Loại bỏ các thẻ HTML rác bằng BeautifulSoup."""
    if not text:
        return ""
    try:
        soup = BeautifulSoup(text, "html.parser")
        return soup.get_text()
    except Exception:
        # Fallback bằng regex nếu BeautifulSoup gặp lỗi
        return re.sub(r'<[^>]*>', '', text)


def remove_emoji(text: str) -> str:
    """Loại bỏ các ký tự emoji và ký tự đặc biệt phi chuẩn."""
    if not text:
        return ""
    # Loại bỏ các ký tự không nằm trong nhóm chữ viết tiếng Việt cơ bản, số, khoảng trắng và các dấu câu tiêu chuẩn
    emoji_pattern = re.compile(
        r'[^\w\s,.:;!?()\-+=\'"/\\đĐ'
        r'àáảãạăằắẳẵặâầấẩẫậ'
        r'eèéẻẽẹêềếểễệ'
        r'iìíỉĩị'
        r'oòóỏõọôồốổỗộơờớởỡợ'
        r'uùúủũụưừứửữự'
        r'yỳýỷỹỵ]',
        re.UNICODE
    )
    return emoji_pattern.sub('', text)


def remove_special_characters(text: str) -> str:
    """Loại bỏ các ký tự đặc biệt thừa thãi, chuẩn hóa khoảng trắng."""
    if not text:
        return ""
    # Thay thế các ký tự đặc biệt phi chữ cái/chữ số thành khoảng trắng
    allowed_pattern = re.compile(
        r'[^a-zA-Z0-9\s_đĐ'
        r'àáảãạăằắẳẵặâầấẩẫậ'
        r'eèéẻẽẹêềếểễệ'
        r'iìíỉĩị'
        r'oòóỏõọôồốổỗộơờớởỡợ'
        r'uùúủũụưừứửữự'
        r'yỳýỷỹỵ]',
        re.UNICODE
    )
    text = allowed_pattern.sub(' ', text)
    return re.sub(r'\s+', ' ', text).strip()


# ============================================================
# THUẬT TOÁN TÁCH TỪ CUSTOM (LONGEST MATCHING) - 100% TỰ CODE
# ============================================================

class CustomVietnameseTokenizer:
    """
    Bộ tách từ tiếng Việt tự code dùng thuật toán Khớp dài nhất (MaxMatch).
    Không dùng AI, không dùng thư viện bên thứ 3.
    """
    def __init__(self):
        # Từ điển các từ ghép phổ biến (Có thể mở rộng thêm)
        """Khởi tạo đối tượng và chuẩn bị các phụ thuộc cần dùng."""
        self.dictionary = {
            "học sinh", "sinh viên", "giáo viên", "công nghệ", "thông tin",
            "kinh tế", "việt nam", "thế giới", "thời tiết", "dự báo",
            "trí tuệ", "nhân tạo", "xe hơi", "ô tô", "giá vàng", "bất động sản",
            "thành phố", "hà nội", "tp.hcm", "sài gòn", "đà nẵng"
        }
        # Tự động thêm các từ từ stop words vào từ điển để tách chính xác
        for word in VIETNAMESE_STOP_WORDS:
            if "_" in word:
                self.dictionary.add(word.replace("_", " "))

    def tokenize(self, text: str) -> List[str]:
        """Thuật toán MaxMatch tách từ."""
        text = text.lower().strip()
        words = text.split()
        result = []
        i = 0
        while i < len(words):
            found = False
            # Thử khớp từ dài nhất (tối đa 3 âm tiết)
            for length in range(3, 1, -1):
                if i + length <= len(words):
                    phrase = " ".join(words[i:i+length])
                    if phrase in self.dictionary:
                        result.append(phrase.replace(" ", "_"))
                        i += length
                        found = True
                        break
            if not found:
                result.append(words[i])
                i += 1
        return result

_tokenizer = CustomVietnameseTokenizer()

# Làm sạch câu hỏi truy vấn bằng cách loại bỏ các từ dừng không cần thiết
def clean_query(query: str) -> str:
    """Làm sạch câu hỏi: Xóa stopwords thừa (100% Custom Code)."""
    if not query:
        return ""
    
    query = normalize_unicode(query).lower()
    # Dùng tokenizer tự code thay cho underthesea
    words = _tokenizer.tokenize(query)
    
    # Lọc stop words
    cleaned = [w.replace('_', ' ') for w in words if w.lower().replace(' ', '_') not in CUSTOM_STOP_WORDS]
    
    text = " ".join(cleaned)
    return re.sub(r'\s+', ' ', text).strip()

# Tách các từ trong câu tiếng Việt sử dụng thuật toán Custom
def word_segment(text: str) -> str:
    """Tách từ tiếng Việt bằng thuật toán MaxMatch tự viết."""
    words = _tokenizer.tokenize(text)
    return " ".join(words)


# Loại bỏ các từ dừng phổ biến trong tiếng Việt khỏi đoạn văn bản
def remove_stopwords(text: str, stop_words: set = None) -> str:
    """Loại bỏ stop words tiếng Việt"""
    if stop_words is None:
        stop_words = VIETNAMESE_STOP_WORDS
    
    words = text.split()
    filtered = [w for w in words if w.lower() not in stop_words]
    return ' '.join(filtered)


# Hàm tổng hợp thực hiện toàn bộ các bước làm sạch văn bản
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

# Thêm cột mới vào bảng trong MySQL để lưu nội dung đã làm sạch
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


# Duyệt qua và làm sạch nội dung của tất cả các bài báo trong database
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


# Hiển thị kết quả sau khi đã làm sạch để kiểm tra thủ công
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

# Hàm khởi chạy chính của tiến trình tiền xử lý NLP
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
