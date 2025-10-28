"""Photos API routes for AI-powered style visualization."""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Dict, Any
import os
import uuid

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.services.claude_service import claude_service

router = APIRouter()


@router.post("/analyze")
async def analyze_photo(
    file: UploadFile = File(...),
    transformation_request: str = Form("Describe this space and suggest modern improvements"),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Analyze apartment photo and provide AI-powered style recommendations.
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image"
        )

    # Read image data
    image_data = await file.read()

    if len(image_data) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum of {settings.MAX_UPLOAD_SIZE} bytes"
        )

    # Analyze with Claude Vision
    analysis = await claude_service.analyze_property_photos(
        image_data=image_data,
        transformation_request=transformation_request
    )

    return {
        "analysis": analysis["analysis"],
        "transformation_request": transformation_request,
        "filename": file.filename
    }


@router.post("/upload-and-save")
async def upload_photo(
    file: UploadFile = File(...),
    property_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Upload and save apartment photo for future reference.
    This can be linked to the document system for storage.
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image"
        )

    # Generate unique filename
    file_ext = os.path.splitext(file.filename)[1].lower()
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    # Save file
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    return {
        "message": "Photo uploaded successfully",
        "filename": unique_filename,
        "property_id": property_id,
        "file_path": f"/uploads/{unique_filename}"
    }
