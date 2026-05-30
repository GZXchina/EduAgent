<script setup lang="ts">
/**
 * ChatLearning.vue - 对话学习模块全面重构
 *
 * 核心改动：
 * 1. 流式打字机效果：API返回后逐字渲染，模拟大模型流式输出体验
 * 2. Markdown渲染：集成marked + highlight.js，支持代码高亮、表格、公式
 * 3. 消息气泡：用户/AI双色区分，AI侧支持点赞/复制/重新生成操作
 * 4. 增强输入框：Enter发送 / Shift+Enter换行，附件图标（UI预留），语音按钮
 * 5. 骨架屏加载状态 + 空状态引导卡片 + 平滑动画
 * 6. 保持原有 POST /api/chat API调用逻辑不变
 *
 * 依赖安装：
 *   npm install marked highlight.js
 */
import { ref, nextTick, watch, onBeforeUnmount } from 'vue'
import { marked, type Tokens } from 'marked'
import hljs from 'highlight.js'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  liked?: boolean
}

const message = ref('')
const sessionId = ref('')
const loading = ref(false)
const streaming = ref(false)
const error = ref('')
const messages = ref<ChatMessage[]>([])

const actionFeedback = ref('')

marked.setOptions({
  breaks: true,
  gfm: true,
})

function configureMarked() {
  const renderer = new marked.Renderer()
  
  renderer.code = function({ text, lang }: Tokens.Code): string {
    const validLang = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
    try {
      const highlighted = hljs.highlight(text, { language: validLang }).value
      return `<div class="code-block-wrapper">
        <div class="code-block-header">
          <span class="code-lang">${validLang}</span>
          <button class="code-copy-btn" data-code="${escapeAttr(text)}" title="复制代码">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          </button>
        </div>
        <pre><code class="hljs language-${validLang}">${highlighted}</code></pre>
      </div>`
    } catch {
      return `<pre><code>${escapeHtml(text)}</code></pre>`
    }
  }
  
  marked.use({ renderer })
}

configureMarked()

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function escapeAttr(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

let typewriterTimer: ReturnType<typeof setInterval> | null = null

function startTypewriter(fullText: string): Promise<void> {
  return new Promise((resolve) => {
    const lastMsg = messages.value[messages.value.length - 1]
    if (!lastMsg || lastMsg.role !== 'assistant') return resolve()
    
    let index = 0
    const charsPerTick = 3
    streaming.value = true
    
    typewriterTimer = setInterval(() => {
      index += charsPerTick
      if (index >= fullText.length) {
        lastMsg.content = fullText
        streaming.value = false
        if (typewriterTimer) clearInterval(typewriterTimer)
        typewriterTimer = null
        resolve()
        return
      }
      lastMsg.content = fullText.slice(0, index)
    }, 10)
  })
}

function stopTypewriter() {
  if (typewriterTimer) {
    clearInterval(typewriterTimer)
    typewriterTimer = null
  }
  streaming.value = false
  const lastMsg = messages.value[messages.value.length - 1]
  if (lastMsg && lastMsg.role === 'assistant') {
    markRawContent(lastMsg)
  }
}

function markRawContent(msg: ChatMessage) {
  const extended = msg as ChatMessage & { _rawContent?: string }
  if (extended._rawContent === undefined) {
    extended._rawContent = msg.content
  }
}

function getRawContent(msg: ChatMessage): string {
  return (msg as ChatMessage & { _rawContent?: string })._rawContent ?? msg.content
}

function renderMarkdown(text: string): string {
  if (!text) return ''
  try {
    return marked.parse(text) as string
  } catch {
    return escapeHtml(text)
  }
}

async function sendMessage() {
  if (!message.value.trim() || loading.value) return
  
  error.value = ''
  loading.value = true
  
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
  }
  messages.value.push(aiMsg)
  
  await nextTick()
  scrollToBottom()
  
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        message: sentMessage, 
        session_id: sessionId.value || undefined 
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    const reply: string = data.reply ?? ''
    if (data.session_id) sessionId.value = data.session_id
    
    markRawContent(aiMsg)
    await startTypewriter(reply)
  } catch (e) {
    aiMsg.content = '请求失败，请稍后重试。'
    error.value = e instanceof Error ? e.message : '请求失败'
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

async function regenerateMessage(msgIndex: number) {
  if (loading.value) return
  
  const aiMsg = messages.value[msgIndex]
  if (!aiMsg || aiMsg.role !== 'assistant') return
  
  const userMsgIndex = msgIndex - 1
  if (userMsgIndex < 0) return
  const userMsg = messages.value[userMsgIndex]
  
  messages.value.splice(msgIndex, 1)
  
  error.value = ''
  loading.value = true
  
  const newAiMsg: ChatMessage = {
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
  }
  messages.value.push(newAiMsg)
  
  await nextTick()
  scrollToBottom()
  
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        message: userMsg.content, 
        session_id: sessionId.value || undefined 
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    const reply: string = data.reply ?? ''
    if (data.session_id) sessionId.value = data.session_id
    
    markRawContent(newAiMsg)
    await startTypewriter(reply)
  } catch (e) {
    newAiMsg.content = '重新生成失败，请稍后重试。'
    error.value = e instanceof Error ? e.message : '重新生成失败'
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
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

function copyCodeBlock(code: string) {
  navigator.clipboard.writeText(code).then(() => {
    actionFeedback.value = '代码已复制'
    setTimeout(() => { actionFeedback.value = '' }, 2000)
  })
}

function clearChat() {
  stopTypewriter()
  messages.value = []
  sessionId.value = ''
  error.value = ''
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

watch(
  () => messages.value.length,
  () => scrollToBottom(),
)

onBeforeUnmount(() => {
  stopTypewriter()
})
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-140px)]">
    <!-- 操作反馈 Toast -->
    <transition name="toast">
      <div
        v-if="actionFeedback"
        class="fixed top-20 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-xl bg-surface-800 text-white text-sm font-medium shadow-lg"
      >
        {{ actionFeedback }}
      </div>
    </transition>

    <!-- 消息列表区域 -->
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
          我是你的 AI 学习助手，可以帮你解答编程问题、讲解知识点、梳理学习路径。试试下面的问题吧！
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
              U
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
                <!-- 骨架屏加载 -->
                <div v-if="loading && !streaming && msg.content === ''" class="space-y-2.5 py-1">
                  <div class="skeleton h-3 w-3/4" />
                  <div class="skeleton h-3 w-full" />
                  <div class="skeleton h-3 w-5/6" />
                  <div class="skeleton h-3 w-2/3" />
                </div>

                <!-- Markdown 渲染 -->
                <div
                  v-else
                  class="markdown-body text-sm leading-relaxed text-surface-700"
                  v-html="renderMarkdown(msg.content)"
                  @click="(e: MouseEvent) => {
                    const target = e.target as HTMLElement
                    if (target.closest('.code-copy-btn')) {
                      const code = (target.closest('.code-copy-btn') as HTMLElement)?.dataset?.code
                      if (code) copyCodeBlock(code)
                    }
                  }"
                />

                <!-- 打字机光标 -->
                <span
                  v-if="streaming && idx === messages.length - 1"
                  class="inline-block w-0.5 h-4 bg-brand-500 ml-0.5 align-text-bottom"
                  style="animation: typewriter-cursor 0.8s infinite"
                />
              </div>

              <!-- 操作栏 -->
              <div
                v-if="!loading || (msg.content && !streaming)"
                class="flex items-center gap-1 mt-1.5 ml-1"
              >
                <button
                  type="button"
                  class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors"
                  :class="{ 'text-brand-500 bg-brand-50': msg.liked }"
                  @click="toggleLike(msg)"
                  title="赞"
                >
                  <svg class="w-3.5 h-3.5" :fill="msg.liked ? 'currentColor' : 'none'" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H7.22a2 2 0 0 0-2 1.7L4 17" />
                  </svg>
                </button>
                <button
                  type="button"
                  class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors"
                  @click="copyMessage(msg)"
                  title="复制"
                >
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2"/>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                  </svg>
                </button>
                <button
                  type="button"
                  class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors"
                  @click="regenerateMessage(idx)"
                  :disabled="loading"
                  title="重新生成"
                >
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </button>
                <span class="text-[10px] text-surface-300 ml-2">{{ formatTime(msg.timestamp) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="shrink-0 pt-3">
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
            <!-- 附件上传（UI预留） -->
            <button
              type="button"
              class="w-8 h-8 rounded-lg flex items-center justify-center text-surface-400 hover:text-brand-500 hover:bg-brand-50 transition-colors"
              title="上传附件（预留）"
            >
              <svg class="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
            </button>
            <!-- 语音输入按钮 -->
            <button
              type="button"
              class="w-8 h-8 rounded-lg flex items-center justify-center text-surface-400 hover:text-brand-500 hover:bg-brand-50 transition-colors"
              title="语音输入（预留）"
            >
              <svg class="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            </button>
          </div>
          <div class="flex items-center gap-2">
            <!-- 清空对话 -->
            <button
              v-if="messages.length > 0"
              type="button"
              class="text-xs text-surface-400 hover:text-rose-500 transition-colors px-2 py-1"
              @click="clearChat"
            >
              清空
            </button>
            <!-- 发送按钮 -->
            <button
              type="button"
              class="rounded-xl bg-brand-500 text-white w-9 h-9 flex items-center justify-center hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm shadow-brand-500/25 hover:shadow-md hover:shadow-brand-500/30"
              :disabled="loading || !message.trim()"
              @click="sendMessage"
            >
              <svg v-if="!loading" class="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
              <svg v-else class="w-4.5 h-4.5 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </div>
      </div>
      <p class="text-[10px] text-surface-300 text-center mt-2">
        EduAgent 可能产生不准确信息，请核实重要内容。
      </p>
    </div>

    <!-- 错误提示 -->
    <transition name="toast">
      <div
        v-if="error"
        class="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-xl bg-rose-500 text-white text-sm font-medium shadow-lg flex items-center gap-2 cursor-pointer"
        @click="error = ''"
      >
        <svg class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        {{ error }}
        <span class="text-xs opacity-70">点击关闭</span>
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

:deep(.code-block-wrapper) {
  margin: 0.75rem 0;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  background: #1e293b;
}

:deep(.code-block-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  background: #334155;
  border-bottom: 1px solid #475569;
}

:deep(.code-lang) {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

:deep(.code-copy-btn) {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.15s;
  background: transparent;
  border: none;
}

:deep(.code-copy-btn:hover) {
  color: #e2e8f0;
  background: #475569;
}

:deep(.code-block-wrapper pre) {
  margin: 0;
  padding: 1rem;
  overflow-x: auto;
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 13px;
  line-height: 1.6;
}

:deep(.code-block-wrapper code) {
  font-family: inherit;
  font-size: inherit;
}
</style>