"""豆包大模型服务 - 脚本生成、场景识别"""

import base64
import json
import logging
import mimetypes
from pathlib import Path

import httpx
from backend.app.config import settings

logger = logging.getLogger(__name__)


def _resolve_image_url(url: str) -> str:
    """
    将图片URL转换为豆包API可用的格式。

    - 如果已经是 http(s):// 的公网URL，直接返回。
    - 如果是本地路径（如 /files/uploads/images/xxx.png），
      读取文件并转成 base64 data URL。
    """
    if url.startswith("http://") or url.startswith("https://"):
        return url

    # 本地路径：/files/uploads/xxx → data/uploads/xxx
    local_path = url.replace("/files/", "data/", 1) if url.startswith("/files/") else url
    p = Path(local_path)
    if not p.exists():
        logger.warning(f"图片文件不存在，跳过: {local_path}")
        return ""

    mime_type = mimetypes.guess_type(str(p))[0] or "image/png"
    with open(p, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"
    logger.info(f"图片已转为 base64 data URL: {p.name} ({len(b64) // 1024}KB)")
    return data_url

# 场景预设提示词
SCENE_PROMPTS = {
    "entertainment": """你是一位专业的短视频编剧，擅长为视频号、小红书、抖音等平台创作引人入胜的视频脚本。
风格特点：节奏快、内容有趣、情感共鸣强、适合竖屏观看。""",
    "research": """你是一位专业的学术视频策划师，擅长将复杂的科研内容转化为清晰易懂的视频脚本。
风格特点：逻辑清晰、专业严谨、数据可视化、适合横屏观看。""",
}

SCRIPT_SYSTEM_PROMPT = """你是一个专业的AI视频脚本生成器。请根据用户提供的主题、场景类型和其他信息，生成一个完整的视频脚本。

你必须返回一个严格的JSON格式，包含以下字段：
{
  "title": "视频标题",
  "synopsis": "视频简介（1-2句话）",
  "style_description": "整体视觉风格描述（色调、光线、画面风格、氛围等），用于确保所有镜头视觉一致",
  "characters": ["角色1", "角色2"],
  "objects": ["关键物品1", "关键物品2"],
  "shots": [
    {
      "sequence": 1,
      "description": "详细的视频画面描述，用于视频生成模型。描述场景、动作、光线、氛围等。务必在描述开头包含整体风格关键词，确保与其他镜头视觉一致。",
      "dialogue": "这个镜头的旁白或对白文本（如果有）",
      "duration": 5,
      "camera_note": "镜头运动说明（如：缓慢推进、固定机位等）"
    }
  ]
}

关键要求：
1. 每个镜头时长控制在3-8秒之间
2. 镜头描述要具体、生动，适合作为视频生成的提示词
3. 对白要自然流畅
4. 所有镜头总时长应接近用户指定的目标时长
5. **极其重要：所有镜头必须保持视觉风格一致性！** 包括色调、光线、画面质感、角色外观、背景风格。每个镜头描述都应包含统一的风格前缀，如"暖色调，自然光，手绘卡通风格，..."
6. 如果用户上传了参考图片，必须分析图片的视觉风格（色彩、光线、画面风格），并将该风格应用到所有镜头描述中
7. 仅返回JSON，不要包含其他文本"""


async def generate_script(
    theme: str,
    scene_type: str = "entertainment",
    target_duration: int = 30,
    additional_context: str = "",
    image_urls: list[str] | None = None,
) -> dict:
    """
    使用豆包大模型生成视频脚本

    Args:
        theme: 视频主题
        scene_type: 场景类型 (entertainment/research)
        target_duration: 目标时长（秒）
        additional_context: 额外上下文
        image_urls: 参考图片URL列表

    Returns:
        解析后的脚本JSON
    """
    scene_prompt = SCENE_PROMPTS.get(scene_type, SCENE_PROMPTS["entertainment"])

    user_content = []

    # 如果有图片，添加图片分析
    if image_urls:
        for url in image_urls:
            resolved = _resolve_image_url(url)
            if resolved:
                user_content.append({
                    "type": "input_image",
                    "image_url": resolved,
                })

    user_text = f"""{scene_prompt}

请为以下主题创作一个视频脚本：

【主题】{theme}
【目标总时长】约{target_duration}秒
【场景类型】{"娱乐发布" if scene_type == "entertainment" else "科研研究"}
"""
    if additional_context:
        user_text += f"\n【额外信息】{additional_context}"

    if image_urls:
        user_text += "\n\n请仔细分析上传的图片，从中提取：\n1. 角色外观（衣着、发型、体型等具体细节）\n2. 关键物品\n3. 视觉风格（色调、光线、画面风格）\n4. 场景/背景环境\n将这些信息融入脚本，确保每个镜头都与图片的视觉风格保持一致。"

    user_content.append({
        "type": "input_text",
        "text": user_text,
    })

    payload = {
        "model": settings.doubao_model_id,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SCRIPT_SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {settings.doubao_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.seedance_api_base}/responses",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        # 提取模型输出文本
        output_text = ""
        if "output" in data:
            for item in data["output"]:
                if item.get("type") == "message":
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            output_text += content.get("text", "")

        # 解析JSON
        # 处理可能的 markdown 代码块包裹
        clean_text = output_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]

        script_data = json.loads(clean_text.strip())
        logger.info(f"脚本生成成功: {script_data.get('title', 'untitled')}")
        return script_data

    except json.JSONDecodeError as e:
        logger.error(f"脚本JSON解析失败: {e}, 原始文本: {output_text[:500]}")
        raise ValueError(f"脚本生成格式错误: {e}")
    except httpx.HTTPStatusError as e:
        logger.error(f"豆包API调用失败: {e.response.status_code} - {e.response.text}")
        raise RuntimeError(f"AI服务调用失败: {e.response.status_code}")
    except Exception as e:
        logger.error(f"脚本生成异常: {e}")
        raise


async def analyze_image(image_url: str) -> dict:
    """
    使用豆包大模型分析图片，识别物品和角色

    Args:
        image_url: 图片URL

    Returns:
        分析结果
    """
    payload = {
        "model": settings.doubao_model_id,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": _resolve_image_url(image_url),
                    },
                    {
                        "type": "input_text",
                        "text": """请分析这张图片，返回JSON格式：
{
  "description": "图片整体描述",
  "characters": [{"name": "角色名", "description": "角色描述"}],
  "objects": [{"name": "物品名", "description": "物品描述"}],
  "scene": "场景描述",
  "mood": "氛围描述"
}
仅返回JSON。""",
                    },
                ],
            }
        ],
    }

    headers = {
        "Authorization": f"Bearer {settings.doubao_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.seedance_api_base}/responses",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

    output_text = ""
    if "output" in data:
        for item in data["output"]:
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        output_text += content.get("text", "")

    clean_text = output_text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    if clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]

    return json.loads(clean_text.strip())


async def extract_style_context(image_urls: list[str]) -> str:
    """
    从参考图片中提取视觉风格上下文描述。
    返回一段英文风格描述，可以拼接到每个视频生成 prompt 前面。
    """
    if not image_urls:
        return ""

    user_content = []
    for url in image_urls:
        resolved = _resolve_image_url(url)
        if resolved:
            user_content.append({
                "type": "input_image",
                "image_url": resolved,
            })

    if not user_content:
        return ""

    user_content.append({
        "type": "input_text",
        "text": """请分析这些图片的视觉风格，返回一段简洁的英文视频画面风格前缀（不超过80个英文单词），包括：
- 色调和色彩（如 warm tones, pastel colors, vibrant）
- 光线（如 soft natural lighting, golden hour, dramatic lighting）
- 画面风格（如 photorealistic, anime style, 3D cartoon, watercolor）
- 环境/氛围（如 cozy indoor, outdoor garden, dreamy atmosphere）
- 角色外观关键特征（如有，如 a fluffy orange cat, a girl with black hair in red dress）

只返回这段英文风格描述文本，不要返回JSON，不要加引号，不要解释。
例如：Warm soft lighting, pastel color palette, cozy indoor setting, photorealistic style, a fluffy orange tabby cat with green eyes""",
    })

    payload = {
        "model": settings.doubao_model_id,
        "input": [
            {
                "role": "user",
                "content": user_content,
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {settings.doubao_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.seedance_api_base}/responses",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        output_text = ""
        if "output" in data:
            for item in data["output"]:
                if item.get("type") == "message":
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            output_text += content.get("text", "")

        style = output_text.strip().strip('"').strip("'")
        logger.info(f"提取视觉风格上下文: {style[:100]}...")
        return style

    except Exception as e:
        logger.warning(f"提取视觉风格失败（不影响流程）: {e}")
        return ""
