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

interface User {
    id: number
    username: string
}

interface TFConfig {
    id: number
    name: string
    created_at: string
    owner: User
}

const BASE = import.meta.env.VITE_API_BASE
const auth = useAuthStore()

const configs = ref<TFConfig[]>([])
const loading = ref(false)

async function fetchConfigs() {
    loading.value = true
    const usersRes = await auth.apiFetch(`${BASE}/kcore/users/`)
    if (!usersRes.ok) { loading.value = false; return }

    const usersData = await usersRes.json()
    const users: User[] = usersData.data ?? []

    const results = await Promise.all(
        users.map((u) =>
            auth.apiFetch(`${BASE}/autotf/users/${u.id}/tf-configs/`)
                .then((r) => (r.ok ? r.json() : { data: [] }))
                .then((d) => (d.data ?? []).map((c: TFConfig) => ({ ...c, owner: u }))),
        ),
    )

    configs.value = results.flat()
    loading.value = false
}

async function deleteConfig(id: number) {
    const res = await auth.apiFetch(`${BASE}/autotf/tf-configs/${id}/`, {
        method: 'DELETE',
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
