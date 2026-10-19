<template>
  <div class="app-shell">
    <NavComponent v-if="showNav" />
    <div class="app-content">
      <RouterView />
    </div>
    <FooterComponent />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import NavComponent from '@/components/NavComponent.vue'
import FooterComponent from '@/components/FooterComponent.vue'

const route = useRoute()

// Admin 有自己的 Layout，登录页不需要 Nav
const showNav = computed(
  () => !route.path.startsWith('/admin') && route.path !== '/login',
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
