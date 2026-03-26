import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/kcore',
    },
    {
      path: '/kcore',
      name: 'kcore',
      component: () => import('../views/KcoreView.vue'),
    },
    {
      path: '/autotf',
      name: 'autotf',
      component: () => import('../views/AutoTFView.vue'),
    },
  ],
})

export default router
