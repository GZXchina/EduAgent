<script setup lang="ts">
/**
 * ChatLearning.vue - 对话学习模块（用户视角重构）
 *
 * 核心改动：
 * 1. AI回复分层展示：主回复（仅答疑内容）+ 折叠详情（画像/规划/知识检索）
 * 2. 文件上传：支持 MD/PDF/TXT，上传后自动入库RAG
 * 3. 语音输入：浏览器录音 → 讯飞ASR → 文字填入输入框
 * 4. 流式打字机效果 + Markdown渲染 + 代码高亮
 * 5. 快捷提问引导卡片 + 消息操作（复制/点赞/重新生成）
 */

import { ref, nextTick, watch, onBeforeUnmount, onMounted } from 'vue'
import { marked } from 'marked'
import mermaid from 'mermaid'
import { createPcmWavRecorder, type PcmWavRecorder } from '../utils/audioRecorder'

interface InternalStep {
  node: string
  label: string
  content: string
  is_user_facing: boolean
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  liked?: boolean
  internalSteps?: InternalStep[]
  sessionId?: string
  isStreaming?: boolean  // 标记当前消息是否正在流式输出中
  renderedHtml?: string // 流式完成后缓存的渲染结果，避免重复渲染
}

const message = ref('')
const sessionId = ref('')
const loading = ref(false)
const streaming = ref(false)
const error = ref('')
const messages = ref<ChatMessage[]>([])
const actionFeedback = ref('')

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

// AI 实时思考过程
const currentThinkingLabel = ref('')
const currentThinkingNode = ref('')
const thinkingSteps = ref<{ node: string; label: string; status: 'processing' | 'completed' }[]>([])

// AI 模型连接状态
interface ModelStatusInfo {
  status: 'connected' | 'disconnected' | 'error' | 'timeout' | 'checking'
  message: string
  current_model: string | null
  model_label: string | null
  latency_ms: number | null
  fallback_mode: boolean
}
const modelStatus = ref<ModelStatusInfo>({
  status: 'checking',
  message: '检查连接中...',
  current_model: null,
  model_label: null,
  latency_ms: null,
  fallback_mode: false,
})
let statusCheckTimer: ReturnType<typeof setInterval> | null = null

const isRecording = ref(false)
const recordingDuration = ref(0)
let recordingTimer: ReturnType<typeof setInterval> | null = null
let activeRecorder: PcmWavRecorder | null = null

const uploadingFile = ref(false)
const uploadMsg = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)

marked.setOptions({
  breaks: true,
  gfm: true,
})

function configureMarked() {
  const renderer = new marked.Renderer()

  // 使用标准 Markdown 代码块，不添加自定义样式
  // 最终显示效果由客户端/平台渲染决定

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  renderer.table = function(tableData: any): string {
    const headerCells = tableData.header.map((h: any) => `<th>${h.text ?? h}</th>`).join('')
    const thead = `<thead><tr>${headerCells}</tr></thead>`
    const bodyRows = tableData.rows.map((row: any[]) =>
      `<tr>${row.map((cell: any) => `<td>${cell.text ?? cell}</td>`).join('')}</tr>`
    ).join('')
    const tbody = `<tbody>${bodyRows}</tbody>`
    return `<div class="table-wrapper"><table>${thead}${tbody}</table></div>`
  }

  return renderer
}

marked.use({ renderer: configureMarked() })

function escapeHtml(text: string): string {
  const d = document.createElement('div')
  d.textContent = text
  return d.innerHTML
}

function getRawContent(msg: ChatMessage): string {
  return msg.content
}

// Mermaid 渲染计数器
let mermaidCounter = 0

function renderMarkdown(text: string): string {
  if (!text) return ''
  try {
    // 提取 mermaid 代码块，替换为占位 div
    const mermaidBlocks: string[] = []
    const processed = text.replace(/```mermaid\n([\s\S]*?)```/g, (_match, code) => {
      const idx = mermaidBlocks.length
      mermaidBlocks.push(code.trim())
      return `<div class="mermaid-pending" data-mermaid-idx="${idx}"></div>`
    })

    // 将提取的 mermaid 代码存到消息上下文
    pendingMermaidBlocks.value = mermaidBlocks

    return marked.parse(processed) as string
  } catch {
    return escapeHtml(text)
  }
}

// 全局存储当前待渲染的 mermaid 代码块
const pendingMermaidBlocks = ref<string[]>([])

async function renderPendingMermaidBlocks() {
  const blocks = document.querySelectorAll('.mermaid-pending')
  if (!blocks.length || !pendingMermaidBlocks.value.length) return

  for (const block of Array.from(blocks)) {
    const idx = parseInt(block.getAttribute('data-mermaid-idx') || '0', 10)
    const code = pendingMermaidBlocks.value[idx]
    if (!code) continue

    try {
      const id = `mermaid-chat-${Date.now()}-${mermaidCounter++}`
      const { svg } = await mermaid.render(id, code)
      block.innerHTML = svg
      block.classList.remove('mermaid-pending')
      block.classList.add('mermaid-rendered')
    } catch {
      // 渲染失败时显示原始代码
      block.innerHTML = `<pre class="text-xs text-surface-500 bg-surface-50 p-2 rounded"><code>${escapeHtml(code)}</code></pre>`
      block.classList.remove('mermaid-pending')
    }
  }
}

// 自动行为追踪：记录对话行为
function trackBehavior(action: string, detail: Record<string, unknown> = {}, durationMinutes = 0) {
  if (!sessionId.value) return
  fetch('/api/evaluation/track-behavior', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId.value,
      action,
      detail,
      duration_minutes: durationMinutes,
    }),
  }).catch(() => {}) // 静默失败，不影响主流程
}

// 获取可用模型列表
async function fetchModels() {
  try {
    const res = await fetch('/api/chat/models')
    if (res.ok) {
      const data = await res.json()
      availableModels.value = data.models || []
      // 如果当前选择不在列表中，默认选第一个
      if (availableModels.value.length > 0 && !availableModels.value.find(m => m.id === selectedModel.value)) {
        selectedModel.value = availableModels.value[0].id
      }
    }
  } catch {
    // 静默失败，使用默认模型
  }
}

// 检查 AI 模型连接状态
async function checkModelStatus() {
  try {
    modelStatus.value.status = 'checking'
    modelStatus.value.message = `正在检查 ${getSelectedModelLabel()}...`
    // 传递当前选择的模型 ID
    const res = await fetch(`/api/chat/model-status?model=${encodeURIComponent(selectedModel.value)}`)
    if (res.ok) {
      const data = await res.json()
      modelStatus.value = {
        status: data.status,
        message: data.message,
        current_model: data.current_model,
        model_label: data.model_label || null,
        latency_ms: data.latency_ms,
        fallback_mode: data.fallback_mode ?? false,
      }
    } else {
      modelStatus.value = {
        status: 'error',
        message: `HTTP ${res.status}`,
        current_model: selectedModel.value,
        model_label: getSelectedModelLabel(),
        latency_ms: null,
        fallback_mode: true,
      }
    }
  } catch {
    modelStatus.value = {
      status: 'disconnected',
      message: '无法连接到后端',
      current_model: selectedModel.value,
      model_label: getSelectedModelLabel(),
      latency_ms: null,
      fallback_mode: true,
    }
  }
}

// 切换模型下拉框
function toggleModelDropdown() {
  showModelDropdown.value = !showModelDropdown.value
}

function selectModel(modelId: string) {
  selectedModel.value = modelId
  showModelDropdown.value = false
  // 切换模型后自动刷新连接状态
  checkModelStatus()
}

// 获取当前模型的显示标签
function getSelectedModelLabel(): string {
  const model = availableModels.value.find(m => m.id === selectedModel.value)
  return model ? model.label : selectedModel.value
}

// 打开新增模型弹窗
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

// 切换 Provider 时自动填充模板
function onProviderChange(provider: string) {
  const template = providerTemplates[provider]
  if (template) {
    newModel.value.api_url = template.api_url
    newModel.value.protocol = template.protocol
  }
}

// 新增自定义模型
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
    // 刷新模型列表
    await fetchModels()
  } catch (e) {
    addModelError.value = e instanceof Error ? e.message : '添加失败'
  } finally {
    addingModel.value = false
  }
}

// 删除自定义模型
async function deleteCustomModel(modelId: string, event: Event) {
  event.stopPropagation()
  if (!confirm('确定要删除该模型吗？')) return

  try {
    const res = await fetch(`/api/models/custom/${modelId}`, { method: 'DELETE' })
    if (res.ok) {
      // 如果删除的是当前选择的模型，切换到第一个内置模型
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

// 状态指示器颜色
function getStatusColor(): string {
  switch (modelStatus.value.status) {
    case 'connected': return 'bg-emerald-400'
    case 'checking': return 'bg-amber-400 animate-pulse'
    case 'timeout': return 'bg-orange-400'
    case 'error': return 'bg-rose-400'
    default: return 'bg-surface-300'
  }
}

function getStatusText(): string {
  // 兜底模式时显示本地运行状态
  if (modelStatus.value.fallback_mode && modelStatus.value.status !== 'checking') {
    return '使用本地规则引擎'
  }
  return modelStatus.value.message
}

async function sendMessage() {
  if (!message.value.trim() || loading.value) return

  error.value = ''
  loading.value = true
  streaming.value = true
  const startTime = Date.now()

  // 重置思考状态
  currentThinkingLabel.value = ''
  currentThinkingNode.value = ''
  thinkingSteps.value = []

  const userMsg: ChatMessage = {
    role: 'user',
    content: message.value.trim(),
    timestamp: Date.now(),
  }
  messages.value.push(userMsg)
  const sentMessage = message.value.trim()
  message.value = ''

  const aiMsg: ChatMessage = {
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
    internalSteps: [],
    isStreaming: true,
  }
  messages.value.push(aiMsg)

  await nextTick()
  scrollToBottom()

  try {
    // 构建对话历史：取已有消息中最近的用户/AI对话（最多10条，即5轮）
    const historyMessages = messages.value
      .filter(m => m.role === 'user' || (m.role === 'assistant' && m.content))
      .slice(-12, -2) // 排除刚添加的当前用户消息和空AI占位消息
      .map(m => ({ role: m.role, content: m.content }))

    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: sentMessage,
        session_id: sessionId.value || undefined,
        history: historyMessages,
        model: selectedModel.value,
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    if (!res.body) throw new Error('响应体为空')

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))

          // 处理 thinking 事件：实时显示 AI 思考过程
          if (data.type === 'thinking') {
            const stepStatus = data.status || 'processing'

            if (stepStatus === 'processing') {
              // 新节点开始处理
              currentThinkingLabel.value = data.label || '处理中...'
              currentThinkingNode.value = data.node || ''
              thinkingSteps.value.push({ node: data.node, label: data.label || '处理中...', status: 'processing' })
            } else if (stepStatus === 'completed') {
              // 节点完成，更新状态
              const step = thinkingSteps.value.find(s => s.node === data.node)
              if (step) {
                step.status = 'completed'
              }
              // 清除当前 thinking（等待下一个 processing 事件）
              currentThinkingLabel.value = ''
              currentThinkingNode.value = ''
            }

            await nextTick()
            scrollToBottom()
          }

          if (data.type === 'message' && data.content) {
            // 收到正式回复时清除 thinking 状态
            currentThinkingLabel.value = ''
            currentThinkingNode.value = ''
            if (aiMsg.content) {
              aiMsg.content += '\n\n' + data.content
            } else {
              aiMsg.content = data.content
            }
            await nextTick()
            scrollToBottom()
          }

          // 流式消息：逐 token 推送
          if (data.type === 'message_start') {
            currentThinkingLabel.value = ''
            currentThinkingNode.value = ''
            aiMsg.content = ''
            await nextTick()
            scrollToBottom()
          }

          if (data.type === 'message_delta' && data.content) {
            aiMsg.content += data.content
            await nextTick()
            scrollToBottom()
          }

          if (data.type === 'message_end' && data.content) {
            // 用完整内容替换，确保一致性
            aiMsg.content = data.content
            await nextTick()
            scrollToBottom()
          }

          if (data.type === 'done') {
            currentThinkingLabel.value = ''
            currentThinkingNode.value = ''
            if (data.session_id) {
              sessionId.value = data.session_id
              aiMsg.sessionId = data.session_id
              // 持久化到 localStorage，供评估中心自动获取
              localStorage.setItem('edu_session_id', data.session_id)
            }
            if (data.internal_steps) {
              aiMsg.internalSteps = data.internal_steps
            }
          }

          if (data.type === 'error') {
            currentThinkingLabel.value = ''
            currentThinkingNode.value = ''
            error.value = data.message || '工作流执行失败'
          }
        } catch {
        }
      }
    }
  } catch (e) {
    if (!aiMsg.content) {
      aiMsg.content = '抱歉，回复生成失败，请稍后重试。'
    }
    error.value = e instanceof Error ? e.message : '请求失败'
  } finally {
    loading.value = false
    streaming.value = false
    // 流式完成：缓存渲染结果，标记非流式，避免后续轮次重复渲染
    aiMsg.isStreaming = false
    aiMsg.renderedHtml = renderMarkdown(aiMsg.content)
    await nextTick()
    scrollToBottom()
    await renderPendingMermaidBlocks()
    // 自动追踪对话行为
    const durationMin = Math.max(1, Math.round((Date.now() - startTime) / 60000))
    trackBehavior('chat', { question: sentMessage.slice(0, 100) }, durationMin)
  }
}

async function regenerate(_msg: ChatMessage, idx: number) {
  const userMsg = messages.value[idx - 1]
  if (!userMsg || userMsg.role !== 'user') return

  messages.value.splice(idx, 1)
  loading.value = true
  streaming.value = true

  // 重置思考状态
  currentThinkingLabel.value = ''
  currentThinkingNode.value = ''
  thinkingSteps.value = []

  const aiMsg: ChatMessage = {
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
    internalSteps: [],
    isStreaming: true,
  }
  messages.value.push(aiMsg)

  await nextTick()
  scrollToBottom()

  try {
    // 构建对话历史（重新生成时也要带上之前的上下文）
    const regenHistory = messages.value
      .filter(m => m.role === 'user' || (m.role === 'assistant' && m.content))
      .slice(-12, -2)
      .map(m => ({ role: m.role, content: m.content }))

    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: userMsg.content,
        session_id: sessionId.value || undefined,
        history: regenHistory,
        model: selectedModel.value,
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    if (!res.body) throw new Error('响应体为空')

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))

          if (data.type === 'thinking') {
            currentThinkingLabel.value = data.label || '处理中...'
            currentThinkingNode.value = data.node || ''
            thinkingSteps.value.push({ node: data.node, label: data.label || '处理中...', status: 'processing' })
            await nextTick()
            scrollToBottom()
          }

          if (data.type === 'message' && data.content) {
            currentThinkingLabel.value = ''
            currentThinkingNode.value = ''
            if (aiMsg.content) {
              aiMsg.content += '\n\n' + data.content
            } else {
              aiMsg.content = data.content
            }
            await nextTick()
            scrollToBottom()
          }

          // 流式消息：逐 token 推送
          if (data.type === 'message_start') {
            currentThinkingLabel.value = ''
            currentThinkingNode.value = ''
            aiMsg.content = ''
            await nextTick()
            scrollToBottom()
          }

          if (data.type === 'message_delta' && data.content) {
            aiMsg.content += data.content
            await nextTick()
            scrollToBottom()
          }

          if (data.type === 'message_end' && data.content) {
            aiMsg.content = data.content
            await nextTick()
            scrollToBottom()
          }

          if (data.type === 'done') {
            currentThinkingLabel.value = ''
            currentThinkingNode.value = ''
            if (data.session_id) {
              sessionId.value = data.session_id
              aiMsg.sessionId = data.session_id
              // 持久化到 localStorage，供评估中心自动获取
              localStorage.setItem('edu_session_id', data.session_id)
            }
            if (data.internal_steps) {
              aiMsg.internalSteps = data.internal_steps
            }
          }

          if (data.type === 'error') {
            currentThinkingLabel.value = ''
            currentThinkingNode.value = ''
            error.value = data.message || '工作流执行失败'
          }
        } catch {
        }
      }
    }
  } catch (e) {
    currentThinkingLabel.value = ''
    currentThinkingNode.value = ''
    if (!aiMsg.content) {
      aiMsg.content = '重新生成失败，请稍后重试。'
    }
    error.value = e instanceof Error ? e.message : '重新生成失败'
  } finally {
    loading.value = false
    streaming.value = false
    aiMsg.isStreaming = false
    aiMsg.renderedHtml = renderMarkdown(aiMsg.content)
    await nextTick()
    scrollToBottom()
    await renderPendingMermaidBlocks()
    trackBehavior('regenerate', { question: userMsg.content.slice(0, 100) })
  }
}

async function copyMessage(msg: ChatMessage) {
  const text = getRawContent(msg)
  try {
    await navigator.clipboard.writeText(text)
    actionFeedback.value = '已复制'
    setTimeout(() => { actionFeedback.value = '' }, 2000)
  } catch {
    actionFeedback.value = '复制失败'
    setTimeout(() => { actionFeedback.value = '' }, 2000)
  }
}

function toggleLike(msg: ChatMessage) {
  msg.liked = !msg.liked
  actionFeedback.value = msg.liked ? '感谢反馈 👍' : ''
  setTimeout(() => { actionFeedback.value = '' }, 1500)
}

function copySessionId() {
  if (sessionId.value) {
    navigator.clipboard.writeText(sessionId.value).then(() => {
      actionFeedback.value = '会话 ID 已复制'
      setTimeout(() => { actionFeedback.value = '' }, 2000)
    })
  }
}

function clearChat() {
  messages.value = []
  sessionId.value = ''
  localStorage.removeItem('edu_session_id')
  error.value = ''
  streaming.value = false
}

function scrollToBottom() {
  nextTick(() => {
    const container = document.getElementById('chat-messages')
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  })
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function formatTime(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const quickPrompts = [
  { icon: '💡', text: 'Python for循环怎么用？' },
  { icon: '📖', text: '解释一下递归算法的原理' },
  { icon: '🔍', text: '帮我梳理机器学习的学习路线' },
  { icon: '✍️', text: '写一个简单的排序算法代码' },
]

function useQuickPrompt(prompt: string) {
  message.value = prompt
  sendMessage()
}

async function handleFileUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const ext = file.name.split('.').pop()?.toLowerCase()
  if (!ext || !['md', 'txt', 'pdf', 'docx'].includes(ext)) {
    uploadMsg.value = '仅支持 MD / TXT / PDF / DOCX 格式'
    setTimeout(() => { uploadMsg.value = '' }, 3000)
    return
  }

  uploadingFile.value = true
  uploadMsg.value = ''

  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('session_id', sessionId.value || '')

    const res = await fetch('/api/chat/upload-file', {
      method: 'POST',
      body: formData,
    })
    const result = await res.json()

    if (result.status === 'ok') {
      uploadMsg.value = `✅ ${result.message}`
      const sysMsg: ChatMessage = {
        role: 'assistant',
        content: `📄 已上传并分析文件 **${file.name}**\n\n${result.message}。你现在可以针对文件内容向我提问了。`,
        timestamp: Date.now(),
      }
      messages.value.push(sysMsg)
      await nextTick()
      scrollToBottom()
    } else {
      uploadMsg.value = `❌ 上传失败: ${result.message}`
    }
  } catch (e) {
    uploadMsg.value = '上传失败，请检查网络连接'
  } finally {
    uploadingFile.value = false
    input.value = ''
    setTimeout(() => { uploadMsg.value = '' }, 5000)
  }
}

function triggerFileUpload() {
  fileInputRef.value?.click()
}

async function startRecording() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    actionFeedback.value = '您的浏览器不支持录音功能'
    setTimeout(() => { actionFeedback.value = '' }, 2000)
    return
  }

  try {
    activeRecorder = await createPcmWavRecorder()
    isRecording.value = true
    recordingDuration.value = 0

    recordingTimer = setInterval(() => {
      recordingDuration.value++
      if (recordingDuration.value >= 60) {
        stopRecording()
      }
    }, 1000)
  } catch (e) {
    actionFeedback.value = '无法访问麦克风，请检查权限设置'
    setTimeout(() => { actionFeedback.value = '' }, 3000)
  }
}

async function stopRecording() {
  isRecording.value = false
  if (recordingTimer) {
    clearInterval(recordingTimer)
    recordingTimer = null
  }

  const recorder = activeRecorder
  activeRecorder = null
  if (!recorder) return

  try {
    const audioBlob = await recorder.stop()
    if (audioBlob.size === 0) {
      actionFeedback.value = '未录制到语音内容'
      setTimeout(() => { actionFeedback.value = '' }, 2000)
      return
    }
    await sendAudioForASR(audioBlob)
  } catch (e) {
    actionFeedback.value = e instanceof Error ? e.message : '语音识别失败，请重试'
    setTimeout(() => { actionFeedback.value = '' }, 3000)
  }
}

async function sendAudioForASR(audioBlob: Blob) {
  try {
    const formData = new FormData()
    formData.append('audio', audioBlob, 'recording.wav')
    formData.append('format', 'wav')

    const res = await fetch('/api/voice/asr', {
      method: 'POST',
      body: formData,
    })

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      actionFeedback.value = errData.detail || '语音识别服务未配置，请检查讯飞ASR密钥'
      setTimeout(() => { actionFeedback.value = '' }, 3000)
      return
    }

    const data = await res.json()
    const text = data.text || ''
    if (text) {
      message.value = message.value ? message.value + text : text
      actionFeedback.value = '已识别语音'
      setTimeout(() => { actionFeedback.value = '' }, 1500)
    } else {
      actionFeedback.value = '未识别到语音内容'
      setTimeout(() => { actionFeedback.value = '' }, 2000)
    }
  } catch (e) {
    actionFeedback.value = '语音识别失败，请检查网络连接'
    setTimeout(() => { actionFeedback.value = '' }, 3000)
  }
}

function toggleRecording() {
  if (isRecording.value) {
    stopRecording()
  } else {
    startRecording()
  }
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

watch(
  () => messages.value.length,
  () => scrollToBottom(),
)

onMounted(() => {
  // 恢复上次的会话 ID
  const storedSessionId = localStorage.getItem('edu_session_id')
  if (storedSessionId) {
    sessionId.value = storedSessionId
  }

  mermaid.initialize({
    startOnLoad: false,
    theme: 'default',
    fontFamily: 'inherit',
    flowchart: { htmlLabels: true, curve: 'basis' },
    securityLevel: 'loose',
  })

  // 加载可用模型列表和连接状态
  fetchModels()
  checkModelStatus()

  // 每 60 秒检查一次 AI 模型连接状态
  statusCheckTimer = setInterval(() => {
    if (!loading.value) {
      checkModelStatus()
    }
  }, 60000)
})

onBeforeUnmount(() => {
  if (activeRecorder) activeRecorder.cancel().catch(() => {})
  if (recordingTimer) {
    clearInterval(recordingTimer)
  }
  if (statusCheckTimer) {
    clearInterval(statusCheckTimer)
  }
})
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-140px)]">
    <!-- Toast -->
    <transition name="toast">
      <div
        v-if="actionFeedback"
        class="fixed top-20 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-xl bg-surface-800 text-white text-sm font-medium shadow-lg"
      >
        {{ actionFeedback }}
      </div>
    </transition>

    <!-- 系统状态栏：AI 模型连接状态 -->
    <div class="flex items-center justify-between px-3 py-1.5 rounded-xl bg-surface-50 border border-surface-100 mb-2 text-xs">
      <div class="flex items-center gap-2">
        <span class="relative flex h-2 w-2">
          <span class="absolute inline-flex h-full w-full rounded-full opacity-75" :class="getStatusColor()" />
          <span class="relative inline-flex rounded-full h-2 w-2" :class="getStatusColor()" />
        </span>
        <!-- 模型名称标签 -->
        <span class="font-medium text-surface-600">{{ modelStatus.model_label || getSelectedModelLabel() }}</span>
        <!-- 连接状态文本 -->
        <span class="text-surface-400">{{ getStatusText() }}</span>
        <!-- 延迟显示 -->
        <span v-if="modelStatus.latency_ms" class="text-surface-300 font-mono">{{ modelStatus.latency_ms }}ms</span>
        <!-- 兜底模式提示 -->
        <span v-if="modelStatus.fallback_mode && modelStatus.status !== 'checking'" class="px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 border border-amber-200">
          本地模式
        </span>
        <!-- 会话 ID -->
        <span class="flex items-center gap-1 ml-2 border-l border-surface-200 pl-2">
          <span v-if="sessionId" class="text-surface-500 font-mono text-[10px]" :title="'会话 ID：' + sessionId">
            会话: {{ sessionId.slice(0, 8) }}
          </span>
          <span v-else class="text-surface-400 font-mono text-[10px]">
            暂无会话
          </span>
          <button
            v-if="sessionId"
            type="button"
            class="text-surface-400 hover:text-brand-500 transition-colors p-0.5"
            title="复制完整会话 ID"
            @click="copySessionId()"
          >
            <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
            </svg>
          </button>
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

    <!-- 消息区域 -->
    <div
      id="chat-messages"
      class="flex-1 overflow-y-auto chat-scrollbar px-1 space-y-5"
    >
      <!-- 空状态引导 -->
      <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full py-8">
        <div class="w-20 h-20 rounded-2xl bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center text-white text-3xl shadow-xl shadow-brand-400/30 mb-6 animate-scale-in">
          <svg class="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
          </svg>
        </div>
        <h2 class="text-2xl font-bold text-surface-800 mb-2">开始你的学习之旅</h2>
        <p class="text-surface-400 text-sm mb-8 max-w-md text-center">
          我是你的 AI 学习助手，可以帮你解答编程问题、讲解知识点、梳理学习路径。<br />
          支持上传知识文件，也可使用语音输入提问。
        </p>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-lg">
          <button
            v-for="(prompt, idx) in quickPrompts"
            :key="idx"
            type="button"
            class="flex items-center gap-2.5 rounded-xl border border-surface-200 bg-white px-4 py-3 text-sm text-surface-600 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 transition-all duration-200 text-left shadow-sm hover:shadow-md"
            @click="useQuickPrompt(prompt.text)"
          >
            <span class="text-base">{{ prompt.icon }}</span>
            <span>{{ prompt.text }}</span>
          </button>
        </div>
      </div>

      <!-- 消息列表 -->
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="animate-slide-up"
      >
        <!-- 用户消息 -->
        <div v-if="msg.role === 'user'" class="flex justify-end">
          <div class="flex items-end gap-2.5 max-w-[75%]">
            <span class="text-[10px] text-surface-300 mb-1 shrink-0">{{ formatTime(msg.timestamp) }}</span>
            <div class="rounded-2xl rounded-br-md bg-brand-500 text-white px-4 py-2.5 text-sm leading-relaxed shadow-md shadow-brand-500/20">
              {{ msg.content }}
            </div>
            <div class="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center text-white text-xs font-semibold shrink-0 shadow-sm">
              我
            </div>
          </div>
        </div>

        <!-- AI 消息 -->
        <div v-else class="flex justify-start">
          <div class="flex items-start gap-2.5 max-w-[85%]">
            <div class="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-400 to-teal-600 flex items-center justify-center text-white text-xs font-semibold shrink-0 shadow-sm mt-0.5">
              AI
            </div>
            <div class="flex-1 min-w-0">
              <div class="rounded-2xl rounded-bl-md bg-white border border-surface-200 px-4 py-3 shadow-sm">
                <!-- 实时思考过程指示器：仅当前流式消息显示 -->
                <div v-if="msg.isStreaming && loading && streaming && msg.content === '' && (currentThinkingLabel || thinkingSteps.length > 0)" class="py-1">
                  <!-- 思考步骤进度条 -->
                  <div class="space-y-1.5 mb-3">
                    <div
                      v-for="(step, si) in thinkingSteps"
                      :key="si"
                      class="flex items-center gap-2 text-xs"
                    >
                      <!-- 已完成的步骤：绿色勾 -->
                      <template v-if="step.status === 'completed'">
                        <svg class="w-3.5 h-3.5 text-emerald-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
                        </svg>
                        <span class="text-surface-400">{{ step.label }}</span>
                      </template>
                      <!-- 处理中的步骤：旋转动画 -->
                      <template v-else>
                        <svg class="w-3.5 h-3.5 text-brand-500 animate-spin shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                        </svg>
                        <span class="text-brand-600 font-medium">{{ step.label }}</span>
                      </template>
                    </div>
                  </div>
                  <!-- 脉冲骨架 -->
                  <div class="space-y-2 py-1">
                    <div class="skeleton h-3 w-3/4" />
                    <div class="skeleton h-3 w-full" />
                    <div class="skeleton h-3 w-2/3" />
                  </div>
                </div>

                <!-- 加载骨架屏（仅当前流式消息且无 thinking 信息时显示） -->
                <div v-else-if="msg.isStreaming && loading && !streaming && msg.content === ''" class="space-y-2.5 py-1">
                  <div class="skeleton h-3 w-3/4" />
                  <div class="skeleton h-3 w-full" />
                  <div class="skeleton h-3 w-5/6" />
                  <div class="skeleton h-3 w-2/3" />
                </div>

                <!-- 流式生成中的 thinking 指示器（仅当前流式消息已有部分内容时显示在顶部） -->
                <div
                  v-if="msg.isStreaming && loading && streaming && currentThinkingLabel && msg.content"
                  class="flex items-center gap-2 text-xs text-brand-500 mb-2 pb-2 border-b border-surface-100"
                >
                  <svg class="w-3.5 h-3.5 animate-spin shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                  </svg>
                  <span>{{ currentThinkingLabel }}</span>
                </div>

                <!-- Markdown 主回复 -->
                <!-- 已完成的消息：使用缓存的 HTML，避免重复渲染闪烁 -->
                <div
                  v-if="!msg.isStreaming && msg.renderedHtml"
                  class="markdown-body text-sm leading-relaxed text-surface-700"
                  v-html="msg.renderedHtml"
                />
                <!-- 正在流式输出的消息：实时渲染 -->
                <div
                  v-else-if="msg.content"
                  class="markdown-body text-sm leading-relaxed text-surface-700"
                  v-html="renderMarkdown(msg.content)"
                />

                <!-- 打字机光标：仅当前正在流式输出的消息显示 -->
                <span
                  v-if="msg.isStreaming && streaming && idx === messages.length - 1"
                  class="inline-block w-1.5 h-4 bg-brand-500 rounded-sm ml-0.5 animate-pulse align-middle"
                />
              </div>

              <!-- Agent 处理详情（折叠） -->
              <div
                v-if="msg.internalSteps && msg.internalSteps.length > 0"
                class="mt-2"
              >
                <details class="group">
                  <summary class="cursor-pointer text-xs text-surface-400 hover:text-surface-500 select-none flex items-center gap-1 py-1">
                    <svg class="w-3 h-3 transition-transform group-open:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                    查看 AI 处理过程（{{ msg.internalSteps.length }} 步）
                  </summary>
                  <div class="mt-1.5 space-y-1.5 pl-4 border-l-2 border-surface-100">
                    <div
                      v-for="(step, si) in msg.internalSteps"
                      :key="si"
                      class="rounded-lg bg-surface-50 border border-surface-100 px-3 py-2"
                    >
                      <div class="flex items-center gap-1.5 mb-1">
                        <span class="text-[10px] font-semibold text-surface-400 uppercase tracking-wider">{{ step.label }}</span>
                      </div>
                      <p class="text-xs text-surface-500 leading-relaxed">{{ step.content }}</p>
                    </div>
                  </div>
                </details>
              </div>

              <!-- 操作按钮 -->
              <div v-if="msg.content && !msg.isStreaming" class="flex items-center gap-1 mt-2 ml-1">
                <button
                  type="button"
                  class="w-7 h-7 rounded-lg flex items-center justify-center text-surface-300 hover:text-brand-500 hover:bg-brand-50 transition-colors"
                  title="复制"
                  @click="copyMessage(msg)"
                >
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                    <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                  </svg>
                </button>
                <button
                  type="button"
                  class="w-7 h-7 rounded-lg flex items-center justify-center transition-colors"
                  :class="msg.liked ? 'text-rose-500 bg-rose-50' : 'text-surface-300 hover:text-rose-400 hover:bg-rose-50'"
                  title="点赞"
                  @click="toggleLike(msg)"
                >
                  <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M14 9V5a3 3 0 00-3-3l-4 9v11h11.28a2 2 0 002-1.7l1.38-9a2 2 0 00-2-2.3H14zM7 22H4a2 2 0 01-2-2v-7a2 2 0 012-2h3"/>
                  </svg>
                </button>
                <button
                  type="button"
                  class="w-7 h-7 rounded-lg flex items-center justify-center text-surface-300 hover:text-brand-500 hover:bg-brand-50 transition-colors"
                  title="重新生成"
                  @click="regenerate(msg, idx)"
                >
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部输入区 -->
    <div class="shrink-0 pt-3">
      <!-- 上传状态提示 -->
      <div v-if="uploadMsg" class="mb-2 text-xs px-1" :class="uploadMsg.startsWith('✅') ? 'text-emerald-600' : 'text-rose-500'">
        {{ uploadMsg }}
      </div>

      <!-- 输入框 -->
      <div class="rounded-2xl border border-surface-200 bg-white shadow-lg shadow-surface-200/50 focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-400/20 transition-all duration-200">
        <textarea
          v-model="message"
          rows="1"
          class="w-full resize-none rounded-t-2xl bg-transparent px-4 pt-3.5 pb-2 text-sm text-surface-700 placeholder-surface-300 focus:outline-none"
          :class="message.length > 0 ? 'min-h-[48px]' : ''"
          placeholder="输入你的问题... (Enter 发送，Shift+Enter 换行)"
          style="min-height: 48px; max-height: 160px;"
          @keydown="handleKeydown"
          @input="(e: Event) => {
            const target = e.target as HTMLTextAreaElement
            target.style.height = 'auto'
            target.style.height = Math.min(target.scrollHeight, 160) + 'px'
          }"
        />
        <div class="flex items-center justify-between px-3 pb-3">
          <div class="flex items-center gap-1.5">
            <!-- 隐藏的文件上传input -->
            <input
              ref="fileInputRef"
              type="file"
              accept=".md,.txt,.pdf,.docx"
              class="hidden"
              @change="handleFileUpload"
            />
            <!-- 文件上传按钮 -->
            <button
              type="button"
              class="w-8 h-8 rounded-lg flex items-center justify-center transition-colors"
              :class="uploadingFile ? 'text-brand-500 bg-brand-50' : 'text-surface-400 hover:text-brand-500 hover:bg-brand-50'"
              title="上传知识文件（MD/PDF/TXT）"
              :disabled="uploadingFile"
              @click="triggerFileUpload"
            >
              <svg v-if="uploadingFile" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
              </svg>
              <svg v-else class="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/>
              </svg>
            </button>
            <!-- 语音输入按钮 -->
            <button
              type="button"
              class="w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200"
              :class="isRecording ? 'text-rose-500 bg-rose-50 animate-pulse' : 'text-surface-400 hover:text-brand-500 hover:bg-brand-50'"
              :title="isRecording ? '点击停止录音' : '语音输入（讯飞ASR）'"
              @click="toggleRecording"
            >
              <svg class="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"/>
              </svg>
            </button>
            <!-- 录音时长 -->
            <span v-if="isRecording" class="text-xs font-mono text-rose-500 tabular-nums">
              {{ formatDuration(recordingDuration) }}
            </span>

            <!-- AI 模型选择器 -->
            <div class="relative ml-1">
              <button
                type="button"
                class="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium transition-all duration-200 border"
                :class="showModelDropdown ? 'bg-brand-50 text-brand-600 border-brand-200' : 'text-surface-500 border-surface-200 hover:text-brand-500 hover:border-brand-200 hover:bg-brand-50'"
                :disabled="loading"
                @click="toggleModelDropdown()"
              >
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5"/>
                </svg>
                <span>{{ getSelectedModelLabel() }}</span>
                <svg class="w-3 h-3 transition-transform" :class="showModelDropdown ? 'rotate-180' : ''" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
                </svg>
              </button>

              <!-- 模型下拉菜单 -->
              <transition name="dropdown">
                <div
                  v-if="showModelDropdown"
                  class="absolute bottom-full left-0 mb-2 w-72 rounded-xl bg-white border border-surface-200 shadow-xl shadow-surface-200/50 overflow-hidden z-30"
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
                  <div class="max-h-64 overflow-y-auto py-1">
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
                          <!-- 删除按钮（仅自定义模型） -->
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
          </div>
          <div class="flex items-center gap-2">
            <button
              v-if="messages.length > 0"
              type="button"
              class="text-xs text-surface-400 hover:text-rose-500 transition-colors px-2 py-1"
              @click="clearChat"
            >
              清空
            </button>
            <button
              type="button"
              class="w-9 h-9 rounded-xl flex items-center justify-center transition-all duration-200"
              :class="message.trim() && !loading ? 'bg-brand-500 text-white shadow-sm shadow-brand-500/25 hover:bg-brand-600' : 'bg-surface-100 text-surface-300 cursor-not-allowed'"
              :disabled="!message.trim() || loading"
              @click="sendMessage"
            >
              <svg v-if="loading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
              </svg>
              <svg v-else class="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- 输入提示 -->
      <p class="text-center text-[10px] text-surface-300 mt-2">
        Enter 发送 · Shift+Enter 换行 · 支持 Markdown/代码高亮 · 可上传文件到知识库 · 语音输入需讯飞ASR
      </p>
    </div>

    <!-- 错误提示 -->
    <transition name="toast">
      <div
        v-if="error"
        class="mt-3 px-4 py-2.5 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-600 flex items-center gap-2 cursor-pointer"
        @click="error = ''"
      >
        <svg class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        {{ error }}
        <span class="text-xs opacity-70">点击关闭</span>
      </div>
    </transition>

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
            <!-- 服务商 -->
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

            <!-- 模型名称 -->
            <div>
              <label class="block text-sm font-medium text-surface-700 mb-1">模型显示名称 *</label>
              <input
                v-model="newModel.label"
                type="text"
                placeholder="如：GPT-4o、DeepSeek-V3"
                class="w-full px-3 py-2 border border-surface-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>

            <!-- 模型标识符 -->
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

            <!-- API 地址 -->
            <div>
              <label class="block text-sm font-medium text-surface-700 mb-1">API 地址</label>
              <input
                v-model="newModel.api_url"
                type="text"
                placeholder="https://api.example.com/v1/chat/completions"
                class="w-full px-3 py-2 border border-surface-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>

            <!-- API Key -->
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

            <!-- 描述 -->
            <div>
              <label class="block text-sm font-medium text-surface-700 mb-1">描述（可选）</label>
              <input
                v-model="newModel.description"
                type="text"
                placeholder="简短描述模型特点"
                class="w-full px-3 py-2 border border-surface-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>

            <!-- 错误提示 -->
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
.toast-enter-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.toast-leave-active {
  transition: all 0.2s ease-in;
}
.toast-enter-from {
  opacity: 0;
  transform: translate(-50%, 8px);
}
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, -4px);
}

.dropdown-enter-active {
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.dropdown-leave-active {
  transition: all 0.15s ease-in;
}
.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(4px) scale(0.97);
}

.modal-enter-active {
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.modal-leave-active {
  transition: all 0.2s ease-in;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from > div,
.modal-leave-to > div {
  transform: scale(0.95) translateY(10px);
}

/* 内联代码 */
:deep(.markdown-body code) {
  background: #f1f5f9;
  color: #1e293b;
  padding: 0.125rem 0.375rem;
  border-radius: 4px;
  font-size: 0.875em;
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
}

:deep(.table-wrapper) {
  overflow-x: auto;
  margin: 0.75rem 0;
}

:deep(.table-wrapper table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

:deep(.table-wrapper th) {
  background: #f8fafc;
  font-weight: 600;
  color: #475569;
  padding: 0.5rem 1rem;
  text-align: left;
  border: 1px solid #e2e8f0;
}

:deep(.table-wrapper td) {
  padding: 0.5rem 1rem;
  border: 1px solid #e2e8f0;
  color: #334155;
}

:deep(.markdown-body ul),
:deep(.markdown-body ol) {
  padding-left: 1.5rem;
  margin: 0.5rem 0;
}

:deep(.markdown-body li) {
  margin: 0.25rem 0;
}

:deep(.markdown-body p) {
  margin: 0.5rem 0;
}

:deep(.markdown-body h1),
:deep(.markdown-body h2),
:deep(.markdown-body h3) {
  margin: 1rem 0 0.5rem;
  font-weight: 600;
  color: #1e293b;
}

:deep(.markdown-body h1) { font-size: 1.25rem; }
:deep(.markdown-body h2) { font-size: 1.1rem; }
:deep(.markdown-body h3) { font-size: 1rem; }

:deep(.markdown-body a) {
  color: #6366f1;
  text-decoration: underline;
}
</style>
