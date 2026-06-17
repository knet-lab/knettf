<template>
  <nav class="top-nav">
    <div class="nav-brand">
      <span class="brand-name">NetSentinel</span>
    </div>

    <!-- wide: inline links -->
    <div class="nav-links wide-only">
      <RouterLink v-for="l in links" :key="l.to" :to="l.to" class="nav-link">
        <el-icon><component :is="l.icon" /></el-icon>
        {{ l.label }}
      </RouterLink>
    </div>

    <div class="nav-right">
      <span class="username wide-only">{{ user?.username }}</span>
      <el-button size="small" text style="color: #a0aec0" class="wide-only" @click="handleLogout">Sign Out</el-button>

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
        <span class="drawer-username">{{ user?.username }}</span>
        <el-button size="small" text style="color:#a0aec0" @click="handleLogout">Sign Out</el-button>
      </div>
      <div class="drawer-links">
        <RouterLink v-for="l in links" :key="l.to" :to="l.to" class="drawer-link"
          @click="drawerOpen = false">
          <el-icon><component :is="l.icon" /></el-icon>
          {{ l.label }}
        </RouterLink>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Monitor, DataAnalysis, QuestionFilled, Menu } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

const auth = useAuthStore()
const { user } = storeToRefs(auth)
const router = useRouter()
const drawerOpen = ref(false)

const links = [
  { to: '/kcore',  label: 'Kubernetes',     icon: Monitor },
  { to: '/autotf', label: 'Terraform Scan', icon: DataAnalysis },
  { to: '/vigil',  label: 'AI Vigil',       icon: DataAnalysis },
  { to: '/help',   label: 'Help',           icon: QuestionFilled },
]

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.top-nav {
  display: flex;
  align-items: center;
  height: 52px;
  padding: 0 16px;
  background: #1d2535;
  border-bottom: 1px solid #2d3748;
  flex-shrink: 0;
}

.nav-brand {
  display: flex;
  align-items: center;
  margin-right: 32px;
}

.brand-name {
  font-size: 16px;
  font-weight: 700;
  color: #e2e8f0;
  letter-spacing: 0.5px;
}

.nav-links {
  display: flex;
  gap: 4px;
  flex: 1;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 6px;
  color: #a0aec0;
  text-decoration: none;
  font-size: 14px;
  transition: background 0.15s, color 0.15s;
}

.nav-link:hover { background: #2d3748; color: #e2e8f0; }
.nav-link.router-link-active { background: #2563eb; color: #fff; }

.nav-right {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
}

.username { font-size: 14px; color: #a0aec0; }

.hamburger { color: #a0aec0 !important; padding: 4px 8px; }

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
  background: #1d2535;
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
  border-bottom: 1px solid #2d3748;
  margin-bottom: 12px;
}

.drawer-username { font-size: 14px; color: #a0aec0; }

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
  color: #a0aec0;
  text-decoration: none;
  font-size: 14px;
  transition: background 0.15s, color 0.15s;
}

.drawer-link:hover { background: #2d3748; color: #e2e8f0; }
.drawer-link.router-link-active { background: #2563eb; color: #fff; }
</style>
