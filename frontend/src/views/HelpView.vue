<script setup lang="ts">
import { computed, nextTick, ref, shallowRef, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import './help/guide.css'

// 手册页面：src/views/help/pages/<key>.vue，路由 /help/<key>
const loaders = import.meta.glob<{ default: Component }>('./help/pages/*.vue')
const load = (key: string) => loaders[`./help/pages/${key}.vue`]

const GROUPS = [
  { name: '使用网站', pages: [
    { key: 'use', title: '网页使用' },
    { key: 'en', title: 'User Manual (English)' },
  ] },
  { name: '运维', pages: [
    { key: 'prepare', title: '接手准备：账户与 Git' },
    { key: 'health', title: '每日健康检查' },
    { key: 'deploy', title: '改动上线' },
    { key: 'power', title: '开关机 · 重建 · 备份' },
    { key: 'account', title: '账号与令牌' },
    { key: 'trouble', title: '排障与日志' },
  ] },
  { name: '开发参考', pages: [
    { key: 'index', title: '系统总览' },
    { key: 'frontend', title: '前端代码' },
    { key: 'backend', title: '后端代码' },
    { key: 'detect', title: '检测链路与模型' },
    { key: 'infra', title: '集群与 Shell 脚本' },
    { key: 'lab', title: '实验脚本' },
    { key: 'api', title: 'API 逐接口' },
    { key: 'db', title: '数据库与字段' },
    { key: 'issues', title: '已知问题与练习' },
  ] },
]

const route = useRoute()
const router = useRouter()
const pageKey = computed(() => (route.params.page as string | undefined) ?? '')
const page = shallowRef<Component | null>(null)
const body = ref<HTMLElement | null>(null)
const toc = ref<{ id: string; text: string }[]>([])
const activeId = ref('')

const tabs = [
  { key: '', label: '从这里开始', to: '/help' },
  { key: 'guide', label: '中文手册', to: '/help/use' },
  { key: 'en', label: 'User Manual (English)', to: '/help/en' },
]
const activeTab = computed(() => (!pageKey.value ? '' : pageKey.value === 'en' ? 'en' : 'guide'))

// 页底：同组内的上一页 / 下一页（英文版不参与）
const pager = computed(() => {
  const g = GROUPS.find((x) => x.pages.some((p) => p.key === pageKey.value))
  const list = g ? g.pages.filter((p) => p.key !== 'en') : []
  const i = list.findIndex((p) => p.key === pageKey.value)
  return i < 0 ? { prev: undefined, next: undefined } : { prev: list[i - 1], next: list[i + 1] }
})

function scrollToHash(hash: string) {
  const el = hash ? body.value?.querySelector<HTMLElement>(`[id="${CSS.escape(hash.slice(1))}"]`) : null
  if (el) el.scrollIntoView()
  else body.value?.scrollTo(0, 0)
}

watch(
  () => route.params.page,
  async (key) => {
    if (!key) { page.value = null; return }
    const loader = load(key as string)
    if (!loader) { router.replace('/help'); return }
    page.value = (await loader()).default
    await nextTick()
    toc.value = [...(body.value?.querySelectorAll<HTMLElement>('section[id] > h2') ?? [])]
      .map((h) => ({ id: h.parentElement!.id, text: h.textContent ?? '' }))
    scrollToHash(route.hash)
    onScroll()
  },
  { immediate: true },
)
watch(() => route.hash, (h) => { if (page.value) scrollToHash(h) })

function onScroll() {
  let id = toc.value[0]?.id ?? ''
  for (const t of toc.value) {
    const el = document.getElementById(t.id)
    if (el && el.getBoundingClientRect().top - (body.value?.getBoundingClientRect().top ?? 0) < 120) id = t.id
  }
  activeId.value = id
}

// 页面正文里的 <a href="/help/..."> 和 <a href="#..."> 走路由，不整页刷新
function onClick(e: MouseEvent) {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return
  const a = (e.target as HTMLElement).closest('a')
  const href = a?.getAttribute('href')
  if (!href || a!.target) return
  if (href.startsWith('#')) {
    e.preventDefault()
    if (href === route.hash) scrollToHash(href)
    else router.replace({ hash: href })
  } else if (href.startsWith('/help')) {
    e.preventDefault()
    router.push(href)
  }
}

// 最常做的几件事，一键直达
const quick = [
  { text: '每日健康检查', desc: '确认系统在跑、检测有数据', page: '/help/health' },
  { text: '改动上线', desc: 'scripts/deploy.sh 怎么用', page: '/help/deploy' },
  { text: '开机恢复', desc: '宿主机重启后让检测恢复', page: '/help/power#startup' },
  { text: '出问题了', desc: '按症状找原因和处理', page: '/help/trouble' },
]

// 手册的三块，对应侧栏的三组
const parts = [
  {
    who: '使用网站',
    desc: '登录、管理用户、操作集群、扫描 Terraform、看检测结果。不需要碰服务器。',
    links: [
      { text: '网页使用', page: '/help/use' },
      { text: 'User Manual (English)', page: '/help/en' },
    ],
  },
  {
    who: '运维',
    desc: '接手、巡检、上线、开关机、排障。每一步都写了怎么做、为什么、结果应该是什么。',
    links: [
      { text: '接手准备：账户与 Git', page: '/help/prepare' },
      { text: '每日健康检查', page: '/help/health' },
      { text: '改动上线', page: '/help/deploy' },
      { text: '开关机 · 重建 · 备份', page: '/help/power' },
      { text: '账号与令牌', page: '/help/account' },
      { text: '排障与日志', page: '/help/trouble' },
    ],
  },
  {
    who: '开发参考',
    desc: '改代码前读：系统怎么组成、代码在哪、接口和表字段。',
    links: [
      { text: '系统总览', page: '/help/index' },
      { text: '前端 / 后端 / 检测 / 集群代码', page: '/help/frontend' },
      { text: 'API 逐接口', page: '/help/api' },
      { text: '数据库与字段', page: '/help/db' },
    ],
  },
]
</script>

<template>
  <div class="help-wrapper">
    <div class="help-tabs">
      <RouterLink
        v-for="t in tabs"
        :key="t.key"
        :to="t.to"
        :class="['help-tab', { active: activeTab === t.key }]"
      >
        {{ t.label }}
      </RouterLink>
    </div>

    <div v-if="!pageKey" class="help-home">
      <h1>帮助中心</h1>
      <p class="lead">只有一本手册，分三块。先看下面最常用的四项，找不到再按身份进对应的那一块。</p>

      <div class="quick-grid">
        <RouterLink v-for="q in quick" :key="q.page" :to="q.page" class="quick">
          <strong>{{ q.text }} →</strong>
          <span>{{ q.desc }}</span>
        </RouterLink>
      </div>

      <div class="route-grid">
        <div v-for="p in parts" :key="p.who" class="route-card">
          <h2>{{ p.who }}</h2>
          <p>{{ p.desc }}</p>
          <ul>
            <li v-for="l in p.links" :key="l.page">
              <RouterLink :to="l.page">{{ l.text }} →</RouterLink>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <div v-else class="guide">
      <aside class="sidebar">
        <div class="sidebar-logo">NetSentinel 手册<span>使用 · 运维 · 开发</span></div>
        <template v-for="g in GROUPS" :key="g.name">
          <div class="nav-section">{{ g.name }}</div>
          <template v-for="p in g.pages" :key="p.key">
            <RouterLink :to="`/help/${p.key}`" :class="['nav-page', { current: p.key === pageKey }]">
              {{ p.title }}
            </RouterLink>
            <template v-if="p.key === pageKey">
              <RouterLink
                v-for="t in toc"
                :key="t.id"
                :to="{ hash: `#${t.id}` }"
                replace
                :class="['nav-item', { active: t.id === activeId }]"
              >
                {{ t.text }}
              </RouterLink>
            </template>
          </template>
        </template>
      </aside>
      <div ref="body" class="guide-body" @scroll.passive="onScroll" @click="onClick">
        <main class="main">
          <component :is="page" v-if="page" />
          <div class="pager">
            <RouterLink v-if="pager.prev" :to="`/help/${pager.prev.key}`">← {{ pager.prev.title }}</RouterLink>
            <span v-else />
            <RouterLink v-if="pager.next" :to="`/help/${pager.next.key}`">{{ pager.next.title }} →</RouterLink>
            <span v-else />
          </div>
        </main>
      </div>
    </div>
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
  text-decoration: none;
}

.help-tab:hover {
  color: #e2e8f0;
}

.help-tab.active {
  background: #f0f4f8;
  color: #1d2535;
  font-weight: 600;
}


.help-home {
  flex: 1;
  overflow-y: auto;
  background: #f0f4f8;
  padding: 32px max(40px, calc((100% - 1160px) / 2));
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
