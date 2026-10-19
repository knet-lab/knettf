<template>
    <div>
        <div class="stats">
            <RouterLink v-for="c in cards" :key="c.label" :to="c.to" class="stat" :style="{ '--accent': c.color }">
                <el-icon class="ico"><component :is="c.icon" /></el-icon>
                <div>
                    <div class="value">{{ stats[c.key] }}</div>
                    <div class="label">{{ c.label }}</div>
                </div>
                <el-icon class="go"><ArrowRight /></el-icon>
            </RouterLink>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { User, Connection, Document, ArrowRight } from '@element-plus/icons-vue'

interface UserStat {
    cluster_count?: number
}

const BASE = import.meta.env.VITE_API_BASE
const auth = useAuthStore()

const stats = ref({ users: 0, clusters: 0, tfConfigs: 0 })
const cards = [
    { key: 'users', label: 'Total Users', to: '/admin/users', icon: User, color: '#2563eb' },
    { key: 'clusters', label: 'Total Clusters', to: '/admin/clusters', icon: Connection, color: '#14b8a6' },
    { key: 'tfConfigs', label: 'Total TF Configs', to: '/admin/tf-configs', icon: Document, color: '#8b5cf6' },
] as const

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
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 20px; }
.stat {
    display: flex; align-items: center; gap: 18px; padding: 26px 24px;
    background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; box-shadow: var(--ns-shadow);
    text-decoration: none; color: inherit; transition: transform .15s, box-shadow .15s, border-color .15s;
}
.stat:hover { transform: translateY(-3px); border-color: var(--accent); box-shadow: var(--ns-shadow-lg); }
.ico { width: 54px; height: 54px; border-radius: 14px; font-size: 26px; color: var(--accent); background: color-mix(in srgb, var(--accent) 12%, #fff); }
.stat > div { flex: 1; }
.value { font-size: 36px; font-weight: 800; line-height: 1.1; color: #0f172a; letter-spacing: -0.02em; }
.label { margin-top: 4px; font-size: 13.5px; color: #64748b; }
.go { color: #cbd5e1; transition: color .15s, transform .15s; }
.stat:hover .go { color: var(--accent); transform: translateX(3px); }
</style>
