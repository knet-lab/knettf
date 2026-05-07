<template>
    <div>
        <el-card>
            <template #header>
                <div class="card-header">
                    <span>User List</span>
                    <el-button type="primary" :icon="Plus" @click="openCreate">New User</el-button>
                </div>
            </template>

            <el-table :data="users" v-loading="loading" stripe>
                <el-table-column prop="id" label="ID" width="70" />
                <el-table-column prop="username" label="Username" />
                <el-table-column prop="email" label="Email" />
                <el-table-column label="Role" width="100">
                    <template #default="{ row }">
                        <el-tag :type="row.is_staff ? 'danger' : 'info'" size="small">
                            {{ row.is_staff ? 'Admin' : 'User' }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="Actions" width="120" align="center">
                    <template #default="{ row }">
                        <el-popconfirm title="Delete this user?" @confirm="deleteUser(row.id)">
                            <template #reference>
                                <el-button type="danger" size="small" text>Delete</el-button>
                            </template>
                        </el-popconfirm>
                    </template>
                </el-table-column>
            </el-table>
        </el-card>

        <el-dialog v-model="dialogVisible" title="Create User" width="420px">
            <el-form :model="form" label-width="90px">
                <el-form-item label="Username">
                    <el-input v-model="form.username" />
                </el-form-item>
                <el-form-item label="Email">
                    <el-input v-model="form.email" />
                </el-form-item>
                <el-form-item label="Password">
                    <el-input v-model="form.password" type="password" show-password />
                </el-form-item>
                <el-form-item label="Admin">
                    <el-switch v-model="form.is_staff" />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="dialogVisible = false">Cancel</el-button>
                <el-button type="primary" :loading="submitting" @click="createUser">Create</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

interface User {
    id: number
    username: string
    email: string
    is_staff: boolean
}

const BASE = import.meta.env.VITE_API_BASE
const auth = useAuthStore()

const users = ref<User[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const form = ref({ username: '', email: '', password: '', is_staff: false })

async function fetchUsers() {
    loading.value = true
    const res = await auth.apiFetch(`${BASE}/kcore/users/`)
    if (res.ok) {
        const data = await res.json()
        users.value = data.data ?? []
    }
    loading.value = false
}

function openCreate() {
    form.value = { username: '', email: '', password: '', is_staff: false }
    dialogVisible.value = true
}

async function createUser() {
    submitting.value = true
    const res = await auth.apiFetch(`${BASE}/kcore/users/`, {
        method: 'POST',
        body: JSON.stringify(form.value),
    })
    submitting.value = false
    if (res.ok) {
        ElMessage.success('User created')
        dialogVisible.value = false
        fetchUsers()
    } else {
        ElMessage.error('Failed to create user')
    }
}

async function deleteUser(id: number) {
    const res = await auth.apiFetch(`${BASE}/kcore/users/${id}/`, {
        method: 'DELETE',
    })
    if (res.ok) {
        ElMessage.success('Deleted')
        fetchUsers()
    } else {
        ElMessage.error('Failed to delete')
    }
}

onMounted(fetchUsers)
</script>

<style scoped>
.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}
</style>
