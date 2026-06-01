# EduAgent 前端

基于 **Vue3 + TypeScript + Vite + TailwindCSS** 的多智能体高校个性化学习平台前端。

## 技术栈

- **Vue 3** (Composition API + `<script setup>`)
- **TypeScript**
- **Vite** 构建工具
- **TailwindCSS** 样式框架
- **Mermaid** 思维导图/流程图渲染

## 组件结构

```
src/
├── components/
│   ├── ChatLearning.vue         # 对话学习模块 - 多轮对话、画像分析、路径规划
│   ├── PersonalizedLearning.vue # 个性化学习中心 - 学习路径、资源推荐、进度追踪
│   ├── ResourceGenerator.vue    # AI资源生成中心 - PPT/题库/代码/思维导图/视频
│   ├── EvaluationCenter.vue     # 学习评估中心 - 行为提交、评估报告、指标查看
│   ├── VoiceLearning.vue        # 语音学习中心 - ASR语音识别、TTS语音合成
│   ├── ResultDisplay.vue        # 评估结果展示 - 雷达图、环形进度条、柱状图
│   └── VideoPlayer.vue          # AI视频播放器 - 场景卡片动画、TTS旁白、Canvas录制
├── assets/
│   └── hero.png                 # 首页主视觉图
├── App.vue                      # 主应用 - 导航栏 + 模块路由
├── main.ts                      # 应用入口
└── style.css                    # 全局样式 (TailwindCSS + 自定义)
```

## 快速开始

```bash
cd frontend
npm install
npm run dev
```

启动后访问 `http://localhost:5173`

## 构建部署

```bash
npm run build
```

产物输出到 `dist/` 目录，由 Nginx 提供静态服务。

## Docker 部署

前端通过 Nginx 容器化部署，配置见 `docker/nginx-frontend.conf`：

```bash
docker compose -f docker/docker-compose.yml up --build -d
```

启动后前端运行在 `http://localhost:80`，API 请求通过 Nginx 反向代理到后端 `http://backend:8000`。

## 后端 API 代理

开发模式下，Vite 配置了代理转发 `/api` 请求到后端 `http://127.0.0.1:8000`，详见 `vite.config.ts`。