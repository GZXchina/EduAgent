<script setup lang="ts">
/**
 * VideoPlayer.vue - AI教学视频播放器
 *
 * 核心功能：
 * 1. 场景卡片动画切换（滑动/淡入效果）
 * 2. 同步TTS音频旁白播放（逐场景自动推进）
 * 3. Canvas录制导出视频（MediaRecorder + WebM）
 * 4. 播放控制：播放/暂停、上一页/下一页、进度条
 * 5. 浅色主题适配 + 加载态 + 错误态
 */

import { ref, computed, onBeforeUnmount } from 'vue'

interface SceneData {
  scene_number: number
  duration: string
  content: string
  visual_description: string
  audio_notes: string | null
  audio_base64: string | null
  audio_mime: string
}

const props = defineProps<{
  topic: string
  totalDuration: string
  scenes: SceneData[]
  suggestions: string[]
  ttsAvailable: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const currentSceneIndex = ref(0)
const isPlaying = ref(false)
const audioPlaying = ref(false)
const transitionDirection = ref<'next' | 'prev'>('next')
const transitionKey = ref(0)
const isDownloading = ref(false)
const downloadProgress = ref(0)

const currentScene = computed(() => props.scenes[currentSceneIndex.value] ?? null)
const totalScenes = computed(() => props.scenes.length)
const progressPercent = computed(() => ((currentSceneIndex.value + 1) / totalScenes.value) * 100)
const hasAudio = computed(() => props.ttsAvailable && props.scenes.some(s => s.audio_base64))
const hasNext = computed(() => currentSceneIndex.value < totalScenes.value - 1)
const hasPrev = computed(() => currentSceneIndex.value > 0)

let audioElement: HTMLAudioElement | null = null
let mediaRecorder: MediaRecorder | null = null
let recordedChunks: Blob[] = []
let sceneSwitchTimer: ReturnType<typeof setTimeout> | null = null

const sceneTransitionClass = computed(() => {
  return transitionDirection.value === 'next'
    ? 'animate-slide-in-right'
    : 'animate-slide-in-left'
})

function goToScene(index: number) {
  if (index < 0 || index >= totalScenes.value) return
  transitionDirection.value = index > currentSceneIndex.value ? 'next' : 'prev'
  currentSceneIndex.value = index
  transitionKey.value++
  stopAudio()
  if (isPlaying.value) {
    playCurrentSceneAudio()
  }
}

function nextScene() {
  if (hasNext.value) goToScene(currentSceneIndex.value + 1)
  else {
    isPlaying.value = false
    stopAudio()
  }
}

function prevScene() {
  if (hasPrev.value) goToScene(currentSceneIndex.value - 1)
}

function stopAudio() {
  if (audioElement) {
    audioElement.pause()
    audioElement.currentTime = 0
    audioElement = null
  }
  audioPlaying.value = false
  if (sceneSwitchTimer) {
    clearTimeout(sceneSwitchTimer)
    sceneSwitchTimer = null
  }
}

function playCurrentSceneAudio() {
  const scene = currentScene.value
  if (!scene?.audio_base64) {
    if (isPlaying.value) {
      sceneSwitchTimer = setTimeout(() => nextScene(), 5000)
    }
    return
  }

  stopAudio()

  const binaryString = atob(scene.audio_base64)
  const bytes = new Uint8Array(binaryString.length)
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i)
  }
  const blob = new Blob([bytes], { type: scene.audio_mime })
  const url = URL.createObjectURL(blob)

  audioElement = new Audio(url)
  audioElement.onloadeddata = () => {
    audioPlaying.value = true
    audioElement?.play().catch(() => {})
  }
  audioElement.onended = () => {
    audioPlaying.value = false
    URL.revokeObjectURL(url)
    audioElement = null
    if (isPlaying.value && hasNext.value) {
      sceneSwitchTimer = setTimeout(() => nextScene(), 500)
    } else if (!hasNext.value) {
      isPlaying.value = false
    }
  }
  audioElement.onerror = () => {
    audioPlaying.value = false
    URL.revokeObjectURL(url)
    audioElement = null
  }
}

function togglePlay() {
  isPlaying.value = !isPlaying.value
  if (isPlaying.value) {
    playCurrentSceneAudio()
  } else {
    stopAudio()
  }
}

function getSceneGradient(index: number): string {
  const gradients = [
    'from-brand-500 to-blue-600',
    'from-violet-500 to-purple-600',
    'from-emerald-500 to-teal-600',
    'from-amber-500 to-orange-600',
    'from-rose-500 to-pink-600',
    'from-cyan-500 to-sky-600',
    'from-indigo-500 to-violet-600',
  ]
  return gradients[index % gradients.length]
}

function getSceneEmoji(index: number): string {
  const emojis = ['🎬', '📖', '💡', '🔍', '✏️', '🎯', '🏆']
  return emojis[index % emojis.length]
}

async function downloadVideo() {
  if (isDownloading.value) return
  isDownloading.value = true
  downloadProgress.value = 0

  try {
    const videoCanvas = document.createElement('canvas')
    videoCanvas.width = 1280
    videoCanvas.height = 720
    const ctx = videoCanvas.getContext('2d')!

    const stream = videoCanvas.captureStream(30)
    const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
      ? 'video/webm;codecs=vp9'
      : 'video/webm'

    mediaRecorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 2500000 })
    recordedChunks = []

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) recordedChunks.push(e.data)
    }

    mediaRecorder.onstop = () => {
      const blob = new Blob(recordedChunks, { type: mimeType })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${props.topic.replace(/[\/\\:*?"<>|]/g, '_')}.webm`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      isDownloading.value = false
      downloadProgress.value = 100
    }

    mediaRecorder.start()

    for (let i = 0; i < props.scenes.length; i++) {
      const scene = props.scenes[i]
      drawScene(ctx, scene, i)
      downloadProgress.value = Math.round(((i + 1) / props.scenes.length) * 90)

      const audioDuration = await getSceneAudioDuration(scene)
      const displayDuration = audioDuration > 0 ? audioDuration : 5000

      await sleep(displayDuration)
    }

    if (mediaRecorder.state === 'recording') {
      mediaRecorder.stop()
    }
  } catch (e) {
    console.error('视频导出失败:', e)
    isDownloading.value = false
  }
}

function drawScene(ctx: CanvasRenderingContext2D, scene: SceneData, index: number) {
  ctx.fillStyle = '#0f172a'
  ctx.fillRect(0, 0, 1280, 720)

  const gradient = ctx.createLinearGradient(0, 0, 1280, 0)
  const colors = [
    ['#3b82f6', '#8b5cf6'],
    ['#8b5cf6', '#ec4899'],
    ['#10b981', '#06b6d4'],
    ['#f59e0b', '#ef4444'],
    ['#f43f5e', '#8b5cf6'],
    ['#06b6d4', '#3b82f6'],
    ['#6366f1', '#8b5cf6'],
  ]
  const [c1, c2] = colors[index % colors.length]
  gradient.addColorStop(0, c1)
  gradient.addColorStop(1, c2)

  ctx.fillStyle = gradient
  ctx.beginPath()
  ctx.roundRect(80, 60, 1120, 8, 4)
  ctx.fill()

  ctx.fillStyle = '#ffffff'
  ctx.font = 'bold 36px "Inter", sans-serif'
  ctx.fillText(`场景 ${scene.scene_number}: ${props.topic}`, 80, 150)

  ctx.font = '24px "Inter", sans-serif'
  ctx.fillStyle = '#e2e8f0'
  const lines = wrapText(ctx, scene.content, 1120)
  lines.forEach((line, i) => {
    ctx.fillText(line, 80, 250 + i * 42)
  })

  ctx.font = 'italic 20px "Inter", sans-serif'
  ctx.fillStyle = '#94a3b8'
  const visualLines = wrapText(ctx, `视觉效果: ${scene.visual_description}`, 1120)
  visualLines.forEach((line, i) => {
    ctx.fillText(line, 80, 500 + i * 36)
  })

  ctx.font = '18px "Inter", sans-serif'
  ctx.fillStyle = '#64748b'
  ctx.fillText(`时长: ${scene.duration}`, 80, 660)
  ctx.fillText(`场景 ${index + 1} / ${props.scenes.length}`, 1080, 660)
}

function wrapText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const lines: string[] = []
  let currentLine = ''
  for (let i = 0; i < text.length; i++) {
    const char = text[i]
    const testLine = currentLine + char
    if (ctx.measureText(testLine).width > maxWidth && currentLine.length > 0) {
      lines.push(currentLine)
      currentLine = char
    } else {
      currentLine = testLine
    }
  }
  if (currentLine) lines.push(currentLine)
  return lines
}

async function getSceneAudioDuration(scene: SceneData): Promise<number> {
  const audioBase64 = scene.audio_base64
  if (!audioBase64) return 0
  return new Promise((resolve) => {
    const binaryString = atob(audioBase64)
    const bytes = new Uint8Array(binaryString.length)
    for (let i = 0; i < binaryString.length; i++) bytes[i] = binaryString.charCodeAt(i)
    const blob = new Blob([bytes], { type: scene.audio_mime })
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    audio.onloadedmetadata = () => {
      URL.revokeObjectURL(url)
      resolve(audio.duration * 1000 + 1000)
    }
    audio.onerror = () => {
      URL.revokeObjectURL(url)
      resolve(5000)
    }
  })
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

onBeforeUnmount(() => {
  stopAudio()
  isPlaying.value = false
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop()
  }
})
</script>

<template>
  <div class="video-player rounded-2xl border border-surface-200 bg-white overflow-hidden">
    <!-- 头部信息栏 -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-surface-100 bg-surface-50/50">
      <div class="flex items-center gap-3 min-w-0">
        <span class="text-xl">🎬</span>
        <div class="min-w-0">
          <h3 class="text-base font-semibold text-surface-800 truncate">{{ topic }}</h3>
          <p class="text-xs text-surface-400">总时长 {{ totalDuration }} · {{ totalScenes }} 个场景</p>
        </div>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <span
          v-if="hasAudio"
          class="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700"
        >
          <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          AI配音
        </span>
        <button
          type="button"
          class="rounded-lg p-2 text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors"
          title="关闭"
          @click="emit('close')"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>

    <!-- 播放区域 -->
    <div class="relative bg-surface-900 overflow-hidden" style="aspect-ratio: 16/9; max-height: 540px;">
      <!-- 场景卡片 -->
      <div
        :key="transitionKey"
        :class="['absolute inset-0 flex flex-col items-center justify-center p-8 text-white', sceneTransitionClass]"
      >
        <!-- 渐变背景 -->
        <div
          :class="['absolute inset-0 bg-gradient-to-br opacity-90 transition-colors duration-700', getSceneGradient(currentSceneIndex)]"
        />

        <!-- 场景编号 -->
        <div class="relative z-10 mb-4">
          <span class="inline-flex items-center gap-2 rounded-full bg-white/20 backdrop-blur px-4 py-1.5 text-sm font-medium">
            {{ getSceneEmoji(currentSceneIndex) }}
            场景 {{ currentScene?.scene_number }} / {{ totalScenes }}
          </span>
        </div>

        <!-- 场景内容 -->
        <p class="relative z-10 text-center text-xl font-medium leading-relaxed max-w-2xl">
          {{ currentScene?.content }}
        </p>

        <!-- 视觉效果描述 -->
        <p class="relative z-10 mt-4 text-center text-sm text-white/70 max-w-xl">
          {{ currentScene?.visual_description }}
        </p>

        <!-- 音频备注 -->
        <p v-if="currentScene?.audio_notes" class="relative z-10 mt-3 text-xs text-white/50 italic">
          🎤 {{ currentScene.audio_notes }}
        </p>

        <!-- 时长标签 -->
        <span class="absolute bottom-4 right-4 z-10 rounded-lg bg-white/15 backdrop-blur px-3 py-1 text-xs text-white/80">
          {{ currentScene?.duration }}
        </span>
      </div>

      <!-- 音频播放指示器 -->
      <div
        v-if="audioPlaying"
        class="absolute bottom-4 left-4 z-20 flex items-center gap-1.5"
      >
        <div class="flex items-end gap-0.5 h-4">
          <span v-for="i in 5" :key="i"
            class="w-1 bg-white/80 rounded-full animate-audio-wave"
            :style="{ animationDelay: `${i * 0.12}s`, height: `${0.3 + i * 0.14}rem` }"
          />
        </div>
        <span class="text-xs text-white/70">AI 旁白中...</span>
      </div>
    </div>

    <!-- 控制栏 -->
    <div class="px-6 py-4 space-y-3">
      <!-- 进度条 -->
      <div class="space-y-1.5">
        <div class="h-1.5 bg-surface-100 rounded-full overflow-hidden">
          <div
            class="h-full bg-gradient-to-r from-brand-400 to-brand-500 rounded-full transition-all duration-500"
            :style="{ width: `${progressPercent}%` }"
          />
        </div>
        <div class="flex justify-between text-xs text-surface-400">
          <span>场景 {{ currentSceneIndex + 1 }} / {{ totalScenes }}</span>
          <span>{{ currentScene?.duration }}</span>
        </div>
      </div>

      <!-- 控制按钮 -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-1">
          <button
            type="button"
            class="rounded-lg p-2 text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            :disabled="!hasPrev"
            title="上一场景"
            @click="prevScene"
          >
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          <button
            type="button"
            class="rounded-xl bg-brand-500 p-3 text-white hover:bg-brand-600 transition-all shadow-sm shadow-brand-500/25"
            title="播放/暂停"
            @click="togglePlay"
          >
            <svg v-if="isPlaying" class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <rect x="6" y="4" width="4" height="16" rx="1" />
              <rect x="14" y="4" width="4" height="16" rx="1" />
            </svg>
            <svg v-else class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
          </button>

          <button
            type="button"
            class="rounded-lg p-2 text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            :disabled="!hasNext"
            title="下一场景"
            @click="nextScene"
          >
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        <!-- 场景导航点 -->
        <div class="flex items-center gap-1.5">
          <button
            v-for="(_, i) in scenes"
            :key="i"
            type="button"
            class="rounded-full transition-all duration-300"
            :class="i === currentSceneIndex
              ? 'w-6 h-2 bg-brand-500'
              : 'w-2 h-2 bg-surface-200 hover:bg-surface-300'"
            :title="`场景 ${i + 1}`"
            @click="goToScene(i)"
          />
        </div>

        <div class="flex items-center gap-1">
          <button
            type="button"
            class="rounded-lg px-3 py-2 text-xs font-medium text-surface-500 hover:text-brand-600 hover:bg-brand-50 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            :disabled="isDownloading"
            @click="downloadVideo"
          >
            <span v-if="isDownloading" class="flex items-center gap-1.5">
              <svg class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {{ downloadProgress }}%
            </span>
            <span v-else class="flex items-center gap-1.5">
              <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              导出视频
            </span>
          </button>
        </div>
      </div>
    </div>

    <!-- 拍摄建议 -->
    <div v-if="suggestions.length" class="px-6 pb-4">
      <div class="rounded-xl bg-amber-50 border border-amber-100 p-3">
        <p class="text-xs font-medium text-amber-700 mb-1.5">💡 拍摄建议</p>
        <ul class="space-y-0.5">
          <li v-for="(s, i) in suggestions" :key="i" class="text-xs text-amber-600">· {{ s }}</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-slide-in-right {
  animation: slideInRight 0.35s ease-out;
}

.animate-slide-in-left {
  animation: slideInLeft 0.35s ease-out;
}

@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translateX(60px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes slideInLeft {
  from {
    opacity: 0;
    transform: translateX(-60px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.animate-audio-wave {
  animation: audioWave 0.8s ease-in-out infinite alternate;
}

@keyframes audioWave {
  from { transform: scaleY(0.4); }
  to { transform: scaleY(1); }
}
</style>