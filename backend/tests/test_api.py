"""Backend API Tests"""

import io
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.database import init_db, engine, Base


@pytest_asyncio.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


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
