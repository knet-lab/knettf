<template>
  <div class="admin">
    <aside class="admin-aside">
      <div class="aside-title">Administration</div>
      <RouterLink v-for="m in menu" :key="m.to" :to="m.to" class="aside-link">
        <el-icon><component :is="m.icon" /></el-icon>{{ m.label }}
      </RouterLink>
    </aside>
    <div class="admin-body">
      <header class="admin-head">
        <div>
          <div class="crumb">Admin</div>
          <h1>{{ pageTitle }}</h1>
          <p>{{ pageDesc }}</p>
        </div>
      </header>
      <main class="admin-main">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { DataBoard, User, Connection, Document, Tools } from '@element-plus/icons-vue'

const route = useRoute()

const menu = [
  { to: '/admin/dashboard', label: 'Dashboard', icon: DataBoard, desc: 'Overview of users, clusters and Terraform configs.' },
  { to: '/admin/users', label: 'Users', icon: User, desc: 'Create accounts, reset passwords and set roles.' },
  { to: '/admin/clusters', label: 'Clusters', icon: Connection, desc: 'All Kubernetes clusters registered by users.' },
  { to: '/admin/tf-configs', label: 'TF Configs', icon: Document, desc: 'Terraform configurations uploaded for scanning.' },
  { to: '/admin/tf-tools', label: 'TF Tools', icon: Tools, desc: 'Security scanners used to check Terraform files.' },
]
const current = computed(() => menu.find((m) => m.to === route.path))
const pageTitle = computed(() => current.value?.label ?? 'Admin')
const pageDesc = computed(() => current.value?.desc ?? '')
</script>

<style scoped>
.admin { display: flex; height: 100%; overflow: hidden; background: #f1f5f9; }

.admin-aside { width: 232px; flex-shrink: 0; padding: 22px 14px; background: #fff; border-right: 1px solid #e2e8f0; overflow-y: auto; }
.aside-title { font-size: 11.5px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: #94a3b8; padding: 0 12px 12px; }
.aside-link { display: flex; align-items: center; gap: 10px; padding: 10px 12px; margin-bottom: 2px; border-radius: 10px; font-size: 14px; font-weight: 500; color: #334155; text-decoration: none; transition: background .15s, color .15s; }
.aside-link .el-icon { font-size: 17px; color: #94a3b8; }
.aside-link:hover { background: #f1f5f9; }
.aside-link.router-link-active { background: #eff6ff; color: #1d4ed8; font-weight: 600; }
.aside-link.router-link-active .el-icon { color: #2563eb; }

.admin-body { flex: 1; min-width: 0; overflow-y: auto; }
.admin-head { padding: 28px 32px 64px; background: var(--ns-hero); color: #e2e8f0; }
.crumb { font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: #93c5fd; }
.admin-head h1 { font-size: 28px; font-weight: 800; color: #fff; letter-spacing: -0.02em; margin-top: 4px; }
.admin-head p { color: #94a3b8; font-size: 14px; margin-top: 4px; }
.admin-main { position: relative; margin: -40px 32px 0; padding-bottom: 32px; }

@media (max-width: 760px) {
  .admin { flex-direction: column; overflow-y: auto; }
  .admin-aside { width: 100%; display: flex; gap: 4px; overflow-x: auto; padding: 8px; border-right: none; border-bottom: 1px solid #e2e8f0; }
  .aside-title { display: none; }
  .aside-link { white-space: nowrap; margin: 0; }
  .admin-body { overflow: visible; }
  .admin-head { padding: 20px 16px 56px; }
  .admin-main { margin: -36px 16px 0; }
}
</style>
