<script setup lang="ts">
/**
 * AdminPanel.vue - 管理员用户管理面板
 *
 * 展示用户列表，支持角色修改和用户禁用。
 */
import { onMounted, ref } from 'vue'
import { useAuth } from '../composables/useAuth'

const { authFetch } = useAuth()

interface UserItem {
  id: number
  username: string
  display_name: string
  role: string
  is_active: number
  created_at: string
}

const users = ref<UserItem[]>([])
const loading = ref(false)
const error = ref('')
const success = ref('')

async function fetchUsers() {
  loading.value = true
  error.value = ''
  try {
    const res = await authFetch('/api/auth/users')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    users.value = await res.json()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '获取用户列表失败'
  } finally {
    loading.value = false
  }
}

async function toggleRole(user: UserItem) {
  error.value = ''
  success.value = ''
  const newRole = user.role === 'admin' ? 'user' : 'admin'
  try {
    const res = await authFetch(`/api/auth/users/${user.id}/role`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: newRole }),
    })
    if (!res.ok) {
      const detail = await res.json().catch(() => null)
      throw new Error(detail?.detail || `HTTP ${res.status}`)
    }
    success.value = `已将 ${user.username} 角色修改为 ${newRole === 'admin' ? '管理员' : '普通用户'}`
    await fetchUsers()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '修改角色失败'
  }
}

async function disableUser(user: UserItem) {
  error.value = ''
  success.value = ''
  if (!confirm(`确定要禁用用户 ${user.username} 吗？`)) return
  try {
    const res = await authFetch(`/api/auth/users/${user.id}`, { method: 'DELETE' })
    if (!res.ok) {
      const detail = await res.json().catch(() => null)
      throw new Error(detail?.detail || `HTTP ${res.status}`)
    }
    success.value = `已禁用用户 ${user.username}`
    await fetchUsers()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '操作失败'
  }
}

onMounted(fetchUsers)
</script>

<template>
  <div class="max-w-5xl mx-auto space-y-5">
    <div class="flex items-center gap-3 mb-2">
      <span class="text-2xl">👥</span>
      <div>
        <h2 class="text-xl font-bold text-surface-800">用户管理</h2>
        <p class="text-sm text-surface-400">管理系统用户、角色与权限</p>
      </div>
    </div>

    <!-- 提示消息 -->
    <div v-if="success" class="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-600">
      {{ success }}
    </div>
    <div v-if="error" class="rounded-xl bg-rose-50 border border-rose-200 px-4 py-3 text-sm text-rose-600">
      {{ error }}
    </div>

    <!-- 用户列表 -->
    <div class="rounded-2xl border border-surface-200 bg-white overflow-hidden">
      <div class="px-5 py-4 border-b border-surface-100 flex items-center justify-between">
        <span class="text-sm font-semibold text-surface-700">用户列表 ({{ users.length }})</span>
        <button
          type="button"
          class="text-xs text-brand-500 hover:text-brand-700 font-medium transition-colors"
          @click="fetchUsers"
          :disabled="loading"
        >
          刷新
        </button>
      </div>

      <div v-if="loading && !users.length" class="p-8 text-center text-surface-400 text-sm">
        加载中...
      </div>

      <table v-else class="w-full">
        <thead>
          <tr class="border-b border-surface-100 bg-surface-50/50">
            <th class="text-left text-xs font-semibold uppercase tracking-wider text-surface-400 px-5 py-3">用户名</th>
            <th class="text-left text-xs font-semibold uppercase tracking-wider text-surface-400 px-5 py-3">显示名</th>
            <th class="text-left text-xs font-semibold uppercase tracking-wider text-surface-400 px-5 py-3">角色</th>
            <th class="text-left text-xs font-semibold uppercase tracking-wider text-surface-400 px-5 py-3">状态</th>
            <th class="text-left text-xs font-semibold uppercase tracking-wider text-surface-400 px-5 py-3">注册时间</th>
            <th class="text-right text-xs font-semibold uppercase tracking-wider text-surface-400 px-5 py-3">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="u in users"
            :key="u.id"
            class="border-b border-surface-50 hover:bg-surface-50/50 transition-colors"
          >
            <td class="px-5 py-3 text-sm font-medium text-surface-800">{{ u.username }}</td>
            <td class="px-5 py-3 text-sm text-surface-600">{{ u.display_name }}</td>
            <td class="px-5 py-3">
              <span
                class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
                :class="u.role === 'admin' ? 'bg-brand-100 text-brand-700' : 'bg-surface-100 text-surface-600'"
              >
                {{ u.role === 'admin' ? '管理员' : '用户' }}
              </span>
            </td>
            <td class="px-5 py-3">
              <span
                class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
                :class="u.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-600'"
              >
                {{ u.is_active ? '正常' : '已禁用' }}
              </span>
            </td>
            <td class="px-5 py-3 text-sm text-surface-400">
              {{ u.created_at ? new Date(u.created_at).toLocaleDateString('zh-CN') : '-' }}
            </td>
            <td class="px-5 py-3 text-right space-x-2">
              <button
                type="button"
                class="text-xs text-brand-500 hover:text-brand-700 font-medium transition-colors"
                @click="toggleRole(u)"
              >
                {{ u.role === 'admin' ? '降为用户' : '升为管理员' }}
              </button>
              <button
                v-if="u.is_active"
                type="button"
                class="text-xs text-rose-500 hover:text-rose-700 font-medium transition-colors"
                @click="disableUser(u)"
              >
                禁用
              </button>
            </td>
          </tr>
          <tr v-if="!users.length">
            <td colspan="6" class="px-5 py-8 text-center text-sm text-surface-400">暂无用户</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
