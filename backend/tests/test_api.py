"""Backend API Tests — 使用独立的内存数据库，不影响生产数据"""

import io
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.main import app
from backend.app.database import Base, get_db

# 创建测试专用的内存数据库（每次测试全新，不碰生产 data/video_platform.db）
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def _override_get_db():
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture
async def client():
    # 用内存数据库建表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 覆盖 app 的数据库依赖
    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # 清理：还原依赖覆盖，销毁内存数据库
    app.dependency_overrides.clear()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_get_config(client: AsyncClient):
    response = await client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "available_voice_types" in data
    assert "available_ratios" in data
    assert "scene_types" in data
    assert len(data["available_voice_types"]) > 0


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient):
    payload = {
        "title": "Test",
        "theme": "cat",
        "scene_type": "entertainment",
        "target_duration": 30,
    }
    response = await client.post("/api/projects", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test"
    assert data["status"] == "draft"
    assert data["id"]


@pytest.mark.asyncio
async def test_create_project_validation(client: AsyncClient):
    response = await client.post("/api/projects", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient):
    await client.post("/api/projects", json={"title": "A"})
    await client.post("/api/projects", json={"title": "B"})
    response = await client.get("/api/projects")
    assert response.status_code == 200
    assert len(response.json()) >= 2


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient):
    r = await client.post("/api/projects", json={"title": "Detail"})
    pid = r.json()["id"]
    response = await client.get(f"/api/projects/{pid}")
    assert response.status_code == 200
    assert response.json()["title"] == "Detail"
    assert "shots" in response.json()


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient):
    response = await client.get("/api/projects/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient):
    r = await client.post("/api/projects", json={"title": "Old"})
    pid = r.json()["id"]
    response = await client.put(
        f"/api/projects/{pid}", json={"title": "New", "theme": "updated"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "New"
    assert response.json()["theme"] == "updated"


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient):
    r = await client.post("/api/projects", json={"title": "ToDelete"})
    pid = r.json()["id"]
    response = await client.delete(f"/api/projects/{pid}")
    assert response.status_code == 200
    get_resp = await client.get(f"/api/projects/{pid}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_create_shot(client: AsyncClient):
    r = await client.post("/api/projects", json={"title": "ShotTest"})
    pid = r.json()["id"]
    payload = {"description": "cat on grass", "dialogue": "hello", "duration": 5}
    response = await client.post(f"/api/projects/{pid}/shots", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "cat on grass"
    assert data["sequence"] == 1
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_create_multiple_shots(client: AsyncClient):
    r = await client.post("/api/projects", json={"title": "MultiShot"})
    pid = r.json()["id"]
    for i in range(1, 4):
        resp = await client.post(
            f"/api/projects/{pid}/shots",
            json={"description": f"shot{i}", "duration": 5},
        )
        assert resp.json()["sequence"] == i


@pytest.mark.asyncio
async def test_update_shot(client: AsyncClient):
    r = await client.post("/api/projects", json={"title": "UpdateShot"})
    pid = r.json()["id"]
    sr = await client.post(
        f"/api/projects/{pid}/shots", json={"description": "old", "duration": 5}
    )
    sid = sr.json()["id"]
    response = await client.put(
        f"/api/shots/{sid}", json={"description": "new", "duration": 8}
    )
    assert response.status_code == 200
    assert response.json()["description"] == "new"
    assert response.json()["duration"] == 8


@pytest.mark.asyncio
async def test_delete_shot(client: AsyncClient):
    r = await client.post("/api/projects", json={"title": "DeleteShot"})
    pid = r.json()["id"]
    sr = await client.post(
        f"/api/projects/{pid}/shots", json={"description": "x", "duration": 5}
    )
    sid = sr.json()["id"]
    response = await client.delete(f"/api/shots/{sid}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_image(client: AsyncClient):
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
    response = await client.post(
        "/api/uploads/image",
        files={"file": ("test.png", io.BytesIO(fake_png), "image/png")},
    )
    assert response.status_code == 200
    assert "file_url" in response.json()


@pytest.mark.asyncio
async def test_upload_image_invalid(client: AsyncClient):
    response = await client.post(
        "/api/uploads/image",
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_project_shots_cascade(client: AsyncClient):
    r = await client.post("/api/projects", json={"title": "Cascade"})
    pid = r.json()["id"]
    await client.post(
        f"/api/projects/{pid}/shots", json={"description": "s1", "duration": 5}
    )
    proj = await client.get(f"/api/projects/{pid}")
    assert len(proj.json()["shots"]) == 1
    await client.delete(f"/api/projects/{pid}")
    shots_resp = await client.get(f"/api/projects/{pid}/shots")
    assert len(shots_resp.json()) == 0


# ============ 数字资产测试 ============

@pytest.mark.asyncio
async def test_create_character(client: AsyncClient):
    response = await client.post("/api/assets/characters", json={
        "name": "布偶猫小花",
        "description": "一只可爱的布偶猫",
        "appearance_prompt": "a Ragdoll cat with blue eyes",
        "appearance_prompt_zh": "蓝眼睛的布偶猫",
        "tags": ["猫", "动物"],
        "is_global": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "布偶猫小花"
    assert data["is_global"] is True
    assert "猫" in data["tags"]
    assert data["id"]


@pytest.mark.asyncio
async def test_list_characters(client: AsyncClient):
    # 创建两个角色
    await client.post("/api/assets/characters", json={"name": "角色A"})
    await client.post("/api/assets/characters", json={"name": "角色B"})

    response = await client.get("/api/assets/characters")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_update_character(client: AsyncClient):
    r = await client.post("/api/assets/characters", json={"name": "原始名"})
    cid = r.json()["id"]

    r2 = await client.put(f"/api/assets/characters/{cid}", json={"name": "新名字"})
    assert r2.status_code == 200
    assert r2.json()["name"] == "新名字"


@pytest.mark.asyncio
async def test_delete_character(client: AsyncClient):
    r = await client.post("/api/assets/characters", json={"name": "待删除"})
    cid = r.json()["id"]

    r2 = await client.delete(f"/api/assets/characters/{cid}")
    assert r2.status_code == 200

    r3 = await client.get(f"/api/assets/characters/{cid}")
    assert r3.status_code == 404


@pytest.mark.asyncio
async def test_create_scene(client: AsyncClient):
    response = await client.post("/api/assets/scenes", json={
        "name": "现代客厅",
        "description": "温馨的现代客厅",
        "environment_prompt": "a cozy modern living room",
        "mood": "温馨",
        "lighting": "柔和自然光",
        "tags": ["室内", "现代"],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "现代客厅"
    assert data["mood"] == "温馨"


@pytest.mark.asyncio
async def test_list_scenes(client: AsyncClient):
    await client.post("/api/assets/scenes", json={"name": "场景A"})
    await client.post("/api/assets/scenes", json={"name": "场景B"})

    response = await client.get("/api/assets/scenes")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_delete_scene(client: AsyncClient):
    r = await client.post("/api/assets/scenes", json={"name": "待删除场景"})
    sid = r.json()["id"]

    r2 = await client.delete(f"/api/assets/scenes/{sid}")
    assert r2.status_code == 200

    r3 = await client.get(f"/api/assets/scenes/{sid}")
    assert r3.status_code == 404


@pytest.mark.asyncio
async def test_project_character_link(client: AsyncClient):
    # 创建项目和角色
    pr = await client.post("/api/projects", json={"title": "测试项目"})
    pid = pr.json()["id"]
    cr = await client.post("/api/assets/characters", json={"name": "测试角色"})
    cid = cr.json()["id"]

    # 关联
    r = await client.post(f"/api/assets/projects/{pid}/characters", json={
        "character_id": cid,
        "custom_description": "在这个项目中角色穿红色衣服",
    })
    assert r.status_code == 200
    assert r.json()["character"]["name"] == "测试角色"
    assert r.json()["custom_description"] == "在这个项目中角色穿红色衣服"

    # 列表
    lr = await client.get(f"/api/assets/projects/{pid}/characters")
    assert len(lr.json()) == 1

    # 重复关联应失败
    dup = await client.post(f"/api/assets/projects/{pid}/characters", json={
        "character_id": cid,
    })
    assert dup.status_code == 400

    # 移除关联
    dr = await client.delete(f"/api/assets/projects/{pid}/characters/{cid}")
    assert dr.status_code == 200

    lr2 = await client.get(f"/api/assets/projects/{pid}/characters")
    assert len(lr2.json()) == 0


@pytest.mark.asyncio
async def test_project_scene_link(client: AsyncClient):
    pr = await client.post("/api/projects", json={"title": "测试项目"})
    pid = pr.json()["id"]
    sr = await client.post("/api/assets/scenes", json={"name": "测试场景"})
    sid = sr.json()["id"]

    r = await client.post(f"/api/assets/projects/{pid}/scenes", json={
        "scene_id": sid,
    })
    assert r.status_code == 200
    assert r.json()["scene"]["name"] == "测试场景"

    lr = await client.get(f"/api/assets/projects/{pid}/scenes")
    assert len(lr.json()) == 1

    dr = await client.delete(f"/api/assets/projects/{pid}/scenes/{sid}")
    assert dr.status_code == 200


@pytest.mark.asyncio
async def test_promote_character_to_global(client: AsyncClient):
    r = await client.post("/api/assets/characters", json={
        "name": "项目级角色",
        "is_global": False,
    })
    cid = r.json()["id"]
    assert r.json()["is_global"] is False

    # 升级
    pr = await client.post(f"/api/assets/characters/{cid}/promote", json={
        "name": "全局角色",
    })
    assert pr.status_code == 200
    assert pr.json()["is_global"] is True
    assert pr.json()["name"] == "全局角色"

    # 重复升级应失败
    dup = await client.post(f"/api/assets/characters/{cid}/promote", json={})
    assert dup.status_code == 400


@pytest.mark.asyncio
async def test_promote_scene_to_global(client: AsyncClient):
    r = await client.post("/api/assets/scenes", json={
        "name": "项目级场景",
        "is_global": False,
    })
    sid = r.json()["id"]

    pr = await client.post(f"/api/assets/scenes/{sid}/promote", json={})
    assert pr.status_code == 200
    assert pr.json()["is_global"] is True


@pytest.mark.asyncio
async def test_asset_stats(client: AsyncClient):
    await client.post("/api/assets/characters", json={"name": "全局角色", "is_global": True})
    await client.post("/api/assets/characters", json={"name": "项目角色", "is_global": False})
    await client.post("/api/assets/scenes", json={"name": "全局场景", "is_global": True})

    r = await client.get("/api/assets/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["characters"]["total"] == 2
    assert data["characters"]["global"] == 1
    assert data["characters"]["project_level"] == 1
    assert data["scenes"]["total"] == 1


@pytest.mark.asyncio
async def test_search_characters(client: AsyncClient):
    await client.post("/api/assets/characters", json={"name": "布偶猫", "description": "可爱的猫"})
    await client.post("/api/assets/characters", json={"name": "金毛犬", "description": "忠诚的狗"})

    # 搜索
    r = await client.get("/api/assets/characters?search=猫")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "布偶猫"


@pytest.mark.asyncio
async def test_project_asset_integration(client: AsyncClient):
    """测试完整的项目-资产关联流程：创建角色/场景 → 关联到项目 → 验证关联信息"""
    # 创建项目
    proj_r = await client.post("/api/projects", json={"title": "资产集成测试"})
    project_id = proj_r.json()["id"]

    # 创建角色（带 appearance_prompt 和 voice_type）
    char_r = await client.post("/api/assets/characters", json={
        "name": "测试角色",
        "appearance_prompt": "A young girl with long black hair",
        "voice_type": "BV700_streaming",
        "reference_images": ["http://example.com/img1.jpg"],
        "tags": ["主角"],
    })
    char_id = char_r.json()["id"]

    # 创建场景（带 environment_prompt）
    scene_r = await client.post("/api/assets/scenes", json={
        "name": "测试场景",
        "environment_prompt": "A tranquil bamboo forest with morning mist",
        "mood": "peaceful",
        "lighting": "soft morning light",
    })
    scene_id = scene_r.json()["id"]

    # 关联角色到项目
    link_char = await client.post(f"/api/assets/projects/{project_id}/characters", json={
        "character_id": char_id,
    })
    assert link_char.status_code == 200
    assert link_char.json()["character"]["name"] == "测试角色"
    assert link_char.json()["character"]["appearance_prompt"] == "A young girl with long black hair"

    # 关联场景到项目
    link_scene = await client.post(f"/api/assets/projects/{project_id}/scenes", json={
        "scene_id": scene_id,
    })
    assert link_scene.status_code == 200
    assert link_scene.json()["scene"]["name"] == "测试场景"

    # 查询项目的角色
    chars_list = await client.get(f"/api/assets/projects/{project_id}/characters")
    assert chars_list.status_code == 200
    assert len(chars_list.json()) == 1
    pc = chars_list.json()[0]
    assert pc["character"]["voice_type"] == "BV700_streaming"
    assert pc["character"]["reference_images"] == ["http://example.com/img1.jpg"]

    # 查询项目的场景
    scenes_list = await client.get(f"/api/assets/projects/{project_id}/scenes")
    assert scenes_list.status_code == 200
    assert len(scenes_list.json()) == 1
    ps = scenes_list.json()[0]
    assert ps["scene"]["environment_prompt"] == "A tranquil bamboo forest with morning mist"
    assert ps["scene"]["mood"] == "peaceful"

    # 关联角色带自定义覆盖
    char2_r = await client.post("/api/assets/characters", json={"name": "角色2"})
    char2_id = char2_r.json()["id"]
    link2 = await client.post(f"/api/assets/projects/{project_id}/characters", json={
        "character_id": char2_id,
        "custom_appearance_prompt": "Overridden prompt for project",
        "custom_voice_type": "BV001_streaming",
    })
    assert link2.status_code == 200
    assert link2.json()["custom_appearance_prompt"] == "Overridden prompt for project"
    assert link2.json()["custom_voice_type"] == "BV001_streaming"

    # 验证总数
    chars_all = await client.get(f"/api/assets/projects/{project_id}/characters")
    assert len(chars_all.json()) == 2

    # 移除一个角色
    del_r = await client.delete(f"/api/assets/projects/{project_id}/characters/{char_id}")
    assert del_r.status_code == 200

    # 验证剩余
    chars_remain = await client.get(f"/api/assets/projects/{project_id}/characters")
    assert len(chars_remain.json()) == 1
    assert chars_remain.json()[0]["character_id"] == char2_id
