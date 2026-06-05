/**
 * useAuth - 认证状态管理 composable
 *
 * 管理 JWT 令牌、用户信息、登录/注销操作。
 * 令牌持久化到 localStorage。
 */
import { computed, ref } from 'vue'
import router from '../router'

interface AuthUser {
  id: number
  username: string
  display_name: string
  role: string
}

const TOKEN_KEY = 'eduagent_token'
const USER_KEY = 'eduagent_user'

const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '')
const user = ref<AuthUser | null>(
  localStorage.getItem(USER_KEY) ? JSON.parse(localStorage.getItem(USER_KEY)!) : null
)

const isAuthenticated = computed(() => !!token.value)
const isAdmin = computed(() => user.value?.role === 'admin')

function setAuth(newToken: string, newUser: AuthUser) {
  token.value = newToken
  user.value = newUser
  localStorage.setItem(TOKEN_KEY, newToken)
  localStorage.setItem(USER_KEY, JSON.stringify(newUser))
}

function clearAuth() {
  token.value = ''
  user.value = null
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

async function login(username: string, password: string): Promise<void> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail || `HTTP ${res.status}`)
  }
  const data = await res.json()
  setAuth(data.access_token, data.user)
}

async function register(username: string, password: string, displayName: string): Promise<void> {
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, display_name: displayName }),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail || `HTTP ${res.status}`)
  }
  const data = await res.json()
  setAuth(data.access_token, data.user)
}

function logout() {
  clearAuth()
  router.push('/login')
}

/** 带 Authorization 头的 fetch 封装 */
async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers || {})
  headers.set('Authorization', `Bearer ${token.value}`)
  return fetch(url, { ...options, headers })
}

export function useAuth() {
  return {
    token,
    user,
    isAuthenticated,
    isAdmin,
    login,
    register,
    logout,
    clearAuth,
    authFetch,
  }
}
