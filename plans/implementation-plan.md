# 视频生成平台 - 实施计划

> 方法论: gstack (系统化规划 → 设计 → 搭建 → 测试 → 部署 → 市场验证) + grill-me (严格质疑)
> Source PRD: docs/prd.md

## 架构决策 & 质疑

| 决策 | 选择 | 质疑 & 回答 |
|------|------|------------|
| 后端框架 | FastAPI (异步) | Q: 为什么不用Django? A: 异步IO对AI API调用至关重要 |
| 前端框架 | Next.js 15 + TailwindCSS | Q: SPA够吗? A: Next.js rewrites解决CORS，SSR利于SEO |
| 数据库 | SQLite + SQLAlchemy | Q: 为什么不Postgres? A: 单用户模式零配置，后续可迁移 |
| AI服务 | 火山引擎 (豆包+Seedance+TTS) | Q: 多模型? A: 统一SDK降低复杂度 |
| 视频处理 | FFmpeg | Q: moviepy? A: FFmpeg性能更优，格式支持更广 |
| 实时通信 | WebSocket | Q: SSE? A: 双向通信更灵活 |
| 任务队列 | asyncio内嵌 | Q: Celery? A: 单用户无需分布式队列 |

---

## Phase 1: 基础设施 ✅ DONE

- [x] FastAPI后端骨架 (配置、数据库、模型)
- [x] SQLAlchemy异步 + SQLite (Project, Shot, Asset)
- [x] .env配置管理 (pydantic-settings)
- [x] Next.js 15前端骨架 (布局、路由)
- [x] TailwindCSS样式系统
- [x] Docker + docker-compose部署配置
- [x] 健康检查 API

## Phase 2: AI脚本生成 ✅ DONE

- [x] 豆包LLM脚本生成 (doubao_service.py)
- [x] 场景感知prompt (entertainment/knowledge/ad/story)
- [x] JSON格式脚本输出 (title, shots[])
- [x] 图片分析API (analyze_image)
- [x] 分镜CRUD (create/update/delete shot)

## Phase 3: 视频生成 ✅ DONE

- [x] Seedance 1.5 Pro视频生成 (seedance_service.py)
- [x] 首帧/尾帧图片支持
- [x] 单镜头生成 + 批量生成
- [x] 任务状态轮询
- [x] WebSocket实时状态更新 (ws.py)

## Phase 4: TTS + 合成 ✅ DONE

- [x] 火山引擎TTS语音合成 (tts_service.py)
- [x] 12种语音角色支持
- [x] 单镜头音频 + 批量音频
- [x] FFmpeg视频拼接 (ffmpeg_service.py)
- [x] 音视频合并
- [x] 项目最终成片合成

## Phase 5: 完整平台UI ✅ DONE

- [x] 项目列表页 (创建/删除/搜索)
- [x] 项目详情页 (3标签页工作流)
  - 脚本标签: 主题输入 → AI生成 → 编辑
  - 分镜标签: 视频生成 → TTS → 状态监控
  - 合成标签: 预览 → 最终合成 → 下载
- [x] 文件上传 (拖拽 + 图片/视频)
- [x] 语音选择器组件
- [x] 状态Badge组件
- [x] Toast通知系统
- [x] WebSocket实时更新 + HTTP轮询降级

## Phase 6: 测试验证 ✅ DONE

- [x] 后端API测试 (16 tests, all passed)
  - 健康检查、配置端点
  - 项目CRUD (创建、列表、详情、更新、删除)
  - 分镜CRUD (创建、批量、更新、删除)
  - 文件上传 (有效/无效类型)
  - 级联删除
- [x] 前端TypeScript编译通过 (npm run build成功)
- [x] E2E启动验证 (后端API手动测试通过)

## Phase 7: 部署就绪 ✅ DONE

- [x] Dockerfile.backend (python:3.12-slim + ffmpeg)
- [x] Dockerfile.frontend (node:20-alpine)
- [x] docker-compose.yml (双服务编排)
- [x] start.sh (一键启动脚本)
- [x] README.md (文档)

---

## 快速启动

### 开发模式
```bash
# 后端
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd .. && python -m uvicorn backend.app.main:app --reload --port 8000

# 前端
cd frontend && npm install && npm run dev
```

### Docker模式
```bash
docker-compose up --build
```

### 运行测试
```bash
source backend/.venv/bin/activate
python -m pytest backend/tests/test_api.py -v
```

---

## 关键API端点

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | /health | 健康检查 |
| GET | /api/config | 平台配置 |
| POST | /api/projects | 创建项目 |
| GET | /api/projects | 项目列表 |
| GET | /api/projects/:id | 项目详情 |
| PUT | /api/projects/:id | 更新项目 |
| DELETE | /api/projects/:id | 删除项目 |
| POST | /api/projects/:id/generate-script | AI生成脚本 |
| POST | /api/projects/:id/shots | 添加分镜 |
| PUT | /api/shots/:id | 更新分镜 |
| DELETE | /api/shots/:id | 删除分镜 |
| POST | /api/shots/:id/generate-video | 生成视频 |
| GET | /api/shots/:id/video-status | 查询视频状态 |
| POST | /api/projects/:id/generate-all-videos | 批量生成视频 |
| POST | /api/tts/synthesize | TTS语音合成 |
| POST | /api/shots/:id/generate-audio | 分镜音频 |
| POST | /api/projects/:id/compose | 最终合成 |
| POST | /api/uploads/image | 上传图片 |
| POST | /api/uploads/video | 上传视频 |
| WS | /ws/projects/:id | 实时状态 |
