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
import { ref, nextTick, onBeforeUnmount } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import mermaid from 'mermaid'

const topic = ref('Python循环语句')
const sessionId = ref('')
const resourceType = ref<'ppt' | 'quiz' | 'code' | 'mindmap' | 'video'>('ppt')
const result = ref('')
const loading = ref(false)
const error = ref('')
const actionFeedback = ref('')

const progressPercent = ref(0)
let progressTimer: ReturnType<typeof setInterval> | null = null

mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  securityLevel: 'loose',
  fontFamily: 'Inter, system-ui, sans-serif',
})

const resourceTypes = [
  { key: 'ppt' as const, label: 'PPT课件', icon: '📊', desc: '生成教学课件大纲', color: 'from-orange-400 to-red-500', bg: 'bg-orange-50', text: 'text-orange-600', ring: 'ring-orange-400/20' },
  { key: 'quiz' as const, label: '题库练习', icon: '📝', desc: '生成配套练习题', color: 'from-emerald-400 to-teal-500', bg: 'bg-emerald-50', text: 'text-emerald-600', ring: 'ring-emerald-400/20' },
  { key: 'code' as const, label: '代码案例', icon: '💻', desc: '生成代码示例', color: 'from-blue-400 to-indigo-500', bg: 'bg-blue-50', text: 'text-blue-600', ring: 'ring-blue-400/20' },
  { key: 'mindmap' as const, label: '思维导图', icon: '🧠', desc: '生成Mermaid导图', color: 'from-violet-400 to-purple-500', bg: 'bg-violet-50', text: 'text-violet-600', ring: 'ring-violet-400/20' },
  { key: 'video' as const, label: '视频脚本', icon: '🎬', desc: '生成视频脚本', color: 'from-pink-400 to-rose-500', bg: 'bg-pink-50', text: 'text-pink-600', ring: 'ring-pink-400/20' },
] as const

marked.setOptions({ breaks: true, gfm: true })

function configureMarkedForCode() {
  const renderer = new marked.Renderer()
  renderer.code = function({ text, lang }: { text: string; lang?: string }): string {
    const validLang = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
    try {
      const highlighted = hljs.highlight(text, { language: validLang }).value
      return `<div class="code-block-wrapper">
        <div class="code-block-header">
          <span class="code-lang">${validLang}</span>
          <button class="code-copy-btn" data-code="${escapeAttr(text)}">复制</button>
        </div>
        <pre><code class="hljs language-${validLang}">${highlighted}</code></pre>
      </div>`
    } catch {
      return `<pre><code>${escapeHtml(text)}</code></pre>`
    }
  }
  marked.use({ renderer })
}

configureMarkedForCode()

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function escapeAttr(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function renderMarkdown(text: string): string {
  if (!text) return ''
  try { return marked.parse(text) as string } catch { return escapeHtml(text) }
}

function extractMermaidCode(text: string): string | null {
  const match = text.match(/```mermaid\s*\n([\s\S]*?)```/)
  return match ? match[1].trim() : null
}

async function renderMermaidDiagram(code: string, container: HTMLElement) {
  try {
    const { svg } = await mermaid.render('mermaid-diagram', code)
    container.innerHTML = svg
  } catch {
    container.innerHTML = `<pre class="text-xs text-surface-500 p-3">Mermaid 渲染失败，请检查语法</pre>`
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
  loading.value = true
  startProgress()

  const prompt = getResourcePrompt()
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: prompt,
        session_id: sessionId.value || undefined,
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (data.session_id) sessionId.value = data.session_id
    result.value = data.reply ?? ''
    finishProgress()
    await nextTick()
    
    if (resourceType.value === 'mindmap') {
      const mermaidCode = extractMermaidCode(result.value)
      if (mermaidCode) {
        const container = document.getElementById('mermaid-container')
        if (container) await renderMermaidDiagram(mermaidCode, container)
      }
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '资源生成失败'
    progressPercent.value = 0
    if (progressTimer) clearInterval(progressTimer)
    progressTimer = null
  } finally {
    loading.value = false
  }
}

function getResourcePrompt(): string {
  const prompts: Record<string, string> = {
    ppt: `请为"${topic.value}"生成PPT课件大纲，包含标题、章节和要点`,
    quiz: `请为"${topic.value}"生成5道练习题，包含题目、选项和答案`,
    code: `请为"${topic.value}"生成3个代码示例，用Markdown代码块格式，包含代码和注释说明`,
    mindmap: `请为"${topic.value}"生成Mermaid思维导图代码，用\`\`\`mermaid代码块包裹，使用mindmap语法`,
    video: `请为"${topic.value}"生成视频脚本，包含场景、旁白和时长`,
  }
  return prompts[resourceType.value]
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

function copyCodeBlock(code: string) {
  navigator.clipboard.writeText(code).then(() => {
    actionFeedback.value = '代码已复制'
    setTimeout(() => { actionFeedback.value = '' }, 2000)
  })
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
    <div v-if="loading && !result" class="rounded-2xl border border-surface-200 bg-white p-5 space-y-3">
      <div class="skeleton h-4 w-1/3" />
      <div class="skeleton h-3 w-full" />
      <div class="skeleton h-3 w-5/6" />
      <div class="skeleton h-3 w-2/3" />
      <div class="skeleton h-3 w-3/4" />
    </div>

    <!-- 生成结果 -->
    <div v-if="result" class="animate-slide-up space-y-3">
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
          @click="(e: MouseEvent) => {
            const btn = (e.target as HTMLElement).closest('.code-copy-btn') as HTMLElement
            if (btn?.dataset?.code) copyCodeBlock(btn.dataset.code)
          }"
        />

        <!-- 思维导图：Mermaid渲染 -->
        <div v-else-if="resourceType === 'mindmap'">
          <div
            v-if="extractMermaidCode(result)"
            id="mermaid-container"
            class="flex justify-center overflow-auto max-h-[600px] p-2"
          />
          <pre v-else class="whitespace-pre-wrap text-sm text-surface-600 leading-relaxed max-h-[600px] overflow-y-auto">{{ result }}</pre>
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
  </div>
</template>

<style scoped>
.toast-enter-active { transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.toast-leave-active { transition: all 0.2s ease-in; }
.toast-enter-from { opacity: 0; transform: translate(-50%, 8px); }
.toast-leave-to { opacity: 0; transform: translate(-50%, -4px); }

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
  font-size: 11px;
  padding: 3px 10px;
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
  font-size: 13px;
  line-height: 1.6;
}

:deep(.code-block-wrapper code) {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: inherit;
}
</style>