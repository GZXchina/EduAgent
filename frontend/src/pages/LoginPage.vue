<script setup lang="ts">
/**
 * LoginPage.vue - 登录/注册页面
 *
 * 左侧品牌展示区，右侧登录/注册表单切换。
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const { login, register } = useAuth()

const isLogin = ref(true)
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const displayName = ref('')
const error = ref('')
const loading = ref(false)

function switchMode() {
  isLogin.value = !isLogin.value
  error.value = ''
  confirmPassword.value = ''
}

async function handleSubmit() {
  error.value = ''

  if (!username.value.trim() || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }

  if (!isLogin.value) {
    if (password.value.length < 6) {
      error.value = '密码至少6位'
      return
    }
    if (password.value !== confirmPassword.value) {
      error.value = '两次密码不一致'
      return
    }
  }

  loading.value = true
  try {
    if (isLogin.value) {
      await login(username.value, password.value)
    } else {
      await register(username.value, password.value, displayName.value || username.value)
    }
    router.push('/')
  } catch (e) {
    error.value = e instanceof Error ? e.message : '操作失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex">
    <!-- 左侧品牌区 -->
    <div class="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-brand-600 via-brand-500 to-indigo-600 relative overflow-hidden">
      <!-- 装饰圆 -->
      <div class="absolute -top-20 -left-20 w-80 h-80 bg-white/10 rounded-full blur-2xl" />
      <div class="absolute bottom-10 right-10 w-64 h-64 bg-white/5 rounded-full blur-3xl" />
      <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-white/5 rounded-full blur-3xl" />

      <div class="relative z-10 flex flex-col justify-center px-16 text-white">
        <div class="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center text-3xl font-bold mb-8 shadow-lg">
          E
        </div>
        <h1 class="text-4xl font-extrabold mb-4 leading-tight">
          EduAgent
        </h1>
        <p class="text-lg text-white/80 mb-8 leading-relaxed">
          基于讯飞星火与多智能体协同的<br />高校个性化学习平台
        </p>
        <div class="space-y-3">
          <div class="flex items-center gap-3 text-white/70 text-sm">
            <span class="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center text-xs">1</span>
            AI 智能对话辅导，随时解答疑惑
          </div>
          <div class="flex items-center gap-3 text-white/70 text-sm">
            <span class="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center text-xs">2</span>
            个性化学习路径，精准推荐资源
          </div>
          <div class="flex items-center gap-3 text-white/70 text-sm">
            <span class="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center text-xs">3</span>
            多维度学习评估，实时跟踪进度
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧表单区 -->
    <div class="flex-1 flex items-center justify-center bg-surface-50 px-6">
      <div class="w-full max-w-md">
        <!-- 移动端 Logo -->
        <div class="lg:hidden flex items-center gap-3 mb-10">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-brand-500/25">
            E
          </div>
          <span class="text-xl font-bold text-surface-800">EduAgent</span>
        </div>

        <h2 class="text-2xl font-bold text-surface-800 mb-1">
          {{ isLogin ? '欢迎回来' : '创建账号' }}
        </h2>
        <p class="text-sm text-surface-400 mb-8">
          {{ isLogin ? '登录以继续学习之旅' : '注册开始使用 EduAgent' }}
        </p>

        <!-- 错误提示 -->
        <div
          v-if="error"
          class="mb-4 rounded-xl bg-rose-50 border border-rose-200 px-4 py-3 text-sm text-rose-600"
        >
          {{ error }}
        </div>

        <form @submit.prevent="handleSubmit" class="space-y-4">
          <div>
            <label class="block text-xs font-semibold uppercase tracking-wider text-surface-400 mb-1.5">用户名</label>
            <input
              v-model="username"
              type="text"
              autocomplete="username"
              class="w-full rounded-xl border border-surface-200 bg-white px-4 py-3 text-sm text-surface-800 placeholder:text-surface-300 focus:border-brand-400 focus:ring-2 focus:ring-brand-400/20 focus:outline-none transition-all"
              placeholder="输入用户名"
            />
          </div>

          <div v-if="!isLogin">
            <label class="block text-xs font-semibold uppercase tracking-wider text-surface-400 mb-1.5">显示名称</label>
            <input
              v-model="displayName"
              type="text"
              class="w-full rounded-xl border border-surface-200 bg-white px-4 py-3 text-sm text-surface-800 placeholder:text-surface-300 focus:border-brand-400 focus:ring-2 focus:ring-brand-400/20 focus:outline-none transition-all"
              placeholder="可选，默认使用用户名"
            />
          </div>

          <div>
            <label class="block text-xs font-semibold uppercase tracking-wider text-surface-400 mb-1.5">密码</label>
            <input
              v-model="password"
              type="password"
              autocomplete="current-password"
              class="w-full rounded-xl border border-surface-200 bg-white px-4 py-3 text-sm text-surface-800 placeholder:text-surface-300 focus:border-brand-400 focus:ring-2 focus:ring-brand-400/20 focus:outline-none transition-all"
              placeholder="输入密码"
            />
          </div>

          <div v-if="!isLogin">
            <label class="block text-xs font-semibold uppercase tracking-wider text-surface-400 mb-1.5">确认密码</label>
            <input
              v-model="confirmPassword"
              type="password"
              autocomplete="new-password"
              class="w-full rounded-xl border border-surface-200 bg-white px-4 py-3 text-sm text-surface-800 placeholder:text-surface-300 focus:border-brand-400 focus:ring-2 focus:ring-brand-400/20 focus:outline-none transition-all"
              placeholder="再次输入密码"
            />
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="w-full rounded-xl bg-gradient-to-r from-brand-500 to-brand-600 py-3 text-sm font-semibold text-white shadow-lg shadow-brand-500/25 hover:shadow-xl hover:shadow-brand-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
          >
            <span v-if="loading" class="inline-flex items-center gap-2">
              <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
              处理中...
            </span>
            <span v-else>{{ isLogin ? '登录' : '注册' }}</span>
          </button>
        </form>

        <div class="mt-6 text-center">
          <button
            type="button"
            class="text-sm text-brand-500 hover:text-brand-700 font-medium transition-colors"
            @click="switchMode"
          >
            {{ isLogin ? '没有账号？立即注册' : '已有账号？去登录' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
