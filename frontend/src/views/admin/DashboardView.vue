<template>
  <div>
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.users }}</div>
          <div class="stat-label">Total Users</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.clusters }}</div>
          <div class="stat-label">Total Clusters</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.tfConfigs }}</div>
          <div class="stat-label">Total TF Configs</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

interface UserStat {
  cluster_count?: number
}

const BASE = 'http://127.0.0.1:8000/api'
const auth = useAuthStore()

const stats = ref({ users: 0, clusters: 0, tfConfigs: 0 })

onMounted(async () => {
  const [usersRes, tfRes] = await Promise.all([
    auth.apiFetch(`${BASE}/kcore/users/`),
    auth.apiFetch(`${BASE}/autotf/tf-configs/all/`),
  ])

  if (usersRes.ok) {
    const data = await usersRes.json()
    const users = data.data ?? []
    stats.value.users = users.length
    stats.value.clusters = (users as UserStat[]).reduce(
      (acc, u) => acc + (u.cluster_count ?? 0),
      0,
    )
  }

  if (tfRes.ok) {
    const data = await tfRes.json()
    stats.value.tfConfigs = (data.data ?? []).length
  }
})
</script>

<style scoped>
.stat-card {
  text-align: center;
  padding: 12px 0;
}

.stat-value {
  font-size: 40px;
  font-weight: 700;
  color: #409eff;
}

.stat-label {
  margin-top: 8px;
  font-size: 14px;
  color: #909399;
}
</style>
