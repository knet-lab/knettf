<script setup lang="ts">
import { ref } from 'vue'

interface Manual {
  key: string
  label: string
  src: string
}

const manuals: Manual[] = [
  { key: 'home', label: '从这里开始', src: '' },
  { key: 'guide', label: '中文手册', src: '/guide/use.html' },
  { key: 'user', label: 'User Manual (English)', src: '/manual_en.html' },
]
const current = ref<Manual>(manuals[0]!)
const frameSrc = ref('')

function open(key: string, page?: string) {
  const m = manuals.find((x) => x.key === key)!
  current.value = m
  frameSrc.value = page ?? m.src
}

// 最常做的几件事，一键直达
const quick = [
  { text: '每日健康检查', desc: '确认系统在跑、检测有数据', page: '/guide/health.html' },
  { text: '改动上线', desc: 'scripts/deploy.sh 怎么用', page: '/guide/deploy.html' },
  { text: '开机恢复', desc: '宿主机重启后让检测恢复', page: '/guide/power.html#startup' },
  { text: '出问题了', desc: '按症状找原因和处理', page: '/guide/trouble.html' },
]

// 手册的三块，对应侧栏的三组
const parts = [
  {
    who: '使用网站',
    desc: '登录、管理用户、操作集群、扫描 Terraform、看检测结果。不需要碰服务器。',
    links: [
      { text: '网页使用', page: '/guide/use.html' },
      { text: 'User Manual (English)', page: '/manual_en.html', key: 'user' },
    ],
  },
  {
    who: '运维',
    desc: '接手、巡检、上线、开关机、排障。每一步都写了怎么做、为什么、结果应该是什么。',
    links: [
      { text: '接手准备：账户与 Git', page: '/guide/prepare.html' },
      { text: '每日健康检查', page: '/guide/health.html' },
      { text: '改动上线', page: '/guide/deploy.html' },
      { text: '开关机 · 重建 · 备份', page: '/guide/power.html' },
      { text: '账号与令牌', page: '/guide/account.html' },
      { text: '排障与日志', page: '/guide/trouble.html' },
    ],
  },
  {
    who: '开发参考',
    desc: '改代码前读：系统怎么组成、代码在哪、接口和表字段。',
    links: [
      { text: '系统总览', page: '/guide/index.html' },
      { text: '前端 / 后端 / 检测 / 集群代码', page: '/guide/frontend.html' },
      { text: 'API 逐接口', page: '/guide/api.html' },
      { text: '数据库与字段', page: '/guide/db.html' },
    ],
  },
]
</script>

<template>
  <div class="help-wrapper">
    <div class="help-tabs">
      <button
        v-for="m in manuals"
        :key="m.key"
        :class="['help-tab', { active: current.key === m.key }]"
        @click="open(m.key)"
      >
        {{ m.label }}
      </button>
      <a v-if="frameSrc" class="help-newwin" :href="frameSrc" target="_blank" rel="noopener">新窗口打开 ↗</a>
    </div>

    <div v-if="current.key === 'home'" class="help-home">
      <h1>帮助中心</h1>
      <p class="lead">只有一本手册，分三块。先看下面最常用的四项，找不到再按身份进对应的那一块。</p>

      <div class="quick-grid">
        <a v-for="q in quick" :key="q.page" href="#" class="quick" @click.prevent="open('guide', q.page)">
          <strong>{{ q.text }} →</strong>
          <span>{{ q.desc }}</span>
        </a>
      </div>

      <div class="route-grid">
        <div v-for="p in parts" :key="p.who" class="route-card">
          <h2>{{ p.who }}</h2>
          <p>{{ p.desc }}</p>
          <ul>
            <li v-for="l in p.links" :key="l.page">
              <a href="#" @click.prevent="open(l.key ?? 'guide', l.page)">{{ l.text }} →</a>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <iframe v-else :src="frameSrc" class="help-frame" :title="current.label" />
  </div>
</template>

<style scoped>
.help-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.help-tabs {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  padding: 8px 12px 0;
  background: #1d2535;
}

.help-tab {
  padding: 8px 16px;
  font-size: 13px;
  color: #a0aec0;
  background: transparent;
  border: none;
  border-radius: 6px 6px 0 0;
  cursor: pointer;
}

.help-tab:hover {
  color: #e2e8f0;
}

.help-tab.active {
  background: #f0f4f8;
  color: #1d2535;
  font-weight: 600;
}

.help-newwin {
  margin-left: auto;
  padding: 8px 4px;
  font-size: 12px;
  color: #a0aec0;
  text-decoration: none;
}

.help-newwin:hover {
  color: #e2e8f0;
}

.help-frame {
  flex: 1;
  width: 100%;
  border: none;
}

.help-home {
  flex: 1;
  overflow-y: auto;
  background: #f0f4f8;
  padding: 32px 40px;
  color: #1a202c;
}

.help-home h1 {
  margin: 0 0 6px;
  font-size: 24px;
}

.lead {
  margin: 0 0 24px;
  color: #4a5568;
  font-size: 14px;
}

.route-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}

.route-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 18px 20px;
}

.route-card h2 {
  margin: 0 0 4px;
  font-size: 16px;
}

.route-card p {
  margin: 0 0 12px;
  font-size: 13px;
  color: #718096;
}

.route-card ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

.route-card li + li {
  margin-top: 6px;
}

.route-card a {
  font-size: 14px;
  color: #2b6cb0;
  text-decoration: none;
}

.route-card a:hover {
  text-decoration: underline;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.quick {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  background: #1d2535;
  border-radius: 10px;
  text-decoration: none;
}

.quick strong {
  font-size: 14.5px;
  color: #fff;
}

.quick span {
  font-size: 12.5px;
  color: #a0aec0;
}

.quick:hover {
  background: #2d3748;
}

@media (max-width: 700px) {
  .help-home {
    padding: 20px 16px;
  }
}
</style>
