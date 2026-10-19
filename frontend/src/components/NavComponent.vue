<template>
  <nav class="top-nav">
    <div class="nav-brand"><BrandMark /></div>

    <!-- wide: inline links -->
    <div class="nav-links wide-only">
      <RouterLink v-for="l in links" :key="l.to" :to="l.to" class="nav-link" :exact-active-class="l.to === '/' ? 'router-link-active' : undefined" :active-class="l.to === '/' ? '' : 'router-link-active'">
        <el-icon><component :is="l.icon" /></el-icon>
        {{ l.label }}
        <el-icon v-if="!l.public && !auth.isLoggedIn" class="lock"><Lock /></el-icon>
      </RouterLink>
    </div>

    <div class="nav-right">
      <template v-if="auth.isLoggedIn">
        <span class="user-chip wide-only"><span class="avatar">{{ initial }}</span>{{ user?.username }}</span>
        <button class="ghost-btn wide-only" @click="handleLogout"><el-icon><SwitchButton /></el-icon>Sign Out</button>
      </template>
      <el-button v-else type="primary" class="wide-only" @click="signIn">Sign In</el-button>

      <!-- narrow: hamburger -->
      <el-button class="narrow-only hamburger" text @click="drawerOpen = true">
        <el-icon size="20"><Menu /></el-icon>
      </el-button>
    </div>
  </nav>

  <!-- mobile drawer -->
  <el-drawer v-model="drawerOpen" direction="rtl" size="80%" :show-close="false"
    :with-header="false" class="nav-drawer">
    <div class="drawer-inner">
      <div class="drawer-user">
        <template v-if="auth.isLoggedIn">
          <span class="drawer-username">{{ user?.username }}</span>
          <el-button size="small" text style="color:#94a3b8" @click="handleLogout">Sign Out</el-button>
        </template>
        <el-button v-else size="small" type="primary" @click="signIn">Sign In</el-button>
      </div>
      <div class="drawer-links">
        <RouterLink v-for="l in links" :key="l.to" :to="l.to" class="drawer-link" :active-class="l.to === '/' ? '' : 'router-link-active'"
          @click="drawerOpen = false">
          <el-icon><component :is="l.icon" /></el-icon>
          {{ l.label }}
          <el-icon v-if="!l.public && !auth.isLoggedIn" class="lock"><Lock /></el-icon>
        </RouterLink>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Menu, Lock, SwitchButton } from '@element-plus/icons-vue'
import BrandMark from '@/components/BrandMark.vue'
import { NAV_LINKS, ADMIN_LINK } from '@/config/navLinks'
import { useAuthStore } from '@/stores/auth'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

const auth = useAuthStore()
const { user } = storeToRefs(auth)
const router = useRouter()
const drawerOpen = ref(false)

const route = useRoute()
const initial = computed(() => (user.value?.username ?? '?').slice(0, 1).toUpperCase())
const links = computed(() => (auth.isAdmin ? [...NAV_LINKS, ADMIN_LINK] : NAV_LINKS))

function signIn() {
  drawerOpen.value = false
  router.push({ path: '/login', query: { redirect: route.fullPath } })
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.top-nav {
  position: relative;
  z-index: 10;
  display: flex;
  align-items: center;
  height: 60px;
  padding: 0 max(20px, calc((100% - 1440px) / 2));
  background: rgba(15, 23, 42, .96);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(255, 255, 255, .06);
  flex-shrink: 0;
}

.nav-brand { display: flex; align-items: center; margin-right: 36px; }

.nav-links { display: flex; gap: 2px; flex: 1; height: 100%; }

.nav-link {
  position: relative;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0 14px;
  color: #94a3b8;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: color .15s;
}
.nav-link::after {
  content: '';
  position: absolute;
  left: 14px; right: 14px; bottom: 0;
  height: 2px;
  border-radius: 2px;
  background: linear-gradient(90deg, #60a5fa, #8b5cf6);
  transform: scaleX(0);
  transition: transform .2s;
}
.nav-link:hover { color: #f1f5f9; }
.nav-link.router-link-active { color: #fff; font-weight: 600; }
.nav-link.router-link-active::after { transform: scaleX(1); }
.lock { font-size: 11px; opacity: .55; }

.nav-right { display: flex; align-items: center; gap: 10px; margin-left: auto; }

.user-chip { align-items: center; gap: 8px; font-size: 13.5px; color: #e2e8f0; }
.avatar {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  color: #fff; font-size: 12.5px; font-weight: 700;
}
.ghost-btn {
  align-items: center; gap: 6px; height: 32px; padding: 0 12px;
  font: inherit; font-size: 13px; color: #94a3b8; cursor: pointer;
  background: transparent; border: 1px solid rgba(255,255,255,.12); border-radius: 8px;
  transition: color .15s, border-color .15s;
}
.ghost-btn:hover { color: #fff; border-color: rgba(255,255,255,.3); }

.hamburger { color: #94a3b8 !important; padding: 4px 8px; }

/* responsive breakpoint */
.wide-only  { display: flex; }
.narrow-only { display: none; }

@media (max-width: 680px) {
  .wide-only   { display: none !important; }
  .narrow-only { display: flex !important; }
  .nav-brand   { margin-right: auto; }
}

/* drawer */
:deep(.nav-drawer .el-drawer__body) {
  padding: 0;
  background: #0f172a;
}

.drawer-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px 12px;
}

.drawer-user {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid #1e293b;
  margin-bottom: 12px;
}

.drawer-username { font-size: 14px; color: #94a3b8; }

.drawer-links {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.drawer-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 6px;
  color: #94a3b8;
  text-decoration: none;
  font-size: 14px;
  transition: background 0.15s, color 0.15s;
}

.drawer-link:hover { background: #1e293b; color: #e2e8f0; }
.drawer-link.router-link-active { background: rgba(37,99,235,.18); color: #fff; box-shadow: inset 3px 0 0 #60a5fa; }
</style>
