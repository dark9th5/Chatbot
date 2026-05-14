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
    Pipeline: Text → Article DB → Chunking → Vector Embedding → Qdrant
    """
    from pipeline.chunking_vectorizer import semantic_chunking
    from chatbot_api.dependencies import get_embedding_service, get_qdrant_service
    import re

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Bước 1: Lưu document dưới dạng article vào MySQL (để quản lý bài gốc)
        cursor.execute('''
            INSERT IGNORE INTO articles (title, link, summary, content, source, published_date, category)
            VALUES (%s, %s, %s, %s, %s, NOW(), %s)
        ''', (
            filename,
            f"upload://{filename}",
            text[:300] if len(text) > 300 else text,
            text,
            "Upload",
            "Tài liệu"
        ))
        article_id = cursor.lastrowid
        conn.commit()

        if article_id == 0:
            # Article đã tồn tại (IGNORE), lấy ID hiện có
            cursor.execute('SELECT id FROM articles WHERE link = %s', (f"upload://{filename}",))
            row = cursor.fetchone()
            article_id = row['id'] if row else None

        if not article_id:
            conn.close()
            return False

        # Bước 2: Chunking (Sử dụng Vietnamese Optimized Splitter)
        chunks = semantic_chunking(text, chunk_size=500, chunk_overlap=100)

        if not chunks:
            conn.close()
            return False

        # Bước 3: Vector Embedding
        embedding_service = get_embedding_service()
        embeddings = embedding_service.encode_batch(chunks)

        # Bước 4: Chuẩn bị Metadata và lưu vào Qdrant
        qdrant = get_qdrant_service()
        
        from datetime import date
        today_str = date.today().strftime("%Y-%m-%d")
        today_int = int(date.today().strftime("%Y%m%d"))
        
        metadatas = []
        for chunk in chunks:
            metadatas.append({
                "article_id": article_id,
                "title": filename,
                "source": "Upload",
                "link": f"upload://{filename}",
                "published_date": today_str,
                "pub_date_int": today_int,
                "category": "Tài liệu"
            })
            
        qdrant.add_chunks(chunks, embeddings, metadatas)

        # Bước 5: Đánh dấu document đã xử lý trong bảng documents của Web Admin
        cursor.execute('''
            UPDATE documents SET processed = 1, chunks_count = %s
            WHERE id = %s
        ''', (len(chunks), doc_id))
        conn.commit()
        conn.close()

        return True

    except Exception as e:
        print(f"Error processing document for chatbot: {e}")
        if conn:
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
