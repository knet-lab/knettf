<template>
  <div>
    <el-card>
      <template #header>
        <span>Cluster List</span>
      </template>

      <el-table :data="clusters" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="Name" />
        <el-table-column label="Owner">
          <template #default="{ row }">
            {{ row.owner?.username }}
          </template>
        </el-table-column>
        <el-table-column label="Status" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? 'Active' : 'Inactive' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="Created">
          <template #default="{ row }">
            {{ new Date(row.created_at).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="120" align="center">
          <template #default="{ row }">
            <el-popconfirm title="Delete this cluster?" @confirm="deleteCluster(row.id)">
              <template #reference>
                <el-button type="danger" size="small" text>Delete</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

interface User {
  id: number
  username: string
}

interface Cluster {
  id: number
  name: string
  is_active: boolean
  created_at: string
  owner?: { username: string }
}

const BASE = 'http://127.0.0.1:8000/api'
const auth = useAuthStore()

const clusters = ref<Cluster[]>([])
const loading = ref(false)

async function fetchClusters() {
  loading.value = true
  const usersRes = await auth.apiFetch(`${BASE}/kcore/users/`)
  if (!usersRes.ok) { loading.value = false; return }

  const usersData = await usersRes.json()
  const users: User[] = usersData.data ?? []

  const results = await Promise.all(
    users.map((u) =>
      auth.apiFetch(`${BASE}/kcore/users/${u.id}/clusters/`)
        .then((r) => (r.ok ? r.json() : { data: [] }))
        .then((d) => d.data ?? []),
    ),
  )

  clusters.value = results.flat()
  loading.value = false
}

async function deleteCluster(id: number) {
  const res = await auth.apiFetch(`${BASE}/kcore/clusters/${id}/`, {
    method: 'DELETE',
  })
  if (res.ok) {
    ElMessage.success('Deleted')
    fetchClusters()
  } else {
    ElMessage.error('Failed to delete')
  }
}

onMounted(fetchClusters)
</script>
