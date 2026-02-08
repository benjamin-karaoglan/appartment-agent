"""
Pydantic schemas for Photo and PhotoRedesign models.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PhotoUpload(BaseModel):
    """Schema for uploading a new photo."""

    property_id: Optional[int] = Field(None, description="Associated property ID")
    room_type: Optional[str] = Field(
        None, description="Type of room (living_room, bedroom, kitchen, etc.)"
    )
    description: Optional[str] = Field(None, description="Optional description of the photo")


class PhotoUpdate(BaseModel):
    """Schema for updating photo metadata."""

    room_type: Optional[str] = Field(
        None, description="Type of room (living_room, bedroom, kitchen, etc.)"
    )
    filename: Optional[str] = Field(None, description="Display name for the photo")


class PromotedRedesignResponse(BaseModel):
    """Schema for the promoted redesign shown on property overview."""

    id: int
    redesign_uuid: str
    style_preset: Optional[str] = None
    prompt: Optional[str] = None
    presigned_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PhotoResponse(BaseModel):
    """Schema for photo response."""

    id: int
    uuid: Optional[str] = None
    user_id: int
    property_id: Optional[int]
    filename: str
    storage_key: str
    storage_bucket: str
    file_size: Optional[int]
    mime_type: Optional[str]
    room_type: Optional[str]
    description: Optional[str]
    uploaded_at: datetime
    presigned_url: Optional[str] = Field(None, description="Temporary URL to access the photo")
    redesign_count: int = Field(0, description="Number of redesigns created from this photo")
    promoted_redesign: Optional[PromotedRedesignResponse] = None

    class Config:
        from_attributes = True


class RedesignRequest(BaseModel):
    """Schema for requesting a photo redesign."""

    style_preset: Optional[str] = Field(
        None, description="Preset style: modern_norwegian, minimalist_scandinavian, or cozy_hygge"
    )
    custom_prompt: Optional[str] = Field(
        None, description="Custom redesign prompt (used if style_preset not provided)"
    )
    room_type: str = Field("living room", description="Type of room being redesigned")
    additional_details: Optional[str] = Field(None, description="Additional customization details")
    aspect_ratio: str = Field(
        "16:9", description="Image aspect ratio: 1:1, 16:9, 9:16, 4:3, or 3:4"
    )
    parent_redesign_id: Optional[int] = Field(
        None, description="ID of parent redesign for multi-turn iteration"
    )
    reference_image_keys: Optional[List[str]] = Field(
        None, description="Storage keys of reference/inspiration images (max 2)"
    )


class ReferenceImageUploadResponse(BaseModel):
    """Schema for reference image upload response."""

    storage_key: str
    presigned_url: str
    file_size: int
    mime_type: str


class RedesignResponse(BaseModel):
    """Schema for redesign response."""

    id: int
    redesign_uuid: str
    photo_id: int
    storage_key: str
    storage_bucket: str
    file_size: Optional[int]
    style_preset: Optional[str]
    prompt: str
    aspect_ratio: str
    model_used: str
    conversation_history: Optional[List[Dict[str, Any]]]
    is_multi_turn: bool
    parent_redesign_id: Optional[int]
    created_at: datetime
    generation_time_ms: Optional[int]
    is_favorite: bool
    user_rating: Optional[int]
    presigned_url: Optional[str] = Field(
        None, description="Temporary URL to access the redesigned image"
    )
    reference_image_urls: Optional[List[str]] = Field(
        None, description="Presigned URLs for reference images used in this redesign"
    )

    class Config:
        from_attributes = True


class PhotoListResponse(BaseModel):
    """Schema for list of photos."""

    photos: List[PhotoResponse]
    total: int


class RedesignListResponse(BaseModel):
    """Schema for list of redesigns."""

    redesigns: List[RedesignResponse]
    total: int


class StylePresetsResponse(BaseModel):
    """Schema for available style presets."""

    presets: List[Dict[str, str]] = Field(
        default=[
            {
                "id": "modern_norwegian",
                "name": "Modern Norwegian",
                "description": "Clean lines, natural wood tones, Nordic light, minimalist elegance",
                "prompt_template": (
                    "You are an interior architect.\n"
                    "Redesign this apartment {room_type} in a modern Norwegian style:\n"
                    "- Keep room geometry and windows unchanged\n"
                    "- Use clean lines with warm, natural wood tones (light oak or birch)\n"
                    "- Flooring: warm oak wood\n"
                    "- Walls: white and cream with accents of deep forest green, midnight blue, or charcoal gray\n"
                    "- Add cozy textiles like wool throws and linen cushions\n"
                    "- Lighting: warm and inviting with designer pendant lights or floor lamps\n"
                    "- Include minimal but impactful decor: a single statement plant, ceramic vases, or contemporary Norwegian art\n"
                    "- The overall atmosphere should feel spacious, airy, and connected to nature while maintaining sophisticated modern elegance\n"
                    "Return only the edited image."
                ),
            },
            {
                "id": "minimalist_scandinavian",
                "name": "Minimalist Scandinavian",
                "description": "Lagom philosophy, monochromatic whites and grays, functional design",
                "prompt_template": (
                    "You are an interior architect.\n"
                    "Redesign this apartment {room_type} as a minimalist Scandinavian sanctuary:\n"
                    "- Keep room geometry and windows unchanged\n"
                    "- Use monochromatic white and light gray base with pale wood accents\n"
                    "- Furniture should be functional, sculptural pieces with clean geometric forms\n"
                    "- Include subtle warmth through natural materials: jute rug, linen textiles\n"
                    "- Add one or two green plants in simple ceramic pots\n"
                    "- The space should have generous negative space, emphasizing openness and tranquility\n"
                    "- Every object serves a purpose while contributing to the overall aesthetic harmony\n"
                    "- Mood: calm, uncluttered, and effortlessly sophisticated\n"
                    "Return only the edited image."
                ),
            },
            {
                "id": "cozy_hygge",
                "name": "Cozy Hygge",
                "description": "Warm embrace, soft textiles, ambient lighting, intimate comfort",
                "prompt_template": (
                    "You are an interior architect.\n"
                    "Transform this apartment {room_type} into the ultimate hygge retreat:\n"
                    "- Keep room geometry and windows unchanged\n"
                    "- Feature a plush, oversized sofa with layers of soft blankets and cushions in warm neutrals (creams, beiges, soft grays)\n"
                    "- Add warm, ambient lighting from multiple sources: candles clustered on surfaces, vintage-style floor lamp with warm LED bulbs\n"
                    "- Include natural wood elements with a weathered, lived-in quality\n"
                    "- A chunky knit throw drapes over a chair\n"
                    "- Color palette: warm and inviting - caramel, terracotta, dusty rose, and cream\n"
                    "- Add books stacked casually, a steaming mug on a side table\n"
                    "- The atmosphere should evoke safety, comfort, and intimate togetherness\n"
                    "- Lighting: cozy warm evening\n"
                    "Return only the edited image."
                ),
            },
            {
                "id": "fancy_dark_modern",
                "name": "Fancy Dark Modern",
                "description": "Dark wood, luxurious lighting, ultra-modern elegance, full redesign",
                "prompt_template": (
                    "You are an interior architect.\n"
                    "Completely redesign this apartment {room_type} in an ultra-modern luxurious style:\n"
                    "- Keep room geometry and windows unchanged\n"
                    "- Redesign every element of the room: furniture, flooring, walls, ceiling, lighting, and decor\n"
                    "- Use rich, dark wood throughout — walnut, smoked oak, or dark ebony for floors, wall panels, and furniture\n"
                    "- Lighting must feel luxurious: recessed LED strips along ceiling and floor edges, sculptural designer pendant lights, and warm accent spotlights highlighting textures\n"
                    "- Furniture: sleek contemporary pieces with dark leather, matte black metal, and brushed brass accents\n"
                    "- Walls: a mix of dark wood paneling, deep charcoal plaster, and subtle textured surfaces\n"
                    "- Add statement decor: oversized contemporary art, an architectural floor lamp, a marble-topped console\n"
                    "- The overall atmosphere should feel bold, sophisticated, and unmistakably high-end — like a modern luxury penthouse\n"
                    "Return only the edited image."
                ),
            },
        ]
    )
