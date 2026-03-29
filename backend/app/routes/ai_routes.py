"""AI 服务路由 - 脚本生成、视频生成、语音合成"""

import asyncio
import logging
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.database import get_db
from backend.app.models import Project, Shot, ProjectStatus, ShotStatus, ProjectCharacter, ProjectScene, Character, Scene
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


# ============ 角色/场景上下文辅助 ============

async def _build_asset_context(db: AsyncSession, project_id: str) -> dict:
    """
    查询项目关联的角色和场景，构建可注入 prompt 的上下文信息。
    返回:
      {
        "character_prompt": str,   # 角色描述文本（注入脚本/视频prompt）
        "scene_prompt": str,       # 场景描述文本
        "voice_type": str,         # 首选角色音色（用于TTS）
        "character_ref_images": list[str],  # 角色参考图片
        "scene_ref_images": list[str],       # 场景参考图片
        "all_ref_images": list[str],         # 所有参考图片（角色+场景，用于LLM视觉分析）
      }
    """
    # 查询项目角色
    char_result = await db.execute(
        select(ProjectCharacter)
        .where(ProjectCharacter.project_id == project_id)
        .options(selectinload(ProjectCharacter.character))
    )
    project_chars = char_result.scalars().all()

    # 查询项目场景
    scene_result = await db.execute(
        select(ProjectScene)
        .where(ProjectScene.project_id == project_id)
        .options(selectinload(ProjectScene.scene))
    )
    project_scenes = scene_result.scalars().all()

    # 构建角色描述
    char_parts = []
    voice_type = ""
    char_ref_images = []
    for pc in project_chars:
        ch = pc.character
        if not ch:
            continue
        name = ch.name
        desc = pc.custom_description or ch.description or ""
        appearance = pc.custom_appearance_prompt or ch.appearance_prompt or ""
        if appearance:
            char_parts.append(f"角色[{name}]: {appearance}")
        elif desc:
            char_parts.append(f"角色[{name}]: {desc}")
        # 取第一个角色的音色
        if not voice_type:
            voice_type = pc.custom_voice_type or ch.voice_type or ""
        # 收集角色参考图
        if ch.reference_images:
            char_ref_images.extend(ch.reference_images)

    # 构建场景描述
    scene_parts = []
    scene_ref_images = []
    for ps in project_scenes:
        sc = ps.scene
        if not sc:
            continue
        name = sc.name
        env = ps.custom_environment_prompt or sc.environment_prompt or ""
        mood = sc.mood or ""
        lighting = sc.lighting or ""
        parts = [p for p in [env, f"mood:{mood}" if mood else "", f"lighting:{lighting}" if lighting else ""] if p]
        if parts:
            scene_parts.append(f"场景[{name}]: {', '.join(parts)}")
        # 收集场景参考图
        if sc.reference_images:
            scene_ref_images.extend(sc.reference_images)

    character_prompt = "; ".join(char_parts)
    scene_prompt = "; ".join(scene_parts)

    # 合并所有参考图（角色优先，场景其次），用于 LLM 视觉分析
    all_ref_images = char_ref_images[:3] + scene_ref_images[:2]  # 最多5张

    return {
        "character_prompt": character_prompt,
        "scene_prompt": scene_prompt,
        "voice_type": voice_type,
        "character_ref_images": char_ref_images,
        "scene_ref_images": scene_ref_images,
        "all_ref_images": all_ref_images,
    }


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

        # === 查询项目关联的角色和场景，注入脚本生成上下文 ===
        asset_ctx = await _build_asset_context(db, project_id)
        asset_hint = ""
        if asset_ctx["character_prompt"]:
            asset_hint += f"\n\n【项目角色设定】\n{asset_ctx['character_prompt']}\n请在每个镜头的画面描述中保持以上角色的外观一致性。"
        if asset_ctx["scene_prompt"]:
            asset_hint += f"\n\n【项目场景设定】\n{asset_ctx['scene_prompt']}\n请在镜头描述中融入以上场景氛围。"

        # === 合并参考图片：用户上传 + 角色/场景资产参考图 ===
        # 角色和场景的参考图必须传给 LLM 做视觉分析，不能只靠文字描述
        image_urls = list(request.image_urls) if request.image_urls else []
        asset_images = asset_ctx["all_ref_images"]
        # 将资产参考图合并到 image_urls（去重）
        existing_set = set(image_urls)
        for img in asset_images:
            if img and img not in existing_set:
                image_urls.append(img)
                existing_set.add(img)

        if asset_images:
            asset_hint += f"\n\n⚠️ 注意：已附带了 {len(asset_images)} 张角色/场景参考图片。请仔细分析这些图片中的角色外观和场景环境，确保脚本中的描述与图片完全一致。"
            logger.info(f"脚本生成: 合并 {len(asset_images)} 张资产参考图 + {len(request.image_urls or [])} 张用户上传图")

        # 如果有参考图（含资产图），提取视觉风格上下文
        if image_urls and not style_context:
            style_context = await doubao_service.extract_style_context(image_urls)
            project.style_context = style_context
            project.reference_images = image_urls

        # 调用豆包大模型生成脚本
        # 将提取的风格/主体描述作为额外上下文传入，让LLM在每个镜头中复用
        style_hint = ""
        if style_context:
            style_hint = f"\n\n【已提取的主体与风格信息】\n{style_context}\n请在每个镜头description开头使用以上主体描述。"

        script_data = await doubao_service.generate_script(
            theme=request.theme or project.theme,
            scene_type=request.scene_type or project.scene_type,
            target_duration=request.target_duration or project.target_duration,
            additional_context=(request.additional_context or "") + style_hint + asset_hint,
            image_urls=image_urls if image_urls else None,
        )

        # 同时提取 subject_description 存入 style_context
        if script_data.get("subject_description"):
            subject_desc = script_data["subject_description"]
            # 合并 subject + style 作为完整上下文
            if style_context and subject_desc not in style_context:
                style_context = f"{subject_desc}. {style_context}"
            elif not style_context:
                style_context = subject_desc
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

    # 获取项目的风格上下文和参考图片
    proj_result = await db.execute(select(Project).where(Project.id == shot.project_id))
    project = proj_result.scalar_one_or_none()
    style_prefix = project.style_context if project else ""
    reference_images = project.reference_images if project else []
    subject_ref_image = reference_images[0] if reference_images else ""

    # 查询角色/场景上下文
    asset_ctx = await _build_asset_context(db, shot.project_id) if project else {
        "character_prompt": "", "scene_prompt": "", "voice_type": "",
        "character_ref_images": [], "scene_ref_images": [], "all_ref_images": [],
    }
    # 如果没有用户参考图，尝试使用角色/场景参考图
    if not subject_ref_image and asset_ctx["character_ref_images"]:
        subject_ref_image = asset_ctx["character_ref_images"][0]
    elif not subject_ref_image and asset_ctx["scene_ref_images"]:
        subject_ref_image = asset_ctx["scene_ref_images"][0]

    # 确定首帧（尾帧链接模式，与批量生成一致）
    # 优先级：手动传入 > shot已存 > 上一镜头尾帧 > 参考图片（仅首个镜头）
    first_frame = request.first_frame_url or shot.first_frame_url or ""

    if not first_frame and project:
        # 优先使用上一镜头的尾帧（场景连续 + 主体延续）
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
            logger.info(f"单镜头生成: 首帧=镜头 {prev_shot.sequence} 尾帧 ✅ 尾帧链接")
        elif subject_ref_image:
            # 没有上一镜头尾帧（首个镜头或前面都失败了），用参考图
            first_frame = subject_ref_image
            logger.info(f"单镜头生成: 首帧=参考图片（无可用尾帧）")

    try:
        prompt = request.prompt or shot.description
        # 融合角色/场景描述到提示词
        asset_parts = []
        if asset_ctx["character_prompt"]:
            asset_parts.append(asset_ctx["character_prompt"])
        if asset_ctx["scene_prompt"]:
            asset_parts.append(asset_ctx["scene_prompt"])
        if asset_parts:
            prompt = f"{'. '.join(asset_parts)}. {prompt}"
        if style_prefix:
            prompt = f"{style_prefix}. {prompt}"

        task_data = await seedance_service.create_video_task(
            prompt=prompt,
            first_frame_url=first_frame or None,
            # 不传 last_frame_url — pro-fast 不支持首尾帧同传
            last_frame_url=request.last_frame_url,  # 仅当用户显式传入时
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
                last_frame_url = content.get("last_frame_url", "")
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
            logger.info(f"镜头状态查询完成: video_url={'有' if video_url else '无'}, last_frame_url={'有' if last_frame_url else '无'}")

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
    后台批量生成 worker — 尾帧链接模式。

    核心策略（适用于 Seedance 1.0 pro fast 等只支持 first_frame 的模型）：
      - 镜头 1：first_frame = 用户上传的参考图片（锚定主体外观）
      - 镜头 2：first_frame = 镜头 1 返回的 last_frame（场景连续 + 主体延续）
      - 镜头 3：first_frame = 镜头 2 返回的 last_frame
      - ...以此类推

    这样每个镜头都从上一个镜头的最后一帧开始，保证：
      1. 主体一致（同一只猫从头到尾）
      2. 场景连续（每个镜头衔接自然）
      3. 每个镜头有不同内容（因为 prompt 不同，产生不同动作/场景）

    注意：不要给每个镜头都传同一张参考图做 first_frame！
    那样会导致所有镜头都从同一个静态画面开始，看起来完全一样。
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
            # 参考图仅用于第一个镜头的首帧
            subject_ref_image = reference_images[0] if reference_images else ""

            # === 查询项目关联的角色和场景 ===
            asset_ctx = await _build_asset_context(db, project_id)
            asset_prompt_parts = []
            if asset_ctx["character_prompt"]:
                asset_prompt_parts.append(asset_ctx["character_prompt"])
            if asset_ctx["scene_prompt"]:
                asset_prompt_parts.append(asset_ctx["scene_prompt"])
            asset_prompt_prefix = ". ".join(asset_prompt_parts) if asset_prompt_parts else ""

            # 如果没有用户参考图，但角色/场景有参考图，使用它们
            if not subject_ref_image and asset_ctx["character_ref_images"]:
                subject_ref_image = asset_ctx["character_ref_images"][0]
                logger.info(f"使用角色参考图作为首帧: {subject_ref_image[:80]}...")
            elif not subject_ref_image and asset_ctx["scene_ref_images"]:
                subject_ref_image = asset_ctx["scene_ref_images"][0]
                logger.info(f"使用场景参考图作为首帧: {subject_ref_image[:80]}...")

            # 角色的默认音色（用于TTS）
            asset_voice_type = asset_ctx["voice_type"]

            sorted_shots = sorted(project.shots, key=lambda s: s.sequence)
            prev_last_frame_url = ""

            for i, shot in enumerate(sorted_shots):
                # 跳过已完成的，但记录其尾帧以供后续镜头使用
                if shot.status == ShotStatus.COMPLETED.value and shot.video_url:
                    prev_last_frame_url = shot.last_frame_url or ""
                    logger.info(f"镜头 {shot.sequence}: 已完成，尾帧={'有' if prev_last_frame_url else '无'}")
                    continue

                try:
                    # === 第一步：确定首帧（尾帧链接模式） ===
                    # 优先级：
                    # 1. 用户手动指定的 first_frame_url
                    # 2. 上一镜头的尾帧（核心链接逻辑！）
                    # 3. 参考图片（仅第一个镜头或没有尾帧时使用）
                    first_frame = shot.first_frame_url or ""

                    if not first_frame and prev_last_frame_url:
                        # 核心：使用上一镜头尾帧，实现连续过渡
                        first_frame = prev_last_frame_url
                        logger.info(f"镜头 {shot.sequence}: 首帧=上一镜头尾帧 ✅ 尾帧链接")
                    elif not first_frame and subject_ref_image:
                        # 仅第一个镜头（或前面都失败没有尾帧时）使用参考图
                        first_frame = subject_ref_image
                        logger.info(f"镜头 {shot.sequence}: 首帧=参考图片（{'首个镜头' if i == 0 else '无可用尾帧，回退'}）")

                    # === 构建增强提示词（融合风格+角色+场景） ===
                    enhanced_prompt = shot.description
                    if asset_prompt_prefix:
                        enhanced_prompt = f"{asset_prompt_prefix}. {enhanced_prompt}"
                    if style_prefix:
                        enhanced_prompt = f"{style_prefix}. {enhanced_prompt}"

                    logger.info(f"镜头 {shot.sequence}: 提交生成, first_frame={'有' if first_frame else '无'}")

                    task_data = await seedance_service.create_video_task(
                        prompt=enhanced_prompt,
                        first_frame_url=first_frame or None,
                        # 不传 last_frame_url — pro-fast 模型不支持首尾帧同时传入
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
                                    last_frame_url = content.get("last_frame_url", "")
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
                                logger.info(
                                    f"镜头 {shot.sequence} 视频完成 ✅ "
                                    f"尾帧={'已获取' if last_frame_url else '❌ 未获取'}"
                                )
                                if not last_frame_url:
                                    logger.warning(
                                        f"镜头 {shot.sequence}: API 未返回尾帧！"
                                        f"后续镜头将回退到参考图。content keys: {list(content.keys()) if isinstance(content, dict) else 'list'}"
                                    )
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
                                voice_type=asset_voice_type or None,  # 使用角色音色（如果有）
                            )
                            shot.audio_url = tts_result["audio_url"]
                            shot.audio_duration = tts_result["duration"]
                            await db.flush()
                            voice_info = f", 音色={asset_voice_type}" if asset_voice_type else ""
                            logger.info(f"镜头 {shot.sequence} TTS完成: {tts_result['duration']:.1f}s{voice_info}")
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
                    "dialogue": shot.dialogue or "",
                    "duration": shot.duration,
                })

        if not shots_data:
            raise HTTPException(status_code=400, detail="没有已完成的视频分镜")

        # 字幕样式
        subtitle_style = None
        if request.subtitle_style:
            subtitle_style = request.subtitle_style.model_dump()

        compose_result = await ffmpeg_service.compose_project_video(
            shots_data=shots_data,
            project_id=project_id,
            include_subtitles=request.include_subtitles,
            subtitle_style=subtitle_style,
        )

        project.output_video_url = compose_result["output_video_url"]
        project.status = ProjectStatus.COMPLETED.value
        await db.flush()

        return ComposeResponse(
            output_video_url=compose_result["output_video_url"],
            duration=compose_result["duration"],
            subtitle_url=compose_result.get("subtitle_url", ""),
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
