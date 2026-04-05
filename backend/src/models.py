from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class SceneStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    ANALYZING = "analyzing"
    SCREENPLAY_REVIEW = "screenplay_review"
    APPROVED = "approved"
    PRODUCING = "producing"
    ASSEMBLING = "assembling"
    COMPLETE = "complete"
    PUBLISHED = "published"
    FAILED = "failed"


class JobStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    WRITING = "writing"
    AWAITING_APPROVAL = "awaiting_approval"
    PRODUCING = "producing"
    ASSEMBLING = "assembling"
    COMPLETE = "complete"
    FAILED = "failed"


# --- Request models ---

class SceneCreate(BaseModel):
    title: str = "Untitled Scene"
    backstory: Optional[str] = None
    director_name: str = "Jackson"
    movie_style: str = "cinematic"


class SceneUpdate(BaseModel):
    title: Optional[str] = None
    backstory: Optional[str] = None
    director_name: Optional[str] = None
    movie_style: Optional[str] = None
    music_mood: Optional[str] = None


class MediaRegister(BaseModel):
    file_url: str
    file_type: str  # 'photo' or 'video'
    file_name: Optional[str] = None
    file_size_bytes: Optional[int] = None
    sort_order: int = 0
    source: str = "upload"


class MediaReorder(BaseModel):
    media_ids: list[str]  # ordered list of media UUIDs


# --- Response models ---

class SceneResponse(BaseModel):
    id: str
    user_id: str
    title: str
    backstory: Optional[str] = None
    status: str
    director_name: Optional[str] = None
    movie_style: Optional[str] = None
    music_mood: Optional[str] = None
    scene_bible: Optional[dict] = None
    screenplay: Optional[dict] = None
    screenplay_feedback: Optional[str] = None
    screenplay_version: int = 0
    voiceover_url: Optional[str] = None
    final_video_url: Optional[str] = None
    final_video_duration_seconds: Optional[int] = None
    published_platforms: Optional[list] = None
    created_at: str
    updated_at: str
    media: Optional[list] = None


class MediaResponse(BaseModel):
    id: str
    scene_id: str
    file_url: str
    file_type: str
    file_name: Optional[str] = None
    file_size_bytes: Optional[int] = None
    sort_order: int = 0
    source: str = "upload"
    created_at: str
