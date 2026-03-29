# AI 视频生成平台

> 基于豆包大模型 + Seedance 视频生成 + TTS 语音合成的全流程 AI 视频生成工具

## 🎯 功能特性

- **AI 脚本生成** — 输入主题，豆包大模型自动生成完整视频脚本和分镜
- **智能分镜** — 自动拆分镜头，支持手动调整每个镜头的描述、对白、时长
- **视频生成** — 调用 Seedance 1.5 Pro，支持文生视频、图生视频
- **语音合成** — 豆包 TTS 多音色语音合成，支持情感和语速调节
- **视频拼接** — FFmpeg 自动拼接所有镜头，合并音频，导出最终视频
- **场景预设** — 娱乐发布（短视频平台）和科研研究两种场景模式

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────┐
│                   前端 (Next.js)                      │
│           http://localhost:3000                       │
├─────────────────────────────────────────────────────┤
│                   后端 (FastAPI)                      │
│           http://localhost:8000                       │
├──────────┬──────────────┬──────────┬────────────────┤
│ 豆包大模型  │  Seedance     │  豆包TTS  │    FFmpeg      │
│ 脚本生成   │  视频生成      │  语音合成  │   视频拼接     │
├──────────┴──────────────┴──────────┴────────────────┤
│              SQLite + 本地文件存储                      │
└─────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+
- FFmpeg (`brew install ffmpeg`)

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

### 2. 一键启动

```bash
chmod +x start.sh
./start.sh
```

### 3. 或手动启动

**后端：**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
python -m uvicorn backend.app.main:app --reload --port 8000
```

**前端：**
```bash
cd frontend
npm install
npm run dev
```

### 4. Docker 部署

```bash
docker-compose up -d
```

## 📡 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `GET` | `/api/config` | 获取配置（音色列表、比例等） |
| `GET` | `/api/projects` | 项目列表 |
| `POST` | `/api/projects` | 创建项目 |
| `GET` | `/api/projects/{id}` | 项目详情（含分镜） |
| `PUT` | `/api/projects/{id}` | 更新项目 |
| `DELETE` | `/api/projects/{id}` | 删除项目 |
| `POST` | `/api/projects/{id}/generate-script` | AI 生成脚本 |
| `POST` | `/api/projects/{id}/generate-all-videos` | 批量生成视频 |
| `POST` | `/api/projects/{id}/compose` | 合成最终视频 |
| `GET` | `/api/projects/{id}/shots` | 获取分镜列表 |
| `POST` | `/api/projects/{id}/shots` | 添加分镜 |
| `PUT` | `/api/shots/{id}` | 更新分镜 |
| `DELETE` | `/api/shots/{id}` | 删除分镜 |
| `POST` | `/api/shots/{id}/generate-video` | 单镜头视频生成 |
| `GET` | `/api/shots/{id}/video-status` | 查询视频状态 |
| `POST` | `/api/shots/{id}/generate-audio` | 分镜语音合成 |
| `POST` | `/api/tts/synthesize` | 独立 TTS 合成 |
| `POST` | `/api/analyze-image` | 图片分析 |

完整 API 文档: http://localhost:8000/docs

## 📁 项目结构

```
video-platform/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 应用入口
│   │   ├── config.py            # 配置管理
│   │   ├── database.py          # 数据库连接
│   │   ├── models.py            # 数据模型
│   │   ├── schemas.py           # Pydantic 模型
│   │   ├── routes/
│   │   │   ├── projects.py      # 项目 CRUD 路由
│   │   │   └── ai_routes.py     # AI 服务路由
│   │   └── services/
│   │       ├── doubao_service.py    # 豆包大模型（脚本生成）
│   │       ├── seedance_service.py  # Seedance（视频生成）
│   │       ├── tts_service.py       # TTS（语音合成）
│   │       └── ffmpeg_service.py    # FFmpeg（视频处理）
│   ├── tests/
│   │   └── test_api.py          # API 测试
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx       # 根布局
│   │   │   ├── page.tsx         # 首页（项目列表）
│   │   │   └── projects/[id]/
│   │   │       └── page.tsx     # 项目详情（工作台）
│   │   └── lib/
│   │       └── api.ts           # API 客户端
│   ├── package.json
│   └── tailwind.config.js
├── docs/                         # 文档
├── plans/                        # 实施计划
├── data/                         # 运行时数据（gitignored）
├── .env                          # 环境变量（gitignored）
├── .env.example                  # 环境变量模板
├── docker-compose.yml
├── start.sh                      # 一键启动脚本
└── README.md
```

## 🔄 工作流程

```
1. 创建项目 → 设置主题、场景、时长、比例
       ↓
2. AI 脚本生成 → 豆包大模型生成脚本和分镜
       ↓
3. 分镜微调 → 手动编辑描述、对白、时长
       ↓
4. 视频生成 → Seedance 逐镜头生成视频
       ↓
5. 语音合成 → TTS 为有对白的镜头生成语音
       ↓
6. 合成导出 → FFmpeg 拼接视频、合并音频
       ↓
7. 下载/发布 → 导出最终视频文件
```

## ⚙️ 环境变量说明

| 变量 | 说明 |
|------|------|
| `DOUBAO_API_KEY` | 豆包 API Key（用于大模型和视频生成） |
| `DOUBAO_MODEL_ID` | 豆包大模型 ID |
| `DOUBAO_API_ID` | TTS 应用 ID |
| `DOUBAO_ACCESS_TOKEN` | TTS 访问令牌 |
| `DOUBAO_VOICE_TYPE` | 默认音色 |
| `DOUBAO_CLUSTER_ID` | TTS 集群 |
| `SEEDANCE_MODEL_ID` | 视频生成模型 ID |

## 📋 测试

```bash
# 运行后端测试
cd backend && source .venv/bin/activate && cd ..
python -m pytest backend/tests/ -v
```

## 📜 License

MIT
