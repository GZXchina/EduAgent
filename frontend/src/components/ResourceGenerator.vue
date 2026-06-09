<script setup lang="ts">
/**
 * ResourceGenerator.vue - AI资源生成中心重构
 *
 * 核心改动：
 * 1. 卡片化网格布局：5 种资源类型卡片，含图标 + 预览缩略图 + 状态标签 + 快捷操作
 * 2. 实时进度条：模拟生成步骤指示器，避免白屏等待
 * 3. 代码案例：marked + highlight.js 语法高亮，一键复制按钮
 * 4. 思维导图：markmap 交互式渲染，支持缩放/拖拽/折叠/导出
 * 5. PPT/题库/视频脚本：结构化卡片呈现 + 导出复制
 * 6. 浅色主题适配 + 骨架屏 + 空状态引导
 * 7. 保持原有 /api/chat API 调用逻辑不变
 *
 * 依赖安装：npm install markmap-lib markmap-view markmap-toolbar
 */
import { ref, nextTick, onBeforeUnmount, watch, onMounted } from 'vue'
import { marked } from 'marked'
import { Transformer } from 'markmap-lib'
import { Markmap } from 'markmap-view'
import { Toolbar } from 'markmap-toolbar'
import 'markmap-toolbar/dist/style.css'
import VideoPlayer from './VideoPlayer.vue'

const topic = ref('Python循环语句')
const sessionId = ref('')
const resourceType = ref<'ppt' | 'quiz' | 'code' | 'mindmap' | 'video'>('ppt')
const result = ref('')
const loading = ref(false)
const error = ref('')
const actionFeedback = ref('')
const markmapContainerRef = ref<SVGSVGElement | null>(null)
const markmapInstance = ref<Markmap | null>(null)
const markmapToolbarRef = ref<HTMLDivElement | null>(null)
const mindmapMarkdown = ref('')

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

// ========== PPT 生成状态 ==========
interface PPTProgressInfo {
  sid: string
  status: 'done' | 'building' | 'failed'
  ppt_status: string
  ai_image_status: string
  card_note_status: string
  total_pages: number
  done_pages: number
  ppt_url: string
  cover_img: string
  progress_percent: number
}

const pptProgress = ref<PPTProgressInfo | null>(null)
const pptTaskId = ref('')
const pptQueryUsed = ref('')
const pptMode = ref<'online' | 'local' | 'html'>('online') // PPT生成模式
const pptTheme = ref<'default' | 'dark' | 'education'>('default') // 本地模式主题

// ========== HTML PPT 演示状态 ==========
const htmlTheme = ref('corporate-clean')
const htmlContent = ref('')
const htmlPreviewReady = ref(false)
const htmlThemes = ref<{ id: string; label: string }[]>([
  { id: 'corporate-clean', label: '企业商务' },
  { id: 'academic-paper', label: '学术论文' },
  { id: 'tokyo-night', label: '东京暗夜' },
  { id: 'blueprint', label: '蓝图工程' },
  { id: 'soft-pastel', label: '柔和马卡龙' },
  { id: 'xiaohongshu-white', label: '小红书白底' },
  { id: 'minimal-white', label: '极简白' },
  { id: 'dracula', label: 'Dracula暗色' },
])
let progressPollTimer: ReturnType<typeof setInterval> | null = null
let progressPollCount = 0
let progressErrorCount = 0
const MAX_PROGRESS_POLL = 100 // 最多轮询100次（约5分钟）
const MAX_PROGRESS_ERRORS = 3 // 连续错误3次后停止轮询

// ========== PPT 预览状态 ==========
interface PPTOutlineChapter {
  chapterTitle?: string
  title?: string
  chapterSections?: PPTOutlineSection[]
  sections?: PPTOutlineSection[]
  [key: string]: unknown
}
interface PPTOutlineSection {
  sectionTitle?: string
  title?: string
  [key: string]: unknown
}
interface PPTOutlineData {
  title: string
  sub_title: string
  outline: string
  outline_parsed: PPTOutlineChapter[]
}
const showPPTPreview = ref(false)
const pptOutline = ref<PPTOutlineData | null>(null)
const pptPreviewLoading = ref(false)
const pptPreviewError = ref('')

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
const modelDropdownRef = ref<HTMLDivElement | null>(null)

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

async function renderMarkmap(markdown: string) {
  if (!markmapContainerRef.value) return
  try {
    const transformer = new Transformer()
    const { root } = transformer.transform(markdown)

    if (markmapInstance.value) {
      markmapInstance.value.setData(root)
      markmapInstance.value.fit()
    } else {
      markmapInstance.value = Markmap.create(markmapContainerRef.value, {
        autoFit: true,
        duration: 300,
        padding: 20,
      }, root)

      // 挂载工具栏
      if (markmapToolbarRef.value) {
        const toolbar = Toolbar.create(markmapInstance.value)
        markmapToolbarRef.value.innerHTML = ''
        markmapToolbarRef.value.appendChild(toolbar.el)
      }
    }
  } catch (e) {
    console.error('markmap渲染失败:', e)
  }
}

function exportMindmapSVG() {
  if (!markmapContainerRef.value) return
  const svgData = new XMLSerializer().serializeToString(markmapContainerRef.value)
  const blob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${topic.value}-mindmap.svg`
  a.click()
  URL.revokeObjectURL(url)
  showActionFeedback('SVG已下载')
}

function exportMindmapHTML() {
  if (!mindmapMarkdown.value) return
  const html = `<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<script src="https://cdn.jsdelivr.net/npm/markmap-autoloader@latest"><\/script>
<style>body{margin:0;padding:0;} .markmap{width:100%;height:100vh;}</style>
</head><body>
<textarea style="display:none">${mindmapMarkdown.value}</textarea>
</body></html>`
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${topic.value}-mindmap.html`
  a.click()
  URL.revokeObjectURL(url)
  showActionFeedback('HTML已下载')
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
  if (loading.value) return // 防止重复点击
  // 清理旧的轮询定时器
  if (progressPollTimer) {
    clearInterval(progressPollTimer)
    progressPollTimer = null
  }
  error.value = ''
  result.value = ''
  videoData.value = null
  videoError.value = ''
  pptProgress.value = null
  pptTaskId.value = ''
  pptQueryUsed.value = ''
  htmlContent.value = ''
  htmlPreviewReady.value = false
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

  if (resourceType.value === 'ppt') {
    if (pptMode.value === 'local') {
      await generatePPTLocal()
    } else if (pptMode.value === 'html') {
      await generatePPTHtml()
    } else {
      await generatePPTResource()
    }
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

async function generatePPTResource() {
  try {
    const res = await fetch('/api/aippt/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: topic.value,
        optimize_model: selectedModel.value,
        optimize_prompt: true,
        author: 'EduAgent',
        is_card_note: true,
        search: false,
        is_figure: true,
        ai_image: 'normal',
      }),
    })

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error((errData as { detail?: string }).detail || `HTTP ${res.status}`)
    }

    const data = await res.json()
    pptTaskId.value = data.sid
    pptQueryUsed.value = data.optimized_query
    pptProgress.value = {
      sid: data.sid,
      status: data.status === 'done' ? 'done' : 'building',
      ppt_status: '',
      ai_image_status: '',
      card_note_status: '',
      total_pages: data.total_pages,
      done_pages: data.done_pages,
      ppt_url: data.ppt_url,
      cover_img: data.cover_img || '',
      progress_percent: data.total_pages > 0 ? Math.round((data.done_pages / data.total_pages) * 100) : 0,
    }

    if (pptProgress.value.status === 'done') {
      finishProgress()
      trackBehavior('resource_generate', { resource_type: 'ppt' })
    } else {
      startProgressPolling()
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'PPT生成失败'
    progressPercent.value = 0
    if (progressTimer) clearInterval(progressTimer)
    progressTimer = null
    if (progressPollTimer) clearInterval(progressPollTimer)
    progressPollTimer = null
  } finally {
    loading.value = false
  }
}

async function generatePPTLocal() {
  try {
    const res = await fetch('/api/aippt/generate-local', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: topic.value,
        model: selectedModel.value,
        theme: pptTheme.value,
      }),
    })

    if (!res.ok) {
      let errMsg = `HTTP ${res.status}`
      try {
        const errData = await res.json()
        errMsg = (errData as { detail?: string }).detail || errMsg
      } catch {
        // 非 JSON 响应
      }
      throw new Error(errMsg)
    }

    // 直接下载 .pptx 文件
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const disposition = res.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename="?(.+?)"?$/)
    a.download = match ? match[1] : `${topic.value.slice(0, 30)}.pptx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    finishProgress()
    result.value = `本地PPT已生成并下载：${topic.value}`
    await nextTick()
    fetchRecommendations()
    trackBehavior('resource_generate', { resource_type: 'ppt', mode: 'local' })
  } catch (e) {
    error.value = e instanceof Error ? e.message : '本地PPT生成失败'
    progressPercent.value = 0
    if (progressTimer) clearInterval(progressTimer)
    progressTimer = null
  } finally {
    loading.value = false
  }
}

async function generatePPTHtml() {
  try {
    const res = await fetch('/api/aippt/generate-html', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: topic.value,
        model: selectedModel.value,
        theme: htmlTheme.value,
        with_presenter: true,
      }),
    })

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error((errData as { detail?: string }).detail || `HTTP ${res.status}`)
    }

    const data = await res.json()
    htmlContent.value = data.html
    htmlPreviewReady.value = true
    finishProgress()
    await nextTick()
    fetchRecommendations()
    trackBehavior('resource_generate', { resource_type: 'ppt', mode: 'html' })
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'HTML演示生成失败'
    progressPercent.value = 0
    if (progressTimer) clearInterval(progressTimer)
    progressTimer = null
  } finally {
    loading.value = false
  }
}

function openHtmlFullscreen() {
  if (!htmlContent.value) return
  const win = window.open('', '_blank')
  if (!win) { alert('请允许弹出窗口'); return }
  win.document.open()
  win.document.write(htmlContent.value)
  win.document.close()
}

function downloadHtml() {
  if (!htmlContent.value) return
  const blob = new Blob([htmlContent.value], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${topic.value.slice(0, 30)}.html`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  actionFeedback.value = 'HTML文件已下载'
  setTimeout(() => { actionFeedback.value = '' }, 2000)
}

function startProgressPolling() {
  if (progressPollTimer) clearInterval(progressPollTimer)
  progressPollCount = 0
  progressErrorCount = 0
  progressPollTimer = setInterval(async () => {
    if (!pptTaskId.value) {
      if (progressPollTimer) clearInterval(progressPollTimer)
      progressPollTimer = null
      return
    }

    progressPollCount++
    if (progressPollCount > MAX_PROGRESS_POLL) {
      if (progressPollTimer) clearInterval(progressPollTimer)
      progressPollTimer = null
      pptProgress.value = { ...pptProgress.value!, status: 'failed' }
      error.value = 'PPT生成超时，请重试'
      return
    }

    try {
      const res = await fetch('/api/aippt/progress', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sid: pptTaskId.value }),
      })

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      const data = await res.json()
      progressErrorCount = 0 // 成功时重置错误计数
      pptProgress.value = {
        sid: data.sid,
        status: data.status,
        ppt_status: data.ppt_status,
        ai_image_status: data.ai_image_status,
        card_note_status: data.card_note_status,
        total_pages: data.total_pages,
        done_pages: data.done_pages,
        ppt_url: data.ppt_url,
        cover_img: data.cover_img || '',
        progress_percent: data.progress_percent,
      }

      progressPercent.value = data.progress_percent

      if (data.status === 'done' || data.status === 'failed') {
        if (progressPollTimer) clearInterval(progressPollTimer)
        progressPollTimer = null
        finishProgress()
        if (data.status === 'done') {
          trackBehavior('resource_generate', { resource_type: 'ppt' })
        }
      }
    } catch (e) {
      progressErrorCount++
      console.error('轮询进度失败:', e)
      if (progressErrorCount >= MAX_PROGRESS_ERRORS) {
        if (progressPollTimer) clearInterval(progressPollTimer)
        progressPollTimer = null
        error.value = 'PPT进度查询连续失败，请稍后重试'
      }
      // 否则继续轮询，等待下次重试
    }
  }, 3000)
}

function downloadPPT() {
  if (!pptProgress.value?.ppt_url) return
  window.open(pptProgress.value.ppt_url, '_blank')
  actionFeedback.value = '正在下载PPT...'
  setTimeout(() => { actionFeedback.value = '' }, 2000)
}

async function previewPPT() {
  if (!pptTaskId.value) return
  pptPreviewLoading.value = true
  pptPreviewError.value = ''
  showPPTPreview.value = true
  try {
    const res = await fetch(`/api/aippt/outline?sid=${encodeURIComponent(pptTaskId.value)}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    pptOutline.value = await res.json()
  } catch (e) {
    pptOutline.value = null
    pptPreviewError.value = e instanceof Error ? e.message : '获取大纲失败'
  } finally {
    pptPreviewLoading.value = false
  }
}

function closePPTPreview() {
  showPPTPreview.value = false
}

const VALID_RESOURCE_TYPES = new Set(['ppt', 'quiz', 'code', 'mindmap', 'video'])

function applyRecommendation(item: RecommendationItem) {
  if (!VALID_RESOURCE_TYPES.has(item.resource_type)) return
  resourceType.value = item.resource_type as 'ppt' | 'quiz' | 'code' | 'mindmap' | 'video'
  topic.value = item.topic || topic.value
  generateResource()
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
    mindmapMarkdown.value = data.markdown ?? ''
    result.value = data.markdown ?? ''
    if (data.session_id) sessionId.value = data.session_id
    finishProgress()
    await nextTick()
    if (mindmapMarkdown.value) {
      await renderMarkmap(mindmapMarkdown.value)
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
  mindmapMarkdown.value = ''
  if (markmapInstance.value) {
    markmapInstance.value = null
  }
  videoData.value = null
  error.value = ''
  videoError.value = ''
  pptProgress.value = null
  pptTaskId.value = ''
  pptQueryUsed.value = ''
  if (progressPollTimer) {
    clearInterval(progressPollTimer)
    progressPollTimer = null
  }
})

watch(sessionId, (newId) => {
  if (newId) fetchRecommendations()
})

onMounted(async () => {
  if (mindmapMarkdown.value && markmapContainerRef.value) {
    renderMarkmap(mindmapMarkdown.value)
  }
  await fetchModels()
  checkModelStatus()

  // 点击外部关闭模型下拉框
  document.addEventListener('click', handleModelDropdownClickOutside)
})

onBeforeUnmount(() => {
  if (progressTimer) clearInterval(progressTimer)
  if (progressPollTimer) clearInterval(progressPollTimer)
  if (markmapInstance.value) {
    markmapInstance.value.destroy()
    markmapInstance.value = null
  }
  document.removeEventListener('click', handleModelDropdownClickOutside)
})

function handleModelDropdownClickOutside(e: MouseEvent) {
  if (showModelDropdown.value && modelDropdownRef.value && !modelDropdownRef.value.contains(e.target as Node)) {
    showModelDropdown.value = false
  }
}
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
    <div class="relative" ref="modelDropdownRef">
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

      <!-- PPT 模式切换（仅PPT类型时显示） -->
      <div v-if="resourceType === 'ppt'" class="flex items-center gap-3 pt-1 flex-wrap">
        <span class="text-xs text-surface-400">生成模式</span>
        <div class="flex rounded-lg border border-surface-200 overflow-hidden">
          <button
            type="button"
            class="px-3 py-1 text-xs font-medium transition-colors"
            :class="pptMode === 'online' ? 'bg-brand-500 text-white' : 'bg-white text-surface-600 hover:bg-surface-50'"
            @click="pptMode = 'online'"
          >
            在线生成
          </button>
          <button
            type="button"
            class="px-3 py-1 text-xs font-medium transition-colors border-l border-surface-200"
            :class="pptMode === 'local' ? 'bg-brand-500 text-white' : 'bg-white text-surface-600 hover:bg-surface-50'"
            @click="pptMode = 'local'"
          >
            本地生成
          </button>
          <button
            type="button"
            class="px-3 py-1 text-xs font-medium transition-colors border-l border-surface-200"
            :class="pptMode === 'html' ? 'bg-brand-500 text-white' : 'bg-white text-surface-600 hover:bg-surface-50'"
            @click="pptMode = 'html'"
          >
            HTML演示
          </button>
        </div>
        <span v-if="pptMode === 'online'" class="text-[10px] text-surface-400">讯飞智文API云端渲染</span>
        <template v-else-if="pptMode === 'local'">
          <span class="text-[10px] text-surface-400">使用 {{ availableModels.find(m => m.id === selectedModel)?.label || selectedModel }} 生成内容</span>
          <select
            v-model="pptTheme"
            class="text-xs rounded border border-surface-200 bg-surface-50 px-2 py-0.5 focus:outline-none focus:border-brand-400"
          >
            <option value="default">蓝白商务</option>
            <option value="dark">深色主题</option>
            <option value="education">浅色学术</option>
          </select>
        </template>
        <template v-else-if="pptMode === 'html'">
          <span class="text-[10px] text-surface-400">浏览器可交互演示，支持键盘导航和主题切换</span>
          <select
            v-model="htmlTheme"
            class="text-xs rounded border border-surface-200 bg-surface-50 px-2 py-0.5 focus:outline-none focus:border-brand-400"
          >
            <option v-for="t in htmlThemes" :key="t.id" :value="t.id">{{ t.label }}</option>
          </select>
        </template>
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

        <!-- 思维导图：Markmap交互式渲染 -->
        <div v-else-if="resourceType === 'mindmap'">
          <div v-if="mindmapMarkdown" class="rounded-2xl border border-surface-200 bg-white overflow-hidden shadow-sm">
            <!-- 工具栏 -->
            <div class="flex items-center justify-between px-5 py-3 border-b border-surface-100 bg-surface-50/50">
              <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-400 to-purple-500 flex items-center justify-center text-white text-sm">
                  🧠
                </div>
                <div>
                  <div class="text-sm font-semibold text-surface-700">交互式思维导图</div>
                  <div class="text-[10px] text-surface-400">滚轮缩放 · 拖拽平移 · 点击节点折叠/展开</div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <div ref="markmapToolbarRef" class="markmap-toolbar" />
                <button @click="exportMindmapSVG" class="rounded-lg px-3 py-1.5 text-xs font-medium text-brand-600 bg-brand-50 hover:bg-brand-100">
                  <svg class="w-3.5 h-3.5 inline-block mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                  </svg>
                  SVG
                </button>
                <button @click="exportMindmapHTML" class="rounded-lg px-3 py-1.5 text-xs font-medium text-white bg-brand-500 hover:bg-brand-600">
                  <svg class="w-3.5 h-3.5 inline-block mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/>
                  </svg>
                  HTML
                </button>
              </div>
            </div>
            <!-- Markmap渲染区域 -->
            <svg ref="markmapContainerRef" class="w-full" style="height: 500px;" />
          </div>
          <div v-else class="text-sm text-surface-400 text-center py-8">点击生成按钮创建思维导图</div>
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

    <!-- PPT 生成结果 -->
    <div v-if="pptProgress" class="animate-slide-up space-y-3">
      <!-- PPT操作栏 -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span
            class="text-[11px] font-semibold rounded-full px-2.5 py-0.5 bg-orange-50 text-orange-600"
          >
            PPT课件
          </span>
          <span class="text-xs text-surface-400">| {{ topic }}</span>
          <span v-if="pptQueryUsed && pptQueryUsed !== topic" class="text-[10px] text-brand-500 bg-brand-50 px-1.5 py-0.5 rounded" :title="'AI优化查询: ' + pptQueryUsed">AI优化</span>
          <span v-if="pptProgress.status === 'done'" class="text-xs text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">生成完成</span>
          <span v-else-if="pptProgress.status === 'failed'" class="text-xs text-rose-600 bg-rose-50 px-2 py-0.5 rounded-full">生成失败</span>
          <span v-else class="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">生成中 {{ pptProgress.done_pages }}/{{ pptProgress.total_pages }}</span>
        </div>
        <div class="flex items-center gap-1.5">
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

      <!-- PPT进度展示 -->
      <div v-if="pptProgress.status === 'building'" class="rounded-2xl border border-surface-200 bg-white p-5 space-y-3">
        <div class="flex items-center justify-between text-sm">
          <span class="text-surface-600 font-medium">正在生成PPT...</span>
          <span class="text-brand-600 font-semibold">{{ pptProgress.progress_percent }}%</span>
        </div>
        <div class="h-2 bg-surface-100 rounded-full overflow-hidden">
          <div
            class="h-full bg-gradient-to-r from-brand-400 to-brand-600 rounded-full transition-all duration-300 ease-out"
            :style="{ width: pptProgress.progress_percent + '%' }"
          />
        </div>
        <div class="flex gap-3 text-[11px] text-surface-400">
          <span :class="pptProgress.ppt_status === 'done' ? 'text-emerald-500' : pptProgress.ppt_status === 'building' ? 'text-brand-500' : ''">
            ● PPT生成 {{ pptProgress.ppt_status === 'done' ? '完成' : pptProgress.ppt_status === 'building' ? '进行中' : '等待' }}
          </span>
          <span :class="pptProgress.ai_image_status === 'done' ? 'text-emerald-500' : pptProgress.ai_image_status === 'building' ? 'text-brand-500' : ''">
            ● 配图 {{ pptProgress.ai_image_status === 'done' ? '完成' : pptProgress.ai_image_status === 'building' ? '进行中' : '等待' }}
          </span>
          <span :class="pptProgress.card_note_status === 'done' ? 'text-emerald-500' : pptProgress.card_note_status === 'building' ? 'text-brand-500' : ''">
            ● 演讲备注 {{ pptProgress.card_note_status === 'done' ? '完成' : pptProgress.card_note_status === 'building' ? '进行中' : '等待' }}
          </span>
        </div>
      </div>

      <!-- PPT结果展示 -->
      <div v-if="pptProgress.status === 'done'" class="rounded-2xl border border-surface-200 bg-white overflow-hidden">
        <!-- 封面预览 -->
        <div v-if="pptProgress.cover_img" class="relative">
          <img
            :src="pptProgress.cover_img"
            :alt="topic"
            class="w-full h-48 object-cover"
          />
          <div class="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
          <div class="absolute bottom-4 left-4 right-4 flex items-end justify-between">
            <div>
              <div class="text-white font-semibold text-lg">{{ topic }}</div>
              <div class="text-white/70 text-sm">{{ pptProgress.total_pages }} 页</div>
            </div>
          </div>
        </div>

        <!-- 操作区域 -->
        <div class="p-5 flex items-center justify-between">
          <div class="text-sm text-surface-500">
            <div class="text-surface-700 font-medium">PPT课件已生成</div>
            <div class="text-xs mt-1">共 {{ pptProgress.total_pages }} 页，包含演讲备注</div>
          </div>
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="rounded-xl px-4 py-2 text-sm font-medium text-brand-600 bg-brand-50 hover:bg-brand-100 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="pptPreviewLoading"
              @click="previewPPT"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                <path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
              </svg>
              预览大纲
            </button>
            <button
              type="button"
              class="rounded-xl px-4 py-2 text-sm font-medium text-white bg-brand-500 hover:bg-brand-600 transition-colors flex items-center gap-2"
              @click="downloadPPT"
              :disabled="!pptProgress.ppt_url"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
              </svg>
              下载PPT
            </button>
          </div>
        </div>
      </div>

      <!-- PPT生成失败 -->
      <div v-if="pptProgress.status === 'failed'" class="rounded-2xl border border-rose-200 bg-rose-50 p-5">
        <div class="flex items-center gap-3">
          <svg class="w-5 h-5 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          <div>
            <div class="text-sm font-medium text-rose-700">PPT生成失败</div>
            <div class="text-xs text-rose-500 mt-0.5">请重试或修改生成需求</div>
          </div>
        </div>
      </div>
    </div>

    <!-- HTML PPT 演示预览 -->
    <div v-if="htmlPreviewReady && htmlContent" class="animate-slide-up rounded-2xl border border-surface-200 bg-white overflow-hidden shadow-sm">
      <!-- 预览头部 -->
      <div class="flex items-center justify-between px-5 py-3 border-b border-surface-100 bg-surface-50/50">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-400 to-purple-500 flex items-center justify-center text-white text-sm">
            ▶
          </div>
          <div>
            <div class="text-sm font-semibold text-surface-700">HTML 演示文稿</div>
            <div class="text-[10px] text-surface-400">← → 翻页 · F 全屏 · T 切换主题 · S 演讲者模式</div>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="rounded-lg px-3 py-1.5 text-xs font-medium text-brand-600 bg-brand-50 hover:bg-brand-100 transition-colors flex items-center gap-1.5"
            @click="openHtmlFullscreen"
          >
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"/>
            </svg>
            全屏演示
          </button>
          <button
            type="button"
            class="rounded-lg px-3 py-1.5 text-xs font-medium text-white bg-brand-500 hover:bg-brand-600 transition-colors flex items-center gap-1.5"
            @click="downloadHtml"
          >
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
            </svg>
            下载HTML
          </button>
        </div>
      </div>
      <!-- iframe 预览区域 -->
      <div class="relative bg-surface-100" style="padding-bottom: 56.25%;">
        <iframe
          :srcdoc="htmlContent"
          class="absolute inset-0 w-full h-full border-0"
          sandbox="allow-scripts allow-same-origin allow-popups"
          loading="lazy"
        ></iframe>
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
          @click="applyRecommendation(item)"
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

    <!-- PPT 大纲预览弹窗 -->
    <transition name="modal">
      <div v-if="showPPTPreview" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" @click.self="closePPTPreview">
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden mx-4">
          <!-- 弹窗头部 -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-surface-100">
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 rounded-lg bg-orange-50 flex items-center justify-center text-orange-500">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
              </div>
              <div>
                <h3 class="text-base font-semibold text-surface-800">PPT 大纲预览</h3>
                <p v-if="pptOutline?.title" class="text-xs text-surface-400 mt-0.5">{{ pptOutline.title }}</p>
              </div>
            </div>
            <button type="button" class="w-8 h-8 rounded-lg flex items-center justify-center text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors" @click="closePPTPreview">
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>

          <!-- 弹窗内容 -->
          <div class="flex-1 overflow-y-auto px-6 py-4">
            <!-- 加载中 -->
            <div v-if="pptPreviewLoading" class="flex flex-col items-center justify-center py-12 gap-3">
              <svg class="w-8 h-8 text-brand-500 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
              </svg>
              <span class="text-sm text-surface-400">加载大纲中...</span>
            </div>

            <!-- 大纲内容 -->
            <div v-else-if="pptOutline?.outline_parsed?.length" class="space-y-4">
              <!-- 标题信息 -->
              <div v-if="pptOutline.title" class="text-center pb-3 border-b border-surface-100">
                <h2 class="text-lg font-bold text-surface-800">{{ pptOutline.title }}</h2>
                <p v-if="pptOutline.sub_title" class="text-sm text-surface-500 mt-1">{{ pptOutline.sub_title }}</p>
              </div>

              <!-- 章节列表 -->
              <div v-for="(chapter, ci) in pptOutline.outline_parsed" :key="ci" class="rounded-xl border border-surface-200 overflow-hidden">
                <div class="bg-surface-50 px-4 py-2.5 flex items-center gap-2">
                  <span class="w-6 h-6 rounded-full bg-orange-100 text-orange-600 flex items-center justify-center text-xs font-bold">{{ ci + 1 }}</span>
                  <span class="font-medium text-surface-700 text-sm">{{ chapter.chapterTitle || chapter.title || `第${ci + 1}章` }}</span>
                </div>
                <div class="px-4 py-2 space-y-1.5">
                  <div
                    v-for="(section, si) in (chapter.chapterSections || chapter.sections || [])"
                    :key="si"
                    class="flex items-start gap-2 text-sm text-surface-600 py-1"
                  >
                    <span class="w-1.5 h-1.5 rounded-full bg-brand-400 mt-1.5 shrink-0"></span>
                    <span>{{ section.sectionTitle || section.title || `小节 ${si + 1}` }}</span>
                  </div>
                  <div v-if="!(chapter.chapterSections || chapter.sections || []).length" class="text-xs text-surface-400 py-1">暂无详细小节</div>
                </div>
              </div>
            </div>

            <!-- 原始大纲（解析失败时展示） -->
            <div v-else-if="pptOutline?.outline" class="prose prose-sm max-w-none">
              <pre class="whitespace-pre-wrap text-sm text-surface-600 bg-surface-50 rounded-xl p-4 border border-surface-200">{{ pptOutline.outline }}</pre>
            </div>

            <!-- 无数据 -->
            <div v-else class="flex flex-col items-center justify-center py-12 gap-2">
              <svg class="w-10 h-10 text-surface-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
              </svg>
              <span v-if="pptPreviewError" class="text-sm text-rose-500">{{ pptPreviewError }}</span>
              <span v-else class="text-sm text-surface-400">暂无大纲数据</span>
            </div>
          </div>

          <!-- 弹窗底部 -->
          <div class="px-6 py-3 border-t border-surface-100 flex justify-between items-center">
            <span class="text-xs text-surface-400">共 {{ pptOutline?.outline_parsed?.length || 0 }} 个章节</span>
            <div class="flex items-center gap-2">
              <button type="button" class="px-4 py-2 text-sm text-surface-600 hover:text-surface-800 transition-colors" @click="closePPTPreview">关闭</button>
              <button
                type="button"
                class="px-4 py-2 text-sm bg-brand-500 text-white rounded-lg hover:bg-brand-600 transition-colors flex items-center gap-1.5 disabled:opacity-50"
                :disabled="!pptProgress?.ppt_url"
                @click="downloadPPT(); closePPTPreview()"
              >
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                </svg>
                下载PPT
              </button>
            </div>
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