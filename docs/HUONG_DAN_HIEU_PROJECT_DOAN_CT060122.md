# Hướng Dẫn Hiểu Project DoAn_CT060122 Từ Số 0

Tài liệu này được viết cho người chưa biết gì về project, chưa cần biết Python, Kotlin, FastAPI hay AI. Mục tiêu là giúp bạn hiểu dự án theo cách đơn giản nhất: project này là gì, từng phần làm gì, dữ liệu đi như thế nào, và nên đọc file nào trước.

## 1. Project này là gì?

`DoAn_CT060122` là một hệ thống chatbot tin tức tiếng Việt. Hệ thống có 4 phần chính:

1. Thu thập tin tức từ RSS và website.
2. Làm sạch, tách nhỏ và biến văn bản thành vector để máy tìm kiếm được.
3. API backend nhận câu hỏi của người dùng, tìm đoạn tin liên quan rồi nhờ LLM viết câu trả lời.
4. Ứng dụng Android gọi API đó để người dùng chat trên điện thoại.

Nói ngắn gọn: đây không phải chatbot “tự nghĩ ra mọi thứ”, mà là chatbot kiểu RAG, tức là hỏi gì thì nó đi tìm trong dữ liệu tin tức có sẵn rồi mới trả lời.

## 2. Ý tưởng cốt lõi bạn cần nhớ

Hãy nhớ một câu đơn giản này:

**Tin tức đi vào hệ thống -> được xử lý -> được lưu -> người dùng hỏi -> hệ thống tìm lại tin phù hợp -> tạo câu trả lời -> trả về app Android.**

Nếu hiểu được dòng này là bạn đã nắm xương sống của project.

## 3. Các khối lớn của project

### 3.1. ETL / Crawler

Đây là phần lấy tin từ nguồn ngoài. Trong project, phần này nằm ở `etl/` và các file chạy như `main_etl.py`, `rss_collector_full.py`.

Nhiệm vụ của nó là:

- Lấy bài viết từ RSS.
- Cào nội dung đầy đủ của bài báo.
- Loại bỏ bài trùng.
- Tóm tắt hoặc chuẩn hóa dữ liệu.
- Lưu vào database và/hoặc Qdrant.

### 3.2. NLP / Xử lý tiếng Việt

Các file như `nlp_processor.py`, `chunking_vectorizer.py`, `ner_extractor.py`, `question_generator.py` xử lý văn bản.

Nhiệm vụ của nó là:

- Làm sạch tiếng Việt.
- Tách văn bản thành các đoạn nhỏ.
- Tạo vector embedding.
- Nhận diện thực thể như người, địa điểm, thời gian.
- Sinh cặp câu hỏi - câu trả lời từ dữ liệu.

### 3.3. Backend API

Phần backend chính nằm trong `chatbot_api/` và một phần trong `web_admin/`.

Nhiệm vụ của nó là:

- Nhận request từ Android hoặc web.
- Tìm dữ liệu liên quan trong Qdrant.
- Gọi LLM để viết câu trả lời.
- Trả response có answer, confidence và nguồn tham khảo.

### 3.4. Android app

Ứng dụng Android nằm trong `apps/android/`.

Nhiệm vụ của nó là:

- Hiển thị màn hình chat.
- Cho người dùng nhập câu hỏi.
- Gửi câu hỏi lên backend bằng Retrofit.
- Hiển thị câu trả lời, độ tin cậy và nguồn.

## 4. Luồng xử lý thật của hệ thống

### 4.1. Khi nạp dữ liệu

Luồng điển hình là:

1. Chạy crawler trong `main_etl.py`.
2. `AsyncNewsCrawler` ở `etl/crawler.py` lấy RSS.
3. Nó gọi extractor để lấy nội dung bài viết.
4. Dữ liệu được lưu vào tầng lưu trữ.
5. Khi backend cần tìm kiếm, Qdrant chứa các chunk văn bản đã vector hóa.

### 4.2. Khi người dùng hỏi

Luồng xử lý trong backend là:

1. Android gọi `POST /api/chat`.
2. `chatbot_api/routers/chat.py` nhận request.
3. `chatbot_api/services/chatbot_service.py` xử lý logic chính.
4. Câu hỏi có thể được mở rộng truy vấn nếu cần.
5. Câu hỏi được vector hóa bởi `EmbeddingService`.
6. `QdrantService` tìm các chunk gần nghĩa nhất.
7. Các kết quả được xếp lại theo điểm hybrid: vector + keyword.
8. Backend ghép ngữ cảnh và nhờ LLM viết câu trả lời.
9. Response trả về Android gồm answer, confidence, sources.

## 5. File nào là điểm vào chính?

Nếu bạn mới bắt đầu, chỉ cần nhớ các file này trước:

- [main_etl.py](main_etl.py) là điểm vào chạy crawler.
- [chatbot_api/main.py](chatbot_api/main.py) là điểm vào chạy API.
- [chatbot_api/routers/chat.py](chatbot_api/routers/chat.py) là nơi khai báo endpoint.
- [chatbot_api/services/chatbot_service.py](chatbot_api/services/chatbot_service.py) là nơi xử lý logic chính.
- [chatbot_api/dependencies.py](chatbot_api/dependencies.py) là nơi ghép các service lại với nhau.
- [apps/android/app/src/main/java/com/chatbot/newsviet/ui/ChatActivity.kt](apps/android/app/src/main/java/com/chatbot/newsviet/ui/ChatActivity.kt) là điểm vào UI Android.
- [apps/android/app/src/main/java/com/chatbot/newsviet/ui/ChatScreen.kt](apps/android/app/src/main/java/com/chatbot/newsviet/ui/ChatScreen.kt) là màn hình chat.
- [apps/android/app/src/main/java/com/chatbot/newsviet/ui/ChatViewModel.kt](apps/android/app/src/main/java/com/chatbot/newsviet/ui/ChatViewModel.kt) là logic trạng thái của app.

## 6. Giải thích từng phần bằng ngôn ngữ rất đơn giản

### 6.1. `main_etl.py`

Đây là file để chạy pipeline lấy dữ liệu. Nó tạo `AsyncNewsCrawler`, cho crawler chạy, và nếu có lỗi thì dừng an toàn.

Nói dễ hiểu: đây là nút bấm để đi lấy tin.

### 6.2. `etl/crawler.py`

File này điều khiển toàn bộ crawler bất đồng bộ.

Nó làm việc theo thứ tự:

- Đọc RSS.
- Lấy từng bài.
- Tải nội dung đầy đủ.
- Loại trùng.
- Lưu bài hợp lệ.

Đây là nơi biến dữ liệu thô trên internet thành dữ liệu sạch hơn để dùng tiếp.

### 6.3. `chatbot_api/main.py`

File này tạo ứng dụng FastAPI.

Nó làm mấy việc chính:

- Đọc biến môi trường.
- Bật CORS để Android có thể gọi API.
- Gắn router chat.
- Khởi động server.

### 6.4. `chatbot_api/routers/chat.py`

Đây là lớp nhận request.

Nó không tự nghĩ logic phức tạp, mà chỉ làm nhiệm vụ:

- Nhận câu hỏi.
- Đẩy cho `ChatbotService`.
- Trả response.

### 6.5. `chatbot_api/services/chatbot_service.py`

Đây là bộ não của chatbot.

Nó thực hiện các bước:

- Làm rõ câu hỏi.
- Có thể mở rộng query nếu câu hỏi ngắn.
- Tìm vector trong Qdrant.
- Xếp lại kết quả.
- Ghép context.
- Gọi LLM sinh câu trả lời.

Nếu bạn chỉ có thời gian đọc một file backend, hãy đọc file này trước.

### 6.6. `chatbot_api/services/embedding_service.py`

File này biến câu chữ thành vector.

Vector là dạng số để máy so sánh mức độ giống nhau giữa câu hỏi và bài báo.

### 6.7. `chatbot_api/services/qdrant_service.py`

File này làm việc với Qdrant, tức cơ sở dữ liệu vector.

Nó dùng để:

- Lưu chunks đã vector hóa.
- Tìm kiếm gần nghĩa.
- Lọc theo danh mục và ngày.
- Lưu cache semantic để trả lời nhanh hơn.

### 6.8. `chatbot_api/services/llm_service.py`

File này gọi model ngôn ngữ lớn.

Nó có thể dùng Groq, HuggingFace, hoặc cơ chế fallback tùy cấu hình.

Nhiệm vụ của nó là biến ngữ cảnh đã tìm được thành câu trả lời tự nhiên bằng tiếng Việt.

### 6.9. `apps/android/.../ChatActivity.kt`

Đây là màn hình/Activity mở app Android.

Nó khởi động giao diện chat.

### 6.10. `ChatScreen.kt`

Đây là giao diện chính.

Nó hiển thị:

- danh sách tin nhắn,
- ô nhập câu hỏi,
- bộ lọc danh mục và ngày,
- trạng thái đang tải,
- nguồn tham khảo.

### 6.11. `ChatViewModel.kt`

Đây là nơi quản lý trạng thái cho màn hình chat.

Nó giữ:

- danh sách tin nhắn,
- bộ lọc,
- trạng thái loading,
- lỗi,
- danh mục có sẵn.

Nó cũng gọi repository để gửi câu hỏi lên server.

## 7. Cách dự án hiểu câu hỏi của bạn

Khi bạn hỏi một câu như:

“Tin tức kinh tế hôm nay là gì?”

Hệ thống sẽ làm đại khái như sau:

1. Nhìn câu hỏi.
2. Chuyển câu hỏi thành vector.
3. Tìm các đoạn tin có vector gần nhất.
4. Ưu tiên những đoạn có từ khóa phù hợp.
5. Lấy ra vài đoạn tốt nhất.
6. Ghép các đoạn đó thành ngữ cảnh.
7. Đưa ngữ cảnh cho LLM.
8. LLM viết câu trả lời tiếng Việt.

Điều quan trọng là: chatbot không trả lời từ trí nhớ chung chung, mà dựa vào dữ liệu tin tức đã được nạp vào hệ thống.

## 8. Các khái niệm bạn cần hiểu trước tiên

### RSS

RSS là nguồn tin tự động từ báo chí.

### Crawler

Crawler là chương trình đi lấy dữ liệu từ web.

### NLP

NLP là xử lý ngôn ngữ tự nhiên.

### Chunk

Chunk là một đoạn nhỏ của bài viết lớn.

### Embedding / Vector

Đây là cách máy biểu diễn câu chữ bằng số.

### Qdrant

Qdrant là nơi lưu và tìm các vector.

### LLM

LLM là model sinh ngôn ngữ lớn, dùng để viết câu trả lời cuối cùng.

### RAG

RAG là kiểu chatbot có bước tìm tài liệu trước khi trả lời.

## 9. Nên học theo thứ tự nào?

Nếu bạn thực sự bắt đầu từ con số 0, nên đọc theo thứ tự này:

1. Đọc mục 1 đến 4 của file này để hiểu toàn cảnh.
2. Mở [main_etl.py](main_etl.py) để hiểu cách dữ liệu được nạp.
3. Mở [etl/crawler.py](etl/crawler.py) để hiểu crawler hoạt động.
4. Mở [chatbot_api/main.py](chatbot_api/main.py) để hiểu backend chạy thế nào.
5. Mở [chatbot_api/routers/chat.py](chatbot_api/routers/chat.py) để thấy API vào đâu.
6. Mở [chatbot_api/services/chatbot_service.py](chatbot_api/services/chatbot_service.py) để hiểu logic chính.
7. Mở [chatbot_api/services/qdrant_service.py](chatbot_api/services/qdrant_service.py) và [chatbot_api/services/embedding_service.py](chatbot_api/services/embedding_service.py) để hiểu tìm kiếm ngữ nghĩa.
8. Mở [apps/android/app/src/main/java/com/chatbot/newsviet/ui/ChatActivity.kt](apps/android/app/src/main/java/com/chatbot/newsviet/ui/ChatActivity.kt), rồi [ChatScreen.kt](apps/android/app/src/main/java/com/chatbot/newsviet/ui/ChatScreen.kt), rồi [ChatViewModel.kt](apps/android/app/src/main/java/com/chatbot/newsviet/ui/ChatViewModel.kt).

## 10. Tóm tắt vai trò từng thư mục

- `etl/`: lấy và làm sạch tin tức.
- `chatbot_api/`: backend API cho chatbot.
- `apps/android/`: app Android để người dùng chat.
- `web_admin/`: giao diện quản trị và upload dữ liệu.
- `data/`: dữ liệu đầu ra, JSON, Qdrant local, file hỗ trợ.
- `scripts/`: script phụ trợ nếu cần chạy tiện ích bổ sung.

## 11. Trạng thái tài liệu hiện tại

Sau khi dọn dẹp, file tài liệu chính để học dự án là chính file này.

- [docs/HUONG_DAN_HIEU_PROJECT_DOAN_CT060122.md](docs/HUONG_DAN_HIEU_PROJECT_DOAN_CT060122.md)

## 12. Nếu bạn muốn “thông thạo” project này thì cần nắm 3 tầng

### Tầng 1: Dữ liệu

Biết dữ liệu được lấy từ đâu, sạch ra sao, lưu ở đâu.

### Tầng 2: Luồng xử lý

Biết câu hỏi đi qua API, Qdrant, LLM như thế nào.

### Tầng 3: Giao diện

Biết app Android hiển thị và gửi câu hỏi thế nào.

Chỉ cần nắm chắc 3 tầng này là bạn sẽ hiểu được phần lớn project.

## 13. Một câu mô tả cực ngắn cho toàn project

**Đây là hệ thống chatbot tin tức tiếng Việt, lấy dữ liệu từ RSS/web, xử lý thành vector, tìm kiếm ngữ nghĩa bằng Qdrant, rồi dùng LLM để trả lời trên Android.**

## 14. Gợi ý cách học thực tế

Nếu bạn không biết gì, đừng cố đọc tất cả một lúc. Hãy làm theo kiểu sau:

1. Đọc file này một lượt.
2. Chạy thử backend hoặc xem logs nếu có.
3. Tìm câu hỏi trên app Android.
4. Quan sát response trả về.
5. Lần ngược lên backend để xem nó lấy nguồn từ đâu.
6. Sau đó mới quay lại đọc ETL và NLP.

## 15. Thiết lập file code rõ ràng (quan trọng nhất để chạy)

Phần này là checklist cấu hình ngắn gọn, theo đúng file bạn cần quan tâm khi chạy dự án.

### 15.1. File môi trường

- `.env`: file cấu hình chính khi chạy thật.
- `.env.example`: file mẫu tham chiếu.

Biến tối thiểu nên có trong `.env`:

```env
# LLM
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile

# Database
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=chatbot_db

# (Tùy chọn) fallback
HUGGINGFACE_API_KEY=
HUGGINGFACE_MODEL=mistralai/Mistral-7B-Instruct-v0.2
```

### 15.2. File backend entry

- [chatbot_api/main.py](chatbot_api/main.py): entry chạy API chatbot.
- [web_admin/main.py](web_admin/main.py): entry chạy web admin + router chatbot.

Khi muốn chạy một server thống nhất cho cả admin và API, ưu tiên chạy `web_admin.main:app`.

### 15.3. File kết nối và dependency

- [db_config.py](db_config.py): thông số kết nối DB.
- [chatbot_api/dependencies.py](chatbot_api/dependencies.py): tạo singleton service (Embedding, Qdrant, LLM, ChatbotService).

Nếu API lỗi lúc khởi động, kiểm tra 2 file này trước.

### 15.4. File xử lý lõi chatbot

- [chatbot_api/routers/chat.py](chatbot_api/routers/chat.py): endpoint API.
- [chatbot_api/services/chatbot_service.py](chatbot_api/services/chatbot_service.py): luồng RAG chính.
- [chatbot_api/services/qdrant_service.py](chatbot_api/services/qdrant_service.py): tìm kiếm vector.
- [chatbot_api/services/embedding_service.py](chatbot_api/services/embedding_service.py): encode văn bản thành vector.
- [chatbot_api/services/llm_service.py](chatbot_api/services/llm_service.py): gọi model sinh câu trả lời.

### 15.5. File ETL để nạp dữ liệu

- [main_etl.py](main_etl.py): chạy pipeline ETL.
- [etl/crawler.py](etl/crawler.py): crawler chính.
- [chunking_vectorizer.py](chunking_vectorizer.py): chunk + embedding cho dữ liệu.

Nếu bạn chưa nạp dữ liệu, chatbot có thể chạy nhưng trả lời yếu hoặc không có nguồn phù hợp.

### 15.6. File Android cần chỉnh để gọi đúng API

- [apps/android/app/src/main/java/com/chatbot/newsviet/data/api/ChatApiService.kt](apps/android/app/src/main/java/com/chatbot/newsviet/data/api/ChatApiService.kt): interface endpoint.
- [apps/android/app/build.gradle.kts](apps/android/app/build.gradle.kts): nơi chứa BuildConfig URL (nếu dùng cấu hình base URL qua gradle).

Bạn cần chắc base URL Android trỏ đúng backend đang chạy.

### 15.7. Lệnh chạy nhanh

```powershell
# 1) Backend (web admin + chatbot api)
uvicorn web_admin.main:app --host 0.0.0.0 --port 8000 --reload

# 2) ETL nạp dữ liệu
python main_etl.py
```

Thứ tự khuyến nghị:

1. Cấu hình `.env`.
2. Chạy ETL để có dữ liệu.
3. Chạy backend.
4. Mở Android app để chat.

## 16. Ghi chú cuối

Project này không phải chỉ có một file chính. Nó là một chuỗi xử lý nhiều bước, nên cách hiểu đúng nhất là đi theo luồng dữ liệu, không đi theo tên file ngẫu nhiên.

Nếu bạn đọc theo đúng thứ tự trong tài liệu này, bạn sẽ hiểu được project từ mức người mới hoàn toàn cho đến mức có thể giải thích lại toàn bộ kiến trúc bằng lời của mình.