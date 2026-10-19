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
      name: 'home',
      component: () => import('../views/HomeView.vue'),
      meta: { public: true, title: 'NetSentinel' },
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
      path: '/vigil/log',
      name: 'vigil-log',
      component: () => import('../views/VigilLogView.vue'),
      meta: { requiresAuth: true, title: 'NetSentinel - Detection Log' },
    },
    {
      path: '/help/:page?',
      name: 'help',
      component: () => import('../views/HelpView.vue'),
      meta: { requiresAuth: true, title: 'NetSentinel - Help' },
    },

    // 旧的静态手册地址 → /help/<页>
    { path: '/guide/:file', redirect: (to) => ({ path: `/help/${String(to.params.file).replace(/\.html$/, '')}`, hash: to.hash }) },
    { path: '/manual_en.html', redirect: (to) => ({ path: '/help/en', hash: to.hash }) },

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

  if (!auth.isLoggedIn) return { name: 'login', query: { redirect: to.fullPath } }

  if (to.meta.requiresAdmin && !auth.isAdmin) return { path: '/kcore' }

  return true
})

export default router
