"""火山引擎 Seedance 视频生成服务"""

import logging
import httpx
from backend.app.config import settings

logger = logging.getLogger(__name__)


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
        content.append({
            "type": "image_url",
            "image_url": {"url": first_frame_url},
            "role": "first_frame",
        })

    # 添加尾帧图片
    if last_frame_url:
        content.append({
            "type": "image_url",
            "image_url": {"url": last_frame_url},
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
