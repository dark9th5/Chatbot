# News Chatbot System

Hệ thống gồm 3 phần chính:

- `Tin tức`: dữ liệu bài báo đã crawl.
- `Tài liệu`: dữ liệu từ file người dùng upload.
- Android app + Web Admin cùng gọi chung FastAPI backend, nhưng hai nguồn trên được truy hồi tách biệt hoàn toàn.

## Chạy dự án

1. Tạo file `.env` từ `.env.example` và điền thông tin MySQL / API key.
2. Cài dependency Python:

```bash
pip install -r requirements.txt
```

3. Chạy backend:

```bash
python start_project.py
```

Hoặc:

```bash
uvicorn web_admin.main:app --host 0.0.0.0 --port 8000 --reload
```

4. Mở Web Admin tại `http://127.0.0.1:8000`.

## Hành vi chatbot

- Phía trên chatbot Android có 2 nguồn độc lập: `Tin tức` và `Tài liệu`.
- Nút reset ở góc phải chỉ xóa hội thoại của nguồn đang mở.
- Câu hỏi ngày tương đối như `hôm nay`, `hôm qua`, `ngày mai` được lọc theo ngày xuất bản.
- Câu hỏi ngày tuyệt đối như `16/5` được ưu tiên theo ngày xuất hiện trong nội dung, để không bỏ lỡ các bài dự báo đăng từ tối hôm trước.
- Khi người dùng hỏi `ngày 16/5`, câu trả lời sẽ neo vào ngày tuyệt đối đó, không gọi nhầm là `hôm nay`.

## Kiểm thử

Chạy unit test:

```bash
python -m unittest discover -s tests
```

Chạy smoke test thật sau khi backend đang bật:

```bash
python scripts/live_api_smoke.py
```

Biên dịch Android:

```bash
cd apps/android
.\gradlew.bat :app:compileDebugKotlin
```

## Các endpoint chính

- `GET /health`
- `GET /api/health`
- `POST /api/chat`
- `GET /news`
- `GET /upload`
- `GET /documents`

