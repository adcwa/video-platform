"""AI 服务路由 - 脚本生成、视频生成、语音合成"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.database import get_db
from backend.app.models import Project, Shot, ProjectStatus, ShotStatus
from backend.app.schemas import (
    ScriptGenerateRequest, ScriptGenerateResponse,
    VideoGenerateRequest, VideoGenerateResponse, VideoTaskStatusResponse,
    TTSRequest, TTSResponse,
    ComposeRequest, ComposeResponse,
    ShotCreate, ShotUpdate, ShotResponse,
)
from backend.app.services import doubao_service, seedance_service, tts_service, ffmpeg_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["AI服务"])


# ============ 脚本生成 ============

@router.post("/projects/{project_id}/generate-script", response_model=ScriptGenerateResponse)
async def generate_script(
    project_id: str,
    request: ScriptGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """为项目生成AI脚本"""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    try:
        # 调用豆包大模型生成脚本
        script_data = await doubao_service.generate_script(
            theme=request.theme or project.theme,
            scene_type=request.scene_type or project.scene_type,
            target_duration=request.target_duration or project.target_duration,
            additional_context=request.additional_context,
            image_urls=request.image_urls if request.image_urls else None,
        )

        # 更新项目
        project.script_content = str(script_data)
        project.script_json = script_data
        project.status = ProjectStatus.SCRIPTING.value
        if request.theme:
            project.theme = request.theme

        # 创建分镜
        # 先清除旧分镜
        for old_shot in await db.execute(
            select(Shot).where(Shot.project_id == project_id)
        ):
            for s in old_shot.scalars().all():
                await db.delete(s)

        shots_data = script_data.get("shots", [])
        for shot_info in shots_data:
            shot = Shot(
                project_id=project_id,
                sequence=shot_info.get("sequence", 0),
                description=shot_info.get("description", ""),
                dialogue=shot_info.get("dialogue", ""),
                duration=shot_info.get("duration", 5),
            )
            db.add(shot)

        await db.flush()

        return ScriptGenerateResponse(
            script_content=str(script_data),
            shots=shots_data,
            characters=script_data.get("characters", []),
            objects=script_data.get("objects", []),
        )

    except Exception as e:
        logger.error(f"脚本生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"脚本生成失败: {str(e)}")


# ============ 分镜管理 ============

@router.get("/projects/{project_id}/shots", response_model=list[ShotResponse])
async def list_shots(project_id: str, db: AsyncSession = Depends(get_db)):
    """获取项目所有分镜"""
    result = await db.execute(
        select(Shot).where(Shot.project_id == project_id).order_by(Shot.sequence)
    )
    return result.scalars().all()


@router.post("/projects/{project_id}/shots", response_model=ShotResponse)
async def create_shot(
    project_id: str,
    data: ShotCreate,
    db: AsyncSession = Depends(get_db),
):
    """手动添加分镜"""
    # 获取当前最大序号
    result = await db.execute(
        select(Shot)
        .where(Shot.project_id == project_id)
        .order_by(Shot.sequence.desc())
        .limit(1)
    )
    last_shot = result.scalar_one_or_none()
    next_seq = (last_shot.sequence + 1) if last_shot else 1

    shot = Shot(
        project_id=project_id,
        sequence=next_seq,
        description=data.description,
        dialogue=data.dialogue,
        duration=data.duration,
        first_frame_url=data.first_frame_url or "",
        camera_fixed=data.camera_fixed,
    )
    db.add(shot)
    await db.flush()
    await db.refresh(shot)
    return shot


@router.put("/shots/{shot_id}", response_model=ShotResponse)
async def update_shot(
    shot_id: str,
    data: ShotUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新分镜信息"""
    result = await db.execute(select(Shot).where(Shot.id == shot_id))
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="分镜不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(shot, key, value)

    await db.flush()
    await db.refresh(shot)
    return shot


@router.delete("/shots/{shot_id}")
async def delete_shot(shot_id: str, db: AsyncSession = Depends(get_db)):
    """删除分镜"""
    result = await db.execute(select(Shot).where(Shot.id == shot_id))
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="分镜不存在")

    await db.delete(shot)
    return {"message": "分镜已删除"}


# ============ 视频生成 ============

@router.post("/shots/{shot_id}/generate-video", response_model=VideoGenerateResponse)
async def generate_video(
    shot_id: str,
    request: VideoGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """为分镜生成视频"""
    result = await db.execute(select(Shot).where(Shot.id == shot_id))
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="分镜不存在")

    try:
        prompt = request.prompt or shot.description
        task_data = await seedance_service.create_video_task(
            prompt=prompt,
            first_frame_url=request.first_frame_url or shot.first_frame_url or None,
            last_frame_url=request.last_frame_url,
            duration=request.duration or shot.duration,
            ratio=request.ratio,
            resolution=request.resolution,
            generate_audio=request.generate_audio,
            camera_fixed=shot.camera_fixed == "true",
        )

        shot.video_task_id = task_data.get("id", "")
        shot.status = ShotStatus.GENERATING.value
        await db.flush()

        return VideoGenerateResponse(
            task_id=task_data.get("id", ""),
            status="submitted",
        )

    except Exception as e:
        logger.error(f"视频生成失败: {e}")
        shot.status = ShotStatus.FAILED.value
        await db.flush()
        raise HTTPException(status_code=500, detail=f"视频生成失败: {str(e)}")


@router.get("/shots/{shot_id}/video-status", response_model=VideoTaskStatusResponse)
async def get_video_status(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
):
    """查询视频生成任务状态"""
    result = await db.execute(select(Shot).where(Shot.id == shot_id))
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="分镜不存在")

    if not shot.video_task_id:
        return VideoTaskStatusResponse(
            task_id="",
            status="no_task",
        )

    try:
        task_data = await seedance_service.query_video_task(shot.video_task_id)
        status = task_data.get("status", "unknown")

        if status == "succeeded":
            # 获取视频URL和尾帧
            video_url = ""
            last_frame_url = ""
            content = task_data.get("content", {})
            if isinstance(content, dict):
                video_url = content.get("video_url", "")
                last_frame_url = content.get("last_frame_image_url", "")
            elif isinstance(content, list):
                for item in content:
                    if item.get("type") == "video_url":
                        video_url = item.get("video_url", {}).get("url", "")
                    if item.get("type") == "image_url":
                        last_frame_url = item.get("image_url", {}).get("url", "")

            shot.video_url = video_url
            shot.last_frame_url = last_frame_url
            shot.status = ShotStatus.COMPLETED.value
            await db.flush()

            return VideoTaskStatusResponse(
                task_id=shot.video_task_id,
                status=status,
                video_url=video_url,
                last_frame_url=last_frame_url,
            )
        elif status == "failed":
            shot.status = ShotStatus.FAILED.value
            await db.flush()
            return VideoTaskStatusResponse(
                task_id=shot.video_task_id,
                status=status,
                error=task_data.get("error", {}).get("message", "生成失败"),
            )
        else:
            return VideoTaskStatusResponse(
                task_id=shot.video_task_id,
                status=status,
            )

    except Exception as e:
        logger.error(f"查询视频状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/projects/{project_id}/generate-all-videos")
async def generate_all_videos(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """批量为项目所有分镜生成视频"""
    result = await db.execute(
        select(Project).where(Project.id == project_id).options(selectinload(Project.shots))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project.status = ProjectStatus.GENERATING.value
    tasks = []

    for shot in sorted(project.shots, key=lambda s: s.sequence):
        if shot.status == ShotStatus.COMPLETED.value and shot.video_url:
            continue  # 跳过已完成的

        try:
            task_data = await seedance_service.create_video_task(
                prompt=shot.description,
                first_frame_url=shot.first_frame_url or None,
                last_frame_url=shot.last_frame_url or None,
                duration=shot.duration,
                ratio=project.aspect_ratio,
                resolution=project.resolution,
                generate_audio=True,
                return_last_frame=True,
            )
            shot.video_task_id = task_data.get("id", "")
            shot.status = ShotStatus.GENERATING.value
            tasks.append({"shot_id": shot.id, "task_id": task_data.get("id", "")})
        except Exception as e:
            logger.error(f"分镜 {shot.sequence} 视频生成失败: {e}")
            shot.status = ShotStatus.FAILED.value

    await db.flush()
    return {"message": f"已提交 {len(tasks)} 个视频生成任务", "tasks": tasks}


# ============ TTS 语音合成 ============

@router.post("/tts/synthesize", response_model=TTSResponse)
async def synthesize_speech(request: TTSRequest):
    """语音合成"""
    try:
        result = await tts_service.synthesize_speech(
            text=request.text,
            voice_type=request.voice_type,
            speed_ratio=request.speed_ratio,
            volume_ratio=request.volume_ratio,
            pitch_ratio=request.pitch_ratio,
            encoding=request.encoding,
        )
        return TTSResponse(
            audio_url=result["audio_url"],
            duration=result["duration"],
            reqid=result["reqid"],
        )
    except Exception as e:
        logger.error(f"TTS合成失败: {e}")
        raise HTTPException(status_code=500, detail=f"语音合成失败: {str(e)}")


@router.post("/shots/{shot_id}/generate-audio", response_model=TTSResponse)
async def generate_shot_audio(
    shot_id: str,
    voice_type: str = None,
    db: AsyncSession = Depends(get_db),
):
    """为分镜生成语音"""
    result = await db.execute(select(Shot).where(Shot.id == shot_id))
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="分镜不存在")

    if not shot.dialogue:
        raise HTTPException(status_code=400, detail="分镜没有对白文本")

    try:
        tts_result = await tts_service.synthesize_speech(
            text=shot.dialogue,
            voice_type=voice_type,
        )
        shot.audio_url = tts_result["audio_url"]
        shot.audio_duration = tts_result["duration"]
        await db.flush()

        return TTSResponse(
            audio_url=tts_result["audio_url"],
            duration=tts_result["duration"],
            reqid=tts_result["reqid"],
        )
    except Exception as e:
        logger.error(f"分镜语音合成失败: {e}")
        raise HTTPException(status_code=500, detail=f"语音合成失败: {str(e)}")


# ============ 视频合成/拼接 ============

@router.post("/projects/{project_id}/compose", response_model=ComposeResponse)
async def compose_video(
    project_id: str,
    request: ComposeRequest,
    db: AsyncSession = Depends(get_db),
):
    """合成最终视频（拼接所有分镜 + 音频）"""
    result = await db.execute(
        select(Project).where(Project.id == project_id).options(selectinload(Project.shots))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project.status = ProjectStatus.COMPOSING.value
    await db.flush()

    try:
        shots_data = []
        for shot in sorted(project.shots, key=lambda s: s.sequence):
            if shot.video_url:
                shots_data.append({
                    "sequence": shot.sequence,
                    "video_url": shot.video_url,
                    "audio_path": shot.audio_url if request.include_audio else None,
                })

        if not shots_data:
            raise HTTPException(status_code=400, detail="没有已完成的视频分镜")

        compose_result = await ffmpeg_service.compose_project_video(
            shots_data=shots_data,
            project_id=project_id,
        )

        project.output_video_url = compose_result["output_video_url"]
        project.status = ProjectStatus.COMPLETED.value
        await db.flush()

        return ComposeResponse(
            output_video_url=compose_result["output_video_url"],
            duration=compose_result["duration"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"视频合成失败: {e}")
        project.status = ProjectStatus.FAILED.value
        await db.flush()
        raise HTTPException(status_code=500, detail=f"视频合成失败: {str(e)}")


# ============ 图片分析 ============

@router.post("/analyze-image")
async def analyze_image(image_url: str):
    """分析图片内容（角色、物品识别）"""
    try:
        result = await doubao_service.analyze_image(image_url)
        return result
    except Exception as e:
        logger.error(f"图片分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"图片分析失败: {str(e)}")
