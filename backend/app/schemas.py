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
    style_context: str = ""
    reference_images: list[str] = []
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

class SubtitleStyle(BaseModel):
    font_name: str = "PingFang SC"
    font_size: int = Field(default=20, ge=10, le=60)
    outline_width: int = Field(default=2, ge=0, le=5)
    margin_bottom: int = Field(default=40, ge=0, le=200)


class ComposeRequest(BaseModel):
    project_id: str
    include_audio: bool = True
    include_subtitles: bool = False
    subtitle_style: Optional[SubtitleStyle] = None


class ComposeResponse(BaseModel):
    output_video_url: str
    duration: float
    subtitle_url: str = ""


# ============ 数字资产：角色 ============

class CharacterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    appearance_prompt: str = ""
    appearance_prompt_zh: str = ""
    reference_images: list[str] = []
    voice_type: str = ""
    voice_config: dict = {}
    tags: list[str] = []
    is_global: bool = True
    source_project_id: str = ""


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    appearance_prompt: Optional[str] = None
    appearance_prompt_zh: Optional[str] = None
    reference_images: Optional[list[str]] = None
    voice_type: Optional[str] = None
    voice_config: Optional[dict] = None
    tags: Optional[list[str]] = None
    is_global: Optional[bool] = None


class CharacterResponse(BaseModel):
    id: str
    name: str
    description: str
    appearance_prompt: str
    appearance_prompt_zh: str
    reference_images: list[str]
    voice_type: str
    voice_config: dict
    tags: list[str]
    is_global: bool
    source_project_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============ 数字资产：场景 ============

class SceneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    environment_prompt: str = ""
    environment_prompt_zh: str = ""
    reference_images: list[str] = []
    mood: str = ""
    lighting: str = ""
    tags: list[str] = []
    is_global: bool = True
    source_project_id: str = ""


class SceneUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    environment_prompt: Optional[str] = None
    environment_prompt_zh: Optional[str] = None
    reference_images: Optional[list[str]] = None
    mood: Optional[str] = None
    lighting: Optional[str] = None
    tags: Optional[list[str]] = None
    is_global: Optional[bool] = None


class SceneResponse(BaseModel):
    id: str
    name: str
    description: str
    environment_prompt: str
    environment_prompt_zh: str
    reference_images: list[str]
    mood: str
    lighting: str
    tags: list[str]
    is_global: bool
    source_project_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============ 项目-角色/场景关联 ============

class ProjectCharacterCreate(BaseModel):
    character_id: str
    custom_description: str = ""
    custom_appearance_prompt: str = ""
    custom_voice_type: str = ""
    custom_voice_config: dict = {}


class ProjectCharacterResponse(BaseModel):
    id: str
    project_id: str
    character_id: str
    custom_description: str
    custom_appearance_prompt: str
    custom_voice_type: str
    custom_voice_config: dict
    created_at: datetime
    character: CharacterResponse

    model_config = {"from_attributes": True}


class ProjectSceneCreate(BaseModel):
    scene_id: str
    custom_description: str = ""
    custom_environment_prompt: str = ""


class ProjectSceneResponse(BaseModel):
    id: str
    project_id: str
    scene_id: str
    custom_description: str
    custom_environment_prompt: str
    created_at: datetime
    scene: SceneResponse

    model_config = {"from_attributes": True}


# ============ AI 图片识别请求 ============

class ImageRecognizeRequest(BaseModel):
    image_url: str = Field(..., min_length=1)
    auto_create: bool = True  # 是否自动创建识别到的角色和场景


class PromoteToGlobalRequest(BaseModel):
    """将项目级角色/场景升级为全局"""
    name: Optional[str] = None  # 可重命名
