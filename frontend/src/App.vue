<template>
  <div class="app-shell">
    <NavComponent v-if="showNav" />
    <div class="app-content">
      <RouterView />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import NavComponent from '@/components/NavComponent.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()

// Admin 有自己的 Layout；登录页、首页不需要 Nav；未登录看手册时也不显示
const showNav = computed(
  () => !route.path.startsWith('/admin') && route.path !== '/login' && route.path !== '/' &&
    !(route.path.startsWith('/help') && !auth.isLoggedIn),
)
</script>

<style>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.app-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 让登录页和 admin 页撑满全屏 */
.app-content > * {
  flex: 1;
  min-height: 0;
}
</style>
