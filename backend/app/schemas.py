"""Pydantic 请求/响应模型"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ============ Project ============

class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    theme: str = ""
    scene_type: str = "entertainment"
    target_duration: int = Field(default=30, ge=5, le=300)
    aspect_ratio: str = "16:9"
    resolution: str = "720p"


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    theme: Optional[str] = None
    scene_type: Optional[str] = None
    target_duration: Optional[int] = None
    aspect_ratio: Optional[str] = None
    resolution: Optional[str] = None
    script_content: Optional[str] = None
    script_json: Optional[dict] = None
    status: Optional[str] = None


class ShotResponse(BaseModel):
    id: str
    project_id: str
    sequence: int
    description: str
    dialogue: str
    duration: int
    status: str
    video_task_id: str
    video_url: str
    first_frame_url: str
    last_frame_url: str
    audio_url: str
    audio_duration: float
    camera_fixed: str
    seed: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectResponse(BaseModel):
    id: str
    title: str
    description: str
    theme: str
    scene_type: str
    status: str
    target_duration: int
    aspect_ratio: str
    resolution: str
    script_content: str
    script_json: dict
    output_video_url: str
    output_audio_url: str
    created_at: datetime
    updated_at: datetime
    shots: list[ShotResponse] = []

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    id: str
    title: str
    description: str
    scene_type: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============ Shot ============

class ShotCreate(BaseModel):
    description: str = ""
    dialogue: str = ""
    duration: int = Field(default=5, ge=2, le=12)
    first_frame_url: Optional[str] = None
    camera_fixed: str = "false"


class ShotUpdate(BaseModel):
    description: Optional[str] = None
    dialogue: Optional[str] = None
    duration: Optional[int] = None
    first_frame_url: Optional[str] = None
    camera_fixed: Optional[str] = None
    status: Optional[str] = None


# ============ Script Generation ============

class ScriptGenerateRequest(BaseModel):
    theme: str = Field(..., min_length=1)
    scene_type: str = "entertainment"
    target_duration: int = Field(default=30, ge=5, le=300)
    additional_context: str = ""
    image_urls: list[str] = []


class ScriptGenerateResponse(BaseModel):
    script_content: str
    shots: list[dict]
    characters: list[str]
    objects: list[str]


# ============ Video Generation ============

class VideoGenerateRequest(BaseModel):
    shot_id: str
    prompt: Optional[str] = None
    first_frame_url: Optional[str] = None
    last_frame_url: Optional[str] = None
    duration: int = 5
    ratio: str = "16:9"
    resolution: str = "720p"
    generate_audio: bool = True


class VideoGenerateResponse(BaseModel):
    task_id: str
    status: str


class VideoTaskStatusResponse(BaseModel):
    task_id: str
    status: str
    video_url: Optional[str] = None
    last_frame_url: Optional[str] = None
    error: Optional[str] = None


# ============ TTS ============

class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice_type: str = "BV012_streaming"
    speed_ratio: float = Field(default=1.0, ge=0.2, le=3.0)
    volume_ratio: float = Field(default=1.0, ge=0.1, le=3.0)
    pitch_ratio: float = Field(default=1.0, ge=0.1, le=3.0)
    encoding: str = "mp3"


class TTSResponse(BaseModel):
    audio_url: str
    duration: float
    reqid: str


# ============ Compose ============

class ComposeRequest(BaseModel):
    project_id: str
    include_audio: bool = True


class ComposeResponse(BaseModel):
    output_video_url: str
    duration: float
