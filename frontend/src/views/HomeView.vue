<template>
  <div class="home">

    <section class="hero">
      <h1>Kubernetes Network Security Platform</h1>
      <p>Cluster management, Terraform automation, and real-time anomaly detection on Hubble flows.</p>
    </section>

    <section class="grid">
      <a v-for="c in cards" :key="c.to" class="card" @click.prevent="go(c.to)" :href="c.to">
        <b>{{ c.title }}</b>
        <span>{{ c.desc }}</span>
        <em v-if="c.admin">Admin</em>
        <em v-else-if="c.to === '/help'" class="open">Public</em>
      </a>
    </section>

  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const cards = [
  { to: '/kcore', title: 'Kubernetes Clusters', desc: 'View and manage clusters, nodes and workloads' },
  { to: '/autotf', title: 'AutoTF', desc: 'Generate and deploy infrastructure from Terraform configs' },
  { to: '/vigil', title: 'Vigil Live Detection', desc: 'Real-time traffic monitoring and anomaly alerts' },
  { to: '/vigil/log', title: 'Detection Log', desc: 'Search past detection results' },
  { to: '/help', title: 'Manual', desc: 'Usage, deployment and troubleshooting' },
  { to: '/admin/dashboard', title: 'Admin Console', desc: 'Manage users, clusters and TF configs', admin: true },
]

function go(to: string) {
  router.push(auth.isLoggedIn || to === '/help' ? to : { path: '/login', query: { redirect: to } })
}
</script>

<style scoped>
.home { min-height: 100vh; overflow-y: auto; background: #f0f4f8; color: #2d3748; }
.hero { text-align: center; padding: 64px 16px 32px; }
.hero h1 { font-size: 30px; color: #1a202c; margin: 0 0 12px; }
.hero p { font-size: 15px; color: #718096; margin: 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; max-width: 1000px; margin: 0 auto; padding: 16px; }
.card { position: relative; display: block; background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px; text-decoration: none; color: inherit; cursor: pointer; }
.card:hover { border-color: #3b82f6; box-shadow: 0 2px 10px rgba(59,130,246,.15); }
.card b { display: block; font-size: 16px; color: #1a202c; margin-bottom: 6px; }
.card span { font-size: 13px; color: #718096; line-height: 1.6; }
.card em { position: absolute; top: 12px; right: 12px; font-style: normal; font-size: 11px; background: #faf5ff; color: #6b46c1; padding: 1px 8px; border-radius: 10px; }
.card em.open { background: #e6fffa; color: #2c7a7b; }
</style>
