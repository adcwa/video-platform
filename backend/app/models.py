"""数据库模型定义"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, JSON, ForeignKey, Enum as SAEnum
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

    # 最终输出
    output_video_url = Column(String(500), default="")
    output_audio_url = Column(String(500), default="")

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # 关联
    shots = relationship("Shot", back_populates="project", cascade="all, delete-orphan",
                         order_by="Shot.sequence")
    assets = relationship("Asset", back_populates="project", cascade="all, delete-orphan")


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
