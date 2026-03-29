"""FastAPI 应用入口"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.database import init_db
from backend.app.routes.projects import router as projects_router
from backend.app.routes.ai_routes import router as ai_router
from backend.app.routes.uploads import router as uploads_router
from backend.app.routes.ws import router as ws_router
from backend.app.routes.assets import router as assets_router

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("🚀 视频生成平台启动中...")
    await init_db()
    logger.info("✅ 数据库初始化完成")

    # 确保静态文件目录存在
    for dir_path in [settings.upload_dir, settings.output_dir, settings.temp_dir]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    yield

    logger.info("👋 视频生成平台关闭")


app = FastAPI(
    title="AI视频生成平台",
    description="基于豆包大模型 + Seedance 的AI视频生成平台",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务
for sub in ["images", "videos"]:
    (Path(settings.upload_dir) / sub).mkdir(parents=True, exist_ok=True)
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
Path(settings.output_dir).mkdir(parents=True, exist_ok=True)
app.mount("/files/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
app.mount("/files/outputs", StaticFiles(directory=settings.output_dir), name="outputs")

# 注册路由
app.include_router(projects_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(uploads_router, prefix="/api")
app.include_router(assets_router, prefix="/api")
app.include_router(ws_router)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "video-platform",
        "version": "1.0.0",
    }


@app.get("/api/config")
async def get_public_config():
    """获取公开配置（供前端使用）"""
    return {
        "available_voice_types": [
            {"id": "BV012_streaming", "name": "新闻男声", "category": "新闻播报"},
            {"id": "BV700_streaming", "name": "灿灿", "category": "通用场景"},
            {"id": "BV701_streaming", "name": "擎苍", "category": "有声阅读"},
            {"id": "BV001_streaming", "name": "通用女声", "category": "通用场景"},
            {"id": "BV002_streaming", "name": "通用男声", "category": "通用场景"},
            {"id": "BV405_streaming", "name": "甜美小源", "category": "智能助手"},
            {"id": "BV406_streaming", "name": "超自然音色-梓梓", "category": "通用场景"},
            {"id": "BV407_streaming", "name": "超自然音色-燃燃", "category": "通用场景"},
            {"id": "BV411_streaming", "name": "影视解说小帅", "category": "视频配音"},
            {"id": "BV412_streaming", "name": "影视解说小美", "category": "视频配音"},
            {"id": "BV700_V2_streaming", "name": "灿灿 2.0", "category": "通用场景"},
            {"id": "BV701_V2_streaming", "name": "擎苍 2.0", "category": "有声阅读"},
        ],
        "available_ratios": ["16:9", "9:16", "4:3", "3:4", "1:1", "21:9"],
        "available_resolutions": ["480p", "720p", "1080p"],
        "scene_types": [
            {"id": "entertainment", "name": "娱乐发布", "description": "适配视频号、小红书、抖音等平台"},
            {"id": "research", "name": "科研研究", "description": "学术、实验等专业领域"},
        ],
    }
