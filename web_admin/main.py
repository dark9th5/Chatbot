"""
Main FastAPI Application - Web Admin + Chatbot API
"""

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from web_admin.routes import news, upload
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
app.state.public_base_url = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")

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
app.include_router(news.router, tags=["News"])
app.include_router(upload.router, tags=["Upload"])
app.include_router(chatbot_router.router)  # /api/chat, /api/health


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_admin.main:app", host="0.0.0.0", port=8000, reload=True)

