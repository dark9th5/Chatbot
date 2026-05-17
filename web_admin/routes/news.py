"""
News routes - Display news articles + Auto-refresh RSS
"""

from fastapi import APIRouter, Request, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import math
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

from web_admin.utils.db import (
    get_all_news, get_news_by_id, search_news, get_statistics,
    delete_article, get_categories_list
)
from chatbot_api.services.chatbot_service import ChatbotService
from chatbot_api.dependencies import get_graph_search_service


router = APIRouter()
templates = Jinja2Templates(directory="web_admin/templates")

# Khởi tạo scheduler để tự động lấy tin mỗi 1h
scheduler = BackgroundScheduler()
scheduler.start()


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Trang chủ - Dashboard"""
    stats = get_statistics()
    news, _ = get_all_news(limit=5)  # Lấy 5 tin mới nhất

    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": stats,
        "recent_news": news
    })




@router.get("/news", response_class=HTMLResponse)
def news_list(
    request: Request,
    page: int = Query(1, ge=1),
    q: str = Query(None),
    category: str = Query(None)
):
    """Danh sách tin tức với pagination, search và filter theo category"""
    limit = 20
    offset = (page - 1) * limit

    if q:
        # Tìm kiếm
        news = search_news(q, limit=100)
        total = len(news)
        news = news[offset:offset+limit]
    else:
        # Lấy tất cả hoặc theo category
        news, total = get_all_news(limit=limit, offset=offset, category=category)

    total_pages = math.ceil(total / limit)

    return templates.TemplateResponse("news_list.html", {
        "request": request,
        "news": news,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "query": q,
        "category": category
    })


@router.get("/news/{news_id}", response_class=HTMLResponse)
def news_detail(request: Request, news_id: int):
    """Chi tiết một tin tức"""
    news = get_news_by_id(news_id)

    if not news:
        return templates.TemplateResponse("404.html", {
            "request": request,
            "message": "Không tìm thấy tin tức"
        }, status_code=404)

    return templates.TemplateResponse("news_detail.html", {
        "request": request,
        "news": news
    })


# ==============================================================
# AUTO-REFRESH RSS — Thu thập tin tức mới nhất
# ==============================================================

def _run_rss_refresh():
    """Background: Crawl RSS + Chunking + Vectorize"""
    try:
        print(f"\n[{datetime.now()}] Starting RSS refresh...")
        
        from etl.crawler import AsyncNewsCrawler
        from pipeline.knowledge_graph_builder import KnowledgeGraphBuilder

        # Bước 1: Thu thập tin tức mới từ RSS (Dùng ETL mới)
        crawler = AsyncNewsCrawler()
        new_count = crawler.run() 

        # Bước 2: Xây dựng Đồ thị tri thức (Knowledge Graph)
        builder = KnowledgeGraphBuilder()
        builder.build_graph()
        builder.close()
        
        print(f"[{datetime.now()}] RSS refresh completed: {new_count} new articles added to Knowledge Graph.\n")

        return {"new_articles": new_count}
    except Exception as e:
        print(f"RSS Refresh Error: {e}")
        raise


def _auto_refresh_job():
    """Job tự động chạy mỗi 1h"""
    try:
        _run_rss_refresh()
    except Exception as e:
        print(f"Auto refresh job failed: {e}")


# Đăng ký job tự động lấy tin mỗi 1h
scheduler.add_job(_auto_refresh_job, 'interval', hours=1, id='auto_refresh_news')
print("[OK] Scheduled auto-refresh news every 1 hour")


@router.post("/api/refresh-news")
async def refresh_news(background_tasks: BackgroundTasks):
    """
    API cập nhật tin tức mới từ RSS feeds.
    Chạy: Crawl RSS → Lưu DB → Chunk & Vectorize (Incremental)
    """
    try:
        # Chạy ngầm để trả về response ngay lập tức
        background_tasks.add_task(_run_rss_refresh_task)
        
        return JSONResponse(content={
            "success": True,
            "message": "Đang cập nhật tin tức trong nền. Vui lòng đợi trong giây lát...",
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

def _run_rss_refresh_task():
    """Wrapper để chạy _run_rss_refresh và bắt lỗi nếu có"""
    try:
        _run_rss_refresh()
    except Exception as e:
        print(f"Background Refresh Error: {e}")


# Removed duplicate categories endpoint to avoid conflict with chatbot API.
# The chatbot API version in chatbot_api/routers/chat.py will handle this.


@router.delete("/api/news/{news_id}")
async def delete_news_endpoint(news_id: int):
    """API xóa bài báo (Quan hệ đồ thị tự động xóa nhờ CASCADE)"""
    # Xóa trong MySQL
    success = delete_article(news_id)
    
    if success:
        return JSONResponse(content={"success": True, "message": "Đã xóa bài báo thành công"})
    else:
        return JSONResponse(status_code=404, content={"success": False, "message": "Không tìm thấy bài báo hoặc lỗi khi xóa"})
