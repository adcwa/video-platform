"""数据库模型定义"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from backend.app.database import Base
import enum


def generate_uuid():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    SCRIPTING = "scripting"
    GENERATING = "generating"
    COMPOSING = "composing"
    COMPLETED = "completed"
    FAILED = "failed"


class SceneType(str, enum.Enum):
    ENTERTAINMENT = "entertainment"  # 娱乐发布
    RESEARCH = "research"            # 科研研究


class ShotStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class Project(Base):
    """视频项目"""
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    theme = Column(Text, default="")  # 输入主题
    scene_type = Column(String(50), default=SceneType.ENTERTAINMENT.value)
    status = Column(String(50), default=ProjectStatus.DRAFT.value)

    # 视频参数
    target_duration = Column(Integer, default=30)  # 目标时长（秒）
    aspect_ratio = Column(String(20), default="16:9")
    resolution = Column(String(10), default="720p")

    # AI生成的脚本
    script_content = Column(Text, default="")
    script_json = Column(JSON, default=dict)

    # 图片分析获得的风格/背景上下文（注入每个镜头 prompt）
    style_context = Column(Text, default="")
    # 用户上传的参考图片URL列表（JSON数组）
    reference_images = Column(JSON, default=list)

    # 最终输出
    output_video_url = Column(String(500), default="")
    output_audio_url = Column(String(500), default="")

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # 关联
    shots = relationship("Shot", back_populates="project", cascade="all, delete-orphan",
                         order_by="Shot.sequence")
    assets = relationship("Asset", back_populates="project", cascade="all, delete-orphan")
    project_characters = relationship("ProjectCharacter", back_populates="project", cascade="all, delete-orphan")
    project_scenes = relationship("ProjectScene", back_populates="project", cascade="all, delete-orphan")


class Shot(Base):
    """视频分镜/镜头"""
    __tablename__ = "shots"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    sequence = Column(Integer, nullable=False)  # 顺序
    description = Column(Text, default="")      # 镜头描述/提示词
    dialogue = Column(Text, default="")         # 对白文本
    duration = Column(Integer, default=5)       # 镜头时长（秒）
    status = Column(String(50), default=ShotStatus.PENDING.value)

    # 视频生成
    video_task_id = Column(String(200), default="")   # Seedance 任务ID
    video_url = Column(String(500), default="")       # 生成的视频URL
    first_frame_url = Column(String(500), default="")  # 首帧图片
    last_frame_url = Column(String(500), default="")   # 尾帧图片

    # 语音合成
    audio_url = Column(String(500), default="")
    audio_duration = Column(Float, default=0)

    # 参数
    camera_fixed = Column(String(10), default="false")
    seed = Column(Integer, default=-1)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # 关联
    project = relationship("Project", back_populates="shots")


class Asset(Base):
    """素材资源（图片、视频等）"""
    __tablename__ = "assets"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    asset_type = Column(String(50), nullable=False)  # image, video, audio
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_url = Column(String(500), default="")
    mime_type = Column(String(100), default="")
    file_size = Column(Integer, default=0)

    created_at = Column(DateTime, default=utcnow)

    # 关联
    project = relationship("Project", back_populates="assets")


# ============ 数字资产：全局角色 & 场景 ============

class Character(Base):
    """全局角色 — 可复用的数字资产"""
    __tablename__ = "characters"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)              # 角色名称
    description = Column(Text, default="")                  # 角色简介
    appearance_prompt = Column(Text, default="")            # 外观提示词（英文，用于 Seedance）
    appearance_prompt_zh = Column(Text, default="")         # 外观提示词（中文，用于脚本生成）
    reference_images = Column(JSON, default=list)           # 参考图片URL列表
    voice_type = Column(String(100), default="")            # 默认语音类型
    voice_config = Column(JSON, default=dict)               # 语音参数 {speed_ratio, volume_ratio, pitch_ratio}
    tags = Column(JSON, default=list)                       # 标签
    is_global = Column(Boolean, default=True)               # 是否全局（True=全局资产, False=项目级）
    source_project_id = Column(String, default="")          # 来源项目ID（如从项目升级而来）

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # 关联
    project_characters = relationship("ProjectCharacter", back_populates="character", cascade="all, delete-orphan")


class Scene(Base):
    """全局场景 — 可复用的数字资产"""
    __tablename__ = "scenes"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)              # 场景名称
    description = Column(Text, default="")                  # 场景简介
    environment_prompt = Column(Text, default="")           # 环境提示词（英文，用于 Seedance）
    environment_prompt_zh = Column(Text, default="")        # 环境提示词（中文，用于脚本生成）
    reference_images = Column(JSON, default=list)           # 参考图片URL列表
    mood = Column(String(100), default="")                  # 氛围/情绪
    lighting = Column(String(100), default="")              # 光照风格
    tags = Column(JSON, default=list)                       # 标签
    is_global = Column(Boolean, default=True)               # 是否全局
    source_project_id = Column(String, default="")          # 来源项目ID

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # 关联
    project_scenes = relationship("ProjectScene", back_populates="scene", cascade="all, delete-orphan")


class ProjectCharacter(Base):
    """项目-角色关联 — 支持项目级覆盖"""
    __tablename__ = "project_characters"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    character_id = Column(String, ForeignKey("characters.id"), nullable=False)
    custom_description = Column(Text, default="")           # 项目级自定义描述（覆盖全局）
    custom_appearance_prompt = Column(Text, default="")     # 项目级自定义外观提示词
    custom_voice_type = Column(String(100), default="")     # 项目级自定义语音
    custom_voice_config = Column(JSON, default=dict)        # 项目级自定义语音参数

    created_at = Column(DateTime, default=utcnow)

    # 关联
    project = relationship("Project", back_populates="project_characters")
    character = relationship("Character", back_populates="project_characters")


class ProjectScene(Base):
    """项目-场景关联 — 支持项目级覆盖"""
    __tablename__ = "project_scenes"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    scene_id = Column(String, ForeignKey("scenes.id"), nullable=False)
    custom_description = Column(Text, default="")           # 项目级自定义描述
    custom_environment_prompt = Column(Text, default="")    # 项目级自定义环境提示词

    created_at = Column(DateTime, default=utcnow)

    # 关联
    project = relationship("Project", back_populates="project_scenes")
    scene = relationship("Scene", back_populates="project_scenes")
