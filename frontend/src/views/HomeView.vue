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
.home { height: 100%; overflow-y: auto; background: #f1f5f9; color: #1e293b; }

/* 满宽深色 hero */
.hero {
  position: relative; overflow: hidden; text-align: center;
  padding: clamp(56px, 9vh, 112px) 24px clamp(96px, 13vh, 150px);
  background:
    radial-gradient(ellipse 60% 80% at 15% 0%, rgba(59,130,246,.35), transparent 60%),
    radial-gradient(ellipse 50% 70% at 90% 100%, rgba(139,92,246,.30), transparent 60%),
    linear-gradient(160deg, #0f172a 0%, #0f172a 100%);
  color: #e2e8f0;
}
.hero::after { /* 细网格纹理 */
  content: ''; position: absolute; inset: 0; pointer-events: none;
  background-image: linear-gradient(rgba(255,255,255,.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at center, #000 30%, transparent 75%);
}
.hero > * { position: relative; z-index: 1; }
.hero h1 { font-size: clamp(30px, 4.2vw, 56px); font-weight: 800; letter-spacing: -0.02em; line-height: 1.15; color: #fff; margin: 0 auto 18px; max-width: 18ch; }
.hero p { font-size: clamp(15px, 1.3vw, 19px); color: #94a3b8; margin: 0 auto; max-width: 60ch; line-height: 1.6; }
.cta { display: flex; justify-content: center; flex-wrap: wrap; gap: 14px; margin-top: 36px; }
.cta .el-button { height: 48px; padding: 0 28px; font-size: 16px; border-radius: 10px; }
.cta .el-button + .el-button { margin-left: 0; background: rgba(255,255,255,.06); border-color: rgba(255,255,255,.25); color: #e2e8f0; }
.cta .el-button + .el-button:hover { background: rgba(255,255,255,.14); }
.hero .hint { margin-top: 16px; font-size: 14px; color: #94a3b8; }
.hero .hint b { color: #e2e8f0; }

/* 卡片上移压住 hero 底边，宽屏多列 */
.grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px;
  width: min(1440px, 100% - 48px); margin: -72px auto 0; padding-bottom: 48px; position: relative; z-index: 2;
}
.card {
  position: relative; display: flex; gap: 18px; align-items: flex-start; background: #fff;
  border: 1px solid #e2e8f0; border-radius: 14px; padding: 26px 24px; min-height: 120px;
  text-decoration: none; color: inherit; box-shadow: 0 8px 24px rgba(15,23,42,.06);
  transition: border-color .15s, box-shadow .15s, transform .15s;
}
.card:hover { border-color: #3b82f6; box-shadow: 0 14px 32px rgba(37,99,235,.16); transform: translateY(-3px); }
.ico { flex-shrink: 0; font-size: 26px; width: 52px; height: 52px; border-radius: 12px; }
.txt { min-width: 0; padding-right: 64px; }
.card b { display: block; font-size: 18px; color: #0f172a; margin-bottom: 6px; }
.card span { font-size: 14px; color: #64748b; line-height: 1.6; }
.card em { position: absolute; top: 14px; right: 14px; display: inline-flex; align-items: center; gap: 3px; font-style: normal; font-size: 12px; background: #faf5ff; color: #6b46c1; padding: 2px 10px; border-radius: 10px; }
.card em.open { background: #e6fffa; color: #2c7a7b; }
.card em.locked { background: #f1f5f9; color: #64748b; }
@media (min-width: 1100px) { .grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 600px) {
  .grid { width: calc(100% - 32px); grid-template-columns: 1fr; margin-top: -56px; }
  .card { padding: 20px 18px; }
}
</style>
