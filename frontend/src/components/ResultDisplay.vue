<script setup lang="ts">
/**
 * ResultDisplay.vue - 评估结果展示组件
 *
 * 展示评估报告的核心可视化：
 * 1. SVG 环形进度条：总评分数 + 等级
 * 2. SVG 雷达图：4维评估指标（正确率/掌握度/利用率/投入度）
 * 3. 知识掌握度柱状图
 * 4. 优势/薄弱/建议三栏信息
 * 5. 学习行为摘要卡片
 * 6. 导出按钮
 */

import { ref, computed } from 'vue'

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

const props = defineProps<{
  parsedReport: EvalReport | null
  report: string
  knowledgeMastery: Record<string, number>
  studyDuration: number
  quizCorrect: number
  quizTotal: number
  resourceUsageTotal: number
  llmSource: string
  ringCircumference: number
  ringOffset: number
  radarDimensions: string[]
  radarScores: number[]
  radarPolygonPoints: string
  radarGridRings: { x: number; y: number }[][]
  radarAxisPoints: { x: number; y: number }[]
  radarLabelOffsets: { x: number; y: number; anchor: string }[]
  radarCenter: number
}>()

const emit = defineEmits<{
  export: [format: 'json' | 'md']
}>()

const RADAR_MAX_SCORE = 100
const RADAR_RADIUS = 100

const radarPoints = computed(() => {
  return props.radarScores.map((score, i) => {
    const angle = (Math.PI * 2 * i) / 4 - Math.PI / 2
    const r = (score / RADAR_MAX_SCORE) * RADAR_RADIUS
    return { x: props.radarCenter + r * Math.cos(angle), y: props.radarCenter + r * Math.sin(angle) }
  })
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

const profileUpdating = ref(false)
const profileUpdateMsg = ref('')
const profileUpdateSuccess = ref(false)

async function updateProfile() {
  if (!props.parsedReport) return
  profileUpdating.value = true
  profileUpdateMsg.value = ''
  try {
    const res = await fetch('/api/evaluation/profile-update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        student_profile: {},
        report: {
          score: props.parsedReport.score,
          level: props.parsedReport.level,
          comment: props.parsedReport.comment,
          analysis: props.parsedReport.analysis || {},
          strengths: props.parsedReport.strengths,
          weaknesses: props.parsedReport.weaknesses,
          suggestions: props.parsedReport.suggestions,
        },
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    await res.json()
    profileUpdateSuccess.value = true
    profileUpdateMsg.value = '画像已更新！学习路径和资源推荐将根据最新评估结果动态调整'
    localStorage.setItem('edu_last_evaluation', JSON.stringify(props.parsedReport))
  } catch (e) {
    profileUpdateSuccess.value = false
    profileUpdateMsg.value = e instanceof Error ? e.message : '画像更新失败'
  } finally {
    profileUpdating.value = false
  }
}
</script>

<template>
  <div v-if="parsedReport" class="space-y-5 animate-slide-up">
    <!-- 评分环形图 + 雷达图 并排 -->
    <div class="grid gap-5 md:grid-cols-2">
      <!-- 环形图 -->
      <div class="rounded-2xl border border-surface-200 bg-white p-6 flex flex-col items-center justify-center">
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
        <p class="mt-3 text-sm text-surface-500 text-center max-w-xs">{{ parsedReport.comment }}</p>
        <span v-if="llmSource" class="mt-2 text-[10px] text-surface-300">
          评估引擎：{{ llmSource }}
        </span>
      </div>

      <!-- 雷达图 -->
      <div class="rounded-2xl border border-surface-200 bg-white p-5 flex flex-col items-center">
        <h3 class="text-sm font-semibold text-surface-700 mb-3 self-start flex items-center gap-2">
          <span class="w-1.5 h-4 bg-violet-500 rounded-full" />
          多维度评估雷达图
        </h3>
        <div class="flex justify-center w-full">
          <svg :viewBox="'0 0 240 240'" class="w-full max-w-[240px]">
            <!-- 网格环 -->
            <polygon
              v-for="(ring, ri) in radarGridRings"
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
              v-for="(_p, i) in radarAxisPoints"
              :key="'dot-' + i"
              :cx="radarPoints[i]?.x ?? 0"
              :cy="radarPoints[i]?.y ?? 0"
              r="4"
              fill="white"
              stroke="#6366f1"
              stroke-width="2"
            />
            <!-- 标签 -->
            <text
              v-for="(label, i) in radarDimensions"
              :key="'label-' + i"
              :x="radarLabelOffsets[i]?.x.toFixed(1) ?? 0"
              :y="radarLabelOffsets[i]?.y.toFixed(1) ?? 0"
              :text-anchor="radarLabelOffsets[i]?.anchor ?? 'middle'"
              fill="#64748b"
              font-size="11"
            >{{ label }}</text>
            <!-- 分数 -->
            <text
              v-for="(score, i) in radarScores"
              :key="'radar-score-' + i"
              :x="(radarPoints[i]?.x ?? radarCenter) + (i === 0 ? 0 : i === 2 ? 0 : i < 2 ? 8 : -8)"
              :y="(radarPoints[i]?.y ?? radarCenter) + (i === 0 ? -8 : i === 2 ? 12 : 4)"
              text-anchor="middle"
              fill="#6366f1"
              font-size="10"
              font-weight="bold"
            >{{ score.toFixed(0) }}</text>
          </svg>
        </div>
      </div>
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
        @click="emit('export', 'json')"
      >
        📄 导出 JSON
      </button>
      <button
        type="button"
        class="flex-1 rounded-xl border border-surface-200 bg-white px-4 py-2.5 text-sm font-medium text-surface-600 hover:bg-surface-50 transition-colors"
        @click="emit('export', 'md')"
      >
        📝 导出 Markdown
      </button>
    </div>

    <!-- 评估→画像联动 -->
    <div class="rounded-2xl border-2 border-brand-100 bg-gradient-to-r from-brand-50 to-white p-4">
      <div class="flex items-center gap-3">
        <span class="text-xl">🔄</span>
        <div class="flex-1">
          <p class="text-sm font-medium text-surface-700">评估→画像联动</p>
          <p class="text-xs text-surface-400 mt-0.5">将评估结果同步到学生画像，动态调整学习路径和资源推荐策略</p>
        </div>
        <button
          type="button"
          class="shrink-0 rounded-xl bg-brand-500 px-4 py-2 text-xs font-semibold text-white hover:bg-brand-600 transition-all shadow-sm shadow-brand-500/25"
          @click="updateProfile"
          :disabled="profileUpdating"
        >
          {{ profileUpdating ? '同步中...' : '🔄 更新画像' }}
        </button>
      </div>
      <p v-if="profileUpdateMsg" class="mt-2 text-xs" :class="profileUpdateSuccess ? 'text-emerald-600' : 'text-rose-500'">
        {{ profileUpdateMsg }}
      </p>
    </div>

    <!-- Raw JSON -->
    <details v-if="report" class="rounded-xl border border-surface-200 bg-surface-50 overflow-hidden">
      <summary class="cursor-pointer px-4 py-2.5 text-xs font-medium text-surface-400 hover:text-surface-500 select-none">原始 JSON 数据</summary>
      <pre class="overflow-x-auto p-4 text-xs text-surface-500 border-t border-surface-100">{{ report }}</pre>
    </details>
  </div>

  <div v-else class="rounded-2xl border border-surface-200 bg-white p-12 text-center">
    <div class="text-4xl mb-3">📊</div>
    <p class="text-sm text-surface-400">还没有评估报告，请先填写学习数据并生成</p>
  </div>
</template>