"""
Upload routes - Handle file uploads, text extraction, and chatbot pipeline processing
"""

import os
import shutil
from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from web_admin.utils.db import (
    save_document, get_all_documents, get_document_by_id,
    get_db_connection
)
from web_admin.utils.file_processor import process_uploaded_file, get_file_info


router = APIRouter()
templates = Jinja2Templates(directory="web_admin/templates")

UPLOAD_DIR = "uploads"
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _process_document_for_chatbot(doc_id: int, filename: str, text: str):
    """
    Tự động xử lý document thành nguồn dữ liệu cho chatbot.
    Pipeline: Text → Article DB → Chunking → Vector Embedding
    """
    from chunking_vectorizer import (
        sliding_window_chunk, TextVectorizer,
        init_chunks_table, save_chunks_to_db
    )

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Bước 1: Lưu document dưới dạng article
        cursor.execute('''
            INSERT IGNORE INTO articles (title, link, summary, content, source, published_date)
            VALUES (%s, %s, %s, %s, %s, NOW())
        ''', (
            filename,
            f"upload://{filename}",
            text[:300] if len(text) > 300 else text,
            text,
            "Upload"
        ))
        article_id = cursor.lastrowid
        conn.commit()

        if article_id == 0:
            # Article đã tồn tại (IGNORE), lấy ID hiện có
            cursor.execute('SELECT id FROM articles WHERE link = %s', (f"upload://{filename}",))
            row = cursor.fetchone()
            article_id = row['id'] if row else None

        conn.close()

        if not article_id:
            return False

        # Bước 2: Chunking (Sliding Window)
        chunks = sliding_window_chunk(text, chunk_size=256, overlap=50)

        if not chunks:
            return False

        # Bước 3: Vector Embedding
        vectorizer = TextVectorizer()
        embeddings = vectorizer.encode(chunks)

        # Bước 4: Lọc trùng lặp
        chunks_filtered, embeddings_filtered = vectorizer.filter_duplicate_chunks(
            chunks, embeddings, threshold=0.95
        )

        # Bước 5: Lưu vào DB
        init_chunks_table()
        save_chunks_to_db(None, article_id, chunks_filtered, embeddings_filtered)

        # Bước 6: Đánh dấu document đã xử lý
        conn2 = get_db_connection()
        cursor2 = conn2.cursor()
        cursor2.execute('''
            UPDATE documents SET processed = 1, chunks_count = %s
            WHERE id = %s
        ''', (len(chunks_filtered), doc_id))
        conn2.commit()
        conn2.close()

        return True

    except Exception as e:
        print(f"Error processing document for chatbot: {e}")
        conn.close()
        return False


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Trang upload file"""
    documents = get_all_documents(limit=20)

    return templates.TemplateResponse("upload.html", {
        "request": request,
        "documents": documents
    })


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Xử lý upload file — Lưu + Trích xuất text + Tự động xử lý cho chatbot"""

    # Kiểm tra extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return JSONResponse(
            status_code=400,
            content={"error": f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}
        )

    # Tạo thư mục uploads nếu chưa có
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Lưu file
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to save file: {str(e)}"}
        )

    # Kiểm tra kích thước file
    file_info = get_file_info(file_path)
    if file_info.get('size', 0) > MAX_FILE_SIZE:
        os.remove(file_path)
        return JSONResponse(
            status_code=400,
            content={"error": "File too large. Maximum size is 10MB"}
        )

    # Trích xuất text
    file_type = file_ext.replace('.', '')

    if file_type == 'txt':
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                extracted_text = f.read()
        except Exception:
            with open(file_path, 'r', encoding='latin-1') as f:
                extracted_text = f.read()
    else:
        extracted_text = process_uploaded_file(file_path, file_type)

    if not extracted_text:
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to extract text from file"}
        )

    # Lưu vào database documents
    try:
        doc_id = save_document(file.filename, extracted_text, file_type)

        # Tự động xử lý cho chatbot (chunk + vectorize)
        processed = _process_document_for_chatbot(doc_id, file.filename, extracted_text)

        return JSONResponse(content={
            "success": True,
            "message": "File uploaded and processed successfully",
            "document_id": doc_id,
            "filename": file.filename,
            "file_type": file_type,
            "text_length": len(extracted_text),
            "chatbot_processed": processed,
            "preview": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to save to database: {str(e)}"}
        )


@router.get("/documents", response_class=HTMLResponse)
async def documents_list(request: Request):
    """Danh sách documents đã upload"""
    documents = get_all_documents(limit=50)

    return templates.TemplateResponse("documents_list.html", {
        "request": request,
        "documents": documents
    })


@router.get("/documents/{doc_id}", response_class=HTMLResponse)
async def document_detail(request: Request, doc_id: int):
    """Chi tiết document"""
    document = get_document_by_id(doc_id)

    if not document:
        return templates.TemplateResponse("404.html", {
            "request": request,
            "message": "Không tìm thấy document"
        }, status_code=404)

    return templates.TemplateResponse("document_detail.html", {
        "request": request,
        "document": document
    })
