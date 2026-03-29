"""FFmpeg 视频处理服务 - 拼接、合并音频"""

import asyncio
import logging
import shutil
import subprocess
from pathlib import Path

import httpx

from backend.app.config import settings

logger = logging.getLogger(__name__)


def _check_ffmpeg():
    """检查FFmpeg是否可用"""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg未安装或不在PATH中。请安装FFmpeg: brew install ffmpeg")


async def download_file(url: str, output_path: str) -> str:
    """下载文件到本地"""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)
    return output_path


async def concatenate_videos(
    video_paths: list[str],
    output_path: str,
    transition: str = "none",
) -> str:
    """
    拼接多个视频片段

    Args:
        video_paths: 视频文件路径列表（有序）
        output_path: 输出文件路径
        transition: 转场效果 (none/fade/crossfade)

    Returns:
        输出文件路径
    """
    _check_ffmpeg()

    if not video_paths:
        raise ValueError("无视频片段可拼接")

    if len(video_paths) == 1:
        shutil.copy2(video_paths[0], output_path)
        return output_path

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # 创建文件列表
    list_file = Path(settings.temp_dir) / "concat_list.txt"
    with open(list_file, "w") as f:
        for vp in video_paths:
            f.write(f"file '{Path(vp).resolve()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        output_path,
    ]

    logger.info(f"拼接 {len(video_paths)} 个视频片段...")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        logger.error(f"FFmpeg拼接失败: {stderr.decode()}")
        raise RuntimeError(f"视频拼接失败: {stderr.decode()[:500]}")

    logger.info(f"视频拼接完成: {output_path}")
    return output_path


async def merge_audio_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    audio_offset: float = 0,
) -> str:
    """
    合并音频和视频

    Args:
        video_path: 视频文件路径
        audio_path: 音频文件路径
        output_path: 输出文件路径
        audio_offset: 音频偏移（秒）

    Returns:
        输出文件路径
    """
    _check_ffmpeg()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path,
    ]

    if audio_offset > 0:
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-itsoffset", str(audio_offset),
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_path,
        ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        logger.error(f"音视频合并失败: {stderr.decode()}")
        raise RuntimeError(f"音视频合并失败: {stderr.decode()[:500]}")

    logger.info(f"音视频合并完成: {output_path}")
    return output_path


async def get_video_duration(video_path: str) -> float:
    """获取视频时长（秒）"""
    _check_ffmpeg()

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        return 0.0

    try:
        return float(stdout.decode().strip())
    except ValueError:
        return 0.0


async def compose_project_video(
    shots_data: list[dict],
    project_id: str,
) -> dict:
    """
    完整的项目视频合成流程：
    1. 下载所有镜头视频
    2. 拼接视频
    3. 合并TTS音频（如有）
    4. 输出最终视频

    Args:
        shots_data: [{video_url, audio_path, sequence}, ...]
        project_id: 项目ID

    Returns:
        {"output_video_path": "...", "output_video_url": "...", "duration": 0}
    """
    project_dir = Path(settings.temp_dir) / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    # 1. 下载所有视频
    video_paths = []
    for shot in sorted(shots_data, key=lambda x: x["sequence"]):
        if not shot.get("video_url"):
            continue
        local_path = str(project_dir / f"shot_{shot['sequence']:03d}.mp4")
        await download_file(shot["video_url"], local_path)
        video_paths.append(local_path)

    if not video_paths:
        raise ValueError("没有可用的视频片段")

    # 2. 拼接视频
    concat_path = str(project_dir / "concatenated.mp4")
    await concatenate_videos(video_paths, concat_path)

    # 3. 合并TTS音频
    output_filename = f"{project_id}_final.mp4"
    output_path = str(Path(settings.output_dir) / output_filename)

    has_audio = any(shot.get("audio_path") for shot in shots_data)
    if has_audio:
        # 先拼接所有音频
        audio_paths = [
            shot["audio_path"]
            for shot in sorted(shots_data, key=lambda x: x["sequence"])
            if shot.get("audio_path")
        ]
        if audio_paths:
            concat_audio_path = str(project_dir / "audio_concat.mp3")
            audio_list_file = project_dir / "audio_list.txt"
            with open(audio_list_file, "w") as f:
                for ap in audio_paths:
                    f.write(f"file '{Path(ap).resolve()}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(audio_list_file),
                "-c", "copy",
                concat_audio_path,
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()

            await merge_audio_video(concat_path, concat_audio_path, output_path)
        else:
            shutil.copy2(concat_path, output_path)
    else:
        shutil.copy2(concat_path, output_path)

    duration = await get_video_duration(output_path)

    return {
        "output_video_path": output_path,
        "output_video_url": f"/files/outputs/{output_filename}",
        "duration": duration,
    }
