<script setup lang="ts">
/**
 * EvaluationCenter.vue - 学习评估中心重构
 *
 * 核心改动：
 * 1. SVG 环形进度条：总评分数 + 等级标签，动画填充
 * 2. 知识掌握度柱状图：纯 CSS 实现，带渐变柱 + 百分比标签
 * 3. 优劣结构列表：优势/薄弱/建议三栏分区，图标 + 颜色编码
 * 4. 学习行为信息卡：时长、做题数、资源使用统计
 * 5. 一键导出报告：JSON / Markdown 两种格式
 * 6. 浅色主题适配：卡片 + 分区 + 骨架屏
 * 7. 保持原有 /api/evaluation/report API 调用逻辑不变
 */
import { ref, computed } from 'vue'

interface QuizResult {
  question: string
  correct: boolean
}

interface EvalReport {
  score: number
  level: string
  comment: string
  analysis?: Record<string, unknown>
  strengths: string[]
  weaknesses: string[]
  suggestions: string[]
}

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
  ppt: 2,
  quiz: 3,
  code: 2,
  mindmap: 1,
  video: 1,
})
const report = ref('')
const parsedReport = ref<EvalReport | null>(null)
const loading = ref(false)
const error = ref('')
const activeTab = ref<'input' | 'result'>('input')

const quizCorrect = computed(() => quizResults.value.filter(q => q.correct).length)
const quizTotal = computed(() => quizResults.value.length)

const resourceUsageTotal = computed(() => Object.values(resourceUsage.value).reduce((a, b) => a + b, 0))

const resourceLabels: Record<string, string> = {
  ppt: 'PPT课件', quiz: '题库练习', code: '代码案例', mindmap: '思维导图', video: '视频脚本',
}

const ringCircumference = 2 * Math.PI * 54
const ringOffset = computed(() => {
  const score = parsedReport.value?.score ?? 0
  return ringCircumference - (score / 100) * ringCircumference
})

function levelColor(level: string): string {
  const map: Record<string, string> = {
    '优秀': 'text-emerald-600 bg-emerald-50',
    '良好': 'text-blue-600 bg-blue-50',
    '中等': 'text-amber-600 bg-amber-50',
    '需加强': 'text-rose-600 bg-rose-50',
  }
  return map[level] ?? 'text-surface-600 bg-surface-100'
}

function ringColor(level: string): string {
  const map: Record<string, string> = {
    '优秀': '#10b981', '良好': '#3b82f6', '中等': '#f59e0b', '需加强': '#ef4444',
  }
  return map[level] ?? '#6366f1'
}

function barColor(score: number): string {
  if (score >= 80) return 'from-emerald-400 to-emerald-500'
  if (score >= 60) return 'from-amber-400 to-amber-500'
  return 'from-rose-400 to-rose-500'
}

function tryParseReport(raw: string): EvalReport | null {
  try {
    const data = JSON.parse(raw)
    if (data && typeof data === 'object' && 'score' in data) {
      return {
        score: Number(data.score) || 0,
        level: String(data.level ?? ''),
        comment: String(data.comment ?? ''),
        analysis: data.analysis,
        strengths: Array.isArray(data.strengths) ? data.strengths : [],
        weaknesses: Array.isArray(data.weaknesses) ? data.weaknesses : [],
        suggestions: Array.isArray(data.suggestions) ? data.suggestions : [],
      }
    }
  } catch {
    return null
  }
  return null
}

async function submitEvaluation() {
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
    if (parsedReport.value) activeTab.value = 'result'
  } catch (e) {
    error.value = e instanceof Error ? e.message : '评估失败'
  } finally {
    loading.value = false
  }
}

function addQuizResult() {
  quizResults.value.push({ question: '', correct: false })
}

function removeQuizResult(index: number) {
  quizResults.value.splice(index, 1)
}

function addKnowledgeItem() {
  const key = '新知识点'
  knowledgeMastery.value[key] = 50
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
</script>

<template>
  <div class="space-y-5">
    <div class="flex items-center gap-3">
      <span class="text-2xl">📊</span>
      <div>
        <h2 class="text-xl font-bold text-surface-800">学习评估中心</h2>
        <p class="text-sm text-surface-400">智能评估学习效果，生成个性化分析报告</p>
      </div>
    </div>

    <!-- Tab 切换 -->
    <div class="flex gap-1.5 p-1 bg-surface-100 rounded-xl w-fit">
      <button
        v-for="t in (['input', 'result'] as const)"
        :key="t"
        type="button"
        class="rounded-lg px-5 py-2 text-sm font-medium transition-all duration-200"
        :class="activeTab === t
          ? 'bg-white text-brand-700 shadow-sm'
          : 'text-surface-500 hover:text-surface-700'"
        @click="activeTab = t"
      >
        {{ t === 'input' ? '📝 数据输入' : '📈 评估报告' }}
      </button>
    </div>

    <!-- 输入区 -->
    <div v-if="activeTab === 'input'" class="space-y-5">
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
          <div
            v-for="(q, i) in quizResults"
            :key="i"
            class="flex items-center gap-2.5"
          >
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
          <div
            v-for="(val, key) in knowledgeMastery"
            :key="key"
            class="flex items-center gap-3"
          >
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
          <div
            v-for="(val, key) in resourceUsage"
            :key="key"
            class="text-center"
          >
            <div class="text-2xl font-bold text-surface-800">{{ val }}</div>
            <div class="text-[11px] text-surface-400 mt-1">{{ resourceLabels[key] ?? key }}</div>
          </div>
        </div>
      </div>

      <!-- 提交 -->
      <button
        type="button"
        class="w-full rounded-xl bg-brand-500 px-6 py-3.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50 transition-all shadow-sm shadow-brand-500/25 hover:shadow-md hover:shadow-brand-500/30 flex items-center justify-center gap-2"
        :disabled="loading"
        @click="submitEvaluation"
      >
        <svg v-if="loading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        {{ loading ? '评估中...' : '📊 生成评估报告' }}
      </button>
    </div>

    <!-- 结果区 -->
    <div v-if="activeTab === 'result'">
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

      <!-- 报告内容 -->
      <div v-if="parsedReport" class="space-y-5 animate-slide-up">
        <!-- 评分环形图 -->
        <div class="rounded-2xl border border-surface-200 bg-white p-6 flex flex-col items-center">
          <div class="relative inline-flex items-center justify-center">
            <svg class="w-40 h-40 transform -rotate-90">
              <circle
                cx="80" cy="80" r="54"
                fill="none"
                stroke="#f1f5f9"
                stroke-width="8"
              />
              <circle
                cx="80" cy="80" r="54"
                fill="none"
                :stroke="ringColor(parsedReport.level)"
                stroke-width="8"
                stroke-linecap="round"
                :stroke-dasharray="ringCircumference"
                :stroke-dashoffset="ringOffset"
                class="transition-all duration-1000 ease-out"
              />
            </svg>
            <div class="absolute flex flex-col items-center">
              <span class="text-4xl font-extrabold text-surface-800">{{ parsedReport.score }}</span>
              <span class="text-xs text-surface-400">分</span>
            </div>
          </div>
          <span
            class="mt-3 text-sm font-semibold rounded-full px-4 py-1"
            :class="levelColor(parsedReport.level)"
          >
            {{ parsedReport.level }}
          </span>
          <p class="mt-3 text-sm text-surface-500 text-center max-w-md">{{ parsedReport.comment }}</p>
        </div>

        <!-- 知识掌握柱状图 -->
        <div v-if="Object.keys(knowledgeMastery).length > 0" class="rounded-2xl border border-surface-200 bg-white p-5">
          <h3 class="text-sm font-semibold text-surface-700 mb-4 flex items-center gap-2">
            <span class="w-1.5 h-4 bg-brand-500 rounded-full" />
            知识掌握度
          </h3>
          <div class="space-y-3">
            <div
              v-for="(val, key) in knowledgeMastery"
              :key="key"
              class="flex items-center gap-3"
            >
              <span class="text-sm text-surface-600 w-20 shrink-0 truncate">{{ key }}</span>
              <div class="flex-1 h-6 bg-surface-100 rounded-full overflow-hidden">
                <div
                  class="h-full bg-gradient-to-r rounded-full transition-all duration-700 ease-out flex items-center justify-end pr-2"
                  :class="barColor(val)"
                  :style="{ width: val + '%' }"
                >
                  <span v-if="val > 20" class="text-[10px] font-semibold text-white">{{ val }}%</span>
                </div>
              </div>
              <span v-if="val <= 20" class="text-xs text-surface-400">{{ val }}%</span>
            </div>
          </div>
        </div>

        <!-- 三栏信息 -->
        <div class="grid gap-4 md:grid-cols-3">
          <!-- 优势 -->
          <div class="rounded-2xl border border-surface-200 bg-white p-5">
            <h3 class="text-sm font-semibold text-emerald-600 mb-3 flex items-center gap-2">
              <span class="w-1.5 h-4 bg-emerald-500 rounded-full" />
              ✅ 优势
            </h3>
            <ul v-if="parsedReport.strengths.length > 0" class="space-y-2">
              <li
                v-for="(s, i) in parsedReport.strengths"
                :key="i"
                class="text-sm text-surface-600 pl-3 border-l-2 border-emerald-200"
              >{{ s }}</li>
            </ul>
            <p v-else class="text-sm text-surface-400 italic">暂无数据</p>
          </div>

          <!-- 薄弱点 -->
          <div class="rounded-2xl border border-surface-200 bg-white p-5">
            <h3 class="text-sm font-semibold text-rose-600 mb-3 flex items-center gap-2">
              <span class="w-1.5 h-4 bg-rose-500 rounded-full" />
              ⚠️ 薄弱点
            </h3>
            <ul v-if="parsedReport.weaknesses.length > 0" class="space-y-2">
              <li
                v-for="(w, i) in parsedReport.weaknesses"
                :key="i"
                class="text-sm text-surface-600 pl-3 border-l-2 border-rose-200"
              >{{ w }}</li>
            </ul>
            <p v-else class="text-sm text-surface-400 italic">暂无数据</p>
          </div>

          <!-- 建议 -->
          <div class="rounded-2xl border border-surface-200 bg-white p-5">
            <h3 class="text-sm font-semibold text-brand-600 mb-3 flex items-center gap-2">
              <span class="w-1.5 h-4 bg-brand-500 rounded-full" />
              💡 建议
            </h3>
            <ul v-if="parsedReport.suggestions.length > 0" class="space-y-2">
              <li
                v-for="(s, i) in parsedReport.suggestions"
                :key="i"
                class="text-sm text-surface-600 pl-3 border-l-2 border-brand-200"
              >{{ s }}</li>
            </ul>
            <p v-else class="text-sm text-surface-400 italic">暂无数据</p>
          </div>
        </div>

        <!-- 学习行为摘要 -->
        <div class="rounded-2xl border border-surface-200 bg-white p-5">
          <h3 class="text-sm font-semibold text-surface-700 mb-3 flex items-center gap-2">
            <span class="w-1.5 h-4 bg-surface-400 rounded-full" />
            学习行为摘要
          </h3>
          <div class="grid grid-cols-3 gap-4 text-center">
            <div class="p-3 rounded-xl bg-surface-50">
              <div class="text-lg font-bold text-surface-800">{{ studyDuration }}<span class="text-xs text-surface-400 font-normal"> 分钟</span></div>
              <div class="text-[11px] text-surface-400 mt-1">学习时长</div>
            </div>
            <div class="p-3 rounded-xl bg-surface-50">
              <div class="text-lg font-bold text-surface-800">{{ quizCorrect }}/{{ quizTotal }}</div>
              <div class="text-[11px] text-surface-400 mt-1">测验正确率</div>
            </div>
            <div class="p-3 rounded-xl bg-surface-50">
              <div class="text-lg font-bold text-surface-800">{{ resourceUsageTotal }}</div>
              <div class="text-[11px] text-surface-400 mt-1">资源使用</div>
            </div>
          </div>
        </div>

        <!-- 导出 -->
        <div class="flex gap-3">
          <button
            type="button"
            class="flex-1 rounded-xl border border-surface-200 bg-white px-4 py-2.5 text-sm font-medium text-surface-600 hover:bg-surface-50 transition-colors"
            @click="exportReport('json')"
          >
            📄 导出 JSON
          </button>
          <button
            type="button"
            class="flex-1 rounded-xl border border-surface-200 bg-white px-4 py-2.5 text-sm font-medium text-surface-600 hover:bg-surface-50 transition-colors"
            @click="exportReport('md')"
          >
            📝 导出 Markdown
          </button>
        </div>
      </div>

      <!-- 无报告 -->
      <div v-if="!parsedReport && !loading" class="rounded-2xl border border-surface-200 bg-white p-12 text-center">
        <div class="text-4xl mb-3">📊</div>
        <p class="text-sm text-surface-400">还没有评估报告，请先填写学习数据并生成</p>
        <button
          type="button"
          class="mt-4 text-sm text-brand-500 hover:text-brand-600 font-medium transition-colors"
          @click="activeTab = 'input'"
        >
          前往数据输入 →
        </button>
      </div>

      <!-- Raw JSON -->
      <details v-if="report" class="rounded-xl border border-surface-200 bg-surface-50 overflow-hidden">
        <summary class="cursor-pointer px-4 py-2.5 text-xs font-medium text-surface-400 hover:text-surface-500 select-none">原始 JSON 数据</summary>
        <pre class="overflow-x-auto p-4 text-xs text-surface-500 border-t border-surface-100">{{ report }}</pre>
      </details>
    </div>

    <p v-if="error" class="text-sm text-rose-500 bg-rose-50 rounded-xl px-4 py-3 border border-rose-200 animate-slide-up">{{ error }}</p>
  </div>
</template>

<style scoped>
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