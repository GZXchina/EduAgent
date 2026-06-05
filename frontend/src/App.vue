<script setup lang="ts">
/**
 * App.vue - 全局布局壳
 *
 * 登录后的布局容器：侧边栏 + 顶栏 + 主内容区（router-view）。
 * 登录页不在此布局内，由路由独立渲染。
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from './composables/useAuth'
import HomePage from './pages/HomePage.vue'

const { user, isAdmin, logout } = useAuth()
const route = useRoute()
const router = useRouter()

const sidebarCollapsed = ref(false)

type HomeTab = 'chat' | 'profile' | 'resource' | 'evaluation' | 'voice' | 'rag'

const currentTab = ref<HomeTab>('chat')

interface NavItem {
  key: HomeTab
  label: string
  icon: string
  description: string
}

const homeNavItems: NavItem[] = [
  { key: 'chat', label: '对话学习', icon: '💬', description: 'AI 智能对话辅导' },
  { key: 'profile', label: '个性化学习', icon: '👤', description: '学生画像与学习路径' },
  { key: 'resource', label: '资源生成', icon: '📦', description: 'AI 一键生成学习资源' },
  { key: 'evaluation', label: '学习评估', icon: '📊', description: '多维度学习分析报告' },
  { key: 'voice', label: '语音学习', icon: '🎙️', description: '语音合成与识别' },
  { key: 'rag', label: 'RAG知识库', icon: '📚', description: '知识检索增强生成' },
]

const isHome = computed(() => route.path === '/')
const isLogin = computed(() => route.path === '/login')

const pageTitle = computed(() => {
  if (route.path === '/admin') return '用户管理'
  const item = homeNavItems.find(i => i.key === currentTab.value)
  return item?.label ?? 'EduAgent'
})

const pageDescription = computed(() => {
  if (route.path === '/admin') return '管理系统用户与权限'
  const item = homeNavItems.find(i => i.key === currentTab.value)
  return item?.description ?? ''
})

function goHome() {
  router.push('/')
}

function goAdmin() {
  router.push('/admin')
}
</script>

<template>
  <!-- 登录页直接渲染，不走布局 -->
  <router-view v-if="isLogin" />

  <!-- 登录后的布局壳 -->
  <div v-else class="min-h-screen bg-surface-50 flex">
    <!-- 侧边栏 -->
    <aside
      class="fixed left-0 top-0 z-30 h-full flex flex-col border-r border-surface-200 bg-surface-0 transition-all duration-300 ease-in-out"
      :class="sidebarCollapsed ? 'w-[68px]' : 'w-[240px]'"
    >
      <!-- Logo -->
      <div class="flex items-center h-16 px-4 border-b border-surface-100 shrink-0 cursor-pointer" @click="goHome">
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
        <!-- 主页标签导航 -->
        <template v-if="isHome">
          <button
            v-for="item in homeNavItems"
            :key="item.key"
            type="button"
            class="w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all duration-200 group relative"
            :class="currentTab === item.key
              ? 'bg-brand-50 text-brand-700 font-semibold shadow-sm'
              : 'text-surface-500 hover:bg-surface-50 hover:text-surface-700'"
            @click="currentTab = item.key"
          >
            <span class="text-lg shrink-0">{{ item.icon }}</span>
            <transition name="fade">
              <div v-if="!sidebarCollapsed" class="flex flex-col items-start text-left leading-tight">
                <span class="text-[13px] font-medium">{{ item.label }}</span>
                <span class="text-[10px] text-surface-400 font-normal">{{ item.description }}</span>
              </div>
            </transition>
            <div
              v-if="currentTab === item.key"
              class="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-8 bg-brand-500 rounded-r-full"
            />
          </button>
        </template>

        <!-- 管理员面板导航 -->
        <template v-else>
          <button
            type="button"
            class="w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm bg-brand-50 text-brand-700 font-semibold shadow-sm relative"
          >
            <span class="text-lg shrink-0">👥</span>
            <transition name="fade">
              <div v-if="!sidebarCollapsed" class="flex flex-col items-start text-left leading-tight">
                <span class="text-[13px] font-medium">用户管理</span>
                <span class="text-[10px] text-surface-400 font-normal">管理系统用户与权限</span>
              </div>
            </transition>
          </button>
        </template>
      </nav>

      <!-- 底部：管理员入口 + 折叠按钮 -->
      <div class="p-3 border-t border-surface-100 space-y-2">
        <!-- 管理员入口 -->
        <button
          v-if="isAdmin && isHome"
          type="button"
          class="w-full flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-surface-500 hover:bg-surface-50 hover:text-surface-700 transition-all"
          @click="goAdmin"
          title="用户管理"
        >
          <span class="text-lg shrink-0">⚙️</span>
          <transition name="fade">
            <span v-if="!sidebarCollapsed" class="text-[13px] font-medium">用户管理</span>
          </transition>
        </button>
        <button
          v-if="isAdmin && !isHome"
          type="button"
          class="w-full flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-surface-500 hover:bg-surface-50 hover:text-surface-700 transition-all"
          @click="goHome"
          title="返回首页"
        >
          <span class="text-lg shrink-0">🏠</span>
          <transition name="fade">
            <span v-if="!sidebarCollapsed" class="text-[13px] font-medium">返回首页</span>
          </transition>
        </button>

        <!-- 折叠按钮 -->
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
            <h1 class="text-lg font-bold text-surface-800">{{ pageTitle }}</h1>
            <span class="text-xs text-surface-400 bg-surface-100 rounded-full px-2.5 py-0.5">
              {{ pageDescription }}
            </span>
          </div>

          <!-- 右侧：操作区 -->
          <div class="flex items-center gap-2">
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
                {{ user?.display_name?.charAt(0)?.toUpperCase() || 'U' }}
              </button>
              <div class="absolute right-0 top-full mt-2 w-52 bg-white rounded-xl shadow-xl border border-surface-200 py-1.5 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
                <div class="px-4 py-2 border-b border-surface-100">
                  <p class="text-sm font-semibold text-surface-800">{{ user?.display_name }}</p>
                  <p class="text-xs text-surface-400">{{ user?.role === 'admin' ? '管理员' : '用户' }} · {{ user?.username }}</p>
                </div>
                <div class="border-t border-surface-100" />
                <button
                  class="w-full text-left px-4 py-2 text-sm text-rose-500 hover:bg-rose-50 transition-colors"
                  @click="logout"
                >
                  退出登录
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      <!-- 主内容 -->
      <main class="flex-1 p-6">
        <!-- 主页：传入当前 tab 对应的组件 -->
        <template v-if="isHome">
          <HomePage :current-tab="currentTab" />
        </template>
        <!-- 其他路由 -->
        <router-view v-else />
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
</style>
