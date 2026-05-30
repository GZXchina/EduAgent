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

## 目录结构

```
EduAgent/
├── frontend/              # Vue3 + Tailwind
├── backend/               # FastAPI 入口、settings、core、integrations/{spark,asr,tts}
├── api/routes/            # health, chat, rag, profile, voice, evaluation
├── agents/                # 多智能体（画像、规划、资源、知识、答疑、安全、评估已实装）
├── workflows/             # LangGraph
├── rag/                   # 解析 / 切片 / 向量库 / 检索
├── services/              # 业务服务（profile_service, voice_service, evaluation_service）
├── schemas/               # Pydantic 模型
├── knowledge/             # 课程资料（示例 Markdown 已含）
├── prompts/               # Prompt 模板
├── database/              # ORM + Repository
├── docker/
└── scripts/               # ingest_knowledge.py, smoke_workflow.py
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

| 方法 | 路径 | 阶段 |
|------|------|------|
| GET | `/api/health` | 一 |
| POST | `/api/rag/ingest?sync=true` | 二 |
| POST | `/api/rag/query` | 二 |
| GET | `/api/rag/stats` | 二 |
| POST | `/api/profile/analyze` | 三 |
| GET | `/api/profile/{session_id}` | 三 |
| POST | `/api/chat` | 工作流（画像节点已实装） |

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
