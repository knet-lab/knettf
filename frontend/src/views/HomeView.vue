<template>
  <div class="home">
    <section class="hero">
      <h1>Kubernetes Network Security Platform</h1>
      <p>Cluster management, Terraform automation, and real-time anomaly detection on Hubble flows.</p>

      <div class="cta">
        <template v-if="auth.isLoggedIn">
          <el-button type="primary" size="large" @click="router.push(continueTo.to)">
            {{ continueTo.label }} →
          </el-button>
          <el-button size="large" @click="router.push('/help')">Manual</el-button>
        </template>
        <template v-else>
          <el-button type="primary" size="large" @click="router.push('/login')">Sign In</el-button>
          <el-button size="large" @click="router.push('/help')">Read the Manual</el-button>
        </template>
      </div>
      <p v-if="auth.isLoggedIn" class="hint">Signed in as <b>{{ auth.user?.username }}</b></p>
    </section>

    <section class="grid">
      <RouterLink v-for="c in visibleCards" :key="c.to" :to="c.to" class="card">
        <el-icon class="ico" :style="{ color: c.color, background: c.color + '14' }"><component :is="c.icon" /></el-icon>
        <div class="txt">
          <b>{{ c.title }}</b>
          <span>{{ c.desc }}</span>
        </div>
        <em v-if="c.public" class="open">Public</em>
        <em v-else-if="!auth.isLoggedIn" class="locked"><el-icon><Lock /></el-icon> Sign in</em>
        <em v-else-if="c.admin">Admin</em>
      </RouterLink>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Monitor, Cpu, Aim, Document, Reading, Setting, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const cards = [
  { to: '/kcore', title: 'Kubernetes Clusters', desc: 'View and manage clusters, nodes and workloads', icon: Monitor, color: '#2563eb' },
  { to: '/autotf', title: 'AutoTF', desc: 'Generate and deploy infrastructure from Terraform configs', icon: Cpu, color: '#7c3aed' },
  { to: '/vigil', title: 'Vigil Live Detection', desc: 'Real-time traffic monitoring and anomaly alerts', icon: Aim, color: '#dc2626' },
  { to: '/vigil/log', title: 'Detection Log', desc: 'Search past detection results', icon: Document, color: '#d97706' },
  { to: '/help', title: 'Manual', desc: 'Usage, deployment and troubleshooting', icon: Reading, color: '#0d9488', public: true },
  { to: '/admin/dashboard', title: 'Admin Console', desc: 'Manage users, clusters and TF configs', icon: Setting, color: '#475569', admin: true },
]

// 未登录：全部展示（带锁，点了登录后回来）；已登录：普通用户不显示 Admin
const visibleCards = computed(() => cards.filter((c) => !c.admin || !auth.isLoggedIn || auth.isAdmin))

const continueTo = computed(() => {
  let last: string | null = null
  try { last = localStorage.getItem('lastPage') } catch { /* ignore */ }
  if (last && (!last.startsWith('/admin') || auth.isAdmin)) {
    const c = cards.find((x) => last!.startsWith(x.to))
    return { to: last, label: `Continue to ${c?.title ?? 'last page'}` }
  }
  return auth.isAdmin
    ? { to: '/admin/dashboard', label: 'Open Admin Console' }
    : { to: '/kcore', label: 'Open Kubernetes Clusters' }
})
</script>

<style scoped>
.home { height: 100%; overflow-y: auto; background: #f0f4f8; color: #2d3748; padding-bottom: 32px; }
.hero { text-align: center; padding: 48px 16px 24px; }
.hero h1 { font-size: 28px; color: #1a202c; margin: 0 0 10px; }
.hero p { font-size: 15px; color: #718096; margin: 0; }
.cta { display: flex; justify-content: center; flex-wrap: wrap; gap: 12px; margin-top: 24px; }
.cta .el-button + .el-button { margin-left: 0; }
.hero .hint { margin-top: 12px; font-size: 13px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; max-width: 1000px; margin: 0 auto; padding: 16px; }
.card { position: relative; display: flex; gap: 14px; align-items: flex-start; background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 18px; text-decoration: none; color: inherit; transition: border-color .15s, box-shadow .15s, transform .15s; }
.card:hover { border-color: #3b82f6; box-shadow: 0 4px 14px rgba(59,130,246,.15); transform: translateY(-1px); }
.ico { flex-shrink: 0; font-size: 20px; width: 40px; height: 40px; border-radius: 10px; }
.txt { min-width: 0; padding-right: 56px; }
.card b { display: block; font-size: 15px; color: #1a202c; margin-bottom: 4px; }
.card span { font-size: 13px; color: #718096; line-height: 1.5; }
.card em { position: absolute; top: 12px; right: 12px; display: inline-flex; align-items: center; gap: 3px; font-style: normal; font-size: 11px; background: #faf5ff; color: #6b46c1; padding: 1px 8px; border-radius: 10px; }
.card em.open { background: #e6fffa; color: #2c7a7b; }
.card em.locked { background: #f1f5f9; color: #64748b; }
@media (max-width: 600px) { .hero { padding-top: 28px; } .hero h1 { font-size: 22px; } }
</style>
