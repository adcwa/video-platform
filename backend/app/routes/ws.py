"""WebSocket 路由 - 实时任务状态推送"""

import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db, async_session
from backend.app.models import Project, Shot, ShotStatus, ProjectStatus
from backend.app.services import seedance_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # project_id -> set of websocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: str):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = set()
        self.active_connections[project_id].add(websocket)
        logger.info(f"WebSocket 连接: project={project_id}, 当前连接数={len(self.active_connections[project_id])}")

    def disconnect(self, websocket: WebSocket, project_id: str):
        if project_id in self.active_connections:
            self.active_connections[project_id].discard(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]
        logger.info(f"WebSocket 断开: project={project_id}")

    async def broadcast(self, project_id: str, message: dict):
        if project_id not in self.active_connections:
            return
        dead_connections = set()
        for connection in self.active_connections[project_id]:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)
        for conn in dead_connections:
            self.active_connections[project_id].discard(conn)


manager = ConnectionManager()


@router.websocket("/ws/projects/{project_id}")
async def project_websocket(websocket: WebSocket, project_id: str):
    """
    项目实时状态 WebSocket

    客户端连接后自动轮询所有 generating 状态的 shot，
    每5秒检查一次任务状态并推送更新
    """
    await manager.connect(websocket, project_id)
    try:
        while True:
            # 等待客户端消息或超时
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                msg = json.loads(data)

                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                if msg.get("type") == "refresh":
                    # 客户端请求刷新状态
                    await _poll_and_broadcast(project_id)
                    continue

            except asyncio.TimeoutError:
                pass  # 超时后执行自动轮询

            # 自动轮询 generating 状态的 shot
            await _poll_and_broadcast(project_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id)
    except Exception as e:
        logger.error(f"WebSocket 异常: {e}")
        manager.disconnect(websocket, project_id)


async def _poll_and_broadcast(project_id: str):
    """轮询视频生成状态并广播更新"""
    try:
        async with async_session() as db:
            result = await db.execute(
                select(Shot).where(
                    Shot.project_id == project_id,
                    Shot.status == ShotStatus.GENERATING.value,
                )
            )
            generating_shots = result.scalars().all()

            if not generating_shots:
                return

            updates = []
            for shot in generating_shots:
                if not shot.video_task_id:
                    continue
                try:
                    task_data = await seedance_service.query_video_task(shot.video_task_id)
                    status = task_data.get("status", "unknown")

                    if status == "succeeded":
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

                        updates.append({
                            "type": "shot_update",
                            "shot_id": shot.id,
                            "sequence": shot.sequence,
                            "status": "completed",
                            "video_url": video_url,
                            "last_frame_url": last_frame_url,
                        })

                    elif status == "failed":
                        shot.status = ShotStatus.FAILED.value
                        error_msg = task_data.get("error", {}).get("message", "生成失败")
                        updates.append({
                            "type": "shot_update",
                            "shot_id": shot.id,
                            "sequence": shot.sequence,
                            "status": "failed",
                            "error": error_msg,
                        })

                    else:
                        updates.append({
                            "type": "shot_update",
                            "shot_id": shot.id,
                            "sequence": shot.sequence,
                            "status": status,
                        })

                except Exception as e:
                    logger.error(f"轮询分镜 {shot.id} 状态失败: {e}")

            await db.commit()

            # 广播所有更新
            for update in updates:
                await manager.broadcast(project_id, update)

            # 检查是否所有 shot 都已完成
            all_result = await db.execute(
                select(Shot).where(Shot.project_id == project_id)
            )
            all_shots = all_result.scalars().all()
            if all_shots and all(
                s.status in (ShotStatus.COMPLETED.value, ShotStatus.FAILED.value)
                for s in all_shots
            ):
                await manager.broadcast(project_id, {
                    "type": "all_shots_done",
                    "completed": sum(1 for s in all_shots if s.status == ShotStatus.COMPLETED.value),
                    "failed": sum(1 for s in all_shots if s.status == ShotStatus.FAILED.value),
                    "total": len(all_shots),
                })

    except Exception as e:
        logger.error(f"轮询状态异常: {e}")


async def notify_project_update(project_id: str, message: dict):
    """供其他模块调用：向项目的所有 WebSocket 客户端发送通知"""
    await manager.broadcast(project_id, message)
