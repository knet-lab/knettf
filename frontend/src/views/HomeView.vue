<template>
  <div class="home">
    <header class="home-top">
      <span class="brand">NetSentinel</span>
      <el-button v-if="auth.isLoggedIn" type="primary" @click="router.push(auth.isAdmin ? '/admin/dashboard' : '/kcore')">进入控制台</el-button>
      <el-button v-else type="primary" @click="router.push('/login')">登录</el-button>
    </header>

    <section class="hero">
      <h1>Kubernetes 集群网络安全平台</h1>
      <p>集群管理、Terraform 自动化部署、基于 Hubble 流量的实时异常检测。</p>
    </section>

    <section class="grid">
      <a v-for="c in cards" :key="c.to" class="card" @click.prevent="go(c.to)" :href="c.to">
        <b>{{ c.title }}</b>
        <span>{{ c.desc }}</span>
        <em v-if="c.admin">管理员</em>
      </a>
    </section>

    <footer class="home-foot">功能页需要登录；未登录点击卡片会先跳到登录页，登录后回到所选页面。</footer>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const cards = [
  { to: '/kcore', title: 'Kubernetes 集群', desc: '查看和管理集群、节点与工作负载' },
  { to: '/autotf', title: 'AutoTF', desc: '用 Terraform 配置生成并部署基础设施' },
  { to: '/vigil', title: 'Vigil 实时检测', desc: '流量实时监控与异常告警' },
  { to: '/vigil/log', title: '检测记录', desc: '历史检测结果查询' },
  { to: '/help', title: '使用与运维手册', desc: '使用说明、部署、排障' },
  { to: '/admin/dashboard', title: '管理后台', desc: '用户、集群、TF 配置管理', admin: true },
]

function go(to: string) {
  router.push(auth.isLoggedIn ? to : { path: '/login', query: { redirect: to } })
}
</script>

<style scoped>
.home { min-height: 100vh; overflow-y: auto; background: #f0f4f8; color: #2d3748; }
.home-top { display: flex; justify-content: space-between; align-items: center; padding: 14px 32px; background: #1d2535; }
.brand { color: #fff; font-size: 18px; font-weight: 700; }
.hero { text-align: center; padding: 64px 16px 32px; }
.hero h1 { font-size: 30px; color: #1a202c; margin: 0 0 12px; }
.hero p { font-size: 15px; color: #718096; margin: 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; max-width: 1000px; margin: 0 auto; padding: 16px; }
.card { position: relative; display: block; background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px; text-decoration: none; color: inherit; cursor: pointer; }
.card:hover { border-color: #3b82f6; box-shadow: 0 2px 10px rgba(59,130,246,.15); }
.card b { display: block; font-size: 16px; color: #1a202c; margin-bottom: 6px; }
.card span { font-size: 13px; color: #718096; line-height: 1.6; }
.card em { position: absolute; top: 12px; right: 12px; font-style: normal; font-size: 11px; background: #faf5ff; color: #6b46c1; padding: 1px 8px; border-radius: 10px; }
.home-foot { text-align: center; font-size: 12.5px; color: #a0aec0; padding: 24px 16px 40px; }
</style>
