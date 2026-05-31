# EduAgent

基于 **Vue3 + FastAPI + LangGraph + 讯飞星火** 的多智能体高校个性化学习平台。

架构说明见 [`software_cup_ai_education_system_architecture.md`](software_cup_ai_education_system_architecture.md)。  
分阶段实施说明见 [`docs/phases/README.md`](docs/phases/README.md)。

## 当前进度

| 阶段 | 状态 | 说明 |
|------|------|------|
| 一、基础环境 | ✅ | 配置、日志、Redis、星火 HTTP 客户端、健康检查 |
| 二、RAG 知识库 | ✅ | 文档解析、切片、BGE 嵌入、ChromaDB、入库/检索 API |
| 三、学生画像 Agent | ✅ | Prompt、星火/规则引擎、SQLite/PostgreSQL、Redis 缓存 |
| 四、学习规划 Agent | ✅ | 基于画像生成个性化学习路径、星火+规则兜底、学习进度安排 |
| 五、资源生成 Agent | ✅ | PPT/题库/代码/思维导图/视频脚本生成、星火+规则兜底 |
| 六、LangGraph工作流 | ✅ | 多智能体协同编排、知识拆解、答疑辅导、安全审核、学习评估 |
| 七、讯飞语音接入 | ✅ | ASR语音识别、TTS语音合成、语音服务封装、语音API路由 |
| 八、学习评估闭环 | ✅ | 学习行为采集、评估指标计算、评估报告生成、画像动态更新 |
| 九、前端UI优化 | ✅ | 对话学习、个性化学习中心、资源生成、学习评估、语音学习五大模块 |
| 十、Docker部署 | ✅ | Docker Compose编排、一键启动脚本、多服务协同 |

## 核心特性

- **11个智能体协同**：画像、规划、知识拆解、PPT/题库/代码/思维导图/视频生成、答疑、安全审核、评估
- **学习闭环回流**：评估得分不达标时自动回流重新规划（最多2次），实现动态学习路径调整
- **资源持久化**：生成的学习资源自动保存到数据库，支持历史查询
- **Mermaid可视化**：思维导图资源自动渲染为交互式SVG图表
- **完整工作流API**：支持一键执行全流程（画像→规划→资源生成→评估）
- **讯飞语音集成**：ASR语音识别 + TTS语音合成
- **规则引擎兜底**：未配置星火API时，所有Agent通过启发式规则引擎正常工作

## 目录结构

```
EduAgent/
├── frontend/              # Vue3 + Tailwind + Mermaid
├── backend/               # FastAPI 入口、settings、core、integrations/{spark,asr,tts}
├── api/routes/            # health, chat, rag, profile, voice, evaluation, workflow, resources, progress
├── agents/                # 11个多智能体（画像、规划、知识、PPT、题库、代码、思维导图、视频、答疑、安全、评估）
├── workflows/             # LangGraph 工作流编排（含闭环回流机制）
├── rag/                   # 解析 / 切片 / 向量库 / 检索
├── services/              # 业务服务（profile_service, voice_service, evaluation_service）
├── schemas/               # Pydantic 模型
├── knowledge/             # 课程资料（示例 Markdown 已含）
├── prompts/               # Prompt 模板
├── database/              # ORM + Repository（student_profiles, learning_resources, evaluation_reports）
├── docker/                # Docker Compose 编排、Nginx配置
└── scripts/               # ingest_knowledge.py, smoke_workflow.py, start/stop脚本
```

## 密钥安全（公开仓库必读）

**不要把真实 API Key 写进会提交到 Git 的文件**（如 `.env`、源码、配置文件）。公开仓库一旦推送，密钥可能被他人看到或被盗用。

| 做法 | 说明 |
|------|------|
| 本地密钥 | 只写在 `.env`（已在 `.gitignore` 中忽略，不会上传） |
| 仓库模板 | 仅提交 `.env.example`，值为空或占位符 |
| 已误提交 | 立即在讯飞控制台**作废并重新生成**密钥，勿只删文件不轮换 |
| CI/CD | 使用 GitHub **Secrets**，不要写在 workflow 明文里 |

## 快速开始

### 1. 环境

```bash
cp .env.example .env
# 在 .env 中填写 SPARK_API_PASSWORD（勿提交 .env）
pip install -r requirements.txt
```

### 2. 后端

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. RAG 入库（首次会下载 Embedding 模型）

```bash
python scripts/ingest_knowledge.py
```

### 4. 前端

```bash
cd frontend 
npm install 
npm run dev
```

## 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/rag/ingest?sync=true` | RAG知识入库 |
| POST | `/api/rag/query` | RAG知识检索 |
| GET | `/api/rag/stats` | RAG统计信息 |
| POST | `/api/profile/analyze` | 学生画像分析 |
| POST | `/api/profile/build-profile` | 构建完整画像 |
| GET | `/api/profile/{session_id}` | 查询学生画像 |
| POST | `/api/chat` | 简化工作流对话 |
| POST | `/api/workflow/execute` | 执行完整工作流（含资源生成+评估） |
| GET | `/api/workflow/status/{session_id}` | 查询工作流执行状态 |
| GET | `/api/resources/{session_id}` | 获取所有已生成资源 |
| GET | `/api/resources/{session_id}/{type}` | 按类型获取资源(ppt/quiz/code/mindmap/video) |
| GET | `/api/progress/{session_id}` | 学习进度汇总 |
| POST | `/api/evaluation/report` | 生成评估报告 |
| POST | `/api/evaluation/behavior` | 提交学习行为 |
| GET | `/api/evaluation/metrics` | 评估指标说明 |
| POST | `/api/voice/asr` | 语音识别 |
| POST | `/api/voice/tts` | 语音合成 |

## Docker 部署

```bash
# 一键启动（Windows）
scripts\start.bat

# 或使用 PowerShell
.\scripts\start.ps1

# 或手动 docker compose
docker compose -f docker/docker-compose.yml up --build -d
```

服务启动后：
- 前端：http://localhost:80
- 后端：http://localhost:8000
- API文档：http://localhost:8000/docs

## 讯飞星火配置（WebSocket / Spark Ultra）

1. 复制 `cp .env.example .env`
2. 在 [讯飞开放平台控制台](https://console.xfyun.cn/) 获取 **APPID、APIKey、APISecret**
3. 仅写入本地 `.env`（勿提交 Git）：

```env
SPARK_API_TYPE=websocket
SPARK_APP_ID=你的APPID
SPARK_API_KEY=你的APIKey
SPARK_API_SECRET=你的APISecret
SPARK_WS_URL=wss://spark-api.xf-yun.com/v4.0/chat
SPARK_DOMAIN=4.0Ultra
```

未配置时，学生画像使用**规则引擎**兜底。若曾在聊天/截图中泄露密钥，请在控制台**立即轮换**。
