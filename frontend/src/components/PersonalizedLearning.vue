<script setup lang="ts">
/**
 * PersonalizedLearning.vue - 个性化学习中心重构
 *
 * 核心改动：
 * 1. SVG 雷达图：将 student_profile 6 个维度可视化映射到六边形雷达图
 * 2. 标签云：从画像字段提取关键词，彩色标签 + 尺寸权重展示
 * 3. 时间轴学习路径：解析后端回复，渲染为步骤条组件，三色状态区分
 * 4. 浅色主题全面适配：圆角卡片 + 微阴影 + 渐变图标
 * 5. 保持原有 /api/profile/analyze 和 /api/chat API 调用逻辑不变
 */

import { ref, computed, nextTick } from 'vue'

const message = ref('我是计算机专业学生，想备战蓝桥杯，初学Python，喜欢看图解，每天1小时，循环不太会')
const sessionId = ref('')
const profileJson = ref('')
const learningPathText = ref('')
const loading = ref(false)
const error = ref('')
const activeTab = ref<'profile' | 'path'>('profile')

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

const parsedProfile = ref<ProfileData | null>(null)

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

interface TimelineStep {
  week: number
  title: string
  status: 'done' | 'active' | 'pending'
  topics: string[]
}

const timelineSteps = computed<TimelineStep[]>(() => {
  const text = learningPathText.value
  if (!text) return []
  
  const steps: TimelineStep[] = []
  const weekRegex = /第\s*(\d+)\s*周[：:]\s*(.+?)(?=\n|第\s*\d+\s*周|$)/g
  let match: RegExpExecArray | null
  
  while ((match = weekRegex.exec(text)) !== null) {
    const topics: string[] = []
    const content = match[2]
    const topicMatch = content.match(/学习内容[：:]\s*(.+)/)
    if (topicMatch) {
      topicMatch[1].split(/[,，、]/).forEach(t => {
        const trimmed = t.trim()
        if (trimmed) topics.push(trimmed)
      })
    }
    steps.push({
      week: Number(match[1]),
      title: content.split(/[：:]|\n/)[0]?.trim() ?? `第${match[1]}周`,
      status: steps.length === 0 ? 'active' : 'pending',
      topics: topics.length > 0 ? topics : [content.slice(0, 40) + (content.length > 40 ? '...' : '')],
    })
  }
  
  if (steps.length === 0) {
    const lines = text.split('\n').filter(l => l.trim())
    lines.forEach((line, i) => {
      steps.push({
        week: i + 1,
        title: line.slice(0, 50),
        status: i === 0 ? 'active' : 'pending',
        topics: [line.slice(0, 80)],
      })
    })
  }
  
  if (steps.length > 0) {
    steps[0].status = 'done'
    if (steps.length > 1) steps[1].status = 'active'
  }
  
  return steps
})

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
  } catch (e) {
    error.value = e instanceof Error ? e.message : '画像分析失败'
  } finally {
    loading.value = false
  }
}

async function generatePath() {
  error.value = ''
  learningPathText.value = ''
  loading.value = true
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: '请根据我的画像生成学习路径',
        session_id: sessionId.value || undefined,
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (data.session_id) sessionId.value = data.session_id
    learningPathText.value = data.reply ?? ''
    await nextTick()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '路径生成失败'
  } finally {
    loading.value = false
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

      <!-- 时间轴 -->
      <div v-if="timelineSteps.length > 0" class="rounded-2xl border border-surface-200 bg-white p-6 animate-slide-up">
        <h3 class="text-sm font-semibold text-surface-700 mb-6 flex items-center gap-2">
          <span class="w-1.5 h-4 bg-brand-500 rounded-full" />
          学习进度时间轴
        </h3>
        <div class="relative">
          <div class="space-y-0">
            <div
              v-for="(step, i) in timelineSteps"
              :key="i"
              class="relative flex gap-4 pb-8 last:pb-0"
            >
              <!-- 竖线 -->
              <div class="flex flex-col items-center shrink-0">
                <div
                  class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all"
                  :class="{
                    'bg-emerald-500 text-white shadow-md shadow-emerald-500/25': step.status === 'done',
                    'bg-brand-500 text-white shadow-md shadow-brand-500/25 ring-4 ring-brand-100': step.status === 'active',
                    'bg-surface-200 text-surface-400': step.status === 'pending',
                  }"
                >
                  <svg v-if="step.status === 'done'" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                  <span v-else>{{ step.week }}</span>
                </div>
                <div
                  v-if="i < timelineSteps.length - 1"
                  class="w-0.5 flex-1 min-h-[24px]"
                  :class="step.status === 'done' ? 'bg-emerald-300' : 'bg-surface-200'"
                />
              </div>
              <!-- 内容 -->
              <div class="flex-1 min-w-0 pt-1.5">
                <div class="flex items-center gap-2 mb-1.5">
                  <h4 class="text-sm font-semibold text-surface-800">{{ step.title }}</h4>
                  <span
                    class="text-[10px] font-medium rounded-full px-2 py-0.5"
                    :class="{
                      'bg-emerald-50 text-emerald-600': step.status === 'done',
                      'bg-brand-50 text-brand-600': step.status === 'active',
                      'bg-surface-100 text-surface-400': step.status === 'pending',
                    }"
                  >
                    {{ step.status === 'done' ? '已完成' : step.status === 'active' ? '进行中' : '未开始' }}
                  </span>
                </div>
                <div class="flex flex-wrap gap-1.5">
                  <span
                    v-for="(topic, ti) in step.topics.slice(0, 4)"
                    :key="ti"
                    class="text-[11px] text-surface-500 bg-surface-50 rounded-md px-2 py-0.5 border border-surface-100"
                  >{{ topic }}</span>
                  <span v-if="step.topics.length > 4" class="text-[11px] text-surface-400">+{{ step.topics.length - 4 }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 原文 -->
      <details v-if="learningPathText" class="rounded-xl border border-surface-200 bg-surface-50 overflow-hidden">
        <summary class="cursor-pointer px-4 py-2.5 text-xs font-medium text-surface-400 hover:text-surface-500 select-none">路径原文</summary>
        <div class="whitespace-pre-wrap p-4 text-sm text-surface-600 border-t border-surface-100 leading-relaxed">{{ learningPathText }}</div>
      </details>
    </div>

    <p v-if="error" class="text-sm text-rose-500 bg-rose-50 rounded-xl px-4 py-3 border border-rose-200 animate-slide-up">{{ error }}</p>
  </div>
</template>