"""
FastAPI Application Entry Point
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Load environment variables FIRST before importing anything that uses them
load_dotenv()

from chatbot_api.routers.chat import router as chat_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Chatbot API",
    description="RAG-based Chatbot with Groq + HuggingFace fallback",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat_router)


@app.on_event("startup")
async def startup_event():
    """On startup — initialize services (lazy load via DI)."""
    logger.info("Chatbot API starting...")


@app.on_event("shutdown")
async def shutdown_event():
    """On shutdown — cleanup."""
    logger.info("Chatbot API shutting down...")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Chatbot API is running", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True
    )
