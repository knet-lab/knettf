import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { public: true, title: 'NetSentinel - Login' },
    },

    // ── 用户区 ──────────────────────────────────────
    {
      path: '/',
      redirect: '/kcore',
    },
    {
      path: '/kcore',
      name: 'kcore',
      component: () => import('../views/KcoreView.vue'),
      meta: { requiresAuth: true, title: 'NetSentinel - Clusters' },
    },
    {
      path: '/autotf',
      name: 'autotf',
      component: () => import('../views/AutoTFView.vue'),
      meta: { requiresAuth: true, title: 'NetSentinel - AutoTF' },
    },
    {
      path: '/vigil',
      name: 'vigil',
      component: () => import('../views/VigilView.vue'),
      meta: { requiresAuth: true, title: 'NetSentinel - Vigil' },
    },
    {
      path: '/help',
      name: 'help',
      component: () => import('../views/HelpView.vue'),
      meta: { requiresAuth: true, title: 'NetSentinel - Help' },
    },

    // ── 管理员区 ─────────────────────────────────────
    {
      path: '/admin',
      component: () => import('../views/admin/AdminLayout.vue'),
      meta: { requiresAdmin: true },
      children: [
        { path: '', redirect: '/admin/dashboard' },
        {
          path: 'dashboard',
          name: 'admin-dashboard',
          component: () => import('../views/admin/DashboardView.vue'),
          meta: { title: 'NetSentinel - Dashboard' },
        },
        {
          path: 'users',
          name: 'admin-users',
          component: () => import('../views/admin/UsersView.vue'),
          meta: { title: 'NetSentinel - Users' },
        },
        {
          path: 'clusters',
          name: 'admin-clusters',
          component: () => import('../views/admin/ClustersView.vue'),
          meta: { title: 'NetSentinel - Clusters' },
        },
        {
          path: 'tf-configs',
          name: 'admin-tf-configs',
          component: () => import('../views/admin/TFConfigsView.vue'),
          meta: { title: 'NetSentinel - TF Configs' },
        },
        {
          path: 'tf-tools',
          name: 'admin-tf-tools',
          component: () => import('../views/admin/TFToolsView.vue'),
          meta: { title: 'NetSentinel - TF Tools' },
        },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()

  document.title = (to.meta.title as string) ?? 'NetSentinel'

  if (to.meta.public) return true

  if (!auth.isLoggedIn) return { name: 'login' }

  if (to.meta.requiresAdmin && !auth.isAdmin) return { path: '/kcore' }

  return true
})

export default router
