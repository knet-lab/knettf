<template>
  <nav class="top-nav">
    <div class="nav-brand">
      <span class="brand-name">NetSentinel</span>
    </div>
    <div class="nav-links">
      <RouterLink to="/kcore" class="nav-link">
        <el-icon><Monitor /></el-icon>
        Kubernetes
      </RouterLink>
      <RouterLink to="/autotf" class="nav-link">
        <el-icon><DataAnalysis /></el-icon>
        Terraform Scan
      </RouterLink>
    </div>
    <div class="nav-user">
      <span class="username">{{ user?.username }}</span>
      <el-button size="small" text style="color: #a0aec0" @click="handleLogout">Sign Out</el-button>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { Monitor, DataAnalysis } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

const auth = useAuthStore()
const { user } = storeToRefs(auth)
const router = useRouter()

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
  padding: 0 24px;
  background: #1d2535;
  border-bottom: 1px solid #2d3748;
  flex-shrink: 0;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 8px;
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

.nav-link:hover {
  background: #2d3748;
  color: #e2e8f0;
}

.nav-link.router-link-active {
  background: #2563eb;
  color: #fff;
}

.nav-user {
  display: flex;
  align-items: center;
  gap: 12px;
}

.username {
  font-size: 14px;
  color: #a0aec0;
}
</style>
