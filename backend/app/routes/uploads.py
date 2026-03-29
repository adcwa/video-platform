"""文件上传路由"""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models import Project, Asset

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/uploads", tags=["文件上传"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff", "image/gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm", "video/avi"}
ALLOWED_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_VIDEO_TYPES


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    project_id: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
):
    """上传图片文件（首帧图片、参考图片等）"""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片格式: {file.content_type}。支持: jpeg, png, webp, bmp, tiff, gif",
        )

    max_size = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail=f"文件大小超过限制 ({settings.max_upload_size_mb}MB)")

    # 保存文件
    ext = Path(file.filename or "upload.png").suffix
    filename = f"{uuid.uuid4()}{ext}"
    upload_path = Path(settings.upload_dir) / "images" / filename
    upload_path.parent.mkdir(parents=True, exist_ok=True)

    with open(upload_path, "wb") as f:
        f.write(content)

    file_url = f"/files/uploads/images/{filename}"

    # 如果关联项目，保存到素材表
    if project_id:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            asset = Asset(
                project_id=project_id,
                asset_type="image",
                filename=file.filename or filename,
                file_path=str(upload_path),
                file_url=file_url,
                mime_type=file.content_type or "",
                file_size=len(content),
            )
            db.add(asset)
            await db.flush()

    logger.info(f"图片上传成功: {filename} ({len(content)} bytes)")
    return {
        "filename": filename,
        "file_url": file_url,
        "file_size": len(content),
        "mime_type": file.content_type,
    }


@router.post("/video")
async def upload_video(
    file: UploadFile = File(...),
    project_id: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
):
    """上传视频文件（背景视频等）"""
    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的视频格式: {file.content_type}。支持: mp4, quicktime, webm",
        )

    max_size = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail=f"文件大小超过限制 ({settings.max_upload_size_mb}MB)")

    ext = Path(file.filename or "upload.mp4").suffix
    filename = f"{uuid.uuid4()}{ext}"
    upload_path = Path(settings.upload_dir) / "videos" / filename
    upload_path.parent.mkdir(parents=True, exist_ok=True)

    with open(upload_path, "wb") as f:
        f.write(content)

    file_url = f"/files/uploads/videos/{filename}"

    if project_id:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            asset = Asset(
                project_id=project_id,
                asset_type="video",
                filename=file.filename or filename,
                file_path=str(upload_path),
                file_url=file_url,
                mime_type=file.content_type or "",
                file_size=len(content),
            )
            db.add(asset)
            await db.flush()

    logger.info(f"视频上传成功: {filename} ({len(content)} bytes)")
    return {
        "filename": filename,
        "file_url": file_url,
        "file_size": len(content),
        "mime_type": file.content_type,
    }


@router.get("/assets/{project_id}")
async def list_project_assets(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取项目的所有素材文件"""
    result = await db.execute(
        select(Asset).where(Asset.project_id == project_id).order_by(Asset.created_at.desc())
    )
    assets = result.scalars().all()
    return [
        {
            "id": a.id,
            "asset_type": a.asset_type,
            "filename": a.filename,
            "file_url": a.file_url,
            "file_size": a.file_size,
            "mime_type": a.mime_type,
            "created_at": a.created_at.isoformat() if a.created_at else "",
        }
        for a in assets
    ]
