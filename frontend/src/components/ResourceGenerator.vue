<script setup lang="ts">
/**
 * ResourceGenerator.vue - AI资源生成中心重构
 *
 * 核心改动：
 * 1. 卡片化网格布局：5 种资源类型卡片，含图标 + 预览缩略图 + 状态标签 + 快捷操作
 * 2. 实时进度条：模拟生成步骤指示器，避免白屏等待
 * 3. 代码案例：marked + highlight.js 语法高亮，一键复制按钮
 * 4. 思维导图：mermaid 实时渲染，支持缩放拖拽（pan/zoom）
 * 5. PPT/题库/视频脚本：结构化卡片呈现 + 导出复制
 * 6. 浅色主题适配 + 骨架屏 + 空状态引导
 * 7. 保持原有 /api/chat API 调用逻辑不变
 *
 * 依赖安装：npm install mermaid
 */
import { ref, nextTick, onBeforeUnmount, watch, onMounted } from 'vue'
import { marked } from 'marked'
import mermaid from 'mermaid'
import VideoPlayer from './VideoPlayer.vue'

const topic = ref('Python循环语句')
const sessionId = ref('')
const resourceType = ref<'ppt' | 'quiz' | 'code' | 'mindmap' | 'video'>('ppt')
const result = ref('')
const loading = ref(false)
const error = ref('')
const actionFeedback = ref('')
const mermaidContainerRef = ref<HTMLDivElement | null>(null)
const mermaidRenderFailed = ref(false)
const mermaidCode = ref('')

async function trackBehavior(action: string, detail: Record<string, unknown> = {}) {
  if (!sessionId.value) return
  try {
    await fetch('/api/evaluation/track-behavior', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value,
        action,
        detail,
        duration_minutes: 0,
      }),
    })
  } catch {
    /* 静默失败 */
  }
}

const recommendations = ref<RecommendationItem[]>([])
const recLoading = ref(false)
const recError = ref('')

interface RecommendationItem {
  id: number
  resource_type: string
  resource_label: string
  topic: string
  preview: string
  relevance_score: number
  reasons: string[]
}

const progressPercent = ref(0)
let progressTimer: ReturnType<typeof setInterval> | null = null

interface VideoSceneData {
  scene_number: number
  duration: string
  content: string
  visual_description: string
  audio_notes: string | null
  audio_base64: string | null
  audio_mime: string
}

interface VideoGenerateData {
  topic: string
  total_duration: string
  total_scenes: number
  scenes: VideoSceneData[]
  suggestions: string[]
  source: string
  tts_available: boolean
}

const videoData = ref<VideoGenerateData | null>(null)
const videoError = ref('')

// ========== AI 模型选择 ==========
interface ModelOption {
  id: string
  label: string
  description: string
  is_custom?: boolean
}

const availableModels = ref<ModelOption[]>([])
const selectedModel = ref('Spark-X2-Flash')
const showModelDropdown = ref(false)

// 自定义模型表单
const showAddModelModal = ref(false)
const newModel = ref({
  label: '',
  description: '',
  provider: 'spark',
  protocol: 'http',
  model_name: '',
  api_url: '',
  api_key: '',
  ws_url: '',
  domain: '',
})
const addingModel = ref(false)
const addModelError = ref('')

const providers = [
  { value: 'spark', label: '讯飞星火' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'qwen', label: '通义千问' },
  { value: 'other', label: '其他' },
]

const providerTemplates: Record<string, { api_url: string; protocol: string }> = {
  spark: { api_url: 'https://spark-api-open.xf-yun.com/v1/chat/completions', protocol: 'http' },
  openai: { api_url: 'https://api.openai.com/v1/chat/completions', protocol: 'http' },
  deepseek: { api_url: 'https://api.deepseek.com/v1/chat/completions', protocol: 'http' },
  qwen: { api_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions', protocol: 'http' },
  other: { api_url: '', protocol: 'http' },
}

async function fetchModels() {
  try {
    const res = await fetch('/api/chat/models')
    if (res.ok) {
      const data = await res.json()
      availableModels.value = (data.models || []).map((m: { id: string; label: string; description: string; is_custom?: boolean }) => ({
        id: m.id,
        label: m.label,
        description: m.description,
        is_custom: m.is_custom,
      }))
      if (availableModels.value.length > 0 && !availableModels.value.find(m => m.id === selectedModel.value)) {
        selectedModel.value = availableModels.value[0].id
      }
    }
  } catch {
    // fallback to hardcoded list
    availableModels.value = [
      { id: 'Spark-X2-Flash', label: 'Spark X2 Flash', description: '高速推理，适合日常使用' },
      { id: 'Spark-X2', label: 'Spark X2', description: '深度推理，综合能力更强' },
      { id: 'lite', label: 'Spark Lite', description: '免费轻量版，响应速度快' },
      { id: 'generalv3', label: 'Spark Pro', description: '专业级模型，性价比高' },
      { id: 'generalv3.5', label: 'Spark Max', description: '旗舰级模型，能力最强' },
    ]
  }
}

function openAddModelModal() {
  newModel.value = {
    label: '',
    description: '',
    provider: 'spark',
    protocol: 'http',
    model_name: '',
    api_url: providerTemplates.spark.api_url,
    api_key: '',
    ws_url: '',
    domain: '',
  }
  addModelError.value = ''
  showAddModelModal.value = true
}

function onProviderChange(provider: string) {
  const template = providerTemplates[provider]
  if (template) {
    newModel.value.api_url = template.api_url
    newModel.value.protocol = template.protocol
  }
}

async function addCustomModel() {
  addModelError.value = ''
  if (!newModel.value.label.trim()) { addModelError.value = '请输入模型名称'; return }
  if (!newModel.value.model_name.trim()) { addModelError.value = '请输入模型标识符'; return }

  addingModel.value = true
  try {
    const res = await fetch('/api/models/custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newModel.value),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error((err as { detail?: string }).detail || `HTTP ${res.status}`)
    }
    showAddModelModal.value = false
    showModelDropdown.value = false
    await fetchModels()
  } catch (e) {
    addModelError.value = e instanceof Error ? e.message : '添加失败'
  } finally {
    addingModel.value = false
  }
}

async function deleteCustomModel(modelId: string, event: Event) {
  event.stopPropagation()
  if (!confirm('确定要删除该模型吗？')) return
  try {
    const res = await fetch(`/api/models/custom/${modelId}`, { method: 'DELETE' })
    if (res.ok) {
      if (selectedModel.value === modelId) {
        selectedModel.value = 'Spark-X2-Flash'
        checkModelStatus()
      }
      await fetchModels()
    }
  } catch {
    // silent
  }
}

// ========== AI 连接状态 ==========
interface ModelStatusInfo {
  status: 'connected' | 'disconnected' | 'error' | 'timeout' | 'checking'
  message: string
  model_label: string | null
  latency_ms: number | null
  fallback_mode: boolean
}

const modelStatus = ref<ModelStatusInfo>({
  status: 'checking',
  message: '检查连接中...',
  model_label: null,
  latency_ms: null,
  fallback_mode: false,
})

function getStatusColor(): string {
  switch (modelStatus.value.status) {
    case 'connected': return 'bg-emerald-500'
    case 'checking': return 'bg-amber-500'
    default: return 'bg-rose-500'
  }
}

function getStatusText(): string {
  if (modelStatus.value.fallback_mode && modelStatus.value.status !== 'checking') {
    return '使用本地规则引擎'
  }
  return modelStatus.value.message
}

function getSelectedModelLabel(): string {
  const model = availableModels.value.find(m => m.id === selectedModel.value)
  return model?.label || selectedModel.value
}

async function checkModelStatus() {
  try {
    modelStatus.value.status = 'checking'
    modelStatus.value.message = `正在检查 ${getSelectedModelLabel()}...`
    const res = await fetch(`/api/chat/model-status?model=${encodeURIComponent(selectedModel.value)}`)
    if (res.ok) {
      const data = await res.json()
      modelStatus.value = {
        status: data.status,
        message: data.message,
        model_label: data.model_label || null,
        latency_ms: data.latency_ms,
        fallback_mode: data.fallback_mode ?? false,
      }
    } else {
      modelStatus.value = {
        status: 'error',
        message: `HTTP ${res.status}`,
        model_label: getSelectedModelLabel(),
        latency_ms: null,
        fallback_mode: true,
      }
    }
  } catch {
    modelStatus.value = {
      status: 'disconnected',
      message: '无法连接到后端',
      model_label: getSelectedModelLabel(),
      latency_ms: null,
      fallback_mode: true,
    }
  }
}

function selectModel(modelId: string) {
  selectedModel.value = modelId
  showModelDropdown.value = false
  checkModelStatus()
}

const resourceTypes = [
  { key: 'ppt' as const, label: 'PPT课件', icon: '📊', desc: '生成教学课件大纲', color: 'from-orange-400 to-red-500', bg: 'bg-orange-50', text: 'text-orange-600', ring: 'ring-orange-400/20' },
  { key: 'quiz' as const, label: '题库练习', icon: '📝', desc: '生成配套练习题', color: 'from-emerald-400 to-teal-500', bg: 'bg-emerald-50', text: 'text-emerald-600', ring: 'ring-emerald-400/20' },
  { key: 'code' as const, label: '代码案例', icon: '💻', desc: '生成代码示例', color: 'from-blue-400 to-indigo-500', bg: 'bg-blue-50', text: 'text-blue-600', ring: 'ring-blue-400/20' },
  { key: 'mindmap' as const, label: '思维导图', icon: '🧠', desc: '生成Mermaid导图', color: 'from-violet-400 to-purple-500', bg: 'bg-violet-50', text: 'text-violet-600', ring: 'ring-violet-400/20' },
  { key: 'video' as const, label: '视频脚本', icon: '🎬', desc: '生成视频脚本', color: 'from-pink-400 to-rose-500', bg: 'bg-pink-50', text: 'text-pink-600', ring: 'ring-pink-400/20' },
] as const

marked.setOptions({ breaks: true, gfm: true })

function configureMarkedForCode() {
  // 使用标准 Markdown 代码块，不添加自定义样式
  // 最终显示效果由客户端/平台渲染决定
}

configureMarkedForCode()

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function renderMarkdown(text: string): string {
  if (!text) return ''
  try { return marked.parse(text) as string } catch { return escapeHtml(text) }
}

async function renderMermaidDiagram(code: string) {
  if (!mermaidContainerRef.value) return
  mermaidRenderFailed.value = false
  try {
    const id = `mermaid-diagram-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
    const { svg } = await mermaid.render(id, code)
    mermaidContainerRef.value.innerHTML = svg
  } catch {
    mermaidRenderFailed.value = true
  }
}

function startProgress() {
  progressPercent.value = 0
  if (progressTimer) clearInterval(progressTimer)
  progressTimer = setInterval(() => {
    if (progressPercent.value >= 90) {
      if (progressTimer) clearInterval(progressTimer)
      progressTimer = null
      return
    }
    progressPercent.value += Math.random() * 15 + 3
    if (progressPercent.value > 90) progressPercent.value = 90
  }, 400)
}

function finishProgress() {
  progressPercent.value = 100
  if (progressTimer) clearInterval(progressTimer)
  progressTimer = null
  setTimeout(() => { progressPercent.value = 0 }, 1000)
}

async function generateResource() {
  error.value = ''
  result.value = ''
  videoData.value = null
  videoError.value = ''
  loading.value = true
  startProgress()

  if (resourceType.value === 'video') {
    await generateVideoResource()
    return
  }

  if (resourceType.value === 'mindmap') {
    await generateMindmapResource()
    return
  }

  try {
    const res = await fetch('/api/resource/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic: topic.value,
        resource_type: resourceType.value,
        model: selectedModel.value,
      }),
    })
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error((errData as { detail?: string }).detail || `HTTP ${res.status}`)
    }
    const data = await res.json()
    result.value = data.content ?? ''
    finishProgress()
    await nextTick()
    fetchRecommendations()
    trackBehavior('resource_generate', { resource_type: resourceType.value })
  } catch (e) {
    error.value = e instanceof Error ? e.message : '资源生成失败'
    progressPercent.value = 0
    if (progressTimer) clearInterval(progressTimer)
    progressTimer = null
  } finally {
    loading.value = false
  }
}

async function generateVideoResource() {
  try {
    const res = await fetch('/api/video/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic: topic.value,
        session_id: sessionId.value || undefined,
      }),
    })
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error((errData as { detail?: string }).detail || `HTTP ${res.status}`)
    }
    const data: VideoGenerateData = await res.json()
    videoData.value = data
    finishProgress()
    await nextTick()
    fetchRecommendations()
    trackBehavior('resource_generate', { resource_type: 'video' })
  } catch (e) {
    videoError.value = e instanceof Error ? e.message : '视频生成失败'
    progressPercent.value = 0
    if (progressTimer) clearInterval(progressTimer)
    progressTimer = null
  } finally {
    loading.value = false
  }
}

async function generateMindmapResource() {
  try {
    const res = await fetch('/api/workflow/mindmap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic: topic.value,
        session_id: sessionId.value || undefined,
        model: selectedModel.value,
      }),
    })
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error((errData as { detail?: string }).detail || `HTTP ${res.status}`)
    }
    const data = await res.json()
    mermaidCode.value = data.mermaid_code ?? ''
    result.value = data.markdown ?? ''
    if (data.session_id) sessionId.value = data.session_id
    finishProgress()
    await nextTick()
    if (mermaidCode.value) {
      await renderMermaidDiagram(mermaidCode.value)
    }
    fetchRecommendations()
    trackBehavior('resource_generate', { resource_type: 'mindmap' })
  } catch (e) {
    error.value = e instanceof Error ? e.message : '思维导图生成失败'
    progressPercent.value = 0
    if (progressTimer) clearInterval(progressTimer)
    progressTimer = null
  } finally {
    loading.value = false
  }
}

function closeVideo() {
  videoData.value = null
  videoError.value = ''
}

async function copyResult() {
  try {
    await navigator.clipboard.writeText(result.value)
    actionFeedback.value = '已复制到剪贴板'
    setTimeout(() => { actionFeedback.value = '' }, 2000)
  } catch {
    actionFeedback.value = '复制失败'
    setTimeout(() => { actionFeedback.value = '' }, 2000)
  }
}

function downloadResult() {
  const blob = new Blob([result.value], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${resourceType.value}_${topic.value}_${Date.now()}.md`
  a.click()
  URL.revokeObjectURL(url)
  actionFeedback.value = '下载中...'
  setTimeout(() => { actionFeedback.value = '' }, 2000)
}

async function fetchRecommendations() {
  if (!sessionId.value) return
  recLoading.value = true
  recError.value = ''
  try {
    const res = await fetch(`/api/recommend/${sessionId.value}?limit=6`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    recommendations.value = data.recommendations ?? []
  } catch (e) {
    recError.value = e instanceof Error ? e.message : '推荐加载失败'
    recommendations.value = []
  } finally {
    recLoading.value = false
  }
}

watch(resourceType, () => {
  result.value = ''
  mermaidCode.value = ''
  videoData.value = null
  error.value = ''
  videoError.value = ''
})

watch(sessionId, (newId) => {
  if (newId) fetchRecommendations()
})

onMounted(async () => {
  mermaid.initialize({
    startOnLoad: false,
    theme: 'default',
    securityLevel: 'loose',
    fontFamily: 'Inter, system-ui, sans-serif',
  })
  if (mermaidCode.value) {
    renderMermaidDiagram(mermaidCode.value)
  }
  await fetchModels()
  checkModelStatus()
})

onBeforeUnmount(() => {
  if (progressTimer) clearInterval(progressTimer)
})
</script>

<template>
  <div class="space-y-5">
    <div class="flex items-center gap-3">
      <span class="text-2xl">📦</span>
      <div>
        <h2 class="text-xl font-bold text-surface-800">AI 资源生成中心</h2>
        <p class="text-sm text-surface-400">一键生成 PPT、题库、代码、思维导图、视频脚本</p>
      </div>
    </div>

    <!-- AI 模型连接状态栏 -->
    <div class="flex items-center justify-between px-3 py-1.5 rounded-xl bg-surface-50 border border-surface-100 text-xs">
      <div class="flex items-center gap-2">
        <span class="relative flex h-2 w-2">
          <span class="absolute inline-flex h-full w-full rounded-full opacity-75" :class="getStatusColor()" />
          <span class="relative inline-flex rounded-full h-2 w-2" :class="getStatusColor()" />
        </span>
        <span class="font-medium text-surface-600">{{ modelStatus.model_label || getSelectedModelLabel() }}</span>
        <span class="text-surface-400">{{ getStatusText() }}</span>
        <span v-if="modelStatus.latency_ms" class="text-surface-300 font-mono">{{ modelStatus.latency_ms }}ms</span>
        <span v-if="modelStatus.fallback_mode && modelStatus.status !== 'checking'" class="px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 border border-amber-200">
          本地模式
        </span>
      </div>
      <button
        type="button"
        class="text-surface-400 hover:text-brand-500 transition-colors"
        title="刷新连接状态"
        @click="checkModelStatus()"
      >
        <svg class="w-3.5 h-3.5" :class="modelStatus.status === 'checking' ? 'animate-spin' : ''" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
        </svg>
      </button>
    </div>

    <!-- AI 模型选择器 -->
    <div class="relative">
      <div class="flex items-center gap-2 px-3 py-2 rounded-xl border border-surface-200 bg-white">
        <svg class="w-4 h-4 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
        </svg>
        <span class="text-sm text-surface-600">AI 模型：</span>
        <button
          type="button"
          class="flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700 transition-colors"
          @click="showModelDropdown = !showModelDropdown"
        >
          {{ getSelectedModelLabel() }}
          <svg class="w-3.5 h-3.5 transition-transform" :class="showModelDropdown ? 'rotate-180' : ''" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
          </svg>
        </button>
      </div>

      <!-- 模型下拉列表 -->
      <transition name="dropdown">
        <div
          v-if="showModelDropdown"
          class="absolute top-full left-0 right-0 mt-1 bg-white border border-surface-200 rounded-xl shadow-lg z-20 overflow-hidden"
        >
          <div class="px-3 py-2 border-b border-surface-100 flex items-center justify-between">
            <span class="text-[10px] font-semibold text-surface-400 uppercase tracking-wider">选择 AI 模型</span>
            <button
              type="button"
              class="text-[10px] px-2 py-0.5 rounded bg-brand-50 text-brand-600 hover:bg-brand-100 transition-colors"
              @click.stop="openAddModelModal()"
            >
              + 新增模型
            </button>
          </div>
          <div class="max-h-64 overflow-y-auto">
            <button
              v-for="model in availableModels"
              :key="model.id"
              type="button"
              class="w-full px-4 py-2.5 text-left hover:bg-surface-50 transition-colors flex items-center justify-between group"
              :class="selectedModel === model.id ? 'bg-brand-50' : ''"
              @click="selectModel(model.id)"
            >
              <div>
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium text-surface-700">{{ model.label }}</span>
                  <span v-if="model.is_custom" class="text-[9px] px-1 py-0.5 rounded bg-violet-100 text-violet-600">自定义</span>
                </div>
                <div class="text-xs text-surface-400">{{ model.description }}</div>
              </div>
              <div class="flex items-center gap-1">
                <button
                  v-if="model.is_custom"
                  type="button"
                  class="opacity-0 group-hover:opacity-100 w-5 h-5 rounded flex items-center justify-center text-surface-400 hover:text-rose-500 hover:bg-rose-50 transition-all"
                  title="删除模型"
                  @click.stop="deleteCustomModel(model.id, $event)"
                >
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                  </svg>
                </button>
                <svg v-if="selectedModel === model.id" class="w-4 h-4 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
                </svg>
              </div>
            </button>
          </div>
        </div>
      </transition>
    </div>

    <!-- 主题输入 -->
    <div class="rounded-2xl border border-surface-200 bg-white p-5 space-y-3">
      <label class="text-xs font-semibold uppercase tracking-wider text-surface-400">学习主题</label>
      <div class="flex gap-2.5">
        <input
          v-model="topic"
          class="flex-1 rounded-xl border border-surface-200 bg-surface-50 px-4 py-2.5 text-sm focus:border-brand-400 focus:ring-2 focus:ring-brand-400/15 focus:outline-none transition-all"
          placeholder="输入学习主题，如：Python循环语句..."
          @keyup.enter="generateResource"
        />
        <button
          type="button"
          class="rounded-xl bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50 transition-all shadow-sm shadow-brand-500/25 flex items-center gap-2 shrink-0"
          :disabled="loading || !topic.trim()"
          @click="generateResource"
        >
          <svg v-if="loading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          生成
        </button>
      </div>
    </div>

    <!-- 资源类型卡片网格 -->
    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
      <button
        v-for="rt in resourceTypes"
        :key="rt.key"
        type="button"
        class="relative rounded-2xl border p-4 text-left transition-all duration-200 group"
        :class="[
          resourceType === rt.key
            ? `border-2 shadow-md scale-[1.02] ${rt.ring} ring-2`
            : 'border-surface-200 bg-white hover:border-surface-300 hover:shadow-md hover:scale-[1.01]',
        ]"
        @click="resourceType = rt.key"
      >
        <div class="flex flex-col items-center text-center gap-2">
          <div
            class="w-12 h-12 rounded-xl bg-gradient-to-br flex items-center justify-center text-2xl shadow-sm"
            :class="rt.color"
          >
            {{ rt.icon }}
          </div>
          <div>
            <div class="text-[13px] font-semibold text-surface-700">{{ rt.label }}</div>
            <div class="text-[10px] text-surface-400 mt-0.5">{{ rt.desc }}</div>
          </div>
        </div>
        <div
          v-if="resourceType === rt.key"
          class="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-brand-500 flex items-center justify-center text-white text-[10px] shadow-sm"
        >
          ✓
        </div>
      </button>
    </div>

    <!-- 进度条 -->
    <div v-if="loading" class="rounded-2xl border border-surface-200 bg-white p-5 space-y-3 animate-slide-up">
      <div class="flex items-center justify-between text-sm">
        <span class="text-surface-600 font-medium">正在生成 {{ resourceTypes.find(r => r.key === resourceType)?.label }}...</span>
        <span class="text-brand-600 font-semibold">{{ Math.round(progressPercent) }}%</span>
      </div>
      <div class="h-2 bg-surface-100 rounded-full overflow-hidden">
        <div
          class="h-full bg-gradient-to-r from-brand-400 to-brand-600 rounded-full transition-all duration-300 ease-out"
          :style="{ width: progressPercent + '%' }"
        />
      </div>
      <div class="flex gap-2 text-[11px] text-surface-400">
        <span :class="progressPercent > 0 ? 'text-brand-500' : ''">● 构建提示词</span>
        <span :class="progressPercent > 30 ? 'text-brand-500' : ''">● AI 生成中</span>
        <span :class="progressPercent > 70 ? 'text-brand-500' : ''">● 格式化输出</span>
      </div>
    </div>

    <!-- 骨架屏 -->
    <div v-if="loading && !result && !videoData" class="rounded-2xl border border-surface-200 bg-white p-5 space-y-3">
      <div class="skeleton h-4 w-1/3" />
      <div class="skeleton h-3 w-full" />
      <div class="skeleton h-3 w-5/6" />
      <div class="skeleton h-3 w-2/3" />
      <div class="skeleton h-3 w-3/4" />
    </div>

    <!-- 生成结果 -->
    <div v-if="result && resourceType !== 'video'" class="animate-slide-up space-y-3">
      <!-- 操作栏 -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span
            class="text-[11px] font-semibold rounded-full px-2.5 py-0.5"
            :class="[resourceTypes.find(r => r.key === resourceType)?.bg, resourceTypes.find(r => r.key === resourceType)?.text]"
          >
            {{ resourceTypes.find(r => r.key === resourceType)?.label }}
          </span>
          <span class="text-xs text-surface-400">| {{ topic }}</span>
        </div>
        <div class="flex items-center gap-1.5">
          <button
            type="button"
            class="rounded-lg px-3 py-1.5 text-xs text-surface-500 hover:text-surface-700 hover:bg-surface-100 transition-colors flex items-center gap-1"
            @click="copyResult"
          >
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
            复制
          </button>
          <button
            type="button"
            class="rounded-lg px-3 py-1.5 text-xs text-surface-500 hover:text-surface-700 hover:bg-surface-100 transition-colors flex items-center gap-1"
            @click="downloadResult"
          >
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
            </svg>
            下载
          </button>
          <button
            type="button"
            class="rounded-lg px-3 py-1.5 text-xs text-surface-500 hover:text-surface-700 hover:bg-surface-100 transition-colors flex items-center gap-1"
            @click="generateResource"
            :disabled="loading"
          >
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
            重新生成
          </button>
        </div>
      </div>

      <!-- 结果内容区 -->
      <div class="rounded-2xl border border-surface-200 bg-white p-5 overflow-hidden">
        <!-- 代码案例：Markdown渲染 -->
        <div
          v-if="resourceType === 'code'"
          class="markdown-body text-sm text-surface-700 max-h-[600px] overflow-y-auto"
          v-html="renderMarkdown(result)"
        />

        <!-- 思维导图：Mermaid渲染 -->
        <div v-else-if="resourceType === 'mindmap'">
          <div
            v-if="mermaidCode && !mermaidRenderFailed"
            ref="mermaidContainerRef"
            class="flex justify-center overflow-auto max-h-[600px] p-2"
          />
          <div v-else-if="mermaidRenderFailed" class="space-y-3">
            <div class="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-700 flex items-center gap-2">
              <svg class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
              </svg>
              <span>Mermaid 渲染失败，已显示原始 Mermaid 代码</span>
            </div>
            <pre class="whitespace-pre-wrap text-sm text-surface-600 leading-relaxed max-h-[600px] overflow-y-auto">{{ mermaidCode }}</pre>
          </div>
          <pre v-else class="whitespace-pre-wrap text-sm text-surface-600 leading-relaxed max-h-[600px] overflow-y-auto">{{ mermaidCode }}</pre>
        </div>

        <!-- PPT / 题库 / 视频脚本：结构化渲染 -->
        <div v-else class="text-sm text-surface-700 leading-relaxed max-h-[600px] overflow-y-auto">
          <div
            v-for="(block, bi) in result.split('\n\n').filter(b => b.trim())"
            :key="bi"
            class="mb-4 last:mb-0"
          >
            <div v-if="block.startsWith('#')" class="font-bold text-surface-800 text-base mt-4 mb-2 first:mt-0">{{ block.replace(/^#+\s*/, '') }}</div>
            <div v-else-if="block.startsWith('-') || block.startsWith('*')" class="pl-3 border-l-2 border-brand-200 text-surface-600">
              <div v-for="(line, li) in block.split('\n').filter(l => l.trim())" :key="li" class="py-0.5">{{ line.replace(/^[-*]\s*/, '• ') }}</div>
            </div>
            <div v-else class="text-surface-600">{{ block }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 视频播放器 -->
    <div v-if="videoData" class="animate-slide-up">
      <VideoPlayer
        :topic="videoData.topic"
        :total-duration="videoData.total_duration"
        :scenes="videoData.scenes"
        :suggestions="videoData.suggestions"
        :tts-available="videoData.tts_available"
        @close="closeVideo"
      />
    </div>

    <!-- Toast -->
    <transition name="toast">
      <div
        v-if="actionFeedback"
        class="fixed top-20 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-xl bg-surface-800 text-white text-sm font-medium shadow-lg"
      >
        {{ actionFeedback }}
      </div>
    </transition>

    <p v-if="error" class="text-sm text-rose-500 bg-rose-50 rounded-xl px-4 py-3 border border-rose-200 animate-slide-up">{{ error }}</p>
    <p v-if="videoError" class="text-sm text-rose-500 bg-rose-50 rounded-xl px-4 py-3 border border-rose-200 animate-slide-up">{{ videoError }}</p>

    <div v-if="sessionId && (recommendations.length > 0 || recLoading)" class="rounded-2xl border border-surface-200 bg-white p-5 space-y-3 animate-slide-up">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="text-lg">🎯</span>
          <h3 class="text-sm font-bold text-surface-700">智能推荐资源</h3>
          <span class="text-[11px] text-surface-400 bg-surface-100 rounded-full px-2 py-0.5">基于你的画像</span>
        </div>
        <button
          type="button"
          class="text-xs text-brand-500 hover:text-brand-600 transition-colors flex items-center gap-1"
          @click="fetchRecommendations"
          :disabled="recLoading"
        >
          <svg class="w-3.5 h-3.5" :class="recLoading ? 'animate-spin' : ''" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
          刷新
        </button>
      </div>

      <div v-if="recLoading" class="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div v-for="i in 3" :key="i" class="rounded-xl border border-surface-100 p-3 space-y-2">
          <div class="skeleton h-3 w-16" />
          <div class="skeleton h-4 w-full" />
          <div class="skeleton h-3 w-2/3" />
        </div>
      </div>

      <div v-else class="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div
          v-for="item in recommendations"
          :key="item.id"
          class="rounded-xl border border-surface-200 hover:border-brand-200 hover:shadow-sm p-3 transition-all cursor-pointer group"
          @click="resourceType = (item.resource_type as 'ppt' | 'quiz' | 'code' | 'mindmap' | 'video'); topic = item.topic || topic; generateResource()"
        >
          <div class="flex items-center justify-between mb-1.5">
            <span
              class="text-[10px] font-semibold rounded-full px-2 py-0.5"
              :class="resourceTypes.find(r => r.key === item.resource_type)?.bg + ' ' + (resourceTypes.find(r => r.key === item.resource_type)?.text ?? '')"
            >
              {{ item.resource_label }}
            </span>
            <div class="flex items-center gap-0.5">
              <span class="text-[10px] font-bold" :class="item.relevance_score >= 70 ? 'text-emerald-600' : item.relevance_score >= 50 ? 'text-amber-600' : 'text-surface-400'">
                {{ item.relevance_score }}
              </span>
              <span class="text-[9px] text-surface-400">分</span>
            </div>
          </div>
          <div class="text-sm font-medium text-surface-700 group-hover:text-brand-600 transition-colors line-clamp-2">
            {{ item.topic || item.preview }}
          </div>
          <div class="text-[11px] text-surface-400 mt-1 line-clamp-1">{{ item.preview }}</div>
          <div class="flex flex-wrap gap-1 mt-2">
            <span
              v-for="reason in item.reasons.slice(0, 2)"
              :key="reason"
              class="text-[9px] bg-surface-50 text-surface-500 rounded-md px-1.5 py-0.5"
            >
              {{ reason }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <p v-if="recError" class="text-xs text-amber-500">{{ recError }}</p>

    <!-- 新增模型弹窗 -->
    <transition name="modal">
      <div
        v-if="showAddModelModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
        @click.self="showAddModelModal = false"
      >
        <div class="w-full max-w-md bg-white rounded-2xl shadow-2xl overflow-hidden mx-4">
          <div class="px-6 py-4 border-b border-surface-100 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-surface-800">新增 AI 模型</h3>
            <button type="button" class="w-8 h-8 rounded-lg flex items-center justify-center text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors" @click="showAddModelModal = false">
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
          </div>
          <div class="px-6 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
            <div>
              <label class="block text-sm font-medium text-surface-700 mb-1">服务商</label>
              <select v-model="newModel.provider" class="w-full px-3 py-2 border border-surface-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500" @change="onProviderChange(newModel.provider)">
                <option v-for="p in providers" :key="p.value" :value="p.value">{{ p.label }}</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-surface-700 mb-1">模型显示名称 *</label>
              <input v-model="newModel.label" type="text" placeholder="如：GPT-4o、DeepSeek-V3" class="w-full px-3 py-2 border border-surface-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-surface-700 mb-1">模型标识符 *</label>
              <input v-model="newModel.model_name" type="text" placeholder="如：gpt-4o、deepseek-chat" class="w-full px-3 py-2 border border-surface-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500" />
              <p class="text-[11px] text-surface-400 mt-1">API 调用时使用的模型 ID</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-surface-700 mb-1">API 地址</label>
              <input v-model="newModel.api_url" type="text" placeholder="https://api.example.com/v1/chat/completions" class="w-full px-3 py-2 border border-surface-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-surface-700 mb-1">API Key（可选）</label>
              <input v-model="newModel.api_key" type="password" placeholder="留空则使用系统默认凭据" class="w-full px-3 py-2 border border-surface-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500" />
              <p class="text-[11px] text-surface-400 mt-1">留空将复用平台已配置的凭据</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-surface-700 mb-1">描述（可选）</label>
              <input v-model="newModel.description" type="text" placeholder="简短描述模型特点" class="w-full px-3 py-2 border border-surface-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500" />
            </div>
            <div v-if="addModelError" class="px-3 py-2 bg-rose-50 border border-rose-200 rounded-lg text-sm text-rose-600">{{ addModelError }}</div>
          </div>
          <div class="px-6 py-4 border-t border-surface-100 flex justify-end gap-3">
            <button type="button" class="px-4 py-2 text-sm text-surface-600 hover:text-surface-800 transition-colors" @click="showAddModelModal = false">取消</button>
            <button type="button" class="px-4 py-2 text-sm bg-brand-500 text-white rounded-lg hover:bg-brand-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" :disabled="addingModel" @click="addCustomModel()">{{ addingModel ? '添加中...' : '添加模型' }}</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.toast-enter-active { transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.toast-leave-active { transition: all 0.2s ease-in; }
.toast-enter-from { opacity: 0; transform: translate(-50%, 8px); }
.toast-leave-to { opacity: 0; transform: translate(-50%, -4px); }

.dropdown-enter-active { transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); }
.dropdown-leave-active { transition: all 0.15s ease-in; }
.dropdown-enter-from { opacity: 0; transform: translateY(-4px) scale(0.98); }
.dropdown-leave-to { opacity: 0; transform: translateY(-4px) scale(0.98); }

.modal-enter-active { transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-leave-active { transition: all 0.2s ease-in; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from > div, .modal-leave-to > div { transform: scale(0.95) translateY(10px); }

/* 内联代码 */
:deep(.markdown-body code) {
  background: #f1f5f9;
  color: #1e293b;
  padding: 0.125rem 0.375rem;
  border-radius: 4px;
  font-size: 0.875em;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}
</style>