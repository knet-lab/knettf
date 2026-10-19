<template>
  <footer class="app-footer">
    <span class="brand">NetSentinel</span>
    <nav>
      <RouterLink v-for="l in links" :key="l.to" :to="l.to">
        {{ l.label }}<el-icon v-if="!l.public && !auth.isLoggedIn" class="lock"><Lock /></el-icon>
      </RouterLink>
    </nav>
    <span class="note">© {{ year }} · Home and Help are public; <el-icon class="lock"><Lock /></el-icon> pages require signing in</span>
  </footer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { NAV_LINKS, ADMIN_LINK } from '@/config/navLinks'

const auth = useAuthStore()
const links = computed(() => (auth.isAdmin ? [...NAV_LINKS, ADMIN_LINK] : NAV_LINKS))
const year = new Date().getFullYear()
</script>

<style scoped>
.app-footer {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 16px;
  min-height: 32px;
  padding: 4px 16px;
  font-size: 12px;
  color: #909399;
  background: #fafafa;
  border-top: 1px solid #e4e7ed;
}
.brand { font-weight: 600; color: #606266; }
nav { display: flex; flex-wrap: wrap; gap: 12px; }
nav a { display: inline-flex; align-items: center; gap: 2px; color: #409eff; text-decoration: none; }
nav a:hover { text-decoration: underline; }
nav a.router-link-exact-active { color: #303133; font-weight: 600; }
.lock { font-size: 10px; opacity: .6; vertical-align: -1px; }
.note { margin-left: auto; }
@media (max-width: 760px) { .note { display: none; } }
</style>
