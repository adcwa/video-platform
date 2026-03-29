"""FFmpeg 视频处理服务 - 拼接、合并音频、字幕烧录"""

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


async def get_media_duration(file_path: str) -> float:
    """获取音频或视频文件的实际时长（秒）"""
    _check_ffmpeg()
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path,
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


async def _merge_shot_audio_video(
    video_path: str,
    audio_path: str,
    output_path: str,
) -> str:
    """
    单个镜头的音视频对齐合并。
    策略：
      - 音频 <= 视频：音频正常播放，视频剩余部分静音
      - 音频 > 视频：冻结视频最后一帧延长至音频结束
    用 -filter_complex 实现精确控制，不用 -shortest。
    """
    _check_ffmpeg()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    video_dur = await get_media_duration(video_path)
    audio_dur = await get_media_duration(audio_path)

    if video_dur <= 0:
        raise RuntimeError(f"无法获取视频时长: {video_path}")

    if audio_dur <= 0:
        # 音频无效，直接复制视频
        shutil.copy2(video_path, output_path)
        return output_path

    if audio_dur <= video_dur:
        # 音频 <= 视频：正常合并，视频保持原长度，替换音轨
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex",
            # 用 adelay=0 确保音频从头开始，apad 补静音到视频长度
            f"[1:a]apad=whole_dur={video_dur}[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-t", str(video_dur),
            output_path,
        ]
    else:
        # 音频 > 视频：冻结最后一帧延长视频到音频时长
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex",
            f"[0:v]tpad=stop_mode=clone:stop_duration={audio_dur - video_dur}[vout]",
            "-map", "[vout]",
            "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac",
            "-t", str(audio_dur),
            output_path,
        ]

    logger.info(
        f"合并镜头: 视频={video_dur:.1f}s 音频={audio_dur:.1f}s → "
        f"{'视频延长' if audio_dur > video_dur else '音频补静音'}"
    )

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        logger.error(f"镜头音视频合并失败: {stderr.decode()[:500]}")
        raise RuntimeError(f"镜头合并失败: {stderr.decode()[:300]}")

    return output_path


def _generate_srt(
    shots_timing: list[dict],
) -> str:
    """
    生成 SRT 字幕文件内容。

    Args:
        shots_timing: [{"start": 0.0, "end": 5.0, "dialogue": "..."}]

    Returns:
        SRT 格式字符串
    """
    lines = []
    idx = 1
    for item in shots_timing:
        dialogue = (item.get("dialogue") or "").strip()
        if not dialogue:
            continue
        start = item["start"]
        end = item["end"]

        def fmt(t: float) -> str:
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = int(t % 60)
            ms = int((t - int(t)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        lines.append(str(idx))
        lines.append(f"{fmt(start)} --> {fmt(end)}")
        lines.append(dialogue)
        lines.append("")
        idx += 1

    return "\n".join(lines)


def _generate_ass(
    shots_timing: list[dict],
    video_width: int = 1280,
    video_height: int = 720,
    font_name: str = "PingFang SC",
    font_size: int = 20,
    primary_color: str = "&H00FFFFFF",  # 白色 AABBGGRR
    outline_color: str = "&H00000000",  # 黑色描边
    outline_width: int = 2,
    margin_bottom: int = 40,
) -> str:
    """
    生成 ASS 字幕文件（支持更丰富的样式）。

    Args:
        shots_timing: [{"start": 0.0, "end": 5.0, "dialogue": "..."}]
        video_width/height: 视频分辨率
        font_name: 字体名（macOS: PingFang SC, Windows: Microsoft YaHei）
        font_size: 字号
        primary_color: 字体颜色 ASS格式 &HAABBGGRR
        outline_color: 描边颜色
        outline_width: 描边宽度
        margin_bottom: 底部边距

    Returns:
        ASS 格式字符串
    """
    header = f"""[Script Info]
Title: Video Subtitles
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},&H80000000,0,0,0,0,100,100,0,0,1,{outline_width},1,2,20,20,{margin_bottom},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    for item in shots_timing:
        dialogue = (item.get("dialogue") or "").strip()
        if not dialogue:
            continue
        start = item["start"]
        end = item["end"]

        def fmt_ass(t: float) -> str:
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = int(t % 60)
            cs = int((t - int(t)) * 100)
            return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

        # 替换换行为 ASS 换行标记
        text = dialogue.replace("\n", "\\N")
        events.append(
            f"Dialogue: 0,{fmt_ass(start)},{fmt_ass(end)},Default,,0,0,0,,{text}"
        )

    return header + "\n".join(events) + "\n"


async def _burn_subtitles(
    video_path: str,
    subtitle_path: str,
    output_path: str,
    shots_timing: list[dict] | None = None,
    font_size: int = 20,
    margin_bottom: int = 40,
) -> str:
    """
    将字幕烧录到视频中。
    直接使用 drawtext 滤镜（兼容性最好，不依赖 libass）。
    如果 drawtext 也失败，回退到无字幕版本。
    """
    _check_ffmpeg()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if not shots_timing:
        # 无时间轴数据，直接复制
        shutil.copy2(video_path, output_path)
        return output_path

    # 使用 drawtext 逐条烧录（最可靠的方式）
    vf = _build_drawtext_filter(shots_timing, font_size, margin_bottom)
    if not vf:
        # 没有实际对白，直接复制
        shutil.copy2(video_path, output_path)
        return output_path

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "copy",
        output_path,
    ]

    logger.info(f"烧录字幕 (drawtext 滤镜, {sum(1 for t in shots_timing if t.get('dialogue'))} 条)")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        err_msg = stderr.decode()[:500]
        logger.error(f"字幕烧录失败: {err_msg}")
        # 回退到无字幕版本，不要因为字幕失败而中断整个合成
        logger.warning("字幕烧录失败，输出无字幕版本")
        shutil.copy2(video_path, output_path)
        return output_path

    logger.info(f"字幕烧录完成: {output_path}")
    return output_path


def _build_drawtext_filter(
    shots_timing: list[dict],
    font_size: int = 20,
    margin_bottom: int = 40,
) -> str:
    """
    构建 drawtext 滤镜链，为每条对白生成一个 enable='between(t,start,end)' 的 drawtext。
    使用白色文字 + 黑色描边，底部居中。
    需要显式指定 fontfile（ffmpeg 4.x 强制要求）。
    """
    import platform

    # 根据操作系统选择中文字体文件路径
    font_path = ""
    if platform.system() == "Darwin":
        # macOS 字体优先级
        for candidate in [
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/PingFang.ttc",
        ]:
            if Path(candidate).exists():
                font_path = candidate
                break
    elif platform.system() == "Linux":
        for candidate in [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]:
            if Path(candidate).exists():
                font_path = candidate
                break

    if not font_path:
        logger.warning("未找到可用的中文字体文件，字幕可能显示为方块")

    parts = []
    for item in shots_timing:
        dialogue = (item.get("dialogue") or "").strip()
        if not dialogue:
            continue
        start = item["start"]
        end = item["end"]

        # 转义 drawtext 特殊字符
        # drawtext 的 text 参数使用 : 作为选项分隔符，需要转义
        escaped = dialogue.replace("\\", "\\\\\\\\")
        escaped = escaped.replace("'", "'\\\\\\''")
        escaped = escaped.replace(":", "\\:")
        escaped = escaped.replace("%", "%%")
        escaped = escaped.replace("\n", " ")  # drawtext 不支持 \n，用空格替代

        # 构建单条 drawtext 滤镜
        dt = f"drawtext=text='{escaped}'"
        if font_path:
            # fontfile 路径中的冒号和特殊字符也需要转义
            escaped_font = font_path.replace(":", "\\:")
            dt += f":fontfile='{escaped_font}'"
        dt += f":fontsize={font_size}"
        dt += f":fontcolor=white"
        dt += f":borderw=2"
        dt += f":bordercolor=black"
        dt += f":x=(w-text_w)/2"
        dt += f":y=h-{margin_bottom}-text_h"
        dt += f":enable='between(t,{start:.3f},{end:.3f})'"

        parts.append(dt)

    return ",".join(parts) if parts else ""


async def concatenate_videos(
    video_paths: list[str],
    output_path: str,
) -> str:
    """拼接多个视频片段（要求所有片段编码一致时用 -c copy，否则重新编码）"""
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

    # 先尝试 -c copy 快速拼接
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
        # copy 失败（编码不一致），回退到重新编码拼接
        logger.warning("快速拼接失败，回退到重编码拼接")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac",
            output_path,
        ]
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


async def compose_project_video(
    shots_data: list[dict],
    project_id: str,
    include_subtitles: bool = False,
    subtitle_style: dict | None = None,
) -> dict:
    """
    完整的项目视频合成流程（音频 ↔ 视频 精确同步 + 可选字幕）。

    核心策略：**逐镜头对齐**，而非全局拼接后合并。
      对每个镜头：
        - 有音频：音频短则补静音到视频长度；音频长则冻结视频末帧延长
        - 无音频：保持视频原样
      然后拼接所有已对齐的镜头片段，保证每个镜头的音视频完美同步。
      最后（可选）根据对白文本和时间轴烧录字幕。

    Args:
        shots_data: [{"sequence": 1, "video_url": "...", "audio_path": "...", "dialogue": "..."}]
        project_id: 项目ID
        include_subtitles: 是否烧录字幕
        subtitle_style: 字幕样式配置 {"font_size": 22, "margin_bottom": 40, ...}

    Returns:
        {"output_video_path": "...", "output_video_url": "...", "duration": float}
    """
    project_dir = Path(settings.temp_dir) / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    sorted_shots = sorted(shots_data, key=lambda x: x["sequence"])

    # ========== 第一步：下载所有视频 ==========
    download_map = {}  # sequence -> local_video_path
    for shot in sorted_shots:
        if not shot.get("video_url"):
            continue
        local_path = str(project_dir / f"shot_{shot['sequence']:03d}.mp4")
        await download_file(shot["video_url"], local_path)
        download_map[shot["sequence"]] = local_path

    if not download_map:
        raise ValueError("没有可用的视频片段")

    # ========== 第二步：逐镜头音视频对齐 ==========
    aligned_paths = []  # 对齐后的视频路径列表（含音轨或无音轨）
    shots_timing = []   # 字幕时间轴 [{"start": 0, "end": 5, "dialogue": "..."}]
    current_time = 0.0

    for shot in sorted_shots:
        seq = shot["sequence"]
        video_path = download_map.get(seq)
        if not video_path:
            continue

        audio_path = shot.get("audio_path")
        dialogue = shot.get("dialogue", "")
        has_valid_audio = audio_path and Path(audio_path).exists()

        if has_valid_audio:
            # 音频存在 → 对齐合并
            aligned_path = str(project_dir / f"aligned_{seq:03d}.mp4")
            try:
                await _merge_shot_audio_video(video_path, audio_path, aligned_path)
                aligned_paths.append(aligned_path)
                # 获取对齐后的实际时长（可能因冻结延长）
                shot_duration = await get_media_duration(aligned_path)
            except Exception as e:
                logger.warning(f"镜头 {seq} 音视频对齐失败，使用纯视频: {e}")
                aligned_paths.append(video_path)
                shot_duration = await get_media_duration(video_path)
        else:
            # 无音频 → 直接使用原视频
            aligned_paths.append(video_path)
            shot_duration = await get_media_duration(video_path)

        if shot_duration <= 0:
            shot_duration = shot.get("duration", 5)

        # 记录字幕时间轴
        shots_timing.append({
            "start": current_time,
            "end": current_time + shot_duration,
            "dialogue": dialogue,
        })
        current_time += shot_duration
        logger.info(f"镜头 {seq}: 实际时长 {shot_duration:.2f}s, 累计 {current_time:.2f}s")

    # ========== 第三步：拼接所有已对齐的片段 ==========
    if len(aligned_paths) == 1:
        concat_path = aligned_paths[0]
    else:
        concat_path = str(project_dir / "concatenated.mp4")
        await concatenate_videos(aligned_paths, concat_path)

    # ========== 第四步：（可选）烧录字幕 ==========
    output_filename = f"{project_id}_final.mp4"
    output_path = str(Path(settings.output_dir) / output_filename)

    if include_subtitles and any(item.get("dialogue") for item in shots_timing):
        # 获取视频分辨率用于 ASS
        res = await _get_video_resolution(concat_path)
        style = subtitle_style or {}
        ass_content = _generate_ass(
            shots_timing,
            video_width=res[0],
            video_height=res[1],
            font_name=style.get("font_name", "PingFang SC"),
            font_size=style.get("font_size", 20),
            outline_width=style.get("outline_width", 2),
            margin_bottom=style.get("margin_bottom", 40),
        )
        ass_path = str(project_dir / "subtitles.ass")
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        # 同时生成 SRT 备份（可下载）
        srt_content = _generate_srt(shots_timing)
        srt_path = str(project_dir / "subtitles.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        await _burn_subtitles(
            concat_path, ass_path, output_path,
            shots_timing=shots_timing,
            font_size=style.get("font_size", 20),
            margin_bottom=style.get("margin_bottom", 40),
        )
        logger.info(f"字幕烧录完成，共 {sum(1 for t in shots_timing if t.get('dialogue'))} 条")
    else:
        if concat_path != output_path:
            shutil.copy2(concat_path, output_path)

    duration = await get_media_duration(output_path)

    # 生成字幕文件URL（如果有）
    srt_url = ""
    srt_file = project_dir / "subtitles.srt"
    if srt_file.exists():
        # 复制到 outputs 目录供下载
        srt_output = Path(settings.output_dir) / f"{project_id}_subtitles.srt"
        shutil.copy2(str(srt_file), str(srt_output))
        srt_url = f"/files/outputs/{project_id}_subtitles.srt"

    return {
        "output_video_path": output_path,
        "output_video_url": f"/files/outputs/{output_filename}",
        "duration": duration,
        "subtitle_url": srt_url,
    }


async def _get_video_resolution(video_path: str) -> tuple[int, int]:
    """获取视频分辨率"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        video_path,
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    try:
        parts = stdout.decode().strip().split("x")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 1280, 720


# Legacy aliases
async def get_video_duration(video_path: str) -> float:
    """获取视频时长（秒）- 兼容旧接口"""
    return await get_media_duration(video_path)


async def merge_audio_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    audio_offset: float = 0,
) -> str:
    """合并音频和视频 - 兼容旧接口，新代码请用 _merge_shot_audio_video"""
    return await _merge_shot_audio_video(video_path, audio_path, output_path)
