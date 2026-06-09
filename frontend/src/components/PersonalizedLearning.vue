<script setup lang="ts">
/**
 * PersonalizedLearning.vue - 个性化学习中心
 *
 * 功能：
 * 1. SVG 雷达图：student_profile 6 维度可视化映射
 * 2. 标签云：画像字段关键词彩色标签展示
 * 3. 时间轴学习路径：调用 /api/learning-path/generate 获取结构化路径
 * 4. 资源推送：学习路径每步关联推荐资源卡片
 * 5. 智能推荐：基于画像的资源精准推送
 */

import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'

const message = ref('我是计算机专业学生，想备战蓝桥杯，初学Python，喜欢看图解，每天1小时，循环不太会')
const sessionId = ref('')
const profileJson = ref('')
const loading = ref(false)
const error = ref('')
const activeTab = ref<'profile' | 'path'>('profile')

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

interface ProfileData {
  knowledge_level: string
  learning_style: string
  weakness: string
  goal: string
  study_time: string
  major: string
  learning_goal_text: string
  learning_base: string
  learning_style_text: string
  raw_input: string
}

interface StepResource {
  id: number
  resource_type: string
  resource_label: string
  resource_icon: string
  topic: string
  preview?: string
  content?: Record<string, unknown>
}

interface StepWithResources {
  week: number
  title: string
  duration: string
  topics: string[]
  recommended_resource_types: string[]
  assessment: string
  available_resources: StepResource[]
}

interface PathOverview {
  path_name: string
  total_weeks: number
  focus_areas: string[]
  suggestions: string[]
  source: string
}

const parsedProfile = ref<ProfileData | null>(null)
const stepsWithResources = ref<StepWithResources[]>([])
const pathOverview = ref<PathOverview | null>(null)
const pathProfileSummary = ref('')
const pathTotalResources = ref(0)
const expandedStep = ref<number | null>(null)

function parseKnowledgeScore(level: string): number {
  const map: Record<string, number> = { beginner: 25, intermediate: 55, advanced: 85, unknown: 30 }
  return map[level.toLowerCase()] ?? 30
}

function parseStudyTimeScore(time: string): number {
  const match = time.match(/(\d+)/)
  if (!match) return 30
  const hours = Number(match[1])
  return Math.min(hours * 25, 95)
}

function textLengthScore(text: string): number {
  if (!text) return 20
  if (text.length > 50) return 80
  if (text.length > 20) return 55
  return 35
}

function hasContent(text: string): number {
  return text && text.trim().length > 0 ? 75 : 20
}

function parseStyleScore(style: string): number {
  if (!style || style === 'unknown') return 30
  return 70
}

const radarDimensions = ['知识水平', '投入度', '目标明确', '基础扎实', '薄弱认知', '风格适配']

const radarScores = computed(() => {
  const p = parsedProfile.value
  if (!p) return [30, 30, 30, 30, 30, 30]
  return [
    parseKnowledgeScore(p.knowledge_level),
    parseStudyTimeScore(p.study_time),
    textLengthScore(p.learning_goal_text),
    textLengthScore(p.learning_base),
    hasContent(p.weakness),
    parseStyleScore(p.learning_style),
  ]
})

const radarMaxScore = 100
const radarRadius = 120
const radarCenter = 140
const radarPoints = computed(() => {
  return radarScores.value.map((score, i) => {
    const angle = (Math.PI * 2 * i) / 6 - Math.PI / 2
    const r = (score / radarMaxScore) * radarRadius
    return {
      x: radarCenter + r * Math.cos(angle),
      y: radarCenter + r * Math.sin(angle),
    }
  })
})

const radarPolygonPoints = computed(() =>
  radarPoints.value.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
)

const radarGridPoints = computed(() => {
  const rings = [0.33, 0.66, 1.0]
  return rings.map(ratio => {
    return Array.from({ length: 6 }, (_, i) => {
      const angle = (Math.PI * 2 * i) / 6 - Math.PI / 2
      const r = ratio * radarRadius
      return {
        x: radarCenter + r * Math.cos(angle),
        y: radarCenter + r * Math.sin(angle),
      }
    })
  })
})

const radarAxisPoints = computed(() => {
  return Array.from({ length: 6 }, (_, i) => {
    const angle = (Math.PI * 2 * i) / 6 - Math.PI / 2
    return {
      x: radarCenter + radarRadius * Math.cos(angle),
      y: radarCenter + radarRadius * Math.sin(angle),
    }
  })
})

const labelOffsets = computed(() => {
  return Array.from({ length: 6 }, (_, i) => {
    const angle = (Math.PI * 2 * i) / 6 - Math.PI / 2
    const r = radarRadius + 22
    return {
      x: radarCenter + r * Math.cos(angle),
      y: radarCenter + r * Math.sin(angle) + 4,
      anchor: i === 0 ? 'middle' : i === 3 ? 'middle' : i < 3 ? 'end' : 'start',
    }
  })
})

interface TagItem {
  text: string
  size: 'lg' | 'md' | 'sm'
  color: string
}

const profileTags = computed<TagItem[]>(() => {
  const p = parsedProfile.value
  if (!p) return []
  const tags: TagItem[] = []
  
  const levelMap: Record<string, string> = { beginner: '初学者', intermediate: '中级', advanced: '高级' }
  tags.push({ text: levelMap[p.knowledge_level] ?? p.knowledge_level, size: 'lg', color: 'brand' })
  
  const styleMap: Record<string, string> = { visual: '视觉型', auditory: '听觉型', reading: '阅读型', kinesthetic: '动手型' }
  tags.push({ text: styleMap[p.learning_style] ?? p.learning_style, size: 'lg', color: 'emerald' })
  
  if (p.major) tags.push({ text: p.major, size: 'md', color: 'amber' })
  if (p.goal && p.goal !== 'unknown') tags.push({ text: p.goal, size: 'md', color: 'violet' })
  if (p.study_time && p.study_time !== 'unknown') tags.push({ text: p.study_time, size: 'sm', color: 'sky' })
  if (p.weakness) tags.push({ text: p.weakness, size: 'sm', color: 'rose' })
  
  return tags
})

function toggleStep(week: number) {
  expandedStep.value = expandedStep.value === week ? null : week
}

function getResourceTypeClass(type: string) {
  const map: Record<string, string> = {
    ppt: 'bg-rose-50 text-rose-600 border-rose-200',
    quiz: 'bg-amber-50 text-amber-600 border-amber-200',
    code: 'bg-blue-50 text-blue-600 border-blue-200',
    mindmap: 'bg-purple-50 text-purple-600 border-purple-200',
    video: 'bg-cyan-50 text-cyan-600 border-cyan-200',
  }
  return map[type] ?? 'bg-surface-100 text-surface-500 border-surface-200'
}

function tryParseProfile(raw: string): ProfileData | null {
  try {
    const data = JSON.parse(raw)
    if (data && typeof data === 'object') return data as ProfileData
  } catch {
    return null
  }
  return null
}

async function analyzeProfile() {
  error.value = ''
  profileJson.value = ''
  parsedProfile.value = null
  loading.value = true
  try {
    const res = await fetch('/api/profile/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: message.value,
        session_id: sessionId.value || undefined,
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    sessionId.value = data.session_id
    profileJson.value = JSON.stringify(data.profile, null, 2)
    parsedProfile.value = tryParseProfile(profileJson.value)
    await nextTick()
    fetchRecommendations()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '画像分析失败'
  } finally {
    loading.value = false
  }
}

async function generatePath() {
  error.value = ''
  stepsWithResources.value = []
  pathOverview.value = null
  pathProfileSummary.value = ''
  pathTotalResources.value = 0
  loading.value = true
  try {
    const res = await fetch('/api/learning-path/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value,
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (!data.profile_found) {
      error.value = data.message ?? '请先完成画像分析'
      return
    }
    pathProfileSummary.value = data.profile_summary ?? ''
    pathOverview.value = data.learning_path ?? null
    stepsWithResources.value = data.steps_with_resources ?? []
    pathTotalResources.value = data.total_available_resources ?? 0
    await nextTick()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '路径生成失败'
  } finally {
    loading.value = false
  }
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

function tagColorClass(color: string): string {
  const map: Record<string, string> = {
    brand: 'bg-brand-50 text-brand-700 border-brand-200',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    violet: 'bg-violet-50 text-violet-700 border-violet-200',
    sky: 'bg-sky-50 text-sky-700 border-sky-200',
    rose: 'bg-rose-50 text-rose-700 border-rose-200',
  }
  return map[color] ?? 'bg-surface-100 text-surface-600 border-surface-200'
}

onMounted(() => {
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
    <div class="flex items-center gap-3">
      <span class="text-2xl">👤</span>
      <div>
        <h2 class="text-xl font-bold text-surface-800">个性化学习中心</h2>
        <p class="text-sm text-surface-400">AI 驱动的学生画像分析与学习路径规划</p>
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

    <!-- Tab 切换 -->
    <div class="flex gap-1.5 p-1 bg-surface-100 rounded-xl w-fit">
      <button
        v-for="t in (['profile', 'path'] as const)"
        :key="t"
        type="button"
        class="rounded-lg px-5 py-2 text-sm font-medium transition-all duration-200"
        :class="activeTab === t
          ? 'bg-white text-brand-700 shadow-sm'
          : 'text-surface-500 hover:text-surface-700'"
        @click="activeTab = t"
      >
        {{ t === 'profile' ? '🎯 学生画像' : '🗺️ 学习路径' }}
      </button>
    </div>

    <!-- 输入区 -->
    <div class="rounded-2xl border border-surface-200 bg-white p-5 space-y-3">
      <label class="text-xs font-semibold uppercase tracking-wider text-surface-400">学习描述</label>
      <textarea
        v-model="message"
        rows="3"
        class="w-full rounded-xl border border-surface-200 bg-surface-50 px-4 py-3 text-sm text-surface-700 placeholder-surface-300 focus:border-brand-400 focus:ring-2 focus:ring-brand-400/15 focus:outline-none transition-all resize-none"
        placeholder="描述你的学习背景、目标、时间安排..."
      />
    </div>

    <!-- 学生画像 Tab -->
    <div v-if="activeTab === 'profile'" class="space-y-5">
      <button
        type="button"
        class="rounded-xl bg-brand-500 px-6 py-3 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50 transition-all shadow-sm shadow-brand-500/25 hover:shadow-md hover:shadow-brand-500/30 flex items-center gap-2"
        :disabled="loading"
        @click="analyzeProfile"
      >
        <svg v-if="loading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        {{ loading ? '分析中...' : '🔍 生成学生画像' }}
      </button>

      <!-- 骨架屏 -->
      <div v-if="loading" class="grid gap-5 md:grid-cols-2">
        <div class="rounded-2xl border border-surface-200 bg-white p-6 space-y-3">
          <div class="skeleton h-5 w-24" />
          <div class="flex justify-center">
            <div class="skeleton h-[280px] w-[280px] rounded-full" />
          </div>
        </div>
        <div class="rounded-2xl border border-surface-200 bg-white p-6 space-y-3">
          <div class="skeleton h-5 w-20" />
          <div class="flex flex-wrap gap-2">
            <div v-for="i in 5" :key="i" class="skeleton h-8 w-20 rounded-full" />
          </div>
        </div>
      </div>

      <!-- 画像内容 -->
      <div v-if="parsedProfile" class="grid gap-5 md:grid-cols-2 animate-slide-up">
        <!-- 雷达图 -->
        <div class="rounded-2xl border border-surface-200 bg-white p-6">
          <h3 class="text-sm font-semibold text-surface-700 mb-4 flex items-center gap-2">
            <span class="w-1.5 h-4 bg-brand-500 rounded-full" />
            能力维度雷达图
          </h3>
          <div class="flex justify-center">
            <svg :viewBox="'0 0 280 280'" class="w-full max-w-[280px]">
              <!-- 网格 -->
              <polygon
                v-for="(ring, ri) in radarGridPoints"
                :key="'ring-' + ri"
                :points="ring.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')"
                :fill="ri === 2 ? '#eef2ff' : 'none'"
                :stroke="ri === 2 ? '#c7d2fe' : '#e2e8f0'"
                :stroke-width="ri === 2 ? 1.5 : 1"
              />
              <!-- 轴线 -->
              <line
                v-for="(p, i) in radarAxisPoints"
                :key="'axis-' + i"
                :x1="radarCenter" :y1="radarCenter"
                :x2="p.x.toFixed(1)" :y2="p.y.toFixed(1)"
                stroke="#e2e8f0"
                stroke-width="1"
              />
              <!-- 数据多边形 -->
              <polygon
                :points="radarPolygonPoints"
                fill="rgba(99, 102, 241, 0.2)"
                stroke="#6366f1"
                stroke-width="2"
                stroke-linejoin="round"
              />
              <!-- 数据点 -->
              <circle
                v-for="(p, i) in radarPoints"
                :key="'dot-' + i"
                :cx="p.x.toFixed(1)"
                :cy="p.y.toFixed(1)"
                r="4"
                fill="#6366f1"
                stroke="white"
                stroke-width="2"
              />
              <!-- 标签 -->
              <text
                v-for="(l, i) in labelOffsets"
                :key="'label-' + i"
                :x="l.x.toFixed(1)"
                :y="l.y.toFixed(1)"
                :text-anchor="l.anchor"
                class="text-[11px]"
                fill="#475569"
                font-weight="500"
              >{{ radarDimensions[i] }}</text>
            </svg>
          </div>
          <!-- 分数 -->
          <div class="grid grid-cols-3 gap-2 mt-4">
            <div
              v-for="(dim, i) in radarDimensions"
              :key="'score-' + i"
              class="text-center"
            >
              <div class="text-lg font-bold text-surface-800">{{ radarScores[i] }}</div>
              <div class="text-[10px] text-surface-400">{{ dim }}</div>
            </div>
          </div>
        </div>

        <!-- 标签云 + 信息 -->
        <div class="space-y-5">
          <div class="rounded-2xl border border-surface-200 bg-white p-6">
            <h3 class="text-sm font-semibold text-surface-700 mb-4 flex items-center gap-2">
              <span class="w-1.5 h-4 bg-emerald-500 rounded-full" />
              学习标签云
            </h3>
            <div class="flex flex-wrap gap-2">
              <span
                v-for="(tag, i) in profileTags"
                :key="i"
                class="inline-flex items-center rounded-full border px-3 py-1.5 text-xs font-medium transition-all hover:scale-105 cursor-default"
                :class="[
                  tagColorClass(tag.color),
                  tag.size === 'lg' ? 'text-sm px-4 py-2' : tag.size === 'sm' ? 'text-[11px] px-2.5 py-1' : '',
                ]"
              >
                {{ tag.text }}
              </span>
            </div>
          </div>

          <!-- 画像详情 -->
          <div class="rounded-2xl border border-surface-200 bg-white p-6">
            <h3 class="text-sm font-semibold text-surface-700 mb-3 flex items-center gap-2">
              <span class="w-1.5 h-4 bg-amber-500 rounded-full" />
              画像详情
            </h3>
            <div class="space-y-2.5 text-sm">
              <div v-if="parsedProfile.major" class="flex justify-between">
                <span class="text-surface-400">专业</span>
                <span class="text-surface-700 font-medium">{{ parsedProfile.major }}</span>
              </div>
              <div v-if="parsedProfile.learning_goal_text" class="flex justify-between">
                <span class="text-surface-400">学习目标</span>
                <span class="text-surface-700 font-medium max-w-[60%] text-right">{{ parsedProfile.learning_goal_text }}</span>
              </div>
              <div v-if="parsedProfile.learning_base" class="flex justify-between">
                <span class="text-surface-400">学习基础</span>
                <span class="text-surface-700 font-medium max-w-[60%] text-right">{{ parsedProfile.learning_base }}</span>
              </div>
              <div v-if="parsedProfile.learning_style_text" class="flex justify-between">
                <span class="text-surface-400">学习风格</span>
                <span class="text-surface-700 font-medium max-w-[60%] text-right">{{ parsedProfile.learning_style_text }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Raw JSON -->
      <details v-if="profileJson" class="rounded-xl border border-surface-200 bg-surface-50 overflow-hidden">
        <summary class="cursor-pointer px-4 py-2.5 text-xs font-medium text-surface-400 hover:text-surface-500 select-none">原始 JSON 数据</summary>
        <pre class="overflow-x-auto p-4 text-xs text-surface-500 border-t border-surface-100">{{ profileJson }}</pre>
      </details>

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
          >
            <div class="flex items-center justify-between mb-1.5">
              <span
                class="text-[10px] font-semibold rounded-full px-2 py-0.5"
                :class="[
                  item.resource_type === 'ppt' ? 'bg-rose-50 text-rose-600' :
                  item.resource_type === 'quiz' ? 'bg-amber-50 text-amber-600' :
                  item.resource_type === 'code' ? 'bg-blue-50 text-blue-600' :
                  item.resource_type === 'mindmap' ? 'bg-purple-50 text-purple-600' :
                  'bg-cyan-50 text-cyan-600'
                ]"
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
    </div>

    <!-- 学习路径 Tab -->
    <div v-else class="space-y-5">
      <button
        type="button"
        class="rounded-xl bg-brand-500 px-6 py-3 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50 transition-all shadow-sm shadow-brand-500/25 hover:shadow-md hover:shadow-brand-500/30 flex items-center gap-2"
        :disabled="loading || !sessionId"
        @click="generatePath"
      >
        <svg v-if="loading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        {{ loading ? '生成中...' : '🗺️ 生成学习路径' }}
      </button>

      <p v-if="!sessionId && !loading" class="text-sm text-surface-400 bg-surface-50 rounded-xl px-4 py-3 border border-surface-100">
        👈 请先在「学生画像」Tab 中完成画像分析
      </p>

      <!-- 骨架屏 -->
      <div v-if="loading" class="rounded-2xl border border-surface-200 bg-white p-6 space-y-4">
        <div class="skeleton h-5 w-32" />
        <div v-for="i in 3" :key="i" class="flex gap-4">
          <div class="skeleton h-8 w-8 rounded-full shrink-0" />
          <div class="flex-1 space-y-2">
            <div class="skeleton h-4 w-2/3" />
            <div class="skeleton h-3 w-full" />
          </div>
        </div>
      </div>

      <!-- 路径概览卡片 -->
      <div v-if="pathOverview" class="rounded-2xl border border-surface-200 bg-white p-5 space-y-3 animate-slide-up">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-lg">🗺️</span>
            <h3 class="text-sm font-bold text-surface-800">{{ pathOverview.path_name }}</h3>
          </div>
          <span class="text-[11px] text-surface-400 bg-surface-100 rounded-full px-2.5 py-0.5">
            {{ pathOverview.total_weeks }} 周 · {{ pathOverview.source === 'spark' ? 'AI 生成' : '智能规划' }}
          </span>
        </div>

        <div v-if="pathProfileSummary" class="text-xs text-surface-400 bg-surface-50 rounded-lg px-3 py-2">
          {{ pathProfileSummary }}
        </div>

        <div class="flex flex-wrap gap-2">
          <span
            v-for="focus in pathOverview.focus_areas"
            :key="focus"
            class="text-[11px] font-medium bg-brand-50 text-brand-600 rounded-full px-2.5 py-0.5 border border-brand-100"
          >{{ focus }}</span>
        </div>

        <div v-if="pathOverview.suggestions.length > 0" class="border-t border-surface-100 pt-3">
          <div class="text-[11px] font-semibold text-surface-500 mb-2">💡 学习建议</div>
          <ul class="space-y-1">
            <li
              v-for="(s, si) in pathOverview.suggestions"
              :key="si"
              class="text-xs text-surface-500 flex items-start gap-1.5"
            >
              <span class="text-brand-400 mt-0.5">•</span>
              {{ s }}
            </li>
          </ul>
        </div>
      </div>

      <!-- 时间轴 + 资源推送 -->
      <div v-if="stepsWithResources.length > 0" class="rounded-2xl border border-surface-200 bg-white p-6 animate-slide-up">
        <div class="flex items-center justify-between mb-6">
          <h3 class="text-sm font-semibold text-surface-700 flex items-center gap-2">
            <span class="w-1.5 h-4 bg-brand-500 rounded-full" />
            学习进度时间轴
          </h3>
          <span class="text-[11px] text-surface-400">共 {{ stepsWithResources.length }} 步 · {{ pathTotalResources }} 个资源</span>
        </div>

        <div class="relative">
          <div class="space-y-0">
            <div
              v-for="(step, i) in stepsWithResources"
              :key="i"
              class="relative flex gap-4 pb-6 last:pb-0"
            >
              <!-- 竖线 + 节点 -->
              <div class="flex flex-col items-center shrink-0">
                <div
                  class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all cursor-pointer"
                  :class="{
                    'bg-emerald-500 text-white shadow-md shadow-emerald-500/25': i === 0,
                    'bg-brand-500 text-white shadow-md shadow-brand-500/25 ring-4 ring-brand-100': i === 1,
                    'bg-surface-200 text-surface-400': i > 1,
                  }"
                  @click="toggleStep(step.week)"
                >
                  <svg v-if="i === 0" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                  <span v-else>{{ step.week }}</span>
                </div>
                <div
                  v-if="i < stepsWithResources.length - 1"
                  class="w-0.5 flex-1 min-h-[20px]"
                  :class="i === 0 ? 'bg-emerald-300' : 'bg-surface-200'"
                />
              </div>

              <!-- 步骤内容 -->
              <div class="flex-1 min-w-0 pt-1.5">
                <div class="flex items-center gap-2 mb-1.5 cursor-pointer" @click="toggleStep(step.week)">
                  <h4 class="text-sm font-semibold text-surface-800">{{ step.title }}</h4>
                  <span
                    class="text-[10px] font-medium rounded-full px-2 py-0.5"
                    :class="{
                      'bg-emerald-50 text-emerald-600': i === 0,
                      'bg-brand-50 text-brand-600': i === 1,
                      'bg-surface-100 text-surface-400': i > 1,
                    }"
                  >
                    {{ i === 0 ? '已完成' : i === 1 ? '进行中' : '未开始' }}
                  </span>
                  <span class="text-[11px] text-surface-400">{{ step.duration }}</span>
                </div>

                <div class="flex flex-wrap gap-1.5 mb-2">
                  <span
                    v-for="(topic, ti) in step.topics.slice(0, 6)"
                    :key="ti"
                    class="text-[11px] text-surface-500 bg-surface-50 rounded-md px-2 py-0.5 border border-surface-100"
                  >{{ topic }}</span>
                  <span v-if="step.topics.length > 6" class="text-[11px] text-surface-400">+{{ step.topics.length - 6 }}</span>
                </div>

                <div class="flex items-center gap-2 text-[11px] text-surface-400">
                  <span class="flex items-center gap-1">
                    <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
                    评估：{{ step.assessment }}
                  </span>
                  <span v-if="step.available_resources.length > 0" class="text-brand-500 font-medium">
                    已关联 {{ step.available_resources.length }} 个资源
                  </span>
                </div>

                <!-- 资源推送卡片 -->
                <div
                  v-if="expandedStep === step.week && step.available_resources.length > 0"
                  class="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 animate-slide-up"
                >
                  <div
                    v-for="res in step.available_resources"
                    :key="res.id"
                    class="rounded-lg border border-surface-200 hover:border-brand-200 hover:shadow-sm p-2.5 transition-all cursor-pointer bg-surface-50"
                  >
                    <div class="flex items-center gap-2 mb-1">
                      <span class="text-sm">{{ res.resource_icon }}</span>
                      <span
                        class="text-[10px] font-semibold rounded-full px-2 py-0.5 border"
                        :class="getResourceTypeClass(res.resource_type)"
                      >
                        {{ res.resource_label }}
                      </span>
                    </div>
                    <div class="text-xs font-medium text-surface-700 line-clamp-1">{{ res.topic }}</div>
                    <div v-if="res.preview" class="text-[10px] text-surface-400 mt-0.5 line-clamp-1">{{ res.preview }}</div>
                  </div>
                </div>

                <div
                  v-if="expandedStep === step.week && step.available_resources.length === 0"
                  class="mt-2 text-xs text-surface-400 bg-surface-50 rounded-lg px-3 py-2"
                >
                  暂无可关联资源，建议先在「资源生成」模块生成 {{ step.recommended_resource_types.join('、') }} 等资源
                </div>

                <div
                  v-if="expandedStep !== step.week && step.available_resources.length > 0"
                  class="mt-2 flex items-center gap-1 text-[10px] text-brand-500 cursor-pointer"
                  @click="toggleStep(step.week)"
                >
                  <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
                  展开查看关联资源
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 无数据提示 -->
      <div v-if="!loading && pathOverview && stepsWithResources.length === 0" class="rounded-2xl border border-surface-200 bg-surface-50 p-6 text-center">
        <p class="text-sm text-surface-400">学习路径已生成，但无详细步骤数据</p>
      </div>
    </div>

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
</style>
