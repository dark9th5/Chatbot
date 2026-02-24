# Web Admin - News Chatbot

Web Admin đẹp và hiện đại để quản lý tin tức và documents cho dự án Chatbot thu thập tin tức tiếng Việt.

## ✨ Tính năng

### 1. Dashboard
- Thống kê tổng quan: Số lượng tin tức, documents
- Phân loại theo nguồn (VnExpress, Dân Trí)
- Hiển thị tin tức mới nhất

### 2. Quản lý Tin tức
- Xem danh sách tin tức với pagination
- Tìm kiếm tin tức theo từ khóa
- Xem chi tiết nội dung đầy đủ
- Responsive table design

### 3. Upload File
- Upload file PDF và DOCX
- Drag & drop interface
- Trích xuất văn bản tự động
- Preview nội dung đã trích xuất
- Lưu vào database

### 4. Quản lý Documents
- Xem danh sách file đã upload
- Xem nội dung đã trích xuất
- Metadata: Tên file, loại, ngày upload, độ dài

## 🚀 Cách sử dụng

### Cài đặt dependencies

```bash
pip install fastapi uvicorn[standard] jinja2 python-multipart pdfplumber python-docx aiofiles
```

### Chạy server

```bash
# Cách 1: Từ thư mục gốc
python -m uvicorn web_admin.main:app --reload

# Cách 2: Chạy trực tiếp
cd web_admin
python main.py
```

### Truy cập

Mở trình duyệt và truy cập:
- **URL**: http://localhost:8000
- **Dashboard**: http://localhost:8000/
- **Tin tức**: http://localhost:8000/news
- **Upload**: http://localhost:8000/upload
- **Documents**: http://localhost:8000/documents

## 📁 Cấu trúc

```
web_admin/
├── main.py                 # FastAPI application
├── routes/
│   ├── news.py            # Routes cho tin tức
│   └── upload.py          # Routes cho upload
├── templates/
│   ├── base.html          # Base template
│   ├── index.html         # Dashboard
│   ├── news_list.html     # Danh sách tin tức
│   ├── news_detail.html   # Chi tiết tin tức
│   ├── upload.html        # Upload file
│   ├── documents_list.html # Danh sách documents
│   ├── document_detail.html # Chi tiết document
│   └── 404.html           # Error page
├── static/
│   ├── css/
│   │   └── style.css      # Modern CSS
│   └── js/
│       └── main.js        # JavaScript
└── utils/
    ├── db.py              # Database utilities
    └── file_processor.py  # PDF/DOCX processing
```

## 🎨 Design Features

- **Modern UI**: Gradient backgrounds, smooth animations
- **Responsive**: Mobile, tablet, desktop friendly
- **Drag & Drop**: Upload files by dragging
- **Search**: Real-time search functionality
- **Pagination**: Navigate through large datasets
- **Toast Notifications**: User-friendly feedback

## 🔧 API Endpoints

### News
- `GET /` - Dashboard
- `GET /news` - Danh sách tin tức (với pagination & search)
- `GET /news/{id}` - Chi tiết tin tức

### Upload
- `GET /upload` - Trang upload
- `POST /upload` - Upload file (multipart/form-data)
- `GET /documents` - Danh sách documents
- `GET /documents/{id}` - Chi tiết document

### Health
- `GET /health` - Health check

## 📝 Lưu ý

- File upload tối đa: **10MB**
- Hỗ trợ: **PDF, DOCX, DOC**
- Database: SQLite (`data/news_full.db`)
- Upload folder: `uploads/`

## 🐛 Troubleshooting

### Lỗi: "No module named 'web_admin'"
```bash
# Chạy từ thư mục gốc (d:\DoAn_CT060122)
python -m uvicorn web_admin.main:app --reload
```

### Lỗi: "Database not found"
```bash
# Chạy script thu thập RSS trước
python rss_collector_full.py
```

### Lỗi: "Port 8000 already in use"
```bash
# Dùng port khác
uvicorn web_admin.main:app --port 8001 --reload
```

## 📸 Screenshots

(Mở trình duyệt để xem giao diện thực tế)

## 🎯 Next Steps

Sau khi Web Admin hoạt động, bạn có thể:
1. Thu thập thêm dữ liệu (tăng số lượng bài viết)
2. Chuyển sang Giai đoạn 2: Xử lý NLP với Underthesea
3. Thêm tính năng export data
4. Tích hợp với chatbot backend
