<template>
  <footer class="app-footer">
    <span class="brand"><span class="dot" />NetSentinel</span>
    <nav>
      <RouterLink v-for="l in links" :key="l.to" :to="l.to">
        {{ l.label }}<el-icon v-if="!l.public && !auth.isLoggedIn" class="lock"><Lock /></el-icon>
      </RouterLink>
    </nav>
    <span class="note">© {{ year }} NetSentinel · <el-icon class="lock"><Lock /></el-icon> requires sign-in</span>
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
  gap: 20px;
  min-height: 40px;
  padding: 6px max(20px, calc((100% - 1440px) / 2));
  font-size: 12.5px;
  color: #64748b;
  background: #0f172a;
  border-top: 1px solid rgba(255,255,255,.06);
}
.brand { display: inline-flex; align-items: center; gap: 8px; font-weight: 700; color: #e2e8f0; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: linear-gradient(135deg, #60a5fa, #8b5cf6); }
nav { display: flex; flex-wrap: wrap; gap: 16px; }
nav a { display: inline-flex; align-items: center; gap: 3px; color: #94a3b8; text-decoration: none; transition: color .15s; }
nav a:hover { color: #fff; }
nav a.router-link-exact-active { color: #fff; font-weight: 600; }
.lock { font-size: 10px; opacity: .6; vertical-align: -1px; }
.note { margin-left: auto; display: inline-flex; align-items: center; gap: 4px; }
@media (max-width: 760px) { .note { display: none; } }
@media (max-width: 600px) { nav { display: none; } .app-footer { justify-content: center; min-height: 34px; } }
</style>
