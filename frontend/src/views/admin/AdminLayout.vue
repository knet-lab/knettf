<template>
  <el-container class="admin-container">
    <!-- Sidebar -->
    <el-aside width="220px" class="admin-aside">
      <div class="logo">NetSentinel</div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#1d2535"
        text-color="#a6adb9"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/admin/dashboard">
          <el-icon><DataBoard /></el-icon>
          <span>Dashboard</span>
        </el-menu-item>
        <el-menu-item index="/admin/users">
          <el-icon><User /></el-icon>
          <span>Users</span>
        </el-menu-item>
        <el-menu-item index="/admin/clusters">
          <el-icon><Connection /></el-icon>
          <span>Clusters</span>
        </el-menu-item>
        <el-menu-item index="/admin/tf-configs">
          <el-icon><Document /></el-icon>
          <span>TF Configs</span>
        </el-menu-item>
        <el-menu-item index="/admin/tf-tools">
          <el-icon><Tools /></el-icon>
          <span>TF Tools</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- Main -->
    <el-container>
      <el-header class="admin-header">
        <span class="page-title">{{ pageTitle }}</span>
        <div class="header-right">
          <span class="username">{{ auth.user?.username }}</span>
          <el-button text type="danger" @click="handleLogout">Sign Out</el-button>
        </div>
      </el-header>
      <el-main class="admin-main">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DataBoard, User, Connection, Document, Tools } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeMenu = computed(() => route.path)

const titleMap: Record<string, string> = {
  '/admin/dashboard': 'Dashboard',
  '/admin/users': 'Users',
  '/admin/clusters': 'Clusters',
  '/admin/tf-configs': 'TF Configs',
  '/admin/tf-tools': 'TF Tools',
}
const pageTitle = computed(() => titleMap[route.path] ?? 'Admin')

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.admin-container {
  height: 100vh;
}

.admin-aside {
  background: #1d2535;
  display: flex;
  flex-direction: column;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 18px;
  font-weight: 700;
  border-bottom: 1px solid #2d3748;
}

.el-menu {
  border-right: none;
  flex: 1;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
  padding: 0 24px;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.username {
  color: #606266;
  font-size: 14px;
}

.admin-main {
  background: #f5f7fa;
}
</style>
