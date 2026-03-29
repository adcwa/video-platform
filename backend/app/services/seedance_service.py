"""火山引擎 Seedance 视频生成服务"""

import base64
import logging
import mimetypes
from pathlib import Path

import httpx
from backend.app.config import settings

logger = logging.getLogger(__name__)


def _resolve_frame_url(url: str) -> str:
    """
    将帧图片URL转换为Seedance API可用格式。
    公网URL直接返回，本地路径转为base64 data URL。
    """
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://") or url.startswith("data:"):
        return url

    # 本地路径：/files/uploads/xxx → data/uploads/xxx
    local_path = url.replace("/files/", "data/", 1) if url.startswith("/files/") else url
    p = Path(local_path)
    if not p.exists():
        logger.warning(f"帧图片文件不存在: {local_path}")
        return ""

    mime_type = mimetypes.guess_type(str(p))[0] or "image/png"
    with open(p, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"


async def create_video_task(
    prompt: str,
    model: str | None = None,
    first_frame_url: str | None = None,
    last_frame_url: str | None = None,
    duration: int = 5,
    ratio: str = "16:9",
    resolution: str = "720p",
    generate_audio: bool = True,
    return_last_frame: bool = True,
    camera_fixed: bool = False,
    seed: int = -1,
) -> dict:
    """
    创建视频生成任务

    Returns:
        {"id": "task_id", ...}
    """
    model_id = model or settings.seedance_model_id

    content = []

    # 添加文本提示词
    content.append({
        "type": "text",
        "text": prompt,
    })

    # 添加首帧图片
    if first_frame_url:
        resolved_first = _resolve_frame_url(first_frame_url)
        if resolved_first:
            content.append({
                "type": "image_url",
                "image_url": {"url": resolved_first},
                "role": "first_frame",
            })

    # 添加尾帧图片
    if last_frame_url:
        resolved_last = _resolve_frame_url(last_frame_url)
        if resolved_last:
            content.append({
                "type": "image_url",
                "image_url": {"url": resolved_last},
                "role": "last_frame",
            })

    payload = {
        "model": model_id,
        "content": content,
        "duration": duration,
        "ratio": ratio,
        "resolution": resolution,
        "generate_audio": generate_audio,
        "return_last_frame": return_last_frame,
        "camera_fixed": camera_fixed,
        "seed": seed,
        "watermark": False,
    }

    headers = {
        "Authorization": f"Bearer {settings.doubao_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.seedance_api_base}/contents/generations/tasks",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"视频生成任务已创建: {data.get('id', 'unknown')}")
            return data

    except httpx.HTTPStatusError as e:
        logger.error(f"视频生成任务创建失败: {e.response.status_code} - {e.response.text}")
        raise RuntimeError(f"视频生成任务创建失败: {e.response.status_code}")
    except Exception as e:
        logger.error(f"视频生成异常: {e}")
        raise


async def query_video_task(task_id: str) -> dict:
    """
    查询视频生成任务状态

    Returns:
        {"id": "task_id", "status": "...", "video_url": "...", ...}
    """
    headers = {
        "Authorization": f"Bearer {settings.doubao_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{settings.seedance_api_base}/contents/generations/tasks/{task_id}",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data

    except httpx.HTTPStatusError as e:
        logger.error(f"查询视频任务失败: {e.response.status_code} - {e.response.text}")
        raise RuntimeError(f"查询视频任务失败: {e.response.status_code}")
    except Exception as e:
        logger.error(f"查询视频任务异常: {e}")
        raise
