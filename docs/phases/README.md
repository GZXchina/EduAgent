# 分阶段实施说明（阶段一～十）

## 阶段一：项目基础环境

| 能力 | 路径 |
|------|------|
| 统一配置 | `backend/settings.py`、`.env` |
| 日志 | `backend/core/logging_config.py` |
| Redis（可降级内存） | `backend/core/redis_client.py` |
| 依赖注入 | `backend/core/deps.py` |
| 讯飞星火 HTTP 客户端 | `backend/integrations/spark/client.py` |
| 健康检查 | `GET /api/health` |

**验收**：启动 `uvicorn backend.main:app --reload`，访问 `/api/health` 可见 database / redis / spark 状态。

---

## 阶段二：RAG 知识库

| 能力 | 路径 |
|------|------|
| 文档解析 MD/TXT/PDF/DOCX | `rag/loader.py` |
| 文本切片 | `rag/chunker.py` |
| BGE 嵌入 + ChromaDB | `rag/embeddings.py`、`rag/vector_store.py` |
| 批量入库 | `rag/ingest.py`、`scripts/ingest_knowledge.py` |
| 检索 API | `POST /api/rag/query`、`POST /api/rag/ingest`、`GET /api/rag/stats` |

**验收**：

```bash
python scripts/ingest_knowledge.py
curl -X POST http://127.0.0.1:8000/api/rag/query -H "Content-Type: application/json" -d "{\"query\":\"Python循环\"}"
```

---

## 阶段三：学生画像 Agent

| 能力 | 路径 |
|------|------|
| Prompt 模板 | `prompts/profile_agent.md` |
| 画像服务（星火 + 规则兜底 + DB + Redis） | `services/profile_service.py` |
| Agent 接入工作流 | `agents/profile_agent.py` |
| REST API | `POST /api/profile/analyze`、`GET /api/profile/{session_id}` |

**验收**（未配置星火时使用规则引擎）：

```bash
curl -X POST http://127.0.0.1:8000/api/profile/analyze \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"我是计算机专业大一学生，想备战蓝桥杯，基础一般，喜欢看图解，每天1小时，循环不太会\"}"
```

配置 `SPARK_API_PASSWORD` 后，`source` 字段为 `spark`。

---

## 阶段四：学习规划 Agent

| 能力 | 路径 |
|------|------|
| Prompt 模板 | `prompts/planner_agent.md` |
| 学习路径模型 | `schemas/profile.py` (LearningPath, LearningStep) |
| Planner Agent | `agents/planner_agent.py` |
| 规则引擎兜底 | heuristic_path() 函数 |

**核心功能**：
- 根据学生画像（知识水平、学习风格、薄弱点、目标、时长）生成个性化学习路径
- 支持星火大模型生成 + 规则引擎兜底
- 输出结构化学习步骤（周计划、知识点、资源推荐、评估方式）
- 自动识别学习目标（蓝桥杯/考研/就业/通用学习）
- 根据学习时长动态调整路径周期

**验收**（未配置星火时使用规则引擎）：

```bash
# 通过聊天接口测试（会依次调用画像Agent和规划Agent）
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"我是计算机专业大一学生，想备战蓝桥杯，基础一般，喜欢看图解，每天1小时，循环不太会\"}"
```

**输出示例**：
```json
{
  "session_id": "abc123",
  "student_profile": {...},
  "learning_path": {
    "path_name": "蓝桥杯Python竞赛之路",
    "total_weeks": 10,
    "steps": [...],
    "focus_areas": ["算法基础", "真题训练", "循环"],
    "suggestions": ["重点攻克薄弱点：循环", "..."]
  }
}
```

配置 `SPARK_API_PASSWORD` 后，`learning_path.source` 字段为 `spark`。

---

## 阶段五：资源生成 Agent

| 能力 | 路径 |
|------|------|
| Prompt 模板 | `prompts/{ppt,quiz,code,mindmap,video}_agent.md` |
| 资源模型 | `schemas/profile.py` (PPTDeck, QuizSet, CodeSet, MindMap, VideoScript) |
| PPT Agent | `agents/ppt_agent.py` |
| 题库 Agent | `agents/quiz_agent.py` |
| 代码案例 Agent | `agents/code_agent.py` |
| 思维导图 Agent | `agents/mindmap_agent.py` |
| 视频脚本 Agent | `agents/video_agent.py` |

**核心功能**：
- PPT生成：根据学习主题生成Markdown格式的教学课件
- 题库生成：生成选择/填空/判断/编程等多样化练习题
- 代码案例：提供完整可运行的代码示例及预期输出
- 思维导图：生成Mermaid格式的知识结构图
- 视频脚本：生成包含场景、时长、画面描述的拍摄脚本
- 统一支持星火大模型生成 + 规则引擎兜底

**资源模型说明**：
- `PPTDeck`: 包含多个PPTSlide，每个slide有title、content、notes
- `QuizSet`: 包含多道QuizQuestion，覆盖不同难度和知识点
- `CodeSet`: 包含多个CodeExample，每个有完整代码和输出
- `MindMap`: 树形节点结构，支持导出Mermaid和Markdown
- `VideoScript`: 包含多个场景Scene，每个有讲解内容和视觉描述

**验收**：

```bash
# 测试各资源Agent的规则引擎兜底功能
python -c "
import asyncio
from agents.ppt_agent import heuristic_ppt
from agents.quiz_agent import heuristic_quiz
from agents.code_agent import heuristic_code
from agents.mindmap_agent import heuristic_mindmap
from agents.video_agent import heuristic_video

# 测试PPT生成
ppt = heuristic_ppt('Python循环')
print(f'PPT: {ppt.topic}, 共{ppt.total_slides}页')

# 测试题库生成
quiz = heuristic_quiz('Python循环')
print(f'题库: {quiz.topic}, 共{quiz.total_count}题')

# 测试代码案例
code = heuristic_code('Python循环')
print(f'代码: {code.topic}, 共{code.total_count}个示例')

# 测试思维导图
mm = heuristic_mindmap('Python循环')
print(f'思维导图: {mm.topic}')

# 测试视频脚本
video = heuristic_video('Python循环')
print(f'视频: {video.topic}, 时长{video.total_duration}')
"
```

**输出示例**：
```json
{
  "ppt_deck": {
    "topic": "Python循环结构",
    "total_slides": 8,
    "slides": [...]
  },
  "quiz_set": {
    "topic": "Python循环结构",
    "total_count": 10,
    "questions": [...]
  },
  "code_set": {
    "topic": "Python循环结构",
    "total_count": 5,
    "examples": [...]
  },
  "mindmap": {
    "topic": "Python循环结构",
    "root": {"id": "loop", "text": "Python循环结构", "children": [...]}
  },
  "video_script": {
    "topic": "Python循环结构",
    "total_duration": "14分钟",
    "scenes": [...]
  }
}
```

配置 `SPARK_API_PASSWORD` 后，各资源的 `source` 字段为 `spark`。

---

## 阶段六：LangGraph工作流

| 能力 | 路径 |
|------|------|
| 工作流编排 | `workflows/graph.py` |
| 状态管理 | `workflows/state.py` |
| 知识拆解Agent | `agents/knowledge_agent.py` |
| 答疑辅导Agent | `agents/tutor_agent.py` |
| 安全审核Agent | `agents/safety_agent.py` |
| 学习评估Agent | `agents/evaluation_agent.py` |
| Prompt模板 | `prompts/{knowledge,tutor,safety,evaluation}_agent.md` |

**工作流编排**：
```
画像Agent → 规划Agent → 知识拆解Agent → 并行资源生成(PPT/题库/代码/思维导图/视频)
                                                                      ↓
安全审核Agent ← 答疑辅导Agent ← 资源聚合 ← 结果汇总
                                                        ↓
                                                  学习评估Agent
                                                        ↓
                                                   回到画像Agent(循环)
```

**核心功能**：
- 知识拆解：根据学习主题从RAG检索知识，生成结构化知识树
- 答疑辅导：结合RAG和星火大模型回答学生问题，支持规则兜底
- 安全审核：审核所有生成资源的内容安全性（敏感词、可疑代码检测）
- 学习评估：根据资源使用情况和学生画像生成评估报告

**Agent说明**：
- `KnowledgeAgent`：RAG检索 + 星火生成知识树，规则引擎兜底
- `TutorAgent`：RAG检索 + 星火生成答案，支持敏感词过滤
- `SafetyAgent`：内容安全审核，支持PPT/题库/代码/思维导图/视频
- `EvaluationAgent`：评分算法 + 星火生成评估报告，支持优势/劣势分析

**验收**：

```bash
# 测试各Agent规则引擎功能
python -c "
from agents.knowledge_agent import heuristic_knowledge_tree
from agents.tutor_agent import heuristic_answer, is_safe_question
from agents.safety_agent import review_resource
from agents.evaluation_agent import generate_evaluation_report
from schemas.profile import StudentProfile

profile = StudentProfile(knowledge_level='beginner', weakness='循环')

# 知识拆解
tree = heuristic_knowledge_tree('Python循环', profile)
print('Knowledge Tree:', tree['topic'], len(tree['nodes']), 'nodes')

# 答疑
print('Safe Q:', is_safe_question('什么是for循环'))
print('Answer:', heuristic_answer('什么是for循环')[:50])

# 安全审核
review = review_resource({'examples': [{'title': 'Test', 'code': 'for i in range(10): print(i)'}]}, 'code')
print('Code safe:', review['is_safe'])

# 学习评估
report = generate_evaluation_report(profile, {'quiz_set': {}, 'code_set': {}})
print('Score:', report['score'], report['level'])
"
```

**工作流测试**（需网络环境正常，可访问HuggingFace）：
```bash
# 启动后端后，通过聊天接口测试完整工作流
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"我想学习Python循环"}'
```

---

## 阶段七：讯飞语音能力接入

| 能力 | 路径 |
|------|------|
| ASR客户端 | `backend/integrations/asr/client.py` |
| TTS客户端 | `backend/integrations/tts/client.py` |
| 语音服务 | `services/voice_service.py` |
| 语音路由 | `api/routes/voice.py` |
| 配置项 | `backend/settings.py` |

**讯飞ASR配置**：
```bash
# .env
ASR_APP_ID=your_app_id
ASR_API_KEY=your_api_key
ASR_API_SECRET=your_api_secret
```

**讯飞TTS配置**：
```bash
# .env
TTS_APP_ID=your_app_id
TTS_API_KEY=your_api_key
TTS_API_SECRET=your_api_secret
```

**API端点**：
- `POST /api/voice/asr` - 语音识别，接收音频文件，返回识别文字
- `POST /api/voice/tts` - 语音合成，接收文字，返回音频数据
- `GET /api/voice/status` - 查询语音服务配置状态

**语音服务**：
```python
from services.voice_service import get_voice_service

voice = get_voice_service()

# 语音转文字
text = await voice.speech_to_text(audio_bytes, "wav")

# 文字转语音
audio = await voice.text_to_speech("你好，这是一个测试", "xiaoyan")
```

**音色选项**（TTS）：
- `xiaoyan` - 晓燕（女声）
- `aisjiuxu` - 许久（男声）
- `aisbabyxu` - 宝宝xu（童声）

**验收**：

```bash
# 查询语音服务状态
curl http://127.0.0.1:8000/api/voice/status

# 语音识别测试（需配置ASR）
curl -X POST http://127.0.0.1:8000/api/voice/asr \
  -F "audio=@test.wav" \
  -F "format=wav"

# 语音合成测试（需配置TTS）
curl -X POST http://127.0.0.1:8000/api/voice/tts \
  -F "text=你好，欢迎使用EduAgent" \
  -F "voice=xiaoyan" \
  -o speech.mp3
```

---

## 阶段八：学习评估闭环

| 能力 | 路径 |
|------|------|
| 评估服务 | `services/evaluation_service.py` |
| 评估路由 | `api/routes/evaluation.py` |
| 评估Agent | `agents/evaluation_agent.py` |
| 评估指标 | 学习时长、练习正确率、知识掌握度、资源利用率 |

**评估维度**：
- `quiz_accuracy` - 练习正确率(%)
- `knowledge_mastery_score` - 知识掌握度得分(%)
- `resource_utilization` - 资源利用率(%)
- `dedication_score` - 学习投入度得分(%)

**综合评分公式**：
```
score = quiz_accuracy * 0.3 + knowledge_mastery * 0.3 + resource_util * 0.2 + dedication * 0.2
```

**API端点**：
- `POST /api/evaluation/report` - 生成学习评估报告
- `POST /api/evaluation/behavior` - 提交学习行为数据
- `GET /api/evaluation/metrics` - 获取评估指标说明
- `POST /api/evaluation/profile-update` - 根据评估报告更新画像

**学习行为数据结构**：
```python
{
    "study_duration_minutes": 300,  # 本周学习时长
    "quiz_results": [  # 练习结果
        {"question": "for循环", "correct": True},
        {"question": "while循环", "correct": True},
    ],
    "knowledge_mastery": {  # 知识掌握度
        "for循环": 85.0,
        "while循环": 70.0,
    },
    "resource_usage": {  # 资源使用次数
        "ppt": 2, "quiz": 3, "code": 2, "mindmap": 1, "video": 1
    }
}
```

**评估报告结构**：
```python
{
    "score": 74,  # 综合评分
    "level": "中等",  # 等级
    "comment": "基本掌握了内容，建议多做练习",
    "analysis": {
        "quiz_accuracy": 66.7,
        "knowledge_mastery_score": 68.3,
        "resource_utilization": 100.0,
        "dedication_score": 71.4
    },
    "strengths": ["资源利用率高，学习积极"],
    "weaknesses": [],
    "suggestions": ["重点加强: 循环"]
}
```

**验收**：

```bash
# 测试学习评估服务
python -c "
from services.evaluation_service import LearningBehaviorData, EvaluationService, get_evaluation_service
from schemas.profile import StudentProfile

service = get_evaluation_service()
profile = StudentProfile(knowledge_level='beginner', weakness='循环')
behavior = LearningBehaviorData(
    study_duration_minutes=300,
    quiz_results=[{'question': 'for循环', 'correct': True}, {'question': 'while循环', 'correct': False}],
    knowledge_mastery={'for循环': 85.0, 'while循环': 50.0},
    resource_usage={'ppt': 2, 'quiz': 3, 'code': 2, 'mindmap': 1, 'video': 1}
)

analysis = service.analyze_behavior(behavior)
print('Analysis:', analysis)

report = service.generate_report(profile, behavior)
print('Score:', report['score'], report['level'])
print('Strengths:', report['strengths'])
print('Suggestions:', report['suggestions'])
"
```

---

## 阶段九：前端UI优化

| 能力 | 路径 |
|------|------|
| 对话学习模块 | `frontend/src/components/ChatLearning.vue` |
| 个性化学习中心 | `frontend/src/components/PersonalizedLearning.vue` |
| AI资源生成中心 | `frontend/src/components/ResourceGenerator.vue` |
| 学习评估中心 | `frontend/src/components/EvaluationCenter.vue` |
| 语音学习中心 | `frontend/src/components/VoiceLearning.vue` |
| 主应用 | `frontend/src/App.vue` |

**五大核心模块**：

1. **对话学习模块** - 与AI进行学习对话，支持多轮对话历史
2. **个性化学习中心** - 学生画像生成与学习路径规划
3. **AI资源生成中心** - PPT/题库/代码/思维导图/视频脚本生成
4. **学习评估中心** - 学习行为数据提交与评估报告生成
5. **语音学习中心** - 语音合成(TTS)与语音识别(ASR)

**技术栈**：
- Vue3 + TypeScript + TailwindCSS
- Composition API
- 异步fetch调用后端API

**启动前端**：

```bash
cd frontend
npm install
npm run dev
```

**验收**：

前端启动后访问 http://localhost:5173，可看到：
- 顶部导航栏：对话学习 | 个性化学习 | 资源生成 | 学习评估 | 语音学习 | RAG知识库
- 各模块功能正常，可调用后端API

---

## 阶段十：Docker部署

| 能力 | 路径 |
|------|------|
| Docker Compose | `docker/docker-compose.yml` |
| 后端Dockerfile | `docker/Dockerfile.backend` |
| 前端Dockerfile | `docker/Dockerfile.frontend` |
| Nginx配置 | `docker/nginx-frontend.conf` |
| 一键启动脚本 | `scripts/start.ps1` / `scripts/start.sh` / `scripts/start.bat` |
| 停止脚本 | `scripts/stop.sh` / `scripts/stop.bat` |

**服务架构**：
```
┌─────────────┐
│   Nginx     │ :8080 (前端静态资源)
│   前端      │
└──────┬──────┘
       │ /api/
       ▼
┌─────────────┐
│   FastAPI   │ :8000 (后端API)
│   后端      │
└──────┬──────┘
       │
   ┌───┴───┐
   ▼       ▼
┌─────┐ ┌─────┐
│Postgres│ │Redis│
└─────┘ └─────┘
```

**启动方式**：

Windows PowerShell:
```powershell
.\scripts\start.ps1
```

Windows CMD:
```cmd
scripts\start.bat
```

Linux/macOS:
```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

**参数说明**：
- `--skip-build` - 跳过镜像构建，加速启动
- `--backend-only` - 仅启动后端服务

**一键启动特性**：
- 自动检查Docker环境
- 自动等待依赖服务健康
- 自动检查服务启动状态
- 支持跳过构建加速启动

**访问地址**：
- 前端: http://localhost:8080
- 后端: http://localhost:8000
- API文档: http://localhost:8000/docs

**停止服务**：

Windows:
```cmd
scripts\stop.bat
```

Linux/macOS:
```bash
./scripts/stop.sh
```

**验收**：

1. 运行启动脚本
2. 访问 http://localhost:8080 能看到前端页面
3. 访问 http://localhost:8000/docs 能看到API文档
4. 运行停止脚本后服务正常停止
