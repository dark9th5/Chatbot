"""
Main FastAPI Application - Web Admin + Chatbot API
"""

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

import logging
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from web_admin.routes import news
from chatbot_api.routers import chat as chatbot_router


# Khởi tạo FastAPI app
app = FastAPI(
    title="News Chatbot System",
    description="Web Admin + Chatbot API cho hệ thống chatbot tin tức tiếng Việt",
    version="2.0.0"
)

allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = ["*"] if allowed_origins_raw.strip() == "*" else [
    origin.strip() for origin in allowed_origins_raw.split(",") if origin.strip()
]
app.state.public_base_url = os.getenv("PUBLIC_BASE_URL", "http://192.168.0.104:8000")

# CORS Middleware — cho phép Android app gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="web_admin/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="web_admin/templates")

# Include routers
app.include_router(chatbot_router.router)  # /api/chat, /api/health, /api/categories
app.include_router(news.router, tags=["News"])


@app.on_event("startup")
async def startup_event():
    """On startup — initialize services."""
    import logging
    import time
    from starlette.concurrency import run_in_threadpool
    from web_admin.utils.db import initialize_db
    from chatbot_api.dependencies import get_chatbot_service, get_graph_search_service
    
    logger = logging.getLogger(__name__)
    logger.info("Starting News Chatbot System (Knowledge Graph Version)...")
    start_time = time.time()
    
    try:
        # 1. Khởi tạo Database Schema
        logger.info("[1/2] Initializing Database...")
        await run_in_threadpool(initialize_db)
        
        # 2. Pre-load chatbot logic & Graph Search
        logger.info("[2/2] Initializing Graph Search Service...")
        await run_in_threadpool(get_graph_search_service)
        await run_in_threadpool(get_chatbot_service)
        
        duration = time.time() - start_time
        logger.info(f"✅ All services initialized successfully in {duration:.2f}s.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        # Không raise lỗi để app vẫn start được (cho phép sửa lỗi qua Web Admin nếu cần)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "News Chatbot System is running"}


@app.get("/api/public-config")
async def public_config():
    """Thông tin URL public để FE/mobile cấu hình nhanh (ví dụ ngrok)."""
    return {
        "public_base_url": app.state.public_base_url,
        "chat_endpoint": f"{app.state.public_base_url.rstrip('/')}/api/chat",
        "health_endpoint": f"{app.state.public_base_url.rstrip('/')}/api/health"
    }


@app.get("/_debug_env")
async def _debug_env():
    """Debug endpoint to inspect PUBLIC_BASE_URL values at runtime."""
    return {
        "app_state_public_base_url": app.state.public_base_url,
        "env_PUBLIC_BASE_URL": os.getenv("PUBLIC_BASE_URL")
    }


@app.get("/_debug_graph_types")
async def _debug_graph_types():
    """Return counts of entity types in graph_entities for debugging."""
    try:
        import pymysql
        from pipeline.config import MYSQL_CONFIG
        conn = pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cur = conn.cursor()
        cur.execute("SELECT type, COUNT(*) as c FROM graph_entities GROUP BY type ORDER BY c DESC")
        rows = cur.fetchall()
        conn.close()
        return {r['type']: r['c'] for r in rows}
    except Exception as e:
        return {"error": str(e)}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_admin.main:app", host="0.0.0.0", port=8000, reload=True)

