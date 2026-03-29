"""应用配置管理"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 加载项目根目录的 .env
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(ENV_PATH)


class Settings(BaseSettings):
    """应用全局配置"""

    # 豆包 API
    doubao_api_id: str = ""
    doubao_access_token: str = ""
    doubao_secret_key: str = ""
    doubao_voice_type: str = "BV012_streaming"
    doubao_cluster_id: str = "volcano_tts"
    doubao_api_key: str = ""
    doubao_model_id: str = "doubao-seed-2-0-pro-260215"

    # Seedance 视频生成
    seedance_model_id: str = "doubao-seedance-1-5-pro-251215"
    seedance_api_base: str = "https://ark.cn-beijing.volces.com/api/v3"

    # TTS 语音合成
    tts_api_url: str = "https://openspeech.bytedance.com/api/v1/tts"
    tts_ws_url: str = "wss://openspeech.bytedance.com/api/v1/tts/ws_binary"

    # 应用配置
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./data/video_platform.db"
    upload_dir: str = "./data/uploads"
    output_dir: str = "./data/outputs"
    temp_dir: str = "./data/temp"

    # 文件上传限制
    max_upload_size_mb: int = 100

    # 日志
    log_level: str = "INFO"

    class Config:
        env_file = str(ENV_PATH)
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

# 确保必要目录存在
for dir_path in [settings.upload_dir, settings.output_dir, settings.temp_dir]:
    Path(dir_path).mkdir(parents=True, exist_ok=True)
