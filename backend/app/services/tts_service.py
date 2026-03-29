"""豆包 TTS 语音合成服务"""

import base64
import json
import logging
import uuid
from pathlib import Path

import httpx

from backend.app.config import settings

logger = logging.getLogger(__name__)


async def synthesize_speech(
    text: str,
    voice_type: str | None = None,
    speed_ratio: float = 1.0,
    volume_ratio: float = 1.0,
    pitch_ratio: float = 1.0,
    encoding: str = "mp3",
    output_dir: str | None = None,
) -> dict:
    """
    使用豆包TTS合成语音

    Args:
        text: 合成文本
        voice_type: 音色类型
        speed_ratio: 语速
        volume_ratio: 音量
        pitch_ratio: 音高
        encoding: 编码格式 (mp3/wav/pcm/ogg_opus)
        output_dir: 输出目录

    Returns:
        {"audio_path": "...", "audio_url": "...", "duration": 0, "reqid": "..."}
    """
    reqid = str(uuid.uuid4())
    voice = voice_type or settings.doubao_voice_type
    out_dir = output_dir or settings.output_dir
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    payload = {
        "app": {
            "appid": settings.doubao_api_id,
            "token": "access_token",
            "cluster": settings.doubao_cluster_id,
        },
        "user": {
            "uid": "video-platform-user",
        },
        "audio": {
            "voice_type": voice,
            "encoding": encoding,
            "rate": 24000,
            "speed_ratio": speed_ratio,
            "volume_ratio": volume_ratio,
            "pitch_ratio": pitch_ratio,
        },
        "request": {
            "reqid": reqid,
            "text": text,
            "text_type": "plain",
            "operation": "query",
            "silence_duration": "125",
            "with_frontend": "1",
            "frontend_type": "unitTson",
        },
    }

    headers = {
        "Authorization": f"Bearer;{settings.doubao_access_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                settings.tts_api_url,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != 3000:
            raise RuntimeError(f"TTS合成失败: {data.get('message', 'unknown error')}")

        # 解码音频数据
        audio_data = base64.b64decode(data.get("data", ""))
        audio_filename = f"{reqid}.{encoding}"
        audio_path = Path(out_dir) / audio_filename

        with open(audio_path, "wb") as f:
            f.write(audio_data)

        # 获取时长
        duration_ms = 0
        addition = data.get("addition", {})
        if isinstance(addition, dict):
            duration_ms = int(addition.get("duration", "0"))
        duration_sec = duration_ms / 1000.0

        logger.info(f"TTS合成成功: {audio_filename}, 时长: {duration_sec}s")

        return {
            "audio_path": str(audio_path),
            "audio_url": f"/files/outputs/{audio_filename}",
            "duration": duration_sec,
            "reqid": reqid,
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"TTS API调用失败: {e.response.status_code} - {e.response.text}")
        raise RuntimeError(f"TTS服务调用失败: {e.response.status_code}")
    except Exception as e:
        logger.error(f"TTS合成异常: {e}")
        raise
