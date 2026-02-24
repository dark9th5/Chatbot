# 🗺️ LỘ TRÌNH DỰ ÁN: CHATBOT THU THẬP TIN TỨC TIẾNG VIỆT TỰ ĐỘNG

**Mã đồ án:** CT060122  
**Stack công nghệ:** Python, Underthesea, Sentence-Transformers  

---

## ✅ GĐ 1: Xây dựng Module Thu thập & Quản trị (Backend cơ bản)

> **Mục tiêu:** Có code Python chạy được để lấy tin RSS và Web Admin.

### ✅ Bước 1: Thu thập RSS

**Mô tả:** Viết script Python sử dụng thư viện `feedparser` để thu thập tin tức từ RSS của VnExpress và Dân Trí.

**Yêu cầu:**
- Lấy các trường: Tiêu đề, Link, Tóm tắt, Ngày đăng.
- Crawl **nội dung đầy đủ** bài báo (Full Content) bằng `BeautifulSoup`.
- Lưu kết quả vào file JSON và cơ sở dữ liệu SQLite.
- Xử lý ngoại lệ nếu mất kết nối mạng.

**File tạo ra:**
- `rss_collector_full.py` — Script chính thu thập + crawl nội dung.
- `data/news_full.json` — Dữ liệu JSON.
- `data/news_full.db` — Cơ sở dữ liệu SQLite.

**Trạng thái:** ✅ Hoàn thành — Thu thập 30 bài viết với nội dung đầy đủ (~2000 ký tự/bài).

---

### ✅ Bước 2: Xây dựng Web Admin

**Mô tả:** Dựng trang Web Admin bằng Python FastAPI và Jinja2.

**Chức năng:**
- Hiển thị danh sách tin tức đã thu thập từ RSS.
- Form upload file `.pdf` và `.docx`.
- Hàm Python dùng `pdfplumber` / `python-docx` để trích xuất văn bản thô từ file upload.

**File tạo ra:**
- `web_admin/main.py` — FastAPI application.
- `web_admin/routes/news.py` — Routes quản lý tin tức.
- `web_admin/routes/upload.py` — Routes upload file.
- `web_admin/utils/db.py` — Tiện ích cơ sở dữ liệu.
- `web_admin/utils/file_processor.py` — Trích xuất PDF/DOCX.
- `web_admin/templates/` — 8 file HTML (Jinja2).
- `web_admin/static/css/style.css` — Giao diện CSS hiện đại.
- `web_admin/static/js/main.js` — JavaScript (Drag & Drop).

**Trạng thái:** ✅ Hoàn thành — Server chạy tại http://localhost:8000

---

## ⬜ GĐ 2: Xử lý Ngôn ngữ Tự nhiên (NLP Core — Quan trọng nhất)

> **Mục tiêu:** Làm sạch dữ liệu và cắt nhỏ văn bản theo yêu cầu đề cương.

### ✅ Bước 3: Tiền xử lý tiếng Việt

**Mô tả:** Sử dụng thư viện `Underthesea`, viết hàm `clean_text` thực hiện:
- Chuẩn hóa Unicode về dạng NFC.
- Loại bỏ các thẻ HTML, emoji, và ký tự đặc biệt.
- Thực hiện tách từ (Word Segmentation).
- Loại bỏ stop words (từ dừng) tiếng Việt cơ bản.

**File tạo ra:**
- `nlp_processor.py` — Module tiền xử lý tiếng Việt.

**Trạng thái:** ✅ Hoàn thành — Xử lý toàn bộ bài báo, lưu vào cột `cleaned_content` trong database.

---

### ✅ Bước 4: Chunking (Cắt đoạn) & Vector hóa

**Mô tả:** Dùng mô hình `paraphrase-multilingual-MiniLM-L12-v2` từ Sentence-Transformers:
- Cài đặt thuật toán **Sliding Window** để chia bài báo dài thành các đoạn nhỏ (chunk), mỗi đoạn ~256 token, overlap 50 token.
- Tính **Vector Embedding** cho từng đoạn.
- (Nâng cao) Viết hàm tính **Cosine Similarity** để lọc bỏ các đoạn trùng lặp nội dung.

**File tạo ra:**
- `chunking_vectorizer.py` — Module chunking & vector hóa.

**Trạng thái:** ✅ Hoàn thành — 44 chunks từ 29 bài viết, vector 384 chiều.

---

## ⬜ GĐ 3: Trích xuất Thông tin & Sinh Câu hỏi (Logic chính)

> **Mục tiêu:** Tạo ra cặp Q&A từ dữ liệu sạch.

### ✅ Bước 5: Nhận diện Thực thể (NER)

**Mô tả:** Trích xuất các thực thể định danh (Người, Tổ chức, Địa điểm, Thời gian) từ văn bản tiếng Việt. Fine-tune mô hình BiLSTM-CRF hoặc dùng thư viện có sẵn. Viết code trích xuất và lưu vào Dict.

**File tạo ra:**
- `ner_extractor.py` — Module NER.

**Trạng thái:** ✅ Hoàn thành — 534 thực thể (PER, ORG, LOC, TIME) từ 29 bài viết.

---

### ✅ Bước 6: Sinh câu hỏi theo mẫu 5W1H

**Mô tả:** Dựa trên nguyên tắc 5W1H (Who, What, Where, When, Why, How), viết bộ hàm Python thực hiện **Template Matching**:
- Tìm thấy [Người] → Sinh: *"Ai là người thực hiện...?"*
- Tìm thấy [Thời gian] → Sinh: *"Sự kiện này diễn ra khi nào?"*
- Tìm thấy [Địa điểm] → Sinh: *"Sự kiện diễn ra ở đâu?"*

**Input:** Đoạn văn bản + danh sách thực thể.  
**Output:** Cặp {Câu hỏi — Câu trả lời}.

**File tạo ra:**
- `question_generator.py` — Bộ sinh câu hỏi 5W1H.
- `data/qa_dataset.json` — Tập dữ liệu Q&A.

**Trạng thái:** ✅ Hoàn thành — 190 cặp Q&A từ 29 bài viết.

---

## ⬜ GĐ 4: App Android & Tích hợp (Frontend)

> **Mục tiêu:** Có ứng dụng demo trên điện thoại.

### ✅ Bước 7: Viết API kết nối

**Mô tả:** Viết API bằng Python (FastAPI) để App Mobile gọi vào. API nhận `user_question`, tìm kiếm trong database vector các đoạn văn bản liên quan nhất, và trả về câu trả lời kèm nguồn trích dẫn.

**File tạo ra:**
- `chatbot_api/` — Module API (Clean Architecture: 11 files, 5 packages).

**Trạng thái:** ✅ Hoàn thành — API `POST /api/chat` + Semantic Search + nguồn trích dẫn.

---

### ✅ Bước 8: Code App Android

**Mô tả:** Lập trình Android bằng Kotlin:
- RecyclerView hiển thị tin nhắn (phải = user, trái = bot).
- EditText nhập liệu + nút Gửi.
- Sử dụng Retrofit để gọi API lấy câu trả lời từ Server.

**File tạo ra:**
- `android_app/` — Project Android Kotlin (18 files, Clean Architecture MVVM).

**Trạng thái:** ✅ Hoàn thành — MVVM + Repository + Factory + Observer.

---

## ⬜ GĐ 5: Viết Báo cáo & Thuyết minh

> **Mục tiêu:** Hoàn thiện văn bản đồ án.

### ⬜ Bước 9: Viết nội dung chương

**Mô tả:** Viết nội dung chi tiết cho từng chương báo cáo, bao gồm lý thuyết về mô hình Transformer và cơ chế Attention trong xử lý ngôn ngữ tự nhiên, tập trung vào ứng dụng cho tiếng Việt.

**Trạng thái:** ⬜ Chưa thực hiện

---

## 📊 TIẾN ĐỘ TỔNG QUAN

| Giai đoạn | Bước | Trạng thái |
| :--- | :--- | :---: |
| **GĐ 1:** Thu thập & Quản trị | Bước 1: Thu thập RSS | ✅ Xong |
| | Bước 2: Web Admin | ✅ Xong |
| **GĐ 2:** NLP Core | Bước 3: Tiền xử lý tiếng Việt | ✅ Xong |
| | Bước 4: Chunking & Vector hóa | ✅ Xong |
| **GĐ 3:** Trích xuất & Sinh Q&A | Bước 5: NER | ✅ Xong |
| | Bước 6: Sinh câu hỏi 5W1H | ✅ Xong |
| **GĐ 4:** App Android | Bước 7: API kết nối | ✅ Xong |
| | Bước 8: Code App | ✅ Xong |
| **GĐ 5:** Báo cáo | Bước 9: Viết nội dung | ⬜ |

**Tiến độ: 8/9 bước hoàn thành (89%)**
