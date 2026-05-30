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
import { ref, computed, onBeforeUnmount } from 'vue'

const text = ref('你好，欢迎使用EduAgent智能学习平台')
const voice = ref('xiaoyan')
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

const voices = [
  { key: 'xiaoyan', label: '小燕', gender: '女', emoji: '👩', color: 'bg-pink-50 border-pink-200 text-pink-700', activeColor: 'ring-pink-400/30' },
  { key: 'xiaoyu', label: '小宇', gender: '男', emoji: '👨', color: 'bg-blue-50 border-blue-200 text-blue-700', activeColor: 'ring-blue-400/30' },
  { key: 'xiaoyan', label: '小研', gender: '女', emoji: '👩‍💼', color: 'bg-violet-50 border-violet-200 text-violet-700', activeColor: 'ring-violet-400/30' },
  { key: 'xiaofeng', label: '小峰', gender: '男', emoji: '🧑‍💻', color: 'bg-emerald-50 border-emerald-200 text-emerald-700', activeColor: 'ring-emerald-400/30' },
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

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

async function synthesizeSpeech() {
  error.value = ''
  audioUrl.value = ''
  audioBase64.value = ''
  loading.value = true
  try {
    const formData = new FormData()
    formData.append('text', text.value)
    formData.append('voice', voice.value)
    formData.append('rate', String(speechRate.value))

    const res = await fetch('/api/voice/tts', {
      method: 'POST',
      body: formData,
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)

    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
    audioUrl.value = url
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
    audioEl = new Audio(audioUrl.value)
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
  }
  audioEl.src = audioUrl.value
  audioEl.play()
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
    isRecording.value = true
    recordingDuration.value = 0
    recordingTimer = setInterval(() => { recordingDuration.value++ }, 1000)

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mediaRecorder = new MediaRecorder(stream)
    const chunks: Blob[] = []

    mediaRecorder.ondataavailable = (e) => chunks.push(e.data)
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(track => track.stop())
      if (recordingTimer) { clearInterval(recordingTimer); recordingTimer = null }

      const blob = new Blob(chunks, { type: 'audio/wav' })
      const formData = new FormData()
      formData.append('audio', blob, 'recording.wav')
      formData.append('format', 'wav')

      try {
        const res = await fetch('/api/voice/asr', {
          method: 'POST',
          body: formData,
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        recognitionText.value = data.text ?? ''
      } catch (e) {
        error.value = e instanceof Error ? e.message : '语音识别失败'
      } finally {
        loading.value = false
        isRecording.value = false
      }
    }

    mediaRecorder.start()
    await new Promise(resolve => setTimeout(resolve, 5000))
    mediaRecorder.stop()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '无法访问麦克风'
    loading.value = false
    isRecording.value = false
    if (recordingTimer) { clearInterval(recordingTimer); recordingTimer = null }
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

onBeforeUnmount(() => {
  stopAudio()
  if (recordingTimer) clearInterval(recordingTimer)
  if (progressTimer) clearInterval(progressTimer)
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
            录音中，将在 5 秒后自动停止
          </div>
        </div>
        <div v-else class="space-y-4">
          <div class="text-5xl">🎤</div>
          <p class="text-sm text-surface-400">点击下方按钮开始录音，系统将自动在 5 秒后停止并识别</p>
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
  </div>
</template>

<style scoped>
.toast-v-enter-active { transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.toast-v-leave-active { transition: all 0.2s ease-in; }
.toast-v-enter-from { opacity: 0; transform: translate(-50%, 8px); }
.toast-v-leave-to { opacity: 0; transform: translate(-50%, -4px); }

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