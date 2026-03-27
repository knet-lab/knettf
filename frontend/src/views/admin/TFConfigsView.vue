<template>
  <div>
    <el-card>
      <template #header>
        <span>TF Config List</span>
      </template>

      <el-table :data="configs" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="Name" />
        <el-table-column label="Owner">
          <template #default="{ row }">
            {{ row.owner?.username ?? row.owner }}
          </template>
        </el-table-column>
        <el-table-column label="Created">
          <template #default="{ row }">
            {{ new Date(row.created_at).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="120" align="center">
          <template #default="{ row }">
            <el-popconfirm title="Delete this config?" @confirm="deleteConfig(row.id)">
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

const BASE = 'http://127.0.0.1:8000/api'
const auth = useAuthStore()

const configs = ref<any[]>([])
const loading = ref(false)

async function fetchConfigs() {
  loading.value = true
  const usersRes = await fetch(`${BASE}/kcore/users/`, { headers: auth.authHeaders() })
  if (!usersRes.ok) { loading.value = false; return }

  const usersData = await usersRes.json()
  const users: any[] = usersData.data ?? []

  const results = await Promise.all(
    users.map((u) =>
      fetch(`${BASE}/autotf/users/${u.id}/tf-configs/`, { headers: auth.authHeaders() })
        .then((r) => (r.ok ? r.json() : { data: [] }))
        .then((d) => (d.data ?? []).map((c: any) => ({ ...c, owner: u }))),
    ),
  )

  configs.value = results.flat()
  loading.value = false
}

async function deleteConfig(id: number) {
  const res = await fetch(`${BASE}/autotf/tf-configs/${id}/`, {
    method: 'DELETE',
    headers: auth.authHeaders(),
  })
  if (res.ok) {
    ElMessage.success('Deleted')
    fetchConfigs()
  } else {
    ElMessage.error('Failed to delete')
  }
}

onMounted(fetchConfigs)
</script>
