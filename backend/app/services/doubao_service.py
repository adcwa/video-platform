"""豆包大模型服务 - 脚本生成、场景识别"""

import base64
import json
import logging
import mimetypes
from pathlib import Path
from typing import Optional

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
  "subject_description": "主体角色/物体的精确外观描述（品种、毛色、花纹、体型等具体特征），确保所有镜头中的主体完全一致",
  "characters": ["角色1", "角色2"],
  "objects": ["关键物品1", "关键物品2"],
  "shots": [
    {
      "sequence": 1,
      "description": "【极其重要】在描述开头必须先写主体的完整外观特征，然后再描述动作和场景。例如：'一只蓝眼睛的布偶猫，奶油色皮毛带有深褐色重点色，蓬松的长毛，正在...'。每个镜头都必须包含完全相同的主体描述，这是保证主体一致性的关键。",
      "dialogue": "这个镜头的旁白或对白文本（如果有）",
      "duration": 5,
      "camera_note": "镜头运动说明（如：缓慢推进、固定机位等）"
    }
  ]
}

关键要求：
1. 每个镜头时长控制在3-8秒之间
2. **最最重要 - 主体一致性规则**：
   - 每个镜头的description必须以主体的完整外观描述开头（品种、毛色、花纹、眼睛颜色、体型等）
   - 所有镜头中的主体描述必须完全一致，一字不差
   - 如果用户上传了参考图片，必须精确描述图片中的主体特征，而非泛泛描述
   - 错误示例："一只猫在玩耍" ← 太笼统，每次生成会是不同的猫
   - 正确示例："一只蓝眼睛的布偶猫，奶油色皮毛配有深褐色面部和耳朵重点色，蓬松的长毛大尾巴，中大体型，正在客厅里玩耍" ← 足够具体
3. **视觉风格一致性**：所有镜头保持相同的色调、光线、画面质感
4. 对白要自然流畅
5. 所有镜头总时长应接近用户指定的目标时长
6. 如果用户上传了参考图片，必须分析图片中主体的每一个视觉细节，并在每个镜头中重复这些细节
7. 仅返回JSON，不要包含其他文本"""


async def generate_script(
    theme: str,
    scene_type: str = "entertainment",
    target_duration: int = 30,
    additional_context: str = "",
    image_urls: Optional[list] = None,
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
        user_text += """

⚠️ 极其重要：请仔细分析上传的参考图片，从中提取：
1. **主体的精确外观特征**（这是最重要的！）：
   - 如果是动物：品种、毛色、花纹分布、眼睛颜色、体型大小、毛发长短和质感
   - 如果是人物：发型、发色、面部特征、穿着、体型
   - 其他物体：形状、颜色、材质、大小等可辨识特征
2. 视觉风格（色调、光线、画面风格）
3. 场景/背景环境

关键规则：你必须在脚本的每一个镜头description开头，重复写出主体的完整外观描述。
这是因为每个镜头会分别发给视频生成AI，它们之间没有上下文联系，只有在每个镜头都精确描述同一个主体，才能保证生成的视频中出现同一个角色。"""

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
        "text": """请仔细分析这些图片中的主体角色/物体和视觉风格。

返回一段简洁的英文描述（不超过100个英文单词），**必须包含以下内容**：

1. **主体外观精确描述**（最重要！）：如果是动物，描述品种、毛色、花纹、体型、眼睛颜色等可辨识特征。如果是人物，描述发型、发色、五官特征、服装等。尽可能具体，让人一看描述就知道是同一个主体。
   例如：a Ragdoll cat with blue eyes, cream-colored fur with dark brown points on face and ears, fluffy long coat, medium-large build
2. **色调和色彩**（如 warm tones, pastel colors）
3. **光线**（如 soft natural lighting, golden hour）
4. **画面风格**（如 photorealistic, cozy home photography）
5. **环境/氛围**（如 cozy indoor, modern living room）

只返回这段英文描述文本，不要返回JSON，不要加引号，不要解释。
格式参考：[Subject]: a Ragdoll cat with blue eyes and cream-colored fur with dark brown points, fluffy long coat. [Style]: Warm soft natural lighting, photorealistic cozy indoor setting, modern living room with wooden furniture, pastel color palette.""",
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


async def recognize_characters_and_scenes(image_url: str) -> dict:
    """
    使用豆包大模型对图片进行深度识别，提取角色和场景的结构化信息。
    用于数字资产管理 — 自动创建全局角色和场景。

    返回格式:
    {
      "characters": [
        {
          "name": "...",
          "description_zh": "中文描述",
          "appearance_prompt": "英文外观提示词（用于 Seedance）",
          "tags": ["动物", "猫"]
        }
      ],
      "scene": {
        "name": "...",
        "description_zh": "中文描述",
        "environment_prompt": "英文环境提示词",
        "mood": "...",
        "lighting": "...",
        "tags": ["室内", "现代"]
      }
    }
    """
    resolved = _resolve_image_url(image_url)
    if not resolved:
        raise ValueError(f"无法解析图片URL: {image_url}")

    payload = {
        "model": settings.doubao_model_id,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": resolved,
                    },
                    {
                        "type": "input_text",
                        "text": """请仔细分析这张图片，提取其中的角色（人物/动物/主要物体）和场景信息。

你必须返回严格的JSON格式，不要包含任何其他文本：

{
  "characters": [
    {
      "name": "角色的简短名字（如'布偶猫'、'红衣女孩'、'金毛犬'）",
      "description_zh": "角色的详细中文描述，包含所有可辨识的视觉特征（品种/体型/毛色/发型/服装/面部特征等）",
      "appearance_prompt": "Detailed English appearance description for AI video generation. Be very specific about: species/breed, fur color/pattern, eye color, body size, clothing, hair style, distinctive marks. Example: 'a Ragdoll cat with striking blue eyes, cream-colored fur with dark brown points on face, ears and tail, fluffy long coat, medium-large muscular build'",
      "tags": ["分类标签1", "分类标签2"]
    }
  ],
  "scene": {
    "name": "场景的简短名称（如'现代客厅'、'日落海滩'、'森林小径'）",
    "description_zh": "场景的详细中文描述，包含环境、装饰、物品等",
    "environment_prompt": "Detailed English environment description for AI video generation. Include: setting type, key objects, materials, colors, spatial arrangement. Example: 'a cozy modern living room with warm wooden floors, beige sofa with throw pillows, large windows with sheer curtains letting in soft natural light, potted green plants on shelves'",
    "mood": "氛围描述（如'温馨舒适'、'紧张悬疑'、'活泼欢快'）",
    "lighting": "光照描述（如'柔和自然光'、'暖黄色灯光'、'日落金色光线'）",
    "tags": ["分类标签1", "分类标签2"]
  }
}

要求：
1. 角色描述必须非常具体，要让人只看文字就能辨认出这个角色
2. appearance_prompt 必须是英文，要足够详细，用于 AI 视频生成
3. 如果图中没有明显角色，characters 可以为空数组
4. scene 信息必须提供
5. tags 用于后续检索，请给出有意义的分类标签
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

    result = json.loads(clean_text.strip())
    logger.info(
        f"图片识别完成: {len(result.get('characters', []))} 个角色, "
        f"场景={result.get('scene', {}).get('name', '无')}"
    )
    return result
