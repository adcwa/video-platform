"""AI 服务路由 - 脚本生成、视频生成、语音合成"""

import asyncio
import logging
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
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
        # 如果有参考图片，先提取视觉风格上下文
        style_context = ""
        if request.image_urls:
            style_context = await doubao_service.extract_style_context(request.image_urls)
            project.style_context = style_context
            project.reference_images = request.image_urls

        # 调用豆包大模型生成脚本
        script_data = await doubao_service.generate_script(
            theme=request.theme or project.theme,
            scene_type=request.scene_type or project.scene_type,
            target_duration=request.target_duration or project.target_duration,
            additional_context=request.additional_context,
            image_urls=request.image_urls if request.image_urls else None,
        )

        # 从脚本中提取 style_description（如果有的话）
        if not style_context and script_data.get("style_description"):
            style_context = script_data["style_description"]
            project.style_context = style_context

        # 更新项目
        project.script_content = str(script_data)
        project.script_json = script_data
        project.status = ProjectStatus.SCRIPTING.value
        if request.theme:
            project.theme = request.theme

        # 创建分镜
        # 先清除旧分镜
        old_shots_result = await db.execute(
            select(Shot).where(Shot.project_id == project_id)
        )
        for s in old_shots_result.scalars().all():
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

    # 获取项目的风格上下文
    proj_result = await db.execute(select(Project).where(Project.id == shot.project_id))
    project = proj_result.scalar_one_or_none()
    style_prefix = project.style_context if project else ""

    # 确定首帧：手动传入 > shot已存 > 上一镜头尾帧
    first_frame = request.first_frame_url or shot.first_frame_url or ""
    if not first_frame and project:
        # 尝试获取上一个已完成镜头的尾帧
        prev_result = await db.execute(
            select(Shot)
            .where(Shot.project_id == shot.project_id)
            .where(Shot.sequence < shot.sequence)
            .where(Shot.status == ShotStatus.COMPLETED.value)
            .order_by(Shot.sequence.desc())
            .limit(1)
        )
        prev_shot = prev_result.scalar_one_or_none()
        if prev_shot and prev_shot.last_frame_url:
            first_frame = prev_shot.last_frame_url
            logger.info(f"单镜头生成: 使用镜头 {prev_shot.sequence} 的尾帧作为首帧")

    try:
        prompt = request.prompt or shot.description
        if style_prefix:
            prompt = f"{style_prefix}. {prompt}"

        task_data = await seedance_service.create_video_task(
            prompt=prompt,
            first_frame_url=first_frame or None,
            last_frame_url=request.last_frame_url,
            duration=request.duration or shot.duration,
            ratio=request.ratio,
            resolution=request.resolution,
            generate_audio=request.generate_audio,
            camera_fixed=shot.camera_fixed == "true",
            return_last_frame=True,
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
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    批量为项目所有分镜生成视频+TTS语音。
    立即返回，后台按顺序处理（尾帧链接模式确保视觉连续）。
    前端通过 WebSocket / 轮询跟踪进度。
    """
    result = await db.execute(
        select(Project).where(Project.id == project_id).options(selectinload(Project.shots))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 统计待处理的镜头
    pending_shots = [
        s for s in sorted(project.shots, key=lambda s: s.sequence)
        if not (s.status == ShotStatus.COMPLETED.value and s.video_url)
    ]

    if not pending_shots:
        return {"message": "所有镜头已完成，无需生成", "tasks": []}

    # 标记项目为生成中
    project.status = ProjectStatus.GENERATING.value
    for shot in pending_shots:
        shot.status = ShotStatus.GENERATING.value
    await db.flush()

    # 立即返回，后台执行
    background_tasks.add_task(
        _batch_generate_worker,
        project_id=project_id,
    )

    return {
        "message": f"已提交 {len(pending_shots)} 个镜头，后台顺序生成中",
        "tasks": [{"shot_id": s.id, "sequence": s.sequence} for s in pending_shots],
    }


async def _batch_generate_worker(project_id: str):
    """
    后台批量生成 worker：
    1. 按顺序逐个生成视频（上一镜头尾帧 → 下一镜头首帧）
    2. 每个镜头视频完成后自动生成 TTS 语音（如有对白）
    3. 注入统一风格前缀保持视觉一致
    """
    from backend.app.database import async_session

    async with async_session() as db:
        try:
            result = await db.execute(
                select(Project).where(Project.id == project_id).options(selectinload(Project.shots))
            )
            project = result.scalar_one_or_none()
            if not project:
                logger.error(f"后台任务: 项目 {project_id} 不存在")
                return

            style_prefix = project.style_context or ""
            reference_images = project.reference_images or []
            first_ref_image = reference_images[0] if reference_images else ""

            sorted_shots = sorted(project.shots, key=lambda s: s.sequence)
            prev_last_frame_url = ""

            for i, shot in enumerate(sorted_shots):
                # 跳过已完成的，但记录尾帧
                if shot.status == ShotStatus.COMPLETED.value and shot.video_url:
                    prev_last_frame_url = shot.last_frame_url or ""
                    continue

                try:
                    # === 第一步：生成视频 ===
                    first_frame = shot.first_frame_url or ""
                    if not first_frame and prev_last_frame_url:
                        first_frame = prev_last_frame_url
                        logger.info(f"镜头 {shot.sequence}: 使用上一镜头尾帧作为首帧")
                    elif not first_frame and i == 0 and first_ref_image:
                        first_frame = first_ref_image
                        logger.info(f"镜头 {shot.sequence}: 使用参考图片作为首帧")

                    enhanced_prompt = shot.description
                    if style_prefix:
                        enhanced_prompt = f"{style_prefix}. {shot.description}"

                    task_data = await seedance_service.create_video_task(
                        prompt=enhanced_prompt,
                        first_frame_url=first_frame or None,
                        duration=shot.duration,
                        ratio=project.aspect_ratio,
                        resolution=project.resolution,
                        generate_audio=True,
                        return_last_frame=True,
                        camera_fixed=shot.camera_fixed == "true",
                    )
                    shot.video_task_id = task_data.get("id", "")
                    shot.status = ShotStatus.GENERATING.value
                    await db.flush()

                    # 轮询等待视频完成（最多 180 秒）
                    max_wait = 180
                    poll_interval = 5
                    waited = 0
                    while waited < max_wait:
                        await asyncio.sleep(poll_interval)
                        waited += poll_interval
                        try:
                            task_status = await seedance_service.query_video_task(shot.video_task_id)
                            status = task_status.get("status", "")
                            if status == "succeeded":
                                video_url = ""
                                last_frame_url = ""
                                content = task_status.get("content", {})
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
                                prev_last_frame_url = last_frame_url
                                logger.info(f"镜头 {shot.sequence} 视频完成")
                                break
                            elif status == "failed":
                                shot.status = ShotStatus.FAILED.value
                                await db.flush()
                                error_msg = task_status.get("error", {}).get("message", "")
                                logger.error(f"镜头 {shot.sequence} 失败: {error_msg}")
                                prev_last_frame_url = ""
                                break
                        except Exception as poll_err:
                            logger.warning(f"轮询镜头 {shot.sequence} 状态异常: {poll_err}")
                    else:
                        logger.warning(f"镜头 {shot.sequence} 等待超时")
                        prev_last_frame_url = ""

                    # === 第二步：生成 TTS 语音（视频完成后） ===
                    if shot.status == ShotStatus.COMPLETED.value and shot.dialogue and not shot.audio_url:
                        try:
                            tts_result = await tts_service.synthesize_speech(
                                text=shot.dialogue,
                            )
                            shot.audio_url = tts_result["audio_url"]
                            shot.audio_duration = tts_result["duration"]
                            await db.flush()
                            logger.info(f"镜头 {shot.sequence} TTS完成: {tts_result['duration']:.1f}s")
                        except Exception as tts_err:
                            logger.warning(f"镜头 {shot.sequence} TTS失败（不阻塞流程）: {tts_err}")

                except Exception as e:
                    logger.error(f"镜头 {shot.sequence} 生成失败: {e}")
                    shot.status = ShotStatus.FAILED.value
                    await db.flush()
                    prev_last_frame_url = ""

            # 检查最终状态
            await db.refresh(project)
            all_done = all(
                s.status == ShotStatus.COMPLETED.value
                for s in project.shots
                if s.video_url or s.status != ShotStatus.PENDING.value
            )
            project.status = ProjectStatus.COMPLETED.value if all_done else ProjectStatus.FAILED.value
            await db.flush()
            await db.commit()
            logger.info(f"项目 {project_id} 批量生成完成, 状态: {project.status}")

        except Exception as e:
            logger.error(f"批量生成 worker 异常: {e}")
            try:
                await db.rollback()
            except Exception:
                pass


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
                # audio_url 存的是 URL 路径 (如 /files/outputs/xxx.mp3)
                # 需要转换为实际文件系统路径 (如 data/outputs/xxx.mp3)
                audio_path = None
                if request.include_audio and shot.audio_url:
                    audio_path = shot.audio_url.replace("/files/", "data/", 1)
                    if not Path(audio_path).exists():
                        logger.warning(f"音频文件不存在，跳过: {audio_path}")
                        audio_path = None
                shots_data.append({
                    "sequence": shot.sequence,
                    "video_url": shot.video_url,
                    "audio_path": audio_path,
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
