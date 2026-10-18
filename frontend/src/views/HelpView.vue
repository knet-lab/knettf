<script setup lang="ts">
import { ref } from 'vue'

interface Manual {
  key: string
  label: string
  src: string
}

const manuals: Manual[] = [
  { key: 'home', label: '从这里开始', src: '' },
  { key: 'user', label: 'User Manual（英文）', src: '/manual_en.html' },
  { key: 'guide', label: '使用管理手册', src: '/guide/index.html' },
  { key: 'ops', label: '运维对照手册', src: '/ops/index.html' },
]
const current = ref<Manual>(manuals[0]!)
const frameSrc = ref('')

function open(key: string, page?: string) {
  const m = manuals.find((x) => x.key === key)!
  current.value = m
  frameSrc.value = page ?? m.src
}

// 按“你要做什么”组织入口，每条直达具体章节
const routes = [
  {
    who: '我只是用这个网站',
    desc: '登录、查看检测结果、运行实验',
    links: [
      { text: '网页使用全流程', key: 'guide', page: '/guide/use.html' },
      { text: 'English user manual', key: 'user', page: '/manual_en.html' },
    ],
  },
  {
    who: '我是新接手的人',
    desc: '先建账户、拿到 GitHub 权限，再按顺序读',
    links: [
      { text: '① 准备工作：账户与 Git', key: 'guide', page: '/guide/prepare.html' },
      { text: '② 开始之前（环境与目录）', key: 'guide', page: '/guide/index.html' },
      { text: '③ 日常管理与变更', key: 'guide', page: '/guide/manage.html' },
    ],
  },
  {
    who: '我要改代码',
    desc: '先弄清楚代码在哪、数据怎么流动',
    links: [
      { text: '前端代码', key: 'guide', page: '/guide/frontend.html' },
      { text: '后端代码', key: 'guide', page: '/guide/backend.html' },
      { text: '检测链路与模型', key: 'guide', page: '/guide/detect.html' },
      { text: '集群与 Shell 脚本', key: 'guide', page: '/guide/infra.html' },
    ],
  },
  {
    who: '出问题了 / 要查东西',
    desc: '按症状找命令，按名字查接口和字段',
    links: [
      { text: '运维操作逐步骤', key: 'ops', page: '/ops/runbook.html' },
      { text: '已知问题与练习', key: 'guide', page: '/guide/issues.html' },
      { text: 'API 逐接口说明', key: 'ops', page: '/ops/api.html' },
      { text: '数据库与模型字段', key: 'ops', page: '/ops/db.html' },
    ],
  },
]

const manualInfo = [
  { key: 'guide', title: '使用管理手册', body: '按顺序读的教程：从准备工作到每块代码、日常变更。第一次接手时读这本。' },
  { key: 'ops', title: '运维对照手册', body: '查阅型参考：接口、数据库字段、运维命令。遇到具体问题时查这本。' },
  { key: 'user', title: 'User Manual', body: '面向网站使用者的英文说明，不涉及代码和服务器。' },
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
      <p class="lead">先选你要做的事，下面直接给出该读哪一章。</p>

      <div class="route-grid">
        <div v-for="r in routes" :key="r.who" class="route-card">
          <h2>{{ r.who }}</h2>
          <p>{{ r.desc }}</p>
          <ul>
            <li v-for="l in r.links" :key="l.page">
              <a href="#" @click.prevent="open(l.key, l.page)">{{ l.text }} →</a>
            </li>
          </ul>
        </div>
      </div>

      <h3>三本手册分别是什么</h3>
      <div class="manual-list">
        <div v-for="m in manualInfo" :key="m.key" class="manual-row" @click="open(m.key)">
          <strong>{{ m.title }}</strong>
          <span>{{ m.body }}</span>
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

.help-home h3 {
  margin: 0 0 10px;
  font-size: 15px;
}

.manual-list {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.manual-row {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 12px;
  padding: 12px 20px;
  font-size: 13.5px;
  cursor: pointer;
}

.manual-row + .manual-row {
  border-top: 1px solid #edf2f7;
}

.manual-row:hover {
  background: #f7fafc;
}

.manual-row span {
  color: #4a5568;
}

@media (max-width: 700px) {
  .help-home {
    padding: 20px 16px;
  }
  .manual-row {
    grid-template-columns: 1fr;
    gap: 2px;
  }
}
</style>
