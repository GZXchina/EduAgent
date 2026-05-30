<script setup lang="ts">
/**
 * App.vue - 全局布局重构
 * 
 * 核心改动：
 * 1. 从暗色主题切换为现代浅色 AI SaaS 风格
 * 2. 顶栏：品牌Logo + 功能导航 + 用户头像下拉 + 通知铃铛 + 主题切换预留
 * 3. 左侧边栏：可折叠导航，图标 + 标签，适配桌面/平板
 * 4. 页面切换：平滑过渡动画（fade + slide）
 * 5. 保留全部原有 API 调用逻辑不变
 */
import { onMounted, ref } from 'vue'
import ChatLearning from './components/ChatLearning.vue'
import PersonalizedLearning from './components/PersonalizedLearning.vue'
import ResourceGenerator from './components/ResourceGenerator.vue'
import EvaluationCenter from './components/EvaluationCenter.vue'
import VoiceLearning from './components/VoiceLearning.vue'

type Tab = 'chat' | 'profile' | 'resource' | 'evaluation' | 'voice' | 'rag'

const tab = ref<Tab>('chat')
const sidebarCollapsed = ref(false)
const ragQuery = ref('Python for循环')
const ragResults = ref('')
const healthJson = ref('')
const loading = ref(false)
const error = ref('')

async function fetchHealth() {
  try {
    const res = await fetch('/api/health')
    healthJson.value = JSON.stringify(await res.json(), null, 2)
  } catch (e) {
    console.error('Health check failed:', e)
  }
}

async function ingestRag() {
  error.value = ''
  loading.value = true
  try {
    const res = await fetch('/api/rag/ingest?sync=true', { method: 'POST' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    ragResults.value = JSON.stringify(await res.json(), null, 2)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '入库失败'
  } finally {
    loading.value = false
  }
}

async function queryRag() {
  error.value = ''
  loading.value = true
  try {
    const res = await fetch('/api/rag/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: ragQuery.value, top_k: 4 }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    ragResults.value = JSON.stringify(await res.json(), null, 2)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '检索失败'
  } finally {
    loading.value = false
  }
}

interface NavItem {
  key: Tab
  label: string
  icon: string
  description: string
}

const navItems: NavItem[] = [
  { key: 'chat', label: '对话学习', icon: '💬', description: 'AI 智能对话辅导' },
  { key: 'profile', label: '个性化学习', icon: '👤', description: '学生画像与学习路径' },
  { key: 'resource', label: '资源生成', icon: '📦', description: 'AI 一键生成学习资源' },
  { key: 'evaluation', label: '学习评估', icon: '📊', description: '多维度学习分析报告' },
  { key: 'voice', label: '语音学习', icon: '🎙️', description: '语音合成与识别' },
  { key: 'rag', label: 'RAG知识库', icon: '📚', description: '知识检索增强生成' },
]

onMounted(fetchHealth)
</script>

<template>
  <div class="min-h-screen bg-surface-50 flex">
    <!-- 侧边栏 -->
    <aside
      class="fixed left-0 top-0 z-30 h-full flex flex-col border-r border-surface-200 bg-surface-0 transition-all duration-300 ease-in-out"
      :class="sidebarCollapsed ? 'w-[68px]' : 'w-[240px]'"
    >
      <!-- Logo -->
      <div class="flex items-center h-16 px-4 border-b border-surface-100 shrink-0">
        <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-white font-bold text-sm shadow-lg shadow-brand-500/25 shrink-0">
          E
        </div>
        <transition name="fade">
          <span
            v-if="!sidebarCollapsed"
            class="ml-3 font-bold text-surface-800 text-base whitespace-nowrap"
          >
            EduAgent
          </span>
        </transition>
      </div>

      <!-- 导航菜单 -->
      <nav class="flex-1 overflow-y-auto py-3 px-2 space-y-1">
        <button
          v-for="item in navItems"
          :key="item.key"
          type="button"
          class="w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all duration-200 group relative"
          :class="tab === item.key
            ? 'bg-brand-50 text-brand-700 font-semibold shadow-sm'
            : 'text-surface-500 hover:bg-surface-50 hover:text-surface-700'"
          @click="tab = item.key"
        >
          <span class="text-lg shrink-0">{{ item.icon }}</span>
          <transition name="fade">
            <div v-if="!sidebarCollapsed" class="flex flex-col items-start text-left leading-tight">
              <span class="text-[13px] font-medium">{{ item.label }}</span>
              <span class="text-[10px] text-surface-400 font-normal">{{ item.description }}</span>
            </div>
          </transition>
          <div
            v-if="tab === item.key"
            class="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-8 bg-brand-500 rounded-r-full"
          />
        </button>
      </nav>

      <!-- 折叠按钮 -->
      <div class="p-3 border-t border-surface-100">
        <button
          type="button"
          class="w-full flex items-center justify-center rounded-xl p-2 text-surface-400 hover:text-surface-600 hover:bg-surface-50 transition-colors"
          @click="sidebarCollapsed = !sidebarCollapsed"
          :title="sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'"
        >
          <svg class="w-5 h-5 transition-transform duration-300" :class="sidebarCollapsed ? 'rotate-180' : ''" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </div>
    </aside>

    <!-- 主内容区域 -->
    <div class="flex-1 flex flex-col min-h-screen transition-all duration-300" :class="sidebarCollapsed ? 'ml-[68px]' : 'ml-[240px]'">
      <!-- 顶部导航栏 -->
      <header class="glass-strong sticky top-0 z-20 h-16 shrink-0 border-b border-surface-200/60">
        <div class="h-full flex items-center justify-between px-6">
          <!-- 左侧：当前页面标题 -->
          <div class="flex items-center gap-3">
            <h1 class="text-lg font-bold text-surface-800">
              {{ navItems.find(i => i.key === tab)?.label ?? 'EduAgent' }}
            </h1>
            <span class="text-xs text-surface-400 bg-surface-100 rounded-full px-2.5 py-0.5">
              {{ navItems.find(i => i.key === tab)?.description }}
            </span>
          </div>

          <!-- 右侧：操作区 -->
          <div class="flex items-center gap-2">
            <!-- 主题切换预留 -->
            <button
              type="button"
              class="w-9 h-9 rounded-xl flex items-center justify-center text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors"
              title="主题切换（预留）"
            >
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            </button>

            <!-- 通知铃铛 -->
            <button
              type="button"
              class="relative w-9 h-9 rounded-xl flex items-center justify-center text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors"
              title="消息通知"
            >
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              <span class="absolute top-1.5 right-1.5 w-2 h-2 bg-rose-500 rounded-full ring-2 ring-white" />
            </button>

            <!-- 用户头像 -->
            <div class="relative group">
              <button
                type="button"
                class="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center text-white text-sm font-semibold shadow-md shadow-brand-400/20 hover:shadow-lg hover:shadow-brand-400/30 transition-all"
              >
                U
              </button>
              <div class="absolute right-0 top-full mt-2 w-48 bg-white rounded-xl shadow-xl border border-surface-200 py-1.5 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
                <div class="px-4 py-2 border-b border-surface-100">
                  <p class="text-sm font-semibold text-surface-800">用户</p>
                  <p class="text-xs text-surface-400">user@eduagent.cn</p>
                </div>
                <button class="w-full text-left px-4 py-2 text-sm text-surface-600 hover:bg-surface-50 transition-colors">个人设置</button>
                <button class="w-full text-left px-4 py-2 text-sm text-surface-600 hover:bg-surface-50 transition-colors">学习记录</button>
                <div class="border-t border-surface-100" />
                <button class="w-full text-left px-4 py-2 text-sm text-rose-500 hover:bg-rose-50 transition-colors">退出登录</button>
              </div>
            </div>
          </div>
        </div>
      </header>

      <!-- 主内容 -->
      <main class="flex-1 p-6">
        <transition name="page" mode="out-in">
          <div :key="tab" class="max-w-5xl mx-auto">
            <!-- 系统状态（可折叠） -->
            <details v-if="tab === 'chat'" class="mb-5 rounded-xl border border-surface-200 bg-surface-0/50 overflow-hidden">
              <summary class="cursor-pointer px-4 py-2.5 text-xs font-medium text-surface-400 hover:text-surface-500 select-none">
                系统状态
              </summary>
              <pre
                v-if="healthJson"
                class="overflow-x-auto p-4 text-xs text-surface-500 bg-surface-50 border-t border-surface-100"
              >{{ healthJson }}</pre>
            </details>

            <ChatLearning v-if="tab === 'chat'" />
            <PersonalizedLearning v-else-if="tab === 'profile'" />
            <ResourceGenerator v-else-if="tab === 'resource'" />
            <EvaluationCenter v-else-if="tab === 'evaluation'" />
            <VoiceLearning v-else-if="tab === 'voice'" />
            
            <div v-else-if="tab === 'rag'" class="space-y-5">
              <div class="flex items-center gap-3 mb-2">
                <span class="text-2xl">📚</span>
                <div>
                  <h2 class="text-xl font-bold text-surface-800">RAG 知识库</h2>
                  <p class="text-sm text-surface-400">知识检索增强生成，提升AI回答准确度</p>
                </div>
              </div>
              
              <div class="rounded-2xl border border-surface-200 bg-white p-5 space-y-4">
                <div class="space-y-2">
                  <label class="text-xs font-semibold uppercase tracking-wider text-surface-400">检索问题</label>
                  <input
                    v-model="ragQuery"
                    class="w-full rounded-xl border border-surface-200 bg-surface-50 px-4 py-2.5 text-sm focus:border-brand-400 focus:ring-2 focus:ring-brand-400/20 focus:outline-none transition-all"
                    placeholder="输入检索问题..."
                  />
                </div>
                
                <div class="flex gap-2.5">
                  <button
                    type="button"
                    class="rounded-xl bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-600 disabled:opacity-50 transition-all shadow-sm shadow-emerald-500/20"
                    :disabled="loading"
                    @click="ingestRag"
                  >
                    入库 knowledge/
                  </button>
                  <button
                    type="button"
                    class="rounded-xl bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50 transition-all shadow-sm shadow-brand-500/20"
                    :disabled="loading"
                    @click="queryRag"
                  >
                    检索
                  </button>
                </div>
                
                <pre
                  v-if="ragResults"
                  class="overflow-x-auto rounded-xl border border-surface-200 bg-surface-50 p-4 text-xs text-brand-700"
                >{{ ragResults }}</pre>
              </div>
            </div>
            
            <p v-if="error" class="text-sm text-rose-500 bg-rose-50 rounded-xl px-4 py-3 border border-rose-200">{{ error }}</p>
          </div>
        </transition>
      </main>

      <!-- 底部 -->
      <footer class="border-t border-surface-200 bg-surface-0/50 py-4">
        <div class="max-w-5xl mx-auto px-6 text-center text-xs text-surface-400">
          EduAgent · 基于讯飞星火与多智能体协同的高校个性化学习平台
        </div>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.page-enter-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.page-leave-active {
  transition: all 0.2s ease-in;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>