/**
 * Vue Router 配置
 *
 * 路由守卫：未登录用户重定向到 /login，已登录用户访问 /login 重定向到 /。
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../composables/useAuth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../pages/LoginPage.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      name: 'home',
      component: () => import('../pages/HomePage.vue'),
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../pages/AdminPanel.vue'),
      meta: { requiresAdmin: true },
    },
  ],
})

router.beforeEach((to) => {
  const { isAuthenticated, isAdmin } = useAuth()

  // 公开页面直接放行
  if (to.meta.public) {
    // 已登录用户访问登录页，重定向到首页
    if (isAuthenticated.value && to.path === '/login') {
      return { name: 'home' }
    }
    return true
  }

  // 未登录用户重定向到登录页
  if (!isAuthenticated.value) {
    return { name: 'login' }
  }

  // 需要管理员权限的页面
  if (to.meta.requiresAdmin && !isAdmin.value) {
    return { name: 'home' }
  }

  return true
})

export default router
