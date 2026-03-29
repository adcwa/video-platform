#!/bin/bash
# ============================================================
# AI 视频生成平台 - 启动脚本
# ============================================================

set -e

echo "🎬 AI 视频生成平台启动中..."
echo "================================"

# 检查 .env
if [ ! -f .env ]; then
    echo "⚠️  .env 文件不存在，从 .env.example 复制..."
    cp .env.example .env
    echo "📝 请编辑 .env 配置文件后重新运行"
    exit 1
fi

# 检查 FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  FFmpeg 未安装"
    echo "请运行: brew install ffmpeg"
    exit 1
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "⚠️  Python3 未安装"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "⚠️  Node.js 未安装"
    exit 1
fi

# 创建数据目录
mkdir -p data/uploads data/outputs data/temp

# ---------- 后端 ----------
echo ""
echo "📦 安装后端依赖..."
cd backend
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt -q
pip install pytest pytest-asyncio -q
cd ..

echo "✅ 后端依赖已安装"

# ---------- 前端 ----------
echo ""
echo "📦 安装前端依赖..."
cd frontend
npm install --silent 2>/dev/null || npm install
cd ..

echo "✅ 前端依赖已安装"

# ---------- 启动 ----------
echo ""
echo "🚀 启动后端服务 (port 8000)..."
cd backend
source .venv/bin/activate
cd ..
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

sleep 2

echo "🚀 启动前端服务 (port 3000)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "================================"
echo "✅ 服务已启动！"
echo ""
echo "📺 前端: http://localhost:3000"
echo "🔧 后端: http://localhost:8000"
echo "📖 API文档: http://localhost:8000/docs"
echo "❤️ 健康检查: http://localhost:8000/health"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo "================================"

# 等待退出
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
