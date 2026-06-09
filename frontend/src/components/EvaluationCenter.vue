<script setup lang="ts">
/**
 * EvaluationCenter.vue - 学习评估中心（优先级5增强版）
 *
 * 核心增强：
 * 1. 雷达图：SVG实现4维评估指标可视化（正确率/掌握度/利用率/投入度）
 * 2. LLM智能评估：接入星火大模型，替换纯规则引擎
 * 3. 历史评估追踪：进度时间线 + 趋势分析（上升/下降/稳定）
 * 4. 会话式评估：自动从会话拉取行为数据
 * 5. 三Tab结构：规则评估 | 智能评估 | 历史记录
 */
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import ResultDisplay from './ResultDisplay.vue'

/* ------------------------------------------------------------------ */
/*  TypeScript Interfaces                                              */
/* ------------------------------------------------------------------ */

interface QuizResult {
  question: string
  correct: boolean
}

interface EvalReport {
  score: number
  level: string
  comment: string
  analysis?: Record<string, number>
  strengths: string[]
  weaknesses: string[]
  suggestions: string[]
  source?: string
}

interface HistoryItem {
  id: number
  score: number | null
  report: EvalReport
  created_at: string
}

/* ------------------------------------------------------------------ */
/*  Reactive State                                                      */
/* ------------------------------------------------------------------ */

const activeTab = ref<'rule' | 'llm' | 'history'>('rule')
const activeSubTab = ref<'input' | 'result'>('input')

const studyDuration = ref(300)
const quizResults = ref<QuizResult[]>([
  { question: 'for循环', correct: true },
  { question: 'while循环', correct: true },
  { question: 'break语句', correct: false },
])
const knowledgeMastery = ref<Record<string, number>>({
  'for循环': 85,
  'while循环': 70,
  'break语句': 50,
})
const resourceUsage = ref<Record<string, number>>({
  ppt: 2, quiz: 3, code: 2, mindmap: 1, video: 1,
})

const report = ref('')
const parsedReport = ref<EvalReport | null>(null)
const loading = ref(false)
const error = ref('')

const sessionId = ref('')
const useLLM = ref(true)
const llmSource = ref('')

const historyItems = ref<HistoryItem[]>([])
const historyAvg = ref<number | null>(null)
const historyTrend = ref('stable')
const historyLoading = ref(false)

const resourceLabels: Record<string, string> = {
  ppt: 'PPT课件', quiz: '题库练习', code: '代码案例', mindmap: '思维导图', video: '视频脚本',
}

/* ------------------------------------------------------------------ */
/*  AI 模型状态                                                         */
/* ------------------------------------------------------------------ */

interface ModelStatus {
  status: 'connected' | 'disconnected' | 'timeout' | 'error' | 'checking' | 'offline'
  model_label: string
  latency_ms: number | null
  fallback_mode: boolean
  message: string
}

const modelStatus = ref<ModelStatus>({
  status: 'checking',
  model_label: '检测中',
  latency_ms: null,
  fallback_mode: false,
  message: '',
})

let statusCheckTimer: ReturnType<typeof setInterval> | null = null

async function checkModelStatus() {
  modelStatus.value.status = 'checking'
  try {
    const res = await fetch('/api/chat/model-status')
    if (res.ok) {
      const data = await res.json()
      modelStatus.value = {
        status: data.status,
        model_label: data.model_label || 'Spark',
        latency_ms: data.latency_ms,
        fallback_mode: data.fallback_mode,
        message: data.message || '',
      }
    }
  } catch {
    modelStatus.value.status = 'offline'
    modelStatus.value.message = '无法连接'
  }
}

function getStatusColor(): string {
  switch (modelStatus.value.status) {
    case 'connected': return 'bg-emerald-500'
    case 'disconnected': return 'bg-rose-500'
    case 'timeout': return 'bg-amber-500'
    case 'error': return 'bg-rose-500'
    case 'checking': return 'bg-surface-400'
    default: return 'bg-surface-400'
  }
}

function getStatusText(): string {
  switch (modelStatus.value.status) {
    case 'connected': return '已连接'
    case 'disconnected': return '离线'
    case 'timeout': return '超时'
    case 'error': return '错误'
    case 'checking': return '检测中'
    default: return modelStatus.value.message || '未知'
  }
}

/* ------------------------------------------------------------------ */
/*  AI 模型选择                                                         */
/* ------------------------------------------------------------------ */

interface ModelOption {
  id: string
  label: string
  description: string
  is_custom?: boolean
  provider?: string
  protocol?: string
}
const selectedModel = ref('Spark-X2-Flash')
const availableModels = ref<ModelOption[]>([])
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
      availableModels.value = data.models || []
      if (availableModels.value.length > 0 && !availableModels.value.find(m => m.id === selectedModel.value)) {
        selectedModel.value = availableModels.value[0].id
      }
    }
  } catch {
    // 静默失败
  }
}

function getSelectedModelLabel(): string {
  const model = availableModels.value.find(m => m.id === selectedModel.value)
  return model ? model.label : selectedModel.value
}

function toggleModelDropdown() {
  showModelDropdown.value = !showModelDropdown.value
}

function selectModel(modelId: string) {
  selectedModel.value = modelId
  showModelDropdown.value = false
  checkModelStatus()
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
  if (!newModel.value.label.trim()) {
    addModelError.value = '请输入模型名称'
    return
  }
  if (!newModel.value.model_name.trim()) {
    addModelError.value = '请输入模型标识符'
    return
  }
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
    // 静默失败
  }
}

/* ------------------------------------------------------------------ */
/*  Computed Values                                                     */
/* ------------------------------------------------------------------ */

const quizCorrect = computed(() => quizResults.value.filter(q => q.correct).length)
const quizTotal = computed(() => quizResults.value.length)
const resourceUsageTotal = computed(() => Object.values(resourceUsage.value).reduce((a, b) => a + b, 0))

const ringCircumference = 2 * Math.PI * 54
const ringOffset = computed(() => {
  const score = parsedReport.value?.score ?? 0
  return ringCircumference - (score / 100) * ringCircumference
})

const radarDimensions = ['练习正确率', '知识掌握度', '资源利用率', '学习投入度']
const radarScores = computed(() => {
  const a = parsedReport.value?.analysis
  if (!a) return [0, 0, 0, 0]
  return [
    a.quiz_accuracy ?? 0,
    a.knowledge_mastery_score ?? 0,
    a.resource_utilization ?? 0,
    a.dedication_score ?? 0,
  ]
})
const radarMaxScore = 100
const radarRadius = 100
const radarCenter = 140  // 增大中心点，为标签留出空间
const radarPoints = computed(() => {
  return radarScores.value.map((score, i) => {
    const angle = (Math.PI * 2 * i) / 4 - Math.PI / 2
    const r = (score / radarMaxScore) * radarRadius
    return { x: radarCenter + r * Math.cos(angle), y: radarCenter + r * Math.sin(angle) }
  })
})
const radarPolygonPoints = computed(() =>
  radarPoints.value.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
)
const radarGridRings = computed(() => {
  return [0.33, 0.66, 1.0].map(ratio => {
    return Array.from({ length: 4 }, (_, i) => {
      const angle = (Math.PI * 2 * i) / 4 - Math.PI / 2
      const r = ratio * radarRadius
      return { x: radarCenter + r * Math.cos(angle), y: radarCenter + r * Math.sin(angle) }
    })
  })
})
const radarAxisPoints = computed(() => {
  return Array.from({ length: 4 }, (_, i) => {
    const angle = (Math.PI * 2 * i) / 4 - Math.PI / 2
    return {
      x: radarCenter + radarRadius * Math.cos(angle),
      y: radarCenter + radarRadius * Math.sin(angle),
    }
  })
})
const radarLabelOffsets = computed(() => {
  return Array.from({ length: 4 }, (_, i) => {
    const angle = (Math.PI * 2 * i) / 4 - Math.PI / 2
    const r = radarRadius + 24
    return {
      x: radarCenter + r * Math.cos(angle),
      y: radarCenter + r * Math.sin(angle) + 4,
      anchor: i === 0 ? 'middle' : i === 2 ? 'middle' : i < 2 ? 'end' : 'start',
    }
  })
})

const historyTrendLabel = computed(() => {
  if (historyTrend.value === 'improving') return { text: '上升趋势 ↑', color: 'text-emerald-600 bg-emerald-50' }
  if (historyTrend.value === 'declining') return { text: '下降趋势 ↓', color: 'text-rose-600 bg-rose-50' }
  return { text: '趋于稳定 →', color: 'text-amber-600 bg-amber-50' }
})

/* ------------------------------------------------------------------ */
/*  Utility Functions                                                   */
/* ------------------------------------------------------------------ */

function levelColor(level: string): string {
  const map: Record<string, string> = {
    '优秀': 'text-emerald-600 bg-emerald-50',
    '良好': 'text-blue-600 bg-blue-50',
    '中等': 'text-amber-600 bg-amber-50',
    '需加强': 'text-rose-600 bg-rose-50',
  }
  return map[level] ?? 'text-surface-600 bg-surface-100'
}

function tryParseReport(raw: string): EvalReport | null {
  try {
    const data = JSON.parse(raw)
    if (data && typeof data === 'object' && 'score' in data) {
      return {
        score: Number(data.score) || 0,
        level: String(data.level ?? ''),
        comment: String(data.comment ?? ''),
        analysis: data.analysis as Record<string, number> | undefined,
        strengths: Array.isArray(data.strengths) ? data.strengths : [],
        weaknesses: Array.isArray(data.weaknesses) ? data.weaknesses : [],
        suggestions: Array.isArray(data.suggestions) ? data.suggestions : [],
        source: data.source as string | undefined,
      }
    }
  } catch { /* ignore */ }
  return null
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso
  }
}

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
        duration_minutes: Math.round(studyDuration.value / 60),
      }),
    })
  } catch {
    /* 静默失败，不影响主流程 */
  }
}

/* ------------------------------------------------------------------ */
/*  API Calls                                                           */
/* ------------------------------------------------------------------ */

async function submitRuleEvaluation() {
  error.value = ''
  report.value = ''
  parsedReport.value = null
  loading.value = true
  try {
    const res = await fetch('/api/evaluation/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        student_profile: {},
        learning_behavior: {
          study_duration_minutes: studyDuration.value,
          quiz_results: quizResults.value,
          knowledge_mastery: knowledgeMastery.value,
          resource_usage: resourceUsage.value,
        },
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    report.value = JSON.stringify(data, null, 2)
    parsedReport.value = tryParseReport(report.value)
    llmSource.value = '规则引擎'
    if (parsedReport.value) {
      activeSubTab.value = 'result'
      trackBehavior('evaluation_rule', {
        score: parsedReport.value.score,
        level: parsedReport.value.level,
        quiz_total: quizTotal.value,
        quiz_correct: quizCorrect.value,
      })
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '评估失败'
  } finally {
    loading.value = false
  }
}

async function submitLLMEvaluation() {
  error.value = ''
  report.value = ''
  parsedReport.value = null
  loading.value = true
  try {
    if (useLLM.value) {
      const res = await fetch('/api/evaluation/llm-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_profile: {},
          resource_usage: {
            quiz_set: { questions: quizResults.value },
            ppt_deck: resourceUsage.value.ppt > 0 ? { slides: resourceUsage.value.ppt } : {},
            code_set: resourceUsage.value.code > 0 ? { examples: resourceUsage.value.code } : {},
            mindmap: resourceUsage.value.mindmap > 0 ? { nodes: resourceUsage.value.mindmap } : {},
            video_script: resourceUsage.value.video > 0 ? { scenes: resourceUsage.value.video } : {},
          },
          session_id: sessionId.value || undefined,
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      report.value = JSON.stringify(data, null, 2)
      parsedReport.value = tryParseReport(report.value)
      llmSource.value = data.source === 'spark' ? '星火大模型' : '规则引擎'
    } else {
      const res = await fetch('/api/evaluation/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_profile: {},
          learning_behavior: {
            study_duration_minutes: studyDuration.value,
            quiz_results: quizResults.value,
            knowledge_mastery: knowledgeMastery.value,
            resource_usage: resourceUsage.value,
          },
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      report.value = JSON.stringify(data, null, 2)
      parsedReport.value = tryParseReport(report.value)
      llmSource.value = '规则引擎'
    }
    if (parsedReport.value) {
      activeSubTab.value = 'result'
      trackBehavior(useLLM.value ? 'evaluation_llm' : 'evaluation_rule', {
        score: parsedReport.value.score,
        level: parsedReport.value.level,
        engine: useLLM.value ? 'spark' : 'rule',
        quiz_total: quizTotal.value,
        quiz_correct: quizCorrect.value,
      })
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '评估失败'
  } finally {
    loading.value = false
  }
}

async function fetchHistory() {
  if (!sessionId.value) {
    error.value = '请先输入会话ID'
    return
  }
  historyLoading.value = true
  error.value = ''
  try {
    const res = await fetch(`/api/evaluation/history/${sessionId.value}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    historyItems.value = data.reports || []
    historyAvg.value = data.average_score
    historyTrend.value = data.trend || 'stable'
    trackBehavior('view_history', { total: data.total, avg_score: data.average_score })
  } catch (e) {
    error.value = e instanceof Error ? e.message : '获取历史失败'
  } finally {
    historyLoading.value = false
  }
}

async function fetchSessionMetrics() {
  if (!sessionId.value) return
  try {
    const res = await fetch(`/api/evaluation/session-metrics/${sessionId.value}`)
    if (!res.ok) return
    const data = await res.json()
    if (data.resource_types?.length) {
      const usage: Record<string, number> = {}
      for (const t of data.resource_types) {
        usage[t] = (usage[t] || 0) + 1
      }
      resourceUsage.value = {
        ppt: usage.ppt || 0,
        quiz: usage.quiz || 0,
        code: usage.code || 0,
        mindmap: usage.mindmap || 0,
        video: usage.video || 0,
      }
    }
    if (data.latest_evaluation) {
      parsedReport.value = data.latest_evaluation as EvalReport
      activeSubTab.value = 'result'
    }
  } catch { /* silent */ }
}

/* ------------------------------------------------------------------ */
/*  Manual Input Helpers                                                */
/* ------------------------------------------------------------------ */

function addQuizResult() {
  quizResults.value.push({ question: '', correct: false })
}

function removeQuizResult(index: number) {
  quizResults.value.splice(index, 1)
}

function addKnowledgeItem() {
  knowledgeMastery.value['新知识点'] = 50
}

function removeKnowledgeItem(key: string) {
  delete knowledgeMastery.value[key]
}

function exportReport(format: 'json' | 'md') {
  let content = ''
  const fn = `evaluation_report_${Date.now()}.${format === 'json' ? 'json' : 'md'}`

  if (format === 'json') {
    content = report.value || JSON.stringify(parsedReport.value, null, 2)
  } else {
    const r = parsedReport.value
    if (!r) return
    content = `# 学习评估报告\n\n`
    content += `## 总体评分\n\n**${r.score}** 分 - *${r.level}*\n\n`
    content += `> ${r.comment}\n\n`
    if (r.strengths.length) {
      content += `## 优势\n\n` + r.strengths.map(s => `- ${s}`).join('\n') + '\n\n'
    }
    if (r.weaknesses.length) {
      content += `## 薄弱点\n\n` + r.weaknesses.map(w => `- ${w}`).join('\n') + '\n\n'
    }
    if (r.suggestions.length) {
      content += `## 建议\n\n` + r.suggestions.map(s => `- ${s}`).join('\n') + '\n\n'
    }
  }

  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fn
  a.click()
  URL.revokeObjectURL(url)
}

watch(activeTab, () => {
  error.value = ''
})

onMounted(() => {
  const stored = localStorage.getItem('edu_session_id')
  if (stored) {
    sessionId.value = stored
  }
  trackBehavior('view_evaluation_center', {})

  // 加载模型列表和检测 AI 模型连接状态
  fetchModels()
  checkModelStatus()
  statusCheckTimer = setInterval(() => {
    if (!loading.value) {
      checkModelStatus()
    }
  }, 60000)
})

onBeforeUnmount(() => {
  if (statusCheckTimer) {
    clearInterval(statusCheckTimer)
    statusCheckTimer = null
  }
})
</script>

<template>
  <div class="space-y-5">
    <!-- 页面头部 -->
    <div class="flex items-center gap-3">
      <span class="text-2xl">📊</span>
      <div>
        <h2 class="text-xl font-bold text-surface-800">学习评估中心</h2>
        <p class="text-sm text-surface-400">大模型驱动的多维度评估 · 动态调整学习策略</p>
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
        <!-- 模型选择器 -->
        <span class="flex items-center gap-1 ml-2 border-l border-surface-200 pl-2">
          <div class="relative">
            <button
              type="button"
              class="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] transition-all"
              :class="showModelDropdown ? 'bg-brand-50 text-brand-600' : 'text-surface-500 hover:text-brand-500'"
              @click="toggleModelDropdown()"
            >
              <span>{{ getSelectedModelLabel() }}</span>
              <svg class="w-2.5 h-2.5 transition-transform" :class="showModelDropdown ? 'rotate-180' : ''" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
              </svg>
            </button>
            <transition name="dropdown">
              <div
                v-if="showModelDropdown"
                class="absolute top-full left-0 mt-1 w-64 rounded-xl bg-white border border-surface-200 shadow-xl z-30"
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
                <div class="max-h-48 overflow-y-auto py-1">
                  <button
                    v-for="m in availableModels"
                    :key="m.id"
                    type="button"
                    class="w-full text-left px-3 py-2 transition-colors relative group"
                    :class="m.id === selectedModel ? 'bg-brand-50 text-brand-700' : 'text-surface-600 hover:bg-surface-50'"
                    @click="selectModel(m.id)"
                  >
                    <div class="flex items-center justify-between">
                      <div class="flex items-center gap-2">
                        <span class="text-sm font-medium">{{ m.label }}</span>
                        <span v-if="m.is_custom" class="text-[9px] px-1 py-0.5 rounded bg-violet-100 text-violet-600">自定义</span>
                      </div>
                      <div class="flex items-center gap-1">
                        <button
                          v-if="m.is_custom"
                          type="button"
                          class="opacity-0 group-hover:opacity-100 w-5 h-5 rounded flex items-center justify-center text-surface-400 hover:text-rose-500 hover:bg-rose-50 transition-all"
                          title="删除模型"
                          @click.stop="deleteCustomModel(m.id, $event)"
                        >
                          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                          </svg>
                        </button>
                        <svg v-if="m.id === selectedModel" class="w-4 h-4 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
                        </svg>
                      </div>
                    </div>
                    <p class="text-[11px] mt-0.5" :class="m.id === selectedModel ? 'text-brand-500' : 'text-surface-400'">
                      {{ m.description }}
                    </p>
                  </button>
                </div>
              </div>
            </transition>
          </div>
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

    <!-- 会话ID输入 -->
    <div class="rounded-2xl border border-surface-200 bg-white p-4">
      <div class="flex items-center gap-3 flex-wrap">
        <label class="text-sm font-medium text-surface-600 shrink-0">会话ID</label>
        <input
          v-model="sessionId"
          class="flex-1 min-w-[200px] rounded-lg border border-surface-200 bg-surface-50 px-3 py-2 text-sm focus:border-brand-400 focus:ring-2 focus:ring-brand-400/15 focus:outline-none transition-all font-mono"
          placeholder="输入会话ID以关联学习数据"
        />
        <button
          type="button"
          class="rounded-lg bg-surface-100 px-3 py-2 text-xs font-medium text-surface-600 hover:bg-surface-200 transition-colors"
          @click="fetchSessionMetrics"
        >
          🔄 同步数据
        </button>
      </div>
    </div>

    <!-- 三Tab切换 -->
    <div class="flex gap-1.5 p-1 bg-surface-100 rounded-xl w-fit flex-wrap">
      <button
        v-for="t in (['rule', 'llm', 'history'] as const)"
        :key="t"
        type="button"
        class="rounded-lg px-5 py-2 text-sm font-medium transition-all duration-200"
        :class="activeTab === t
          ? 'bg-white text-brand-700 shadow-sm'
          : 'text-surface-500 hover:text-surface-700'"
        @click="activeTab = t"
      >
        {{ t === 'rule' ? '📝 规则评估' : t === 'llm' ? '🤖 智能评估' : '📈 历史记录' }}
      </button>
    </div>

    <!-- ============================================================ -->
    <!-- Tab 1: 规则评估                                                  -->
    <!-- ============================================================ -->
    <template v-if="activeTab === 'rule'">
      <!-- 子Tab -->
      <div class="flex gap-1.5 p-1 bg-surface-50 rounded-xl w-fit">
        <button
          v-for="t in (['input', 'result'] as const)"
          :key="t"
          type="button"
          class="rounded-lg px-4 py-1.5 text-xs font-medium transition-all duration-200"
          :class="activeSubTab === t
            ? 'bg-brand-500 text-white shadow-sm'
            : 'text-surface-500 hover:text-surface-700'"
          @click="activeSubTab = t"
        >
          {{ t === 'input' ? '数据输入' : '评估报告' }}
        </button>
      </div>

      <!-- 输入区 -->
      <div v-if="activeSubTab === 'input'" class="space-y-5">
        <!-- 学习时长 -->
        <div class="rounded-2xl border border-surface-200 bg-white p-5">
          <h3 class="text-sm font-semibold text-surface-700 mb-4 flex items-center gap-2">
            <span class="w-1.5 h-4 bg-brand-500 rounded-full" />
            学习时长
          </h3>
          <div class="flex items-center gap-4">
            <input
              type="range"
              :min="0"
              :max="600"
              :step="15"
              v-model.number="studyDuration"
              class="flex-1 h-2 rounded-full bg-surface-200 accent-brand-500 appearance-none cursor-pointer"
            />
            <span class="text-sm font-semibold text-brand-600 w-16 text-right">{{ studyDuration }}分钟</span>
          </div>
        </div>

        <!-- 测验结果 -->
        <div class="rounded-2xl border border-surface-200 bg-white p-5">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-surface-700 flex items-center gap-2">
              <span class="w-1.5 h-4 bg-emerald-500 rounded-full" />
              测验结果
            </h3>
            <button
              type="button"
              class="text-xs text-brand-500 hover:text-brand-600 font-medium transition-colors"
              @click="addQuizResult"
            >
              + 添加题目
            </button>
          </div>
          <div class="space-y-2">
            <div v-for="(q, i) in quizResults" :key="i" class="flex items-center gap-2.5">
              <input
                v-model="q.question"
                class="flex-1 rounded-lg border border-surface-200 bg-surface-50 px-3 py-2 text-sm focus:border-brand-400 focus:ring-2 focus:ring-brand-400/15 focus:outline-none transition-all"
                placeholder="题目描述"
              />
              <button
                type="button"
                class="rounded-lg px-3 py-2 text-xs font-medium transition-all"
                :class="q.correct
                  ? 'bg-emerald-50 text-emerald-600 border border-emerald-200'
                  : 'bg-rose-50 text-rose-600 border border-rose-200'"
                @click="q.correct = !q.correct"
              >
                {{ q.correct ? '✓ 正确' : '✗ 错误' }}
              </button>
              <button
                type="button"
                class="text-surface-300 hover:text-rose-400 transition-colors p-1"
                @click="removeQuizResult(i)"
              >
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </button>
            </div>
          </div>
          <div v-if="quizResults.length > 0" class="mt-3 text-xs text-surface-400">
            正确率：{{ quizCorrect }}/{{ quizTotal }} ({{ quizTotal > 0 ? Math.round(quizCorrect / quizTotal * 100) : 0 }}%)
          </div>
        </div>

        <!-- 知识掌握 -->
        <div class="rounded-2xl border border-surface-200 bg-white p-5">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-surface-700 flex items-center gap-2">
              <span class="w-1.5 h-4 bg-amber-500 rounded-full" />
              知识掌握度
            </h3>
            <button
              type="button"
              class="text-xs text-brand-500 hover:text-brand-600 font-medium transition-colors"
              @click="addKnowledgeItem"
            >
              + 添加项目
            </button>
          </div>
          <div class="space-y-3">
            <div v-for="(val, key) in knowledgeMastery" :key="key" class="flex items-center gap-3">
              <span class="text-sm text-surface-600 w-24 shrink-0">{{ key }}</span>
              <input
                type="range"
                :min="0"
                :max="100"
                :step="5"
                v-model.number="knowledgeMastery[key]"
                class="flex-1 h-2 rounded-full bg-surface-200 accent-brand-500 appearance-none cursor-pointer"
              />
              <span class="text-sm font-semibold text-surface-700 w-10 text-right">{{ val }}%</span>
              <button
                type="button"
                class="text-surface-300 hover:text-rose-400 transition-colors p-1"
                @click="removeKnowledgeItem(key)"
              >
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- 资源使用 -->
        <div class="rounded-2xl border border-surface-200 bg-white p-5">
          <h3 class="text-sm font-semibold text-surface-700 mb-4 flex items-center gap-2">
            <span class="w-1.5 h-4 bg-violet-500 rounded-full" />
            资源使用统计
          </h3>
          <div class="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <div v-for="(val, key) in resourceUsage" :key="key" class="text-center">
              <div class="text-2xl font-bold text-surface-800">{{ val }}</div>
              <div class="text-[11px] text-surface-400 mt-1">{{ resourceLabels[key] ?? key }}</div>
            </div>
          </div>
        </div>

        <button
          type="button"
          class="w-full rounded-xl bg-brand-500 px-6 py-3.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50 transition-all shadow-sm shadow-brand-500/25 hover:shadow-md hover:shadow-brand-500/30 flex items-center justify-center gap-2"
          :disabled="loading"
          @click="submitRuleEvaluation"
        >
          <svg v-if="loading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {{ loading ? '评估中...' : '📊 生成规则评估报告' }}
        </button>
      </div>

      <!-- 结果区 -->
      <div v-if="activeSubTab === 'result' && !loading">
        <ResultDisplay
          :parsed-report="parsedReport"
          :report="report"
          :knowledge-mastery="knowledgeMastery"
          :study-duration="studyDuration"
          :quiz-correct="quizCorrect"
          :quiz-total="quizTotal"
          :resource-usage-total="resourceUsageTotal"
          :llm-source="llmSource"
          :ring-circumference="ringCircumference"
          :ring-offset="ringOffset"
          :radar-dimensions="radarDimensions"
          :radar-scores="radarScores"
          :radar-polygon-points="radarPolygonPoints"
          :radar-grid-rings="radarGridRings"
          :radar-axis-points="radarAxisPoints"
          :radar-label-offsets="radarLabelOffsets"
          :radar-center="radarCenter"
          @export="exportReport"
        />
      </div>

      <!-- 骨架屏 -->
      <div v-if="loading" class="space-y-5">
        <div class="rounded-2xl border border-surface-200 bg-white p-6 flex flex-col items-center gap-3">
          <div class="skeleton h-32 w-32 rounded-full" />
          <div class="skeleton h-6 w-24" />
          <div class="skeleton h-4 w-48" />
        </div>
        <div class="grid gap-4 md:grid-cols-3">
          <div v-for="i in 3" :key="i" class="rounded-2xl border border-surface-200 bg-white p-5 space-y-2">
            <div class="skeleton h-4 w-16" />
            <div class="skeleton h-3 w-full" />
            <div class="skeleton h-3 w-5/6" />
          </div>
        </div>
      </div>
    </template>

    <!-- ============================================================ -->
    <!-- Tab 2: 智能评估（LLM）                                              -->
    <!-- ============================================================ -->
    <template v-if="activeTab === 'llm'">
      <div class="rounded-2xl border-2 border-brand-200 bg-gradient-to-br from-brand-50/50 to-white p-5">
        <div class="flex items-start gap-3 mb-4">
          <span class="text-2xl">🧠</span>
          <div>
            <h3 class="text-base font-bold text-surface-800">星火大模型智能评估</h3>
            <p class="text-sm text-surface-400 mt-0.5">基于讯飞星火大模型的多维度深度评估，精准分析学习效果并给出个性化建议</p>
          </div>
        </div>

        <div class="flex items-center gap-3 mb-4">
          <span class="text-sm text-surface-500">评估引擎：</span>
          <button
            type="button"
            class="rounded-lg px-4 py-1.5 text-xs font-medium transition-all"
            :class="useLLM
              ? 'bg-brand-500 text-white shadow-sm'
              : 'bg-surface-100 text-surface-500'"
            @click="useLLM = true"
          >
            🚀 星火大模型
          </button>
          <button
            type="button"
            class="rounded-lg px-4 py-1.5 text-xs font-medium transition-all"
            :class="!useLLM
              ? 'bg-brand-500 text-white shadow-sm'
              : 'bg-surface-100 text-surface-500'"
            @click="useLLM = false"
          >
            📐 规则引擎
          </button>
        </div>

        <p class="text-xs text-surface-400 mb-4">
          智能评估将综合考量测验结果、资源使用情况、知识掌握度等数据，由大模型生成深度分析报告。
        </p>

        <div v-if="activeSubTab === 'result' && !loading && parsedReport">
          <div class="flex items-center gap-2 mb-4">
            <span class="text-xs px-2 py-0.5 rounded-full font-medium"
              :class="llmSource === '星火大模型' ? 'bg-violet-50 text-violet-600' : 'bg-amber-50 text-amber-600'">
              {{ llmSource }}
            </span>
          </div>
        </div>

        <div class="flex gap-3">
          <button
            type="button"
            class="flex-1 rounded-xl bg-brand-500 px-5 py-3 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50 transition-all shadow-sm shadow-brand-500/25 flex items-center justify-center gap-2"
            :disabled="loading"
            @click="submitLLMEvaluation"
          >
            <svg v-if="loading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {{ loading ? '大模型分析中...' : '🧠 启动智能评估' }}
          </button>
          <button
            type="button"
            class="rounded-xl border border-surface-200 bg-white px-4 py-3 text-sm font-medium text-surface-600 hover:bg-surface-50 transition-colors"
            @click="activeSubTab = 'input'; activeTab = 'rule'"
          >
            返回数据编辑
          </button>
        </div>
      </div>

      <!-- 智能评估结果 -->
      <div v-if="activeSubTab === 'result' && !loading && parsedReport" class="space-y-5 animate-slide-up">
        <ResultDisplay
          :parsed-report="parsedReport"
          :report="report"
          :knowledge-mastery="knowledgeMastery"
          :study-duration="studyDuration"
          :quiz-correct="quizCorrect"
          :quiz-total="quizTotal"
          :resource-usage-total="resourceUsageTotal"
          :llm-source="llmSource"
          :ring-circumference="ringCircumference"
          :ring-offset="ringOffset"
          :radar-dimensions="radarDimensions"
          :radar-scores="radarScores"
          :radar-polygon-points="radarPolygonPoints"
          :radar-grid-rings="radarGridRings"
          :radar-axis-points="radarAxisPoints"
          :radar-label-offsets="radarLabelOffsets"
          :radar-center="radarCenter"
          @export="exportReport"
        />
      </div>

      <div v-if="loading" class="space-y-5">
        <div class="rounded-2xl border border-surface-200 bg-white p-6 flex flex-col items-center gap-3">
          <div class="skeleton h-32 w-32 rounded-full" />
          <div class="skeleton h-6 w-24" />
          <div class="skeleton h-4 w-48" />
        </div>
      </div>

      <div v-if="!parsedReport && !loading && activeSubTab === 'result'" class="rounded-2xl border border-surface-200 bg-white p-12 text-center">
        <div class="text-4xl mb-3">🤖</div>
        <p class="text-sm text-surface-400">点击"启动智能评估"开始大模型分析</p>
      </div>
    </template>

    <!-- ============================================================ -->
    <!-- Tab 3: 历史记录                                                    -->
    <!-- ============================================================ -->
    <template v-if="activeTab === 'history'">
      <div class="space-y-5">
        <!-- 查询栏 -->
        <div class="rounded-2xl border border-surface-200 bg-white p-4 flex items-center gap-3">
          <input
            v-model="sessionId"
            class="flex-1 rounded-lg border border-surface-200 bg-surface-50 px-3 py-2 text-sm focus:border-brand-400 focus:ring-2 focus:ring-brand-400/15 focus:outline-none transition-all font-mono"
            placeholder="输入会话ID查看历史评估"
          />
          <button
            type="button"
            class="rounded-xl bg-brand-500 px-5 py-2 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50 transition-all flex items-center gap-1.5"
            :disabled="historyLoading"
            @click="fetchHistory"
          >
            <svg v-if="historyLoading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {{ historyLoading ? '查询中...' : '🔍 查询' }}
          </button>
        </div>

        <!-- 统计概览 -->
        <div v-if="historyItems.length > 0" class="grid grid-cols-3 gap-4">
          <div class="rounded-2xl border border-surface-200 bg-white p-4 text-center">
            <div class="text-2xl font-bold text-surface-800">{{ historyItems.length }}</div>
            <div class="text-[11px] text-surface-400 mt-1">评估次数</div>
          </div>
          <div class="rounded-2xl border border-surface-200 bg-white p-4 text-center">
            <div class="text-2xl font-bold text-surface-800">{{ historyAvg ?? '-' }}</div>
            <div class="text-[11px] text-surface-400 mt-1">平均评分</div>
          </div>
          <div class="rounded-2xl border border-surface-200 bg-white p-4 text-center">
            <span class="inline-block text-xs font-semibold rounded-full px-3 py-1 mt-1" :class="historyTrendLabel.color">
              {{ historyTrendLabel.text }}
            </span>
            <div class="text-[11px] text-surface-400 mt-1">趋势分析</div>
          </div>
        </div>

        <!-- 进度时间线 -->
        <div v-if="historyItems.length > 0" class="rounded-2xl border border-surface-200 bg-white p-5">
          <h3 class="text-sm font-semibold text-surface-700 mb-4 flex items-center gap-2">
            <span class="w-1.5 h-4 bg-brand-500 rounded-full" />
            评估进度时间线
          </h3>

          <!-- SVG 折线图 -->
          <div class="mb-6 overflow-x-auto">
            <svg :viewBox="`0 0 ${Math.max(historyItems.length * 80, 300)} 160`" class="w-full" style="min-height: 160px">
              <!-- 网格线 -->
              <line v-for="y in [40, 80, 120]" :key="'grid-' + y"
                :x1="0" :y1="y" :x2="Math.max(historyItems.length * 80, 300)" :y2="y"
                stroke="#f1f5f9" stroke-width="1" />
              <text v-for="(label, i) in ['75', '50', '25']" :key="'ylabel-' + i"
                :x="5" :y="40 + i * 40 + 4" fill="#94a3b8" font-size="10">{{ label }}</text>

              <!-- 折线 -->
              <polyline
                v-if="historyItems.length >= 2"
                :points="historyItems.map((item, i) => {
                  const x = 40 + i * 70
                  const y = 150 - (item.score ?? 0) * 1.2
                  return `${x},${y}`
                }).join(' ')"
                fill="none"
                stroke="#6366f1"
                stroke-width="2.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <!-- 面积填充 -->
              <polygon
                v-if="historyItems.length >= 2"
                :points="`
                  ${40},150
                  ${historyItems.map((item, i) => `${40 + i * 70},${150 - (item.score ?? 0) * 1.2}`).join(' ')}
                  ${40 + (historyItems.length - 1) * 70},150
                `"
                fill="url(#progressGradient)"
                opacity="0.3"
              />
              <defs>
                <linearGradient id="progressGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#6366f1" />
                  <stop offset="100%" stop-color="#6366f1" stop-opacity="0" />
                </linearGradient>
              </defs>

              <!-- 数据点 -->
              <circle
                v-for="(item, i) in historyItems"
                :key="'dot-' + i"
                :cx="40 + i * 70"
                :cy="150 - (item.score ?? 0) * 1.2"
                r="5"
                fill="white"
                stroke="#6366f1"
                stroke-width="2"
              />
              <!-- 分数标签 -->
              <text
                v-for="(item, i) in historyItems"
                :key="'score-' + i"
                :x="40 + i * 70"
                :y="150 - (item.score ?? 0) * 1.2 - 10"
                text-anchor="middle"
                fill="#6366f1"
                font-size="11"
                font-weight="bold"
              >{{ item.score }}</text>
            </svg>
          </div>

          <!-- 时间线列表 -->
          <div class="space-y-3">
            <div
              v-for="(item, i) in historyItems"
              :key="item.id"
              class="flex items-start gap-3 p-3 rounded-xl hover:bg-surface-50 transition-colors cursor-pointer"
              @click="parsedReport = item.report; report = JSON.stringify(item.report, null, 2); activeTab = 'rule'; activeSubTab = 'result'"
            >
              <div class="relative flex flex-col items-center">
                <div
                  class="w-3 h-3 rounded-full shrink-0 mt-1.5"
                  :class="(item.score ?? 0) >= 75 ? 'bg-emerald-400' : (item.score ?? 0) >= 60 ? 'bg-amber-400' : 'bg-rose-400'"
                />
                <div v-if="i < historyItems.length - 1" class="w-0.5 flex-1 min-h-[20px] bg-surface-200 mt-1" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-semibold text-surface-800">{{ item.report.score }}分</span>
                  <span class="text-xs rounded-full px-2 py-0.5" :class="levelColor(item.report.level)">
                    {{ item.report.level }}
                  </span>
                </div>
                <p class="text-xs text-surface-400 mt-0.5 line-clamp-1">{{ item.report.comment }}</p>
                <span class="text-[10px] text-surface-300 mt-1 block">{{ formatDate(item.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-if="!historyLoading && historyItems.length === 0 && sessionId" class="rounded-2xl border border-surface-200 bg-white p-12 text-center">
          <div class="text-4xl mb-3">📭</div>
          <p class="text-sm text-surface-400">该会话暂无评估记录</p>
          <p class="text-xs text-surface-300 mt-1">通过对话学习或资源使用后会自动产生评估记录</p>
        </div>
      </div>
    </template>

    <p v-if="error" class="text-sm text-rose-500 bg-rose-50 rounded-xl px-4 py-3 border border-rose-200 animate-slide-up">{{ error }}</p>

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
            <button
              type="button"
              class="w-8 h-8 rounded-lg flex items-center justify-center text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors"
              @click="showAddModelModal = false"
            >
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>
          <div class="px-6 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
            <div>
              <label class="block text-sm font-medium text-surface-700 mb-1">服务商</label>
              <select
                v-model="newModel.provider"
                class="w-full px-3 py-2 border border-surface-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                @change="onProviderChange(newModel.provider)"
              >
                <option v-for="p in providers" :key="p.value" :value="p.value">{{ p.label }}</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-surface-700 mb-1">模型显示名称 *</label>
              <input
                v-model="newModel.label"
                type="text"
                placeholder="如：GPT-4o、DeepSeek-V3"
                class="w-full px-3 py-2 border border-surface-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-surface-700 mb-1">模型标识符 *</label>
              <input
                v-model="newModel.model_name"
                type="text"
                placeholder="如：gpt-4o、deepseek-chat"
                class="w-full px-3 py-2 border border-surface-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
              <p class="text-[11px] text-surface-400 mt-1">API 调用时使用的模型 ID</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-surface-700 mb-1">API 地址</label>
              <input
                v-model="newModel.api_url"
                type="text"
                placeholder="https://api.example.com/v1/chat/completions"
                class="w-full px-3 py-2 border border-surface-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-surface-700 mb-1">API Key（可选）</label>
              <input
                v-model="newModel.api_key"
                type="password"
                placeholder="留空则使用系统默认凭据"
                class="w-full px-3 py-2 border border-surface-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
              <p class="text-[11px] text-surface-400 mt-1">留空将复用平台已配置的凭据</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-surface-700 mb-1">描述（可选）</label>
              <input
                v-model="newModel.description"
                type="text"
                placeholder="简短描述模型特点"
                class="w-full px-3 py-2 border border-surface-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>
            <div v-if="addModelError" class="px-3 py-2 bg-rose-50 border border-rose-200 rounded-lg text-sm text-rose-600">
              {{ addModelError }}
            </div>
          </div>
          <div class="px-6 py-4 border-t border-surface-100 flex justify-end gap-3">
            <button
              type="button"
              class="px-4 py-2 text-sm text-surface-600 hover:text-surface-800 transition-colors"
              @click="showAddModelModal = false"
            >
              取消
            </button>
            <button
              type="button"
              class="px-4 py-2 text-sm bg-brand-500 text-white rounded-lg hover:bg-brand-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="addingModel"
              @click="addCustomModel()"
            >
              {{ addingModel ? '添加中...' : '添加模型' }}
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.dropdown-enter-active { transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); }
.dropdown-leave-active { transition: all 0.15s ease-in; }
.dropdown-enter-from { opacity: 0; transform: translateY(-4px); }
.dropdown-leave-to { opacity: 0; transform: translateY(-2px); }

.modal-enter-active { transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-leave-active { transition: all 0.2s ease-in; }
.modal-enter-from { opacity: 0; }
.modal-leave-to { opacity: 0; }
.modal-enter-from > div { transform: scale(0.95); opacity: 0; }
.modal-enter-active > div { transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }

input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #6366f1;
  box-shadow: 0 1px 3px rgba(99, 102, 241, 0.3);
  cursor: pointer;
  border: 2px solid white;
}
</style>
