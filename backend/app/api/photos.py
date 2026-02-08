"""Photos API routes for AI-powered apartment redesign using Gemini 2.5 Flash."""

import logging
import time
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.better_auth_security import get_current_user_hybrid as get_current_user
from app.core.database import get_db
from app.core.i18n import get_local, translate
from app.models.photo import Photo, PhotoRedesign
from app.models.property import Property
from app.models.user import User
from app.schemas.photo import (
    PhotoListResponse,
    PhotoResponse,
    PhotoUpdate,
    PromotedRedesignResponse,
    RedesignListResponse,
    RedesignRequest,
    RedesignResponse,
    ReferenceImageUploadResponse,
    StylePresetsResponse,
)
from app.services.ai import get_image_generator
from app.services.storage import get_storage_service

# Initialize services (lazy - will be initialized on first use)
get_gemini_service = get_image_generator
# Note: Don't initialize at module level - use get_storage_service() in route handlers

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/presets")
async def get_style_presets(request: Request) -> StylePresetsResponse:
    """Get available design style presets."""
    locale = get_local(request)

    # Build the default presets list but with translated name/description
    presets = StylePresetsResponse()
    translated_presets = []
    for preset in presets.presets:
        preset_id = preset["id"]
        translated = dict(preset)
        if preset_id == "modern_norwegian":
            translated["name"] = translate("preset_modern_norwegian_name", locale)
            translated["description"] = translate("preset_modern_norwegian_desc", locale)
            translated["prompt_template"] = translate("preset_modern_norwegian_prompt", locale)
        elif preset_id == "minimalist_scandinavian":
            translated["name"] = translate("preset_minimalist_scandinavian_name", locale)
            translated["description"] = translate("preset_minimalist_scandinavian_desc", locale)
            translated["prompt_template"] = translate(
                "preset_minimalist_scandinavian_prompt", locale
            )
        elif preset_id == "cozy_hygge":
            translated["name"] = translate("preset_cozy_hygge_name", locale)
            translated["description"] = translate("preset_cozy_hygge_desc", locale)
            translated["prompt_template"] = translate("preset_cozy_hygge_prompt", locale)
        elif preset_id == "fancy_dark_modern":
            translated["name"] = translate("preset_fancy_dark_modern_name", locale)
            translated["description"] = translate("preset_fancy_dark_modern_desc", locale)
            translated["prompt_template"] = translate("preset_fancy_dark_modern_prompt", locale)
        translated_presets.append(translated)

    return StylePresetsResponse(presets=translated_presets)


@router.post("/upload", response_model=PhotoResponse)
async def upload_photo(
    request: Request,
    file: UploadFile = File(...),
    property_id: Optional[int] = Form(None),
    room_type: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Upload an apartment photo.

    Args:
        file: Image file (JPEG, PNG)
        property_id: Optional property ID to associate with
        room_type: Optional room type (living_room, bedroom, kitchen, etc.)
        description: Optional description

    Returns:
        Uploaded photo details with presigned URL
    """
    locale = get_local(request)

    # Validate file type
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if not file.content_type or file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=translate("file_must_be_image", locale)
        )

    # Validate property ownership if provided
    if property_id:
        property = (
            db.query(Property)
            .filter(Property.id == property_id, Property.user_id == int(current_user))
            .first()
        )

        if not property:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=translate("property_not_found", locale),
            )

    try:
        # Read file data
        file_data = await file.read()
        file_size = len(file_data)

        # Get user UUID for path structure
        user = db.query(User).filter(User.id == int(current_user)).first()
        if not user or not user.uuid:
            raise HTTPException(status_code=500, detail=translate("user_uuid_not_found", locale))
        user_uuid = user.uuid

        # Generate UUID for the photo path
        photo_uuid = str(uuid.uuid4())

        # Upload to storage with structured path: {user_uuid}/photos/{photo_uuid}/{filename}
        storage_service = get_storage_service()
        storage_key = f"{user_uuid}/photos/{photo_uuid}/{file.filename}"
        storage_service.upload_file(file_data=file_data, filename=storage_key, bucket_name="photos")

        # Create database record with storage info
        photo = Photo(
            uuid=photo_uuid,
            user_id=int(current_user),
            property_id=property_id,
            filename=file.filename,
            storage_key=storage_key,
            storage_bucket="photos",
            file_size=file_size,
            mime_type=file.content_type,
            room_type=room_type,
            description=description,
        )

        db.add(photo)
        db.commit()
        db.refresh(photo)

        # Generate presigned URL
        presigned_url = get_storage_service().get_presigned_url(
            storage_key=photo.storage_key, bucket_name="photos", expiry=timedelta(hours=1)
        )

        logger.info(f"✅ Photo {photo.id} uploaded: {file.filename}")

        return PhotoResponse(
            id=photo.id,
            uuid=photo.uuid,
            user_id=photo.user_id,
            property_id=photo.property_id,
            filename=photo.filename,
            storage_key=photo.storage_key,
            storage_bucket=photo.storage_bucket,
            file_size=photo.file_size,
            mime_type=photo.mime_type,
            room_type=photo.room_type,
            description=photo.description,
            uploaded_at=photo.uploaded_at,
            presigned_url=presigned_url,
            redesign_count=0,
        )

    except Exception as e:
        logger.error(f"Error uploading photo: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=translate("failed_upload_photo", locale, error=str(e)),
        )


@router.post("/references/upload", response_model=ReferenceImageUploadResponse)
async def upload_reference_image(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Upload a reference/inspiration image for redesign prompts.

    Returns a storage key to include in the redesign request.
    Max file size: 10MB.
    """
    locale = get_local(request)

    # Validate file type
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if not file.content_type or file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("file_must_be_image", locale),
        )

    try:
        file_data = await file.read()
        file_size = len(file_data)

        # Validate file size (10MB limit)
        max_size = 10 * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=translate("reference_image_too_large", locale),
            )

        # Get user UUID for path structure
        user = db.query(User).filter(User.id == int(current_user)).first()
        if not user or not user.uuid:
            raise HTTPException(status_code=500, detail=translate("user_uuid_not_found", locale))
        user_uuid = user.uuid

        ref_uuid = str(uuid.uuid4())
        storage_key = f"{user_uuid}/references/{ref_uuid}/{file.filename}"
        storage_service = get_storage_service()
        storage_service.upload_file(file_data=file_data, filename=storage_key, bucket_name="photos")

        presigned_url = storage_service.get_presigned_url(
            storage_key=storage_key, bucket_name="photos", expiry=timedelta(hours=1)
        )

        logger.info(f"Reference image uploaded: {storage_key}")

        return ReferenceImageUploadResponse(
            storage_key=storage_key,
            presigned_url=presigned_url,
            file_size=file_size,
            mime_type=file.content_type,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading reference image: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=translate("failed_upload_photo", locale, error=str(e)),
        )


@router.post("/{photo_id}/redesign", response_model=RedesignResponse)
async def create_redesign(
    photo_id: int,
    redesign_request: RedesignRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Generate a redesign of an apartment photo using Gemini 2.5 Flash.

    Args:
        photo_id: ID of the original photo
        redesign_request: Redesign parameters (style_preset or custom_prompt)

    Returns:
        Generated redesign details with presigned URL
    """
    locale = get_local(request)

    # Get original photo
    photo = db.query(Photo).filter(Photo.id == photo_id, Photo.user_id == int(current_user)).first()

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("photo_not_found", locale)
        )

    # Get user UUID for path structure
    user = db.query(User).filter(User.id == int(current_user)).first()
    if not user or not user.uuid:
        raise HTTPException(status_code=500, detail=translate("user_uuid_not_found", locale))
    user_uuid = user.uuid

    # Validate request
    if not redesign_request.style_preset and not redesign_request.custom_prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("style_or_prompt_required", locale),
        )

    try:
        start_time = time.time()

        # Build prompt
        gemini_service = get_gemini_service()

        if redesign_request.style_preset:
            prompt = gemini_service.create_detailed_prompt(
                base_style=redesign_request.style_preset,
                room_type=redesign_request.room_type or photo.room_type or "living room",
                additional_details=redesign_request.additional_details,
            )
        else:
            prompt = redesign_request.custom_prompt

        # Handle multi-turn if parent redesign specified
        conversation_history = None
        is_multi_turn = False
        input_image_data = None

        if redesign_request.parent_redesign_id:
            parent = (
                db.query(PhotoRedesign)
                .filter(
                    PhotoRedesign.id == redesign_request.parent_redesign_id,
                    PhotoRedesign.photo_id == photo_id,
                )
                .first()
            )

            if parent:
                conversation_history = parent.conversation_history or []
                is_multi_turn = True
                # Use the parent redesign's generated image as input
                try:
                    input_image_data = get_storage_service().get_file(
                        storage_key=parent.storage_key, bucket_name=parent.storage_bucket
                    )
                    logger.info(f"Using parent redesign {parent.id} image as input for iteration")
                except Exception as e:
                    logger.warning(
                        f"Failed to fetch parent redesign image, falling back to original: {e}"
                    )

        # Fall back to original photo if no parent image available
        if input_image_data is None:
            input_image_data = get_storage_service().get_file(
                storage_key=photo.storage_key, bucket_name=photo.storage_bucket
            )

        # Fetch reference images if provided
        reference_images_data = []
        reference_image_keys = redesign_request.reference_image_keys or []
        if reference_image_keys:
            if len(reference_image_keys) > 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Maximum 2 reference images allowed",
                )
            for ref_key in reference_image_keys:
                # Validate key belongs to this user (path prefix check)
                if not ref_key.startswith(f"{user_uuid}/references/"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Invalid reference image key",
                    )
                try:
                    ref_data = get_storage_service().get_file(
                        storage_key=ref_key, bucket_name="photos"
                    )
                    reference_images_data.append(ref_data)
                except Exception as e:
                    logger.warning(f"Failed to fetch reference image {ref_key}: {e}")

        # Generate redesign
        logger.info(f"Generating redesign for photo {photo_id} with prompt: {prompt[:100]}...")

        result = await gemini_service.redesign_apartment(
            image_data=input_image_data,
            prompt=prompt,
            aspect_ratio=redesign_request.aspect_ratio,
            conversation_history=conversation_history,
            reference_images=reference_images_data if reference_images_data else None,
        )

        if not result.get("success"):
            raise Exception(result.get("error", "Unknown error"))

        generation_time_ms = int((time.time() - start_time) * 1000)

        redesign_uuid = str(uuid.uuid4())
        # Upload generated image with nested path: {user_uuid}/photos/{photo_uuid}/redesigns/{redesign_uuid}/{filename}
        generated_filename = f"redesign_{redesign_uuid}.png"
        storage_key = (
            f"{user_uuid}/photos/{photo.uuid}/redesigns/{redesign_uuid}/{generated_filename}"
        )
        get_storage_service().upload_file(
            file_data=result["image_data"], filename=storage_key, bucket_name="photos"
        )

        # Update conversation history for multi-turn
        new_conversation_history = conversation_history or []
        user_turn: Dict[str, Any] = {"role": "user", "content": prompt}
        if reference_image_keys:
            user_turn["reference_image_keys"] = reference_image_keys
        new_conversation_history.append(user_turn)
        new_conversation_history.append(
            {
                "role": "model",
                "image": result["image_data"].hex(),  # Store as hex for JSON compatibility
            }
        )

        # Create database record
        redesign = PhotoRedesign(
            photo_id=photo_id,
            redesign_uuid=redesign_uuid,
            storage_key=storage_key,
            storage_bucket="photos",
            file_size=len(result["image_data"]),
            style_preset=redesign_request.style_preset,
            prompt=prompt,
            aspect_ratio=redesign_request.aspect_ratio,
            model_used=result["model"],
            conversation_history=new_conversation_history,
            is_multi_turn=is_multi_turn,
            parent_redesign_id=redesign_request.parent_redesign_id,
            generation_time_ms=generation_time_ms,
        )

        db.add(redesign)

        # Increment user's redesigns generated count
        user.redesigns_generated_count = (user.redesigns_generated_count or 0) + 1

        db.commit()
        db.refresh(redesign)

        # Generate presigned URL
        presigned_url = get_storage_service().get_presigned_url(
            storage_key=redesign.storage_key, bucket_name="photos", expiry=timedelta(hours=1)
        )

        logger.info(
            f"✅ Redesign {redesign.id} created for photo {photo_id} in {generation_time_ms}ms"
        )

        # Generate presigned URLs for reference images
        ref_urls = None
        if reference_image_keys:
            ref_urls = []
            for ref_key in reference_image_keys:
                ref_url = get_storage_service().get_presigned_url(
                    storage_key=ref_key, bucket_name="photos", expiry=timedelta(hours=1)
                )
                ref_urls.append(ref_url)

        return RedesignResponse(
            id=redesign.id,
            redesign_uuid=redesign.redesign_uuid,
            photo_id=redesign.photo_id,
            storage_key=redesign.storage_key,
            storage_bucket=redesign.storage_bucket,
            file_size=redesign.file_size,
            style_preset=redesign.style_preset,
            prompt=redesign.prompt,
            aspect_ratio=redesign.aspect_ratio,
            model_used=redesign.model_used,
            conversation_history=redesign.conversation_history,
            is_multi_turn=redesign.is_multi_turn,
            parent_redesign_id=redesign.parent_redesign_id,
            created_at=redesign.created_at,
            generation_time_ms=redesign.generation_time_ms,
            is_favorite=redesign.is_favorite,
            user_rating=redesign.user_rating,
            presigned_url=presigned_url,
            reference_image_urls=ref_urls,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating redesign: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=translate("failed_generate_redesign", locale, error=str(e)),
        )


@router.get("/", response_model=PhotoListResponse)
async def list_photos(
    request: Request,
    property_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    List all photos for the current user.

    Args:
        property_id: Optional filter by property

    Returns:
        List of photos with presigned URLs
    """
    get_local(request)

    query = db.query(Photo).filter(Photo.user_id == int(current_user))

    if property_id:
        query = query.filter(Photo.property_id == property_id)

    photos = query.order_by(Photo.uploaded_at.desc()).all()

    # Single grouped query for all redesign counts (fixes N+1)
    photo_ids = [photo.id for photo in photos]
    redesign_counts: dict[int, int] = {}
    if photo_ids:
        rows = (
            db.query(PhotoRedesign.photo_id, func.count(PhotoRedesign.id))
            .filter(PhotoRedesign.photo_id.in_(photo_ids))
            .group_by(PhotoRedesign.photo_id)
            .all()
        )
        redesign_counts = {photo_id: cnt for photo_id, cnt in rows}

    # Batch-fetch explicitly promoted redesigns (no fallback — only shown if user promoted)
    explicit_promoted: dict[int, PhotoRedesign] = {}
    explicit_ids = [p.promoted_redesign_id for p in photos if p.promoted_redesign_id]
    if explicit_ids:
        promoted_rows = db.query(PhotoRedesign).filter(PhotoRedesign.id.in_(explicit_ids)).all()
        for r in promoted_rows:
            explicit_promoted[int(r.id)] = r

    # Build response with presigned URLs, redesign counts, and promoted redesign
    storage = get_storage_service()
    photo_responses = []
    for photo in photos:
        presigned_url = storage.get_presigned_url(
            storage_key=photo.storage_key,
            bucket_name=photo.storage_bucket,
            expiry=timedelta(hours=1),
        )

        # Only include promoted redesign if explicitly set
        promoted_redesign_data = None
        if photo.promoted_redesign_id and int(photo.promoted_redesign_id) in explicit_promoted:
            redesign_obj = explicit_promoted[int(photo.promoted_redesign_id)]
            redesign_url = storage.get_presigned_url(
                storage_key=redesign_obj.storage_key,
                bucket_name=redesign_obj.storage_bucket,
                expiry=timedelta(hours=1),
            )
            promoted_redesign_data = PromotedRedesignResponse(
                id=redesign_obj.id,
                redesign_uuid=redesign_obj.redesign_uuid,
                style_preset=redesign_obj.style_preset,
                prompt=redesign_obj.prompt,
                presigned_url=redesign_url,
                created_at=redesign_obj.created_at,
            )

        photo_responses.append(
            PhotoResponse(
                id=photo.id,
                uuid=photo.uuid,
                user_id=photo.user_id,
                property_id=photo.property_id,
                filename=photo.filename,
                storage_key=photo.storage_key,
                storage_bucket=photo.storage_bucket,
                file_size=photo.file_size,
                mime_type=photo.mime_type,
                room_type=photo.room_type,
                description=photo.description,
                uploaded_at=photo.uploaded_at,
                presigned_url=presigned_url,
                redesign_count=redesign_counts.get(photo.id, 0),
                promoted_redesign=promoted_redesign_data,
            )
        )

    return PhotoListResponse(photos=photo_responses, total=len(photo_responses))


@router.get("/{photo_id}/redesigns", response_model=RedesignListResponse)
async def list_redesigns(
    photo_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    List all redesigns for a specific photo.

    Args:
        photo_id: Photo ID

    Returns:
        List of redesigns with presigned URLs
    """
    locale = get_local(request)

    # Verify photo ownership
    photo = db.query(Photo).filter(Photo.id == photo_id, Photo.user_id == int(current_user)).first()

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("photo_not_found", locale)
        )

    redesigns = (
        db.query(PhotoRedesign)
        .filter(PhotoRedesign.photo_id == photo_id)
        .order_by(PhotoRedesign.created_at.desc())
        .all()
    )

    # Build response with presigned URLs
    storage = get_storage_service()
    redesign_responses = []
    for redesign in redesigns:
        presigned_url = storage.get_presigned_url(
            storage_key=redesign.storage_key,
            bucket_name=redesign.storage_bucket,
            expiry=timedelta(hours=1),
        )

        # Extract reference image keys from last user turn in conversation history
        ref_urls = None
        history: List[Dict[str, Any]] = redesign.conversation_history or []
        # Find the last user turn that has reference_image_keys
        for turn in reversed(history):
            if turn.get("role") == "user" and turn.get("reference_image_keys"):
                ref_keys = turn["reference_image_keys"]
                ref_urls = []
                for ref_key in ref_keys:
                    ref_url = storage.get_presigned_url(
                        storage_key=ref_key,
                        bucket_name="photos",
                        expiry=timedelta(hours=1),
                    )
                    ref_urls.append(ref_url)
                break

        redesign_responses.append(
            RedesignResponse(
                id=redesign.id,
                redesign_uuid=redesign.redesign_uuid,
                photo_id=redesign.photo_id,
                storage_key=redesign.storage_key,
                storage_bucket=redesign.storage_bucket,
                file_size=redesign.file_size,
                style_preset=redesign.style_preset,
                prompt=redesign.prompt,
                aspect_ratio=redesign.aspect_ratio,
                model_used=redesign.model_used,
                conversation_history=redesign.conversation_history,
                is_multi_turn=redesign.is_multi_turn,
                parent_redesign_id=redesign.parent_redesign_id,
                created_at=redesign.created_at,
                generation_time_ms=redesign.generation_time_ms,
                is_favorite=redesign.is_favorite,
                user_rating=redesign.user_rating,
                presigned_url=presigned_url,
                reference_image_urls=ref_urls,
            )
        )

    return RedesignListResponse(redesigns=redesign_responses, total=len(redesign_responses))


@router.delete("/{photo_id}")
async def delete_photo(
    photo_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Delete a photo and all its redesigns.

    Args:
        photo_id: Photo ID

    Returns:
        Success message
    """
    locale = get_local(request)

    photo = db.query(Photo).filter(Photo.id == photo_id, Photo.user_id == int(current_user)).first()

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("photo_not_found", locale)
        )

    try:
        # Delete from storage (original photo)
        get_storage_service().delete_file(
            object_name=photo.storage_key, bucket_name=photo.storage_bucket
        )

        # Delete all redesigns from storage
        redesigns = db.query(PhotoRedesign).filter(PhotoRedesign.photo_id == photo_id).all()

        for redesign in redesigns:
            get_storage_service().delete_file(
                object_name=redesign.storage_key, bucket_name=redesign.storage_bucket
            )

        # Database cascade will delete redesigns
        db.delete(photo)
        db.commit()

        logger.info(f"✅ Photo {photo_id} and {len(redesigns)} redesigns deleted")

        return {"message": f"Photo and {len(redesigns)} redesigns deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting photo: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=translate("failed_delete_photo", locale, error=str(e)),
        )


@router.patch("/{photo_id}", response_model=PhotoResponse)
async def update_photo(
    photo_id: int,
    update: PhotoUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Update photo metadata.
    """
    locale = get_local(request)

    photo = db.query(Photo).filter(Photo.id == photo_id, Photo.user_id == int(current_user)).first()

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("photo_not_found", locale)
        )

    if update.room_type is not None:
        photo.room_type = update.room_type
    if update.filename is not None:
        photo.filename = update.filename

    db.commit()
    db.refresh(photo)

    presigned_url = get_storage_service().get_presigned_url(
        storage_key=photo.storage_key, bucket_name=photo.storage_bucket, expiry=timedelta(hours=1)
    )

    redesign_count = db.query(PhotoRedesign).filter(PhotoRedesign.photo_id == photo.id).count()

    return PhotoResponse(
        id=photo.id,
        uuid=photo.uuid,
        user_id=photo.user_id,
        property_id=photo.property_id,
        filename=photo.filename,
        storage_key=photo.storage_key,
        storage_bucket=photo.storage_bucket,
        file_size=photo.file_size,
        mime_type=photo.mime_type,
        room_type=photo.room_type,
        description=photo.description,
        uploaded_at=photo.uploaded_at,
        presigned_url=presigned_url,
        redesign_count=redesign_count,
    )


@router.patch("/{photo_id}/promote/{redesign_id}")
async def promote_redesign(
    photo_id: int,
    redesign_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Set the promoted redesign for a photo."""
    locale = get_local(request)

    photo = db.query(Photo).filter(Photo.id == photo_id, Photo.user_id == int(current_user)).first()
    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("photo_not_found", locale)
        )

    redesign = (
        db.query(PhotoRedesign)
        .filter(PhotoRedesign.id == redesign_id, PhotoRedesign.photo_id == photo_id)
        .first()
    )
    if not redesign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("redesign_not_found", locale)
        )

    photo.promoted_redesign_id = redesign_id
    db.commit()

    logger.info(f"✅ Photo {photo_id} promoted redesign set to {redesign_id}")
    return {"message": "Redesign promoted", "photo_id": photo_id, "redesign_id": redesign_id}


@router.delete("/{photo_id}/promote")
async def demote_redesign(
    photo_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Clear the promoted redesign for a photo (revert to latest default)."""
    locale = get_local(request)

    photo = db.query(Photo).filter(Photo.id == photo_id, Photo.user_id == int(current_user)).first()
    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("photo_not_found", locale)
        )

    photo.promoted_redesign_id = None
    db.commit()

    logger.info(f"✅ Photo {photo_id} promoted redesign cleared")
    return {"message": "Redesign demoted", "photo_id": photo_id}
