<script setup lang="ts">
import { computed, nextTick, ref, shallowRef, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Monitor, Tools, Reading, FirstAidKit, Upload, SwitchButton, Warning, ArrowRight } from '@element-plus/icons-vue'
import './help/guide.css'

// 手册页面：src/views/help/pages/<key>.vue，路由 /help/<key>
const loaders = import.meta.glob<{ default: Component }>('./help/pages/*.vue')
const load = (key: string) => loaders[`./help/pages/${key}.vue`]

const GROUPS = [
  { name: '使用网站', accent: '#3b82f6', pages: [
    { key: 'use', title: '网页使用' },
    { key: 'en', title: 'User Manual (English)' },
  ] },
  { name: '运维', accent: '#14b8a6', pages: [
    { key: 'prepare', title: '接手准备：账户与 Git' },
    { key: 'health', title: '每日健康检查' },
    { key: 'deploy', title: '改动上线' },
    { key: 'power', title: '开关机 · 重建 · 备份' },
    { key: 'account', title: '账号与令牌' },
    { key: 'trouble', title: '排障与日志' },
  ] },
  { name: '开发参考', accent: '#8b5cf6', pages: [
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
const accent = computed(() => GROUPS.find((g) => g.pages.some((p) => p.key === pageKey.value))?.accent ?? '#3b82f6')
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

// 接手路线：新管理员按顺序读
const path = [
  { when: '第一天', text: '学会用网站', desc: '登录、看检测结果、管理用户。只需要浏览器。', page: '/help/use' },
  { when: '第一天', text: '拿到账户和权限', desc: '服务器登录、Git 账号、各个密码放在哪里。', page: '/help/prepare' },
  { when: '以后每天', text: '花 5 分钟做健康检查', desc: '按清单逐项确认，每一项都写了正常时应该看到什么。', page: '/help/health' },
  { when: '出问题时', text: '按看到的现象查', desc: '先找到和你看到的现象一样的那一条，再照着处理。', page: '/help/trouble' },
]

// 最常做的几件事，一键直达
const quick = [
  { text: '每日健康检查', desc: '确认系统在跑、检测有数据', page: '/help/health', icon: FirstAidKit },
  { text: '改动上线', desc: 'scripts/deploy.sh 怎么用', page: '/help/deploy', icon: Upload },
  { text: '开机恢复', desc: '宿主机重启后让检测恢复', page: '/help/power#startup', icon: SwitchButton },
  { text: '出问题了', desc: '按症状找原因和处理', page: '/help/trouble', icon: Warning },
]

// 手册的三块，对应侧栏的三组
const parts = [
  {
    who: '使用网站', tag: 'USE', accent: '#3b82f6', icon: Monitor,
    desc: '只用浏览器就能完成：登录、管理用户、查看检测结果。不需要登录服务器。',
    links: [
      { text: '网页使用', page: '/help/use' },
      { text: 'User Manual (English)', page: '/help/en' },
    ],
  },
  {
    who: '运维', tag: 'OPERATE', accent: '#14b8a6', icon: Tools,
    desc: '需要登录服务器、照着命令一步步做。每一步都写了怎么做、为什么这样做、做完应该看到什么。',
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
    who: '开发参考（改程序时再看）', tag: 'DEVELOP', accent: '#8b5cf6', icon: Reading,
    desc: '要修改程序时才需要看。日常维护不用读这部分。',
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
      <header class="hh-hero">
        <div class="hh-eyebrow">NetSentinel Handbook</div>
        <h1>帮助中心</h1>
        <p>这本手册写给接手 NetSentinel 的管理员。系统的使用、日常维护和出问题时的处理都由你一个人负责，不需要一次全部看懂。先按下面的「接手路线」从第 1 步做到第 4 步；以后每天只做第 3 步，出问题时看第 4 步。</p>
        <ol class="path">
          <li v-for="(s, i) in path" :key="s.page">
            <RouterLink :to="s.page">
              <span class="p-no">{{ i + 1 }}</span>
              <div><em>{{ s.when }}</em><strong>{{ s.text }}</strong><span>{{ s.desc }}</span></div>
            </RouterLink>
          </li>
        </ol>
        <h3 class="hh-sub">常用操作，直接点开</h3>
        <div class="quick-grid">
          <RouterLink v-for="q in quick" :key="q.page" :to="q.page" class="quick">
            <el-icon class="q-ico"><component :is="q.icon" /></el-icon>
            <div><strong>{{ q.text }}</strong><span>{{ q.desc }}</span></div>
            <el-icon class="q-go"><ArrowRight /></el-icon>
          </RouterLink>
        </div>
      </header>

      <div class="route-grid">
        <div v-for="(p, i) in parts" :key="p.who" class="route-card" :style="{ '--accent': p.accent }">
          <div class="rc-head">
            <el-icon class="rc-ico"><component :is="p.icon" /></el-icon>
            <span class="rc-no">0{{ i + 1 }} · {{ p.tag }}</span>
          </div>
          <h2>{{ p.who }}</h2>
          <p>{{ p.desc }}</p>
          <ul>
            <li v-for="l in p.links" :key="l.page">
              <RouterLink :to="l.page">{{ l.text }}<el-icon><ArrowRight /></el-icon></RouterLink>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <div v-else class="guide" :style="{ '--accent': accent }">
      <aside class="sidebar">
        <div class="sidebar-logo">NetSentinel 手册<span>使用 · 运维 · 开发</span></div>
        <template v-for="g in GROUPS" :key="g.name">
          <div class="nav-section" :style="{ '--dot': g.accent }">{{ g.name }}</div>
          <template v-for="p in g.pages" :key="p.key">
            <RouterLink :to="`/help/${p.key}`" :class="['nav-page', { current: p.key === pageKey }]" :style="{ '--accent': g.accent }">
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
  background: #0f172a;
}

.help-tab {
  padding: 8px 16px;
  font-size: 13px;
  color: #94a3b8;
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
  background: #f1f5f9;
  color: #0f172a;
  font-weight: 600;
}


.help-home {
  flex: 1;
  overflow-y: auto;
  background: #f1f5f9;
  color: #0f172a;
  padding-bottom: 56px;
}

/* 深色 hero，与首页同一视觉语言 */
.hh-hero {
  position: relative;
  overflow: hidden;
  padding: clamp(40px, 7vh, 80px) max(24px, calc((100% - 1240px) / 2)) 112px;
  background:
    radial-gradient(ellipse 55% 90% at 0% 0%, rgba(20,184,166,.28), transparent 60%),
    radial-gradient(ellipse 50% 80% at 100% 100%, rgba(139,92,246,.30), transparent 60%),
    linear-gradient(160deg, #0f172a 0%, #0f172a 100%);
  color: #e2e8f0;
}
.hh-hero::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image: linear-gradient(rgba(255,255,255,.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: linear-gradient(180deg, #000 20%, transparent 90%);
}
.hh-hero > * { position: relative; z-index: 1; }
.hh-eyebrow {
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .14em;
  text-transform: uppercase;
  color: #5eead4;
  padding: 4px 12px;
  border: 1px solid rgba(94,234,212,.35);
  border-radius: 999px;
  margin-bottom: 18px;
}
.hh-hero h1 {
  margin: 0 0 12px;
  font-size: clamp(30px, 3.6vw, 48px);
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #fff;
}
.hh-hero p {
  margin: 0;
  max-width: 62ch;
  font-size: clamp(14px, 1.15vw, 17px);
  line-height: 1.7;
  color: #94a3b8;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 14px;
  margin-top: 32px;
}
.quick {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  background: rgba(255,255,255,.05);
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 12px;
  text-decoration: none;
  backdrop-filter: blur(6px);
  transition: background .15s, border-color .15s, transform .15s;
}
.quick:hover { background: rgba(255,255,255,.10); border-color: rgba(94,234,212,.5); transform: translateY(-2px); }
.q-ico {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  font-size: 20px;
  border-radius: 10px;
  color: #5eead4;
  background: rgba(20,184,166,.15);
}
.quick div { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.quick strong { font-size: 15px; color: #fff; }
.quick span { font-size: 12.5px; color: #94a3b8; }
.q-go { color: #64748b; transition: transform .15s, color .15s; }
.quick:hover .q-go { color: #5eead4; transform: translateX(3px); }

/* 三部分卡片：压住 hero 底边，各自主色 */
.route-grid {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  width: min(1240px, 100% - 48px);
  margin: -64px auto 0;
}
.route-card {
  position: relative;
  overflow: hidden;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 26px 26px 22px;
  box-shadow: 0 8px 24px rgba(15,23,42,.06);
}
.route-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 4px;
  background: var(--accent);
}
.rc-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.rc-ico {
  width: 48px;
  height: 48px;
  font-size: 24px;
  border-radius: 12px;
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 12%, #fff);
}
.rc-no { font-size: 11.5px; font-weight: 700; letter-spacing: .12em; color: #94a3b8; }
.route-card h2 { margin: 0 0 6px; font-size: 20px; color: #0f172a; }
.route-card p { margin: 0 0 16px; font-size: 13.5px; line-height: 1.7; color: #64748b; }
.route-card ul { margin: 0; padding: 0; list-style: none; border-top: 1px solid #f1f5f9; }
.route-card li { border-bottom: 1px solid #f1f5f9; }
.route-card a {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 4px;
  font-size: 14px;
  color: #334155;
  text-decoration: none;
  transition: color .15s, padding .15s;
}
.route-card a .el-icon { color: #cbd5e1; transition: color .15s; }
.route-card a:hover { color: var(--accent); padding-left: 10px; }
.route-card a:hover .el-icon { color: var(--accent); }

.path { list-style: none; margin: 28px 0 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; counter-reset: none; }
.path a { display: flex; gap: 14px; height: 100%; padding: 18px; border-radius: 12px; background: #fff; text-decoration: none; box-shadow: 0 8px 24px rgba(0,0,0,.25); transition: transform .15s; }
.path a:hover { transform: translateY(-2px); }
.p-no { flex-shrink: 0; width: 34px; height: 34px; border-radius: 50%; background: #14b8a6; color: #fff; font-weight: 800; display: flex; align-items: center; justify-content: center; }
.path div { display: flex; flex-direction: column; gap: 3px; }
.path em { font-style: normal; font-size: 12px; font-weight: 700; color: #0d9488; }
.path strong { font-size: 16px; color: #0f172a; }
.path span { font-size: 13px; line-height: 1.6; color: #64748b; }
.hh-sub { margin: 32px 0 0; font-size: 13px; font-weight: 700; letter-spacing: .08em; color: #94a3b8; }
.quick-grid { margin-top: 12px; }

@media (max-width: 700px) {
  .hh-hero { padding: 28px 16px 88px; }
  .route-grid { width: calc(100% - 32px); grid-template-columns: 1fr; }
}
</style>
