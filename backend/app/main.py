"""
Main FastAPI application entry point for Appartment Agent.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import logging

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.api import properties, documents, analysis, users, photos

# Initialize logging
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Appartment Agent API",
    description="AI-powered apartment purchasing decision platform for France",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
logger.info(f"Environment: {settings.ENVIRONMENT}")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create uploads directory if it doesn't exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# Mount static files for uploads
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include routers
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(properties.router, prefix="/api/properties", tags=["properties"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(photos.router, prefix="/api/photos", tags=["photos"])


@app.get("/")
async def root():
    """Root endpoint - API health check."""
    return {
        "message": "Welcome to Appartment Agent API",
        "version": "1.0.0",
        "status": "active",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
