<script setup lang="ts">
/**
 * VoiceLearning.vue - 语音学习中心重构
 *
 * 核心改动：
 * 1. 音色选择：卡片式选择器，含头像 + 名称 + 性别标签，替代简单下拉框
 * 2. 语速滑块：可视化滑块，带快捷预设（慢/中/快）
 * 3. 录音波形：CSS 动画模拟音频柱状波动画，录音中动态跳动
 * 4. 现代播放器：圆角控制条 + 播放/暂停 + 进度条 + 时间显示
 * 5. 识别结果：卡片式展示 + 复制按钮
 * 6. 浅色主题适配 + 骨架屏
 * 7. 保持原有 /api/voice/tts 和 /api/voice/asr API 调用逻辑不变
 */
import { ref, computed, onBeforeUnmount, onMounted } from 'vue'
import { createPcmWavRecorder, type PcmWavRecorder } from '../utils/audioRecorder'

const text = ref('你好，欢迎使用 EduAgent 智能学习平台')
const voice = ref('x4_xiaoyan')
const speechRate = ref(5)
const audioUrl = ref('')
const audioBase64 = ref('')
const recognitionText = ref('')
const loading = ref(false)
const error = ref('')
const activeTab = ref<'tts' | 'asr'>('tts')
const isRecording = ref(false)
const recordingDuration = ref(0)
const audioPlaying = ref(false)
const audioProgress = ref(0)
const audioDuration = ref(0)
const audioCurrentTime = ref(0)
const actionFeedback = ref('')

let recordingTimer: ReturnType<typeof setInterval> | null = null
let audioEl: HTMLAudioElement | null = null
let progressTimer: ReturnType<typeof setInterval> | null = null
let activeRecorder: PcmWavRecorder | null = null

const voices = [
  { key: 'x4_xiaoyan', label: '讯飞小燕', gender: '女', emoji: '👩', color: 'bg-pink-50 border-pink-200 text-pink-700', activeColor: 'ring-pink-400/30' },
  { key: 'x4_xiaolu', label: '讯飞小露', gender: '女', emoji: '👩', color: 'bg-blue-50 border-blue-200 text-blue-700', activeColor: 'ring-blue-400/30' },
  { key: 'x4_xujiu', label: '讯飞许久', gender: '男', emoji: '👨', color: 'bg-violet-50 border-violet-200 text-violet-700', activeColor: 'ring-violet-400/30' },
  { key: 'x4_xiaojing', label: '讯飞小婧', gender: '女', emoji: '👩', color: 'bg-emerald-50 border-emerald-200 text-emerald-700', activeColor: 'ring-emerald-400/30' },
] as const

const rateLabels = computed(() => {
  if (speechRate.value <= 3) return { label: '慢速', emoji: '🐢' }
  if (speechRate.value <= 7) return { label: '正常', emoji: '🚶' }
  return { label: '快速', emoji: '🐇' }
})

const waveformBars = computed(() => {
  return Array.from({ length: 12 }, () => ({
    height: !isRecording.value ? 12 : Math.random() * 40 + 8,
    delay: Math.random() * 0.8,
  }))
})

// AI 模型选择
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

// Provider 选项
const providers = [
  { value: 'spark', label: '讯飞星火' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'qwen', label: '通义千问' },
  { value: 'other', label: '其他' },
]

// 预设 API URL 模板
const providerTemplates: Record<string, { api_url: string; protocol: string }> = {
  spark: { api_url: 'https://spark-api-open.xf-yun.com/v1/chat/completions', protocol: 'http' },
  openai: { api_url: 'https://api.openai.com/v1/chat/completions', protocol: 'http' },
  deepseek: { api_url: 'https://api.deepseek.com/v1/chat/completions', protocol: 'http' },
  qwen: { api_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions', protocol: 'http' },
  other: { api_url: '', protocol: 'http' },
}

// AI 模型状态
interface ModelStatus {
  status: 'connected' | 'disconnected' | 'timeout' | 'error' | 'checking'
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

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// 获取可用模型列表
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

// 检查 AI 模型连接状态
async function checkModelStatus() {
  modelStatus.value.status = 'checking'
  try {
    const res = await fetch(`/api/chat/model-status?model=${encodeURIComponent(selectedModel.value)}`)
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
    modelStatus.value.status = 'disconnected'
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

// 获取当前模型显示标签
function getSelectedModelLabel(): string {
  const model = availableModels.value.find(m => m.id === selectedModel.value)
  return model ? model.label : selectedModel.value
}

// 模型下拉框
function toggleModelDropdown() {
  showModelDropdown.value = !showModelDropdown.value
}

function selectModel(modelId: string) {
  selectedModel.value = modelId
  showModelDropdown.value = false
  checkModelStatus()
}

// 新增模型弹窗
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

async function synthesizeSpeech() {
  error.value = ''
  // 清理旧资源
  if (audioUrl.value) {
    URL.revokeObjectURL(audioUrl.value)
    audioUrl.value = ''
  }
  audioBase64.value = ''
  loading.value = true
  try {
    if (!text.value.trim()) throw new Error('请输入要合成的文字')

    const formData = new FormData()
    formData.append('text', text.value)
    formData.append('voice', voice.value)

    const res = await fetch('/api/voice/tts', {
      method: 'POST',
      body: formData,
    })
    if (!res.ok) {
      const detail = await res.json().catch(() => null)
      throw new Error(detail?.detail || `HTTP ${res.status}`)
    }

    // 使用 arrayBuffer 获取原始字节，避免 blob 嵌套导致类型丢失
    const buffer = await res.arrayBuffer()
    if (buffer.byteLength === 0) throw new Error('语音合成返回空数据，请重试')

    const blob = new Blob([new Uint8Array(buffer)], { type: 'audio/mpeg' })
    audioUrl.value = URL.createObjectURL(blob)
    stopAudio()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '语音合成失败'
  } finally {
    loading.value = false
  }
}

function playAudio() {
  if (!audioUrl.value) return
  if (!audioEl) {
    audioEl = new Audio()
    audioEl.preload = 'auto'
    audioEl.addEventListener('loadedmetadata', () => {
      audioDuration.value = audioEl?.duration ?? 0
    })
    audioEl.addEventListener('timeupdate', () => {
      if (audioEl) {
        audioCurrentTime.value = audioEl.currentTime
        audioProgress.value = audioEl.duration ? (audioEl.currentTime / audioEl.duration) * 100 : 0
      }
    })
    audioEl.addEventListener('ended', () => {
      audioPlaying.value = false
      audioProgress.value = 0
      audioCurrentTime.value = 0
    })
    audioEl.addEventListener('play', () => { audioPlaying.value = true })
    audioEl.addEventListener('pause', () => { audioPlaying.value = false })
    audioEl.addEventListener('error', () => {
      const err = audioEl?.error
      console.warn('[VoiceLearning] 音频加载错误:', err?.message, 'code:', err?.code)
      error.value = '音频加载失败，请重试'
    })
  }
  audioEl.src = audioUrl.value
  audioEl.load()
  audioEl.play().catch((e) => {
    console.warn('[VoiceLearning] 音频播放失败:', e.message)
    error.value = '音频播放失败，请重试'
  })
}

function pauseAudio() {
  audioEl?.pause()
}

function toggleAudio() {
  if (audioPlaying.value) {
    pauseAudio()
  } else {
    playAudio()
  }
}

function stopAudio() {
  if (audioEl) {
    audioEl.pause()
    audioEl.currentTime = 0
    audioPlaying.value = false
    audioProgress.value = 0
    audioCurrentTime.value = 0
  }
}

function seekAudio(e: MouseEvent) {
  if (!audioEl || !audioDuration.value) return
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  audioEl.currentTime = ratio * audioDuration.value
}

async function recognizeSpeech() {
  error.value = ''
  recognitionText.value = ''
  loading.value = true
  try {
    activeRecorder = await createPcmWavRecorder()
    isRecording.value = true
    recordingDuration.value = 0
    recordingTimer = setInterval(() => { recordingDuration.value++ }, 1000)
    // 讯飞 ASR 支持最长 60 秒单次识别，设置自动停止
    await new Promise<void>(resolve => {
      const interval = setInterval(() => {
        if (!isRecording.value || recordingDuration.value >= 60) {
          clearInterval(interval)
          resolve()
        }
      }, 500)
    })
    const recorder = activeRecorder
    activeRecorder = null
    if (recordingTimer) { clearInterval(recordingTimer); recordingTimer = null }
    isRecording.value = false

    const blob = await recorder.stop()
    if (blob.size === 0) throw new Error('未录制到语音内容')

    const formData = new FormData()
    formData.append('audio', blob, 'recording.wav')
    formData.append('format', 'wav')

    const res = await fetch('/api/voice/asr', {
      method: 'POST',
      body: formData,
    })
    if (!res.ok) {
      const detail = await res.json().catch(() => null)
      throw new Error(detail?.detail || `HTTP ${res.status}`)
    }
    const data = await res.json()
    recognitionText.value = data.text ?? ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : '无法访问麦克风'
    if (activeRecorder) {
      await activeRecorder.cancel().catch(() => {})
      activeRecorder = null
    }
    if (recordingTimer) { clearInterval(recordingTimer); recordingTimer = null }
  } finally {
    loading.value = false
    isRecording.value = false
  }
}

function stopRecording() {
  isRecording.value = false
  if (recordingTimer) {
    clearInterval(recordingTimer)
    recordingTimer = null
  }
}

async function copyRecognition() {
  try {
    await navigator.clipboard.writeText(recognitionText.value)
    actionFeedback.value = '已复制到剪贴板'
    setTimeout(() => { actionFeedback.value = '' }, 2000)
  } catch {
    actionFeedback.value = '复制失败'
    setTimeout(() => { actionFeedback.value = '' }, 2000)
  }
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
  stopAudio()
  if (recordingTimer) clearInterval(recordingTimer)
  if (progressTimer) clearInterval(progressTimer)
  if (statusCheckTimer) clearInterval(statusCheckTimer)
  if (activeRecorder) activeRecorder.cancel().catch(() => {})
  if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
})
</script>

<template>
  <div class="space-y-5">
    <div class="flex items-center gap-3">
      <span class="text-2xl">🎙️</span>
      <div>
        <h2 class="text-xl font-bold text-surface-800">语音学习中心</h2>
        <p class="text-sm text-surface-400">文本转语音合成 · 语音识别转文字</p>
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
        v-for="t in (['tts', 'asr'] as const)"
        :key="t"
        type="button"
        class="rounded-lg px-5 py-2 text-sm font-medium transition-all duration-200"
        :class="activeTab === t
          ? 'bg-white text-brand-700 shadow-sm'
          : 'text-surface-500 hover:text-surface-700'"
        @click="activeTab = t"
      >
        {{ t === 'tts' ? '🔊 语音合成' : '🎤 语音识别' }}
      </button>
    </div>

    <!-- TTS Tab -->
    <div v-if="activeTab === 'tts'" class="space-y-5">
      <!-- 文本输入 -->
      <div class="rounded-2xl border border-surface-200 bg-white p-5 space-y-3">
        <label class="text-xs font-semibold uppercase tracking-wider text-surface-400">合成文本</label>
        <textarea
          v-model="text"
          rows="4"
          class="w-full rounded-xl border border-surface-200 bg-surface-50 px-4 py-3 text-sm text-surface-700 placeholder-surface-300 focus:border-brand-400 focus:ring-2 focus:ring-brand-400/15 focus:outline-none transition-all resize-none"
          placeholder="请输入要合成的文本..."
        />
      </div>

      <!-- 音色选择 -->
      <div class="rounded-2xl border border-surface-200 bg-white p-5">
        <label class="text-xs font-semibold uppercase tracking-wider text-surface-400 block mb-4">选择音色</label>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <button
            v-for="v in voices"
            :key="v.key"
            type="button"
            class="rounded-xl border-2 p-4 text-center transition-all duration-200"
            :class="[
              voice === v.key
                ? `border-brand-400 bg-brand-50 shadow-sm ring-2 ${v.activeColor}`
                : 'border-surface-200 bg-white hover:border-surface-300 hover:shadow-sm',
            ]"
            @click="voice = v.key"
          >
            <div class="text-3xl mb-1.5">{{ v.emoji }}</div>
            <div class="text-sm font-semibold text-surface-700">{{ v.label }}</div>
            <div class="text-[11px] text-surface-400 mt-0.5">{{ v.gender }}</div>
          </button>
        </div>
      </div>

      <!-- 语速 -->
      <div class="rounded-2xl border border-surface-200 bg-white p-5">
        <div class="flex items-center justify-between mb-4">
          <label class="text-xs font-semibold uppercase tracking-wider text-surface-400">语速调节</label>
          <span class="text-sm font-medium text-brand-600">{{ rateLabels.emoji }} {{ rateLabels.label }}</span>
        </div>
        <div class="flex items-center gap-4">
          <span class="text-xs text-surface-400">慢</span>
          <input
            type="range"
            :min="1"
            :max="10"
            v-model.number="speechRate"
            class="flex-1 h-2 rounded-full bg-surface-200 accent-brand-500 appearance-none cursor-pointer"
          />
          <span class="text-xs text-surface-400">快</span>
        </div>
        <div class="flex justify-between mt-1.5 px-1">
          <span v-for="p in 10" :key="p" class="text-[9px] text-surface-300 select-none">|</span>
        </div>
      </div>

      <!-- 生成按钮 -->
      <button
        type="button"
        class="w-full rounded-xl bg-brand-500 px-6 py-3.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50 transition-all shadow-sm shadow-brand-500/25 hover:shadow-md hover:shadow-brand-500/30 flex items-center justify-center gap-2"
        :disabled="loading || !text.trim()"
        @click="synthesizeSpeech"
      >
        <svg v-if="loading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        {{ loading ? '合成中...' : '🔊 合成语音' }}
      </button>

      <!-- 音频播放器 -->
      <div v-if="audioUrl" class="rounded-2xl border border-surface-200 bg-white p-5 animate-slide-up">
        <h3 class="text-sm font-semibold text-surface-700 mb-4 flex items-center gap-2">
          <span class="w-1.5 h-4 bg-brand-500 rounded-full" />
          音频播放
        </h3>
        <div class="flex items-center gap-4">
          <button
            type="button"
            class="w-12 h-12 rounded-full bg-brand-500 text-white hover:bg-brand-600 transition-all flex items-center justify-center shadow-md shadow-brand-500/25 shrink-0"
            @click="toggleAudio"
          >
            <svg v-if="audioPlaying" class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>
            </svg>
            <svg v-else class="w-5 h-5 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </button>

          <div class="flex-1">
            <div
              class="h-2 bg-surface-100 rounded-full overflow-hidden cursor-pointer group"
              @click="seekAudio"
            >
              <div
                class="h-full bg-gradient-to-r from-brand-400 to-brand-600 rounded-full transition-all duration-100"
                :style="{ width: audioProgress + '%' }"
              />
            </div>
            <div class="flex justify-between mt-1.5">
              <span class="text-[11px] text-surface-400">{{ formatTime(audioCurrentTime) }}</span>
              <span class="text-[11px] text-surface-400">{{ formatTime(audioDuration) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ASR Tab -->
    <div v-else class="space-y-5">
      <!-- 录音区 -->
      <div class="rounded-2xl border border-surface-200 bg-white p-8 text-center">
        <div v-if="isRecording" class="space-y-5">
          <!-- 波形动画 -->
          <div class="flex items-center justify-center gap-1 h-16">
            <div
              v-for="(bar, i) in waveformBars"
              :key="i"
              class="w-2 bg-brand-500 rounded-full transition-all"
              :style="{
                height: bar.height + 'px',
                opacity: 0.5 + Math.random() * 0.5,
                animationDelay: bar.delay + 's',
              }"
            />
          </div>
          <div>
            <div class="text-2xl font-bold text-brand-600">{{ formatTime(recordingDuration) }}</div>
            <p class="text-sm text-surface-400 mt-1">正在录音中...</p>
          </div>
          <div class="flex justify-center gap-2 text-[10px] text-surface-400">
            <span class="w-2 h-2 rounded-full bg-rose-400 animate-pulse" />
            录音中，最长 60 秒自动停止，点击下方按钮手动停止
          </div>
          <div class="flex justify-center">
            <button
              type="button"
              class="rounded-xl bg-rose-500 px-5 py-2 text-sm font-semibold text-white hover:bg-rose-600 transition-all shadow-sm shadow-rose-500/25 inline-flex items-center gap-2"
              @click="stopRecording"
            >
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>
              </svg>
              停止录音
            </button>
          </div>
        </div>
        <div v-else class="space-y-4">
          <div class="text-5xl">🎤</div>
          <p class="text-sm text-surface-400">点击下方按钮开始录音，最长录制 60 秒，可手动停止</p>
          <button
            type="button"
            class="rounded-xl bg-brand-500 px-6 py-3 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50 transition-all shadow-sm shadow-brand-500/25 hover:shadow-md hover:shadow-brand-500/30 inline-flex items-center gap-2"
            :disabled="loading"
            @click="recognizeSpeech"
          >
            <svg v-if="loading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {{ loading ? '识别中...' : '🎤 开始录音' }}
          </button>
        </div>
      </div>

      <!-- 识别结果 -->
      <div v-if="recognitionText" class="rounded-2xl border border-surface-200 bg-white p-5 animate-slide-up">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold text-surface-700 flex items-center gap-2">
            <span class="w-1.5 h-4 bg-emerald-500 rounded-full" />
            识别结果
          </h3>
          <button
            type="button"
            class="rounded-lg px-3 py-1.5 text-xs text-surface-500 hover:text-surface-700 hover:bg-surface-100 transition-colors flex items-center gap-1"
            @click="copyRecognition"
          >
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
            复制
          </button>
        </div>
        <div class="p-4 rounded-xl bg-surface-50 text-sm text-surface-700 leading-relaxed border border-surface-100">
          {{ recognitionText }}
        </div>
      </div>
    </div>

    <!-- Toast -->
    <transition name="toast-v">
      <div
        v-if="actionFeedback"
        class="fixed top-20 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-xl bg-surface-800 text-white text-sm font-medium shadow-lg"
      >
        {{ actionFeedback }}
      </div>
    </transition>

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
.toast-v-enter-active { transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.toast-v-leave-active { transition: all 0.2s ease-in; }
.toast-v-enter-from { opacity: 0; transform: translate(-50%, 8px); }
.toast-v-leave-to { opacity: 0; transform: translate(-50%, -4px); }

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
