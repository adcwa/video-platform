"""数字资产路由 — 全局角色 & 场景管理"""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.database import get_db
from backend.app.models import Character, Scene, ProjectCharacter, ProjectScene, Project
from backend.app.schemas import (
    CharacterCreate, CharacterUpdate, CharacterResponse,
    SceneCreate, SceneUpdate, SceneResponse,
    ProjectCharacterCreate, ProjectCharacterResponse,
    ProjectSceneCreate, ProjectSceneResponse,
    ImageRecognizeRequest, PromoteToGlobalRequest,
)
from backend.app.services import doubao_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assets", tags=["数字资产"])


# ==================== 全局角色 CRUD ====================

@router.get("/characters", response_model=list[CharacterResponse])
async def list_characters(
    is_global: Optional[bool] = Query(default=None, description="筛选全局/项目级"),
    tag: Optional[str] = Query(default=None, description="按标签筛选"),
    search: Optional[str] = Query(default=None, description="搜索名称/描述"),
    db: AsyncSession = Depends(get_db),
):
    """获取角色列表"""
    query = select(Character).order_by(Character.updated_at.desc())
    if is_global is not None:
        query = query.where(Character.is_global == is_global)
    if tag:
        # SQLite JSON 数组搜索：使用 LIKE 模糊匹配
        query = query.where(Character.tags.like(f'%"{tag}"%'))
    if search:
        query = query.where(
            or_(
                Character.name.ilike(f"%{search}%"),
                Character.description.ilike(f"%{search}%"),
            )
        )
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/characters", response_model=CharacterResponse)
async def create_character(
    data: CharacterCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建角色"""
    character = Character(
        name=data.name,
        description=data.description,
        appearance_prompt=data.appearance_prompt,
        appearance_prompt_zh=data.appearance_prompt_zh,
        reference_images=data.reference_images,
        voice_type=data.voice_type,
        voice_config=data.voice_config,
        tags=data.tags,
        is_global=data.is_global,
        source_project_id=data.source_project_id,
    )
    db.add(character)
    await db.flush()
    await db.refresh(character)
    logger.info(f"角色创建成功: {character.name} (id={character.id}, global={character.is_global})")
    return character


@router.get("/characters/{character_id}", response_model=CharacterResponse)
async def get_character(character_id: str, db: AsyncSession = Depends(get_db)):
    """获取角色详情"""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")
    return character


@router.put("/characters/{character_id}", response_model=CharacterResponse)
async def update_character(
    character_id: str,
    data: CharacterUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新角色"""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(character, key, value)

    await db.flush()
    await db.refresh(character)
    logger.info(f"角色更新成功: {character.name}")
    return character


@router.delete("/characters/{character_id}")
async def delete_character(character_id: str, db: AsyncSession = Depends(get_db)):
    """删除角色"""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")

    await db.delete(character)
    logger.info(f"角色删除: {character.name}")
    return {"message": f"角色 '{character.name}' 已删除"}


# ==================== 全局场景 CRUD ====================

@router.get("/scenes", response_model=list[SceneResponse])
async def list_scenes(
    is_global: Optional[bool] = Query(default=None, description="筛选全局/项目级"),
    tag: Optional[str] = Query(default=None, description="按标签筛选"),
    search: Optional[str] = Query(default=None, description="搜索名称/描述"),
    db: AsyncSession = Depends(get_db),
):
    """获取场景列表"""
    query = select(Scene).order_by(Scene.updated_at.desc())
    if is_global is not None:
        query = query.where(Scene.is_global == is_global)
    if tag:
        query = query.where(Scene.tags.like(f'%"{tag}"%'))
    if search:
        query = query.where(
            or_(
                Scene.name.ilike(f"%{search}%"),
                Scene.description.ilike(f"%{search}%"),
            )
        )
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/scenes", response_model=SceneResponse)
async def create_scene(
    data: SceneCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建场景"""
    scene = Scene(
        name=data.name,
        description=data.description,
        environment_prompt=data.environment_prompt,
        environment_prompt_zh=data.environment_prompt_zh,
        reference_images=data.reference_images,
        mood=data.mood,
        lighting=data.lighting,
        tags=data.tags,
        is_global=data.is_global,
        source_project_id=data.source_project_id,
    )
    db.add(scene)
    await db.flush()
    await db.refresh(scene)
    logger.info(f"场景创建成功: {scene.name} (id={scene.id}, global={scene.is_global})")
    return scene


@router.get("/scenes/{scene_id}", response_model=SceneResponse)
async def get_scene(scene_id: str, db: AsyncSession = Depends(get_db)):
    """获取场景详情"""
    result = await db.execute(select(Scene).where(Scene.id == scene_id))
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")
    return scene


@router.put("/scenes/{scene_id}", response_model=SceneResponse)
async def update_scene(
    scene_id: str,
    data: SceneUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新场景"""
    result = await db.execute(select(Scene).where(Scene.id == scene_id))
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(scene, key, value)

    await db.flush()
    await db.refresh(scene)
    logger.info(f"场景更新成功: {scene.name}")
    return scene


@router.delete("/scenes/{scene_id}")
async def delete_scene(scene_id: str, db: AsyncSession = Depends(get_db)):
    """删除场景"""
    result = await db.execute(select(Scene).where(Scene.id == scene_id))
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")

    await db.delete(scene)
    logger.info(f"场景删除: {scene.name}")
    return {"message": f"场景 '{scene.name}' 已删除"}


# ==================== AI 图片识别 → 自动创建资产 ====================

@router.post("/recognize-image")
async def recognize_image(
    request: ImageRecognizeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    上传图片 → AI识别角色和场景 → 可选自动创建数字资产。

    返回识别结果 + 创建的资产列表。
    """
    try:
        # 调用增强的 AI 图片分析（返回结构化角色 + 场景信息）
        recognition = await doubao_service.recognize_characters_and_scenes(request.image_url)

        created_characters = []
        created_scenes = []

        if request.auto_create:
            # 自动创建识别到的角色
            for char_info in recognition.get("characters", []):
                character = Character(
                    name=char_info.get("name", "未命名角色"),
                    description=char_info.get("description_zh", ""),
                    appearance_prompt=char_info.get("appearance_prompt", ""),
                    appearance_prompt_zh=char_info.get("description_zh", ""),
                    reference_images=[request.image_url],
                    tags=char_info.get("tags", []),
                    is_global=True,
                )
                db.add(character)
                await db.flush()
                await db.refresh(character)
                created_characters.append({
                    "id": character.id,
                    "name": character.name,
                    "description": character.description,
                    "appearance_prompt": character.appearance_prompt,
                })

            # 自动创建识别到的场景
            scene_info = recognition.get("scene", {})
            if scene_info and scene_info.get("name"):
                scene = Scene(
                    name=scene_info.get("name", "未命名场景"),
                    description=scene_info.get("description_zh", ""),
                    environment_prompt=scene_info.get("environment_prompt", ""),
                    environment_prompt_zh=scene_info.get("description_zh", ""),
                    reference_images=[request.image_url],
                    mood=scene_info.get("mood", ""),
                    lighting=scene_info.get("lighting", ""),
                    tags=scene_info.get("tags", []),
                    is_global=True,
                )
                db.add(scene)
                await db.flush()
                await db.refresh(scene)
                created_scenes.append({
                    "id": scene.id,
                    "name": scene.name,
                    "description": scene.description,
                    "environment_prompt": scene.environment_prompt,
                })

        return {
            "recognition": recognition,
            "created_characters": created_characters,
            "created_scenes": created_scenes,
        }

    except Exception as e:
        logger.error(f"图片识别失败: {e}")
        raise HTTPException(status_code=500, detail=f"图片识别失败: {str(e)}")


# ==================== 项目-角色/场景关联 ====================

@router.get("/projects/{project_id}/characters", response_model=list[ProjectCharacterResponse])
async def list_project_characters(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取项目关联的角色列表"""
    result = await db.execute(
        select(ProjectCharacter)
        .where(ProjectCharacter.project_id == project_id)
        .options(selectinload(ProjectCharacter.character))
    )
    return result.scalars().all()


@router.post("/projects/{project_id}/characters", response_model=ProjectCharacterResponse)
async def add_project_character(
    project_id: str,
    data: ProjectCharacterCreate,
    db: AsyncSession = Depends(get_db),
):
    """将角色关联到项目（支持项目级覆盖）"""
    # 验证项目和角色存在
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在")

    char_result = await db.execute(select(Character).where(Character.id == data.character_id))
    if not char_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="角色不存在")

    # 检查是否已关联
    existing = await db.execute(
        select(ProjectCharacter)
        .where(ProjectCharacter.project_id == project_id)
        .where(ProjectCharacter.character_id == data.character_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="角色已关联到此项目")

    pc = ProjectCharacter(
        project_id=project_id,
        character_id=data.character_id,
        custom_description=data.custom_description,
        custom_appearance_prompt=data.custom_appearance_prompt,
        custom_voice_type=data.custom_voice_type,
        custom_voice_config=data.custom_voice_config,
    )
    db.add(pc)
    await db.flush()

    # 重新查询以加载关联
    result = await db.execute(
        select(ProjectCharacter)
        .where(ProjectCharacter.id == pc.id)
        .options(selectinload(ProjectCharacter.character))
    )
    return result.scalar_one()


@router.delete("/projects/{project_id}/characters/{character_id}")
async def remove_project_character(
    project_id: str,
    character_id: str,
    db: AsyncSession = Depends(get_db),
):
    """从项目移除角色关联"""
    result = await db.execute(
        select(ProjectCharacter)
        .where(ProjectCharacter.project_id == project_id)
        .where(ProjectCharacter.character_id == character_id)
    )
    pc = result.scalar_one_or_none()
    if not pc:
        raise HTTPException(status_code=404, detail="关联不存在")

    await db.delete(pc)
    return {"message": "角色已从项目移除"}


@router.get("/projects/{project_id}/scenes", response_model=list[ProjectSceneResponse])
async def list_project_scenes(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取项目关联的场景列表"""
    result = await db.execute(
        select(ProjectScene)
        .where(ProjectScene.project_id == project_id)
        .options(selectinload(ProjectScene.scene))
    )
    return result.scalars().all()


@router.post("/projects/{project_id}/scenes", response_model=ProjectSceneResponse)
async def add_project_scene(
    project_id: str,
    data: ProjectSceneCreate,
    db: AsyncSession = Depends(get_db),
):
    """将场景关联到项目（支持项目级覆盖）"""
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="项目不存在")

    scene_result = await db.execute(select(Scene).where(Scene.id == data.scene_id))
    if not scene_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="场景不存在")

    existing = await db.execute(
        select(ProjectScene)
        .where(ProjectScene.project_id == project_id)
        .where(ProjectScene.scene_id == data.scene_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="场景已关联到此项目")

    ps = ProjectScene(
        project_id=project_id,
        scene_id=data.scene_id,
        custom_description=data.custom_description,
        custom_environment_prompt=data.custom_environment_prompt,
    )
    db.add(ps)
    await db.flush()

    result = await db.execute(
        select(ProjectScene)
        .where(ProjectScene.id == ps.id)
        .options(selectinload(ProjectScene.scene))
    )
    return result.scalar_one()


@router.delete("/projects/{project_id}/scenes/{scene_id}")
async def remove_project_scene(
    project_id: str,
    scene_id: str,
    db: AsyncSession = Depends(get_db),
):
    """从项目移除场景关联"""
    result = await db.execute(
        select(ProjectScene)
        .where(ProjectScene.project_id == project_id)
        .where(ProjectScene.scene_id == scene_id)
    )
    ps = result.scalar_one_or_none()
    if not ps:
        raise HTTPException(status_code=404, detail="关联不存在")

    await db.delete(ps)
    return {"message": "场景已从项目移除"}


# ==================== 升级为全局资产 ====================

@router.post("/characters/{character_id}/promote", response_model=CharacterResponse)
async def promote_character_to_global(
    character_id: str,
    request: PromoteToGlobalRequest = PromoteToGlobalRequest(),
    db: AsyncSession = Depends(get_db),
):
    """将项目级角色升级为全局角色"""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")

    if character.is_global:
        raise HTTPException(status_code=400, detail="角色已经是全局资产")

    character.is_global = True
    if request.name:
        character.name = request.name

    await db.flush()
    await db.refresh(character)
    logger.info(f"角色升级为全局: {character.name}")
    return character


@router.post("/scenes/{scene_id}/promote", response_model=SceneResponse)
async def promote_scene_to_global(
    scene_id: str,
    request: PromoteToGlobalRequest = PromoteToGlobalRequest(),
    db: AsyncSession = Depends(get_db),
):
    """将项目级场景升级为全局场景"""
    result = await db.execute(select(Scene).where(Scene.id == scene_id))
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")

    if scene.is_global:
        raise HTTPException(status_code=400, detail="场景已经是全局资产")

    scene.is_global = True
    if request.name:
        scene.name = request.name

    await db.flush()
    await db.refresh(scene)
    logger.info(f"场景升级为全局: {scene.name}")
    return scene


# ==================== 统计 ====================

@router.get("/stats")
async def get_asset_stats(db: AsyncSession = Depends(get_db)):
    """获取数字资产统计"""
    char_result = await db.execute(select(Character))
    all_chars = char_result.scalars().all()

    scene_result = await db.execute(select(Scene))
    all_scenes = scene_result.scalars().all()

    return {
        "characters": {
            "total": len(all_chars),
            "global": sum(1 for c in all_chars if c.is_global),
            "project_level": sum(1 for c in all_chars if not c.is_global),
        },
        "scenes": {
            "total": len(all_scenes),
            "global": sum(1 for s in all_scenes if s.is_global),
            "project_level": sum(1 for s in all_scenes if not s.is_global),
        },
    }
