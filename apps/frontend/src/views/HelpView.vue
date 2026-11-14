<script setup lang="ts">
import { computed, nextTick, ref, shallowRef, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Monitor, Reading, Notebook, Guide, FirstAidKit, Upload, SwitchButton, Warning, ArrowRight, ArrowLeft, Check } from '@element-plus/icons-vue'
import './help/guide.css'

// 手册页面：src/views/help/pages/<key>.vue，路由 /help/<key>
const loaders = import.meta.glob<{ default: Component }>('./help/pages/*.vue')
const load = (key: string) => loaders[`./help/pages/${key}.vue`]
// 旧地址
const ALIAS: Record<string, string> = { use: 'web', en: 'web' }

// 四本：入门教程（按步骤）、中文项目手册、英文项目手册、网站使用说明（英文）
type HelpPage = { key: string; title: string; desc?: string }
type Book = { id: string; name: string; lang: 'zh' | 'en'; accent: string; tutorial?: boolean; twin?: string; groups: { name: string; pages: HelpPage[] }[] }
const BOOKS: Book[] = [
  { id: 'tutorial', name: '入门教程', lang: 'zh', accent: '#14b8a6', tutorial: true, groups: [
    { name: '按顺序做', pages: [
      { key: 'start', title: '先认识这个项目', desc: '系统做什么、由哪几块组成、日常要做的事' },
      { key: 'prepare', title: '账户、权限与 GitHub', desc: '服务器账户、组权限、GitHub 组织、密钥与提交设置' },
      { key: 'account', title: '网站账号与令牌', desc: '改默认密码、加管理员、服务令牌' },
      { key: 'firstday', title: '接手第一天', desc: '第一天要做完的事，做完进入项目手册' },
    ] },
  ] },
  { id: 'manual', name: '项目手册', lang: 'zh', accent: '#2563eb', twin: 'manual-en', groups: [
    { name: '日常运维', pages: [
      { key: 'health', title: '每日健康检查' },
      { key: 'deploy', title: '改动上线' },
      { key: 'power', title: '开关机 · 重建 · 备份' },
      { key: 'trouble', title: '排障与日志' },
      { key: 'handover', title: '人员交接' },
    ] },
    { name: '开发参考', pages: [
      { key: 'index', title: '1 系统总览' },
      { key: 'frontend', title: '2 前端代码' },
      { key: 'backend', title: '3 后端代码' },
      { key: 'detect', title: '4 检测链路与模型' },
      { key: 'infra', title: '5 集群与 Shell 脚本' },
      { key: 'lab', title: '6 实验脚本' },
      { key: 'api', title: '7 API 逐接口' },
      { key: 'db', title: '8 数据库与字段' },
      { key: 'issues', title: '9 已知问题' },
    ] },
  ] },
  { id: 'manual-en', name: 'Project Handbook', lang: 'en', accent: '#2563eb', twin: 'manual', groups: [
    { name: 'Basics', pages: [
      { key: 'en-overview', title: 'System Overview' },
      { key: 'en-access', title: 'Accounts, Permissions & GitHub' },
    ] },
    { name: 'Operations', pages: [
      { key: 'en-health', title: 'Daily Health Check' },
      { key: 'en-deploy', title: 'Deploying Changes' },
      { key: 'en-power', title: 'Shutdown, Startup & Backup' },
      { key: 'en-trouble', title: 'Troubleshooting & Logs' },
      { key: 'en-handover', title: 'Handover' },
    ] },
  ] },
  { id: 'web', name: 'Web Guide', lang: 'en', accent: '#8b5cf6', groups: [
    { name: 'Using the website', pages: [{ key: 'web', title: 'Web Guide' }] },
  ] },
]
const pagesOf = (b: Book) => b.groups.flatMap((g) => g.pages)
const bookHome = (id: string) => `/help/${pagesOf(BOOKS.find((b) => b.id === id)!)[0]!.key}`

const route = useRoute()
const router = useRouter()
const pageKey = computed(() => (route.params.page as string | undefined) ?? '')
const page = shallowRef<Component | null>(null)
const body = ref<HTMLElement | null>(null)
const toc = ref<{ id: string; text: string }[]>([])
const activeId = ref('')

const book = computed(() => BOOKS.find((b) => pagesOf(b).some((p) => p.key === pageKey.value)))
const accent = computed(() => book.value?.accent ?? '#2563eb')
const STEPS = pagesOf(BOOKS[0]!)
const stepNo = computed(() => (book.value?.tutorial ? STEPS.findIndex((p) => p.key === pageKey.value) + 1 : 0))
const en = computed(() => book.value?.lang === 'en')

// 页底上一篇 / 下一篇：在本书内走；教程最后一步接到项目手册
const pager = computed(() => {
  if (!book.value) return { prev: undefined, next: undefined }
  const list = pagesOf(book.value)
  const i = list.findIndex((p) => p.key === pageKey.value)
  let next: HelpPage | undefined = list[i + 1]
  if (!next && book.value.tutorial) next = { key: 'health', title: '项目手册 · 每日健康检查', desc: '教程完成，以后有具体任务时查项目手册' }
  return { prev: list[i - 1], next }
})
const nextLabel = computed(() => {
  if (en.value) return 'Next'
  if (!stepNo.value) return '下一篇'
  return stepNo.value < STEPS.length ? `下一步 · 第 ${stepNo.value + 1} 步` : '教程完成 · 进入项目手册'
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
    if (ALIAS[key as string]) { router.replace({ path: `/help/${ALIAS[key as string]}`, hash: route.hash }); return }
    if (!loader) { router.replace('/help'); return }
    page.value = (await loader()).default
    await nextTick()
    toc.value = [...(body.value?.querySelectorAll<HTMLElement>('section[id] > h2') ?? [])]
      .map((h) => ({ id: h.parentElement!.id, text: h.textContent ?? '' }))
    await renderUml()
    scrollToHash(route.hash)
    onScroll()
  },
  { immediate: true },
)
watch(() => route.hash, (h) => { if (page.value) scrollToHash(h) })

// 手册里的 UML 图：<pre class="uml"> 写 Mermaid 源码，加载页面后渲染成 SVG；只在有图的页面才加载 mermaid
async function renderUml() {
  const nodes = [...(body.value?.querySelectorAll<HTMLElement>('pre.uml:not([data-processed])') ?? [])]
  if (!nodes.length) return
  const { default: mermaid } = await import('mermaid')
  mermaid.initialize({
    startOnLoad: false, securityLevel: 'strict', theme: 'base', fontFamily: 'inherit',
    themeVariables: { fontSize: '15px', primaryColor: '#ebf4ff', primaryBorderColor: '#2b6cb0', primaryTextColor: '#1a202c', lineColor: '#4a5568' },
    // 不按容器宽度缩小：宽图横向滚动，字号保持可读
    flowchart: { useMaxWidth: false, htmlLabels: true, nodeSpacing: 40, rankSpacing: 50, padding: 12 },
    class: { useMaxWidth: false },
    er: { useMaxWidth: false, fontSize: 14 },
  })
  await mermaid.run({ nodes })
}

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

// 首页四个入口
const entries = [
  { to: bookHome('tutorial'), tag: 'Start here', title: 'Getting Started', lang: 'Chinese', icon: Guide, accent: '#14b8a6',
    desc: 'First step for a new maintainer. Four pages in order: the project at a glance, accounts, permissions and GitHub, default passwords, and your first day.', primary: true },
  { to: bookHome('manual'), tag: 'Reference', title: 'Project Handbook', lang: 'Chinese', icon: Notebook, accent: '#2563eb',
    desc: 'Full handbook: daily operations (health check, deploy, startup, troubleshooting) plus developer reference for code, API and database.' },
  { to: bookHome('manual-en'), tag: 'Reference', title: 'Project Handbook', lang: 'English', icon: Reading, accent: '#2563eb',
    desc: 'Operations and setup in English: overview, accounts and GitHub, health check, deploy, startup, troubleshooting.' },
  { to: bookHome('web'), tag: 'Users', title: 'Web Guide', lang: 'English', icon: Monitor, accent: '#8b5cf6',
    desc: 'How to use the website: sign in, Kubernetes, Terraform scan, AI Vigil, admin console.' },
]

// 最常做的几件事，一键直达项目手册
const quick = [
  { text: 'Daily health check', desc: 'Confirm services are up and detection has data', page: '/help/en-health', icon: FirstAidKit },
  { text: 'Deploy a change', desc: 'Ship your changes to production', page: '/help/en-deploy', icon: Upload },
  { text: 'Startup after reboot', desc: 'Bring detection back after a server restart', page: '/help/en-power', icon: SwitchButton },
  { text: 'Something broke', desc: 'Find the cause by symptom and fix it', page: '/help/en-trouble', icon: Warning },
]
</script>

<template>
  <div class="help-wrapper">
    <div v-if="!pageKey" class="help-home">
      <header class="hh-hero">
        <span class="hh-eyebrow">NetSentinel Help</span>
        <h1>Help Center</h1>
        <p>Taking over the project? Start with Getting Started and work through the four pages in order. For specific tasks later, use the Project Handbook. If you only use the website, the Web Guide is all you need.</p>
        <div class="entry-grid">
          <RouterLink v-for="e in entries" :key="e.to" :to="e.to" :class="['entry', { primary: e.primary }]" :style="{ '--accent': e.accent }">
            <div class="e-top"><el-icon class="e-ico"><component :is="e.icon" /></el-icon><span class="e-tag">{{ e.tag }}</span></div>
            <strong>{{ e.title }}<em>{{ e.lang }}</em></strong>
            <p>{{ e.desc }}</p>
            <span class="e-go">Open<el-icon><ArrowRight /></el-icon></span>
          </RouterLink>
        </div>
      </header>
      <div class="hh-quick">
        <h3 class="hh-sub">Common tasks</h3>
        <div class="quick-grid">
          <RouterLink v-for="q in quick" :key="q.page" :to="q.page" class="quick">
            <el-icon class="q-ico"><component :is="q.icon" /></el-icon>
            <div><strong>{{ q.text }}</strong><span>{{ q.desc }}</span></div>
            <el-icon class="q-go"><ArrowRight /></el-icon>
          </RouterLink>
        </div>
      </div>
    </div>

    <div v-else class="guide" :style="{ '--accent': accent }">
      <aside :class="['sidebar', { tut: book?.tutorial }]">
        <div class="sb-head">
          <RouterLink to="/help" class="sb-home"><el-icon><ArrowLeft /></el-icon>Help home</RouterLink>
          <RouterLink v-if="book?.twin" :to="bookHome(book.twin)" class="sb-lang">{{ en ? '中文' : 'EN' }}</RouterLink>
        </div>
        <div class="sb-book">{{ book?.name }}<span v-if="book?.tutorial">共 {{ STEPS.length }} 步，按顺序做</span></div>
        <div v-for="g in book?.groups" :key="g.name" :class="['sb-group', { ordered: book?.tutorial }]" :style="{ '--g': accent }">
          <div v-if="!book?.tutorial" class="sb-title">{{ g.name }}</div>
          <div v-for="(p, i) in g.pages" :key="p.key" :class="['sb-item', { current: p.key === pageKey, done: book?.tutorial && stepNo > i + 1 }]">
            <RouterLink :to="`/help/${p.key}`" class="sb-link">
              <span v-if="book?.tutorial" class="sb-no"><el-icon v-if="stepNo > i + 1"><Check /></el-icon><template v-else>{{ i + 1 }}</template></span>
              <span v-else class="sb-dot" />
              <span class="sb-text">{{ p.title }}<small v-if="book?.tutorial && p.desc">{{ p.desc }}</small></span>
            </RouterLink>
            <div v-if="p.key === pageKey && toc.length" class="sb-toc">
              <RouterLink
                v-for="t in toc"
                :key="t.id"
                :to="{ hash: `#${t.id}` }"
                replace
                :class="['nav-item', { active: t.id === activeId }]"
              >
                {{ t.text }}
              </RouterLink>
            </div>
          </div>
        </div>
      </aside>
      <div ref="body" class="guide-body" @scroll.passive="onScroll" @click="onClick">
        <main class="main">
          <div v-if="stepNo" class="stepbar">
            <div class="sb-meta"><b>入门教程 · 第 {{ stepNo }} 步</b><span>共 {{ STEPS.length }} 步</span></div>
            <div class="sb-track"><i v-for="(x, i) in STEPS" :key="x.key" :class="{ on: i < stepNo }" /></div>
          </div>
          <component :is="page" v-if="page" />
          <nav class="pager">
            <RouterLink v-if="pager.prev" :to="`/help/${pager.prev.key}`" class="pg prev">
              <small><el-icon><ArrowLeft /></el-icon>{{ en ? 'Previous' : stepNo ? '上一步' : '上一篇' }}</small><strong>{{ pager.prev.title }}</strong>
            </RouterLink>
            <span v-else />
            <RouterLink v-if="pager.next" :to="`/help/${pager.next.key}`" class="pg next">
              <small>{{ nextLabel }}<el-icon><ArrowRight /></el-icon></small><strong>{{ pager.next.title }}</strong>
              <span v-if="pager.next.desc">{{ pager.next.desc }}</span>
            </RouterLink>
          </nav>
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
.quick:hover { transform: translateY(-2px); }
.q-ico {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  font-size: 20px;
  border-radius: 10px;
  color: #2563eb;
  background: #eff6ff;
}
.quick div { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.quick strong { font-size: 15px; color: #fff; }
.quick span { font-size: 12.5px; color: #94a3b8; }
.q-go { color: #64748b; transition: transform .15s, color .15s; }
.quick:hover .q-go { color: #2563eb; transform: translateX(3px); }

.hh-hero { padding-bottom: clamp(40px, 6vh, 64px); }
.entry-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin-top: 32px; }
.entry { display: flex; flex-direction: column; gap: 10px; padding: 22px; border-radius: 14px; text-decoration: none; background: #fff; border-top: 4px solid var(--accent); box-shadow: 0 10px 28px rgba(0,0,0,.25); transition: transform .15s, box-shadow .15s; }
.entry:hover { transform: translateY(-3px); box-shadow: 0 14px 34px rgba(0,0,0,.3), 0 0 0 2px var(--accent); }
.entry:hover strong { color: var(--accent); }
.entry.primary { background: linear-gradient(160deg, #fff 55%, color-mix(in srgb, var(--accent) 12%, #fff)); outline: 2px solid var(--accent); outline-offset: -2px; }
.e-top { display: flex; align-items: center; justify-content: space-between; }
.e-ico { width: 44px; height: 44px; font-size: 22px; border-radius: 12px; color: var(--accent); background: color-mix(in srgb, var(--accent) 12%, #fff); }
.e-tag { font-size: 11.5px; font-weight: 800; letter-spacing: .06em; padding: 3px 10px; border-radius: 999px; color: var(--accent); background: color-mix(in srgb, var(--accent) 10%, #fff); }
.entry.primary .e-tag { color: #fff; background: var(--accent); }
.entry strong { display: flex; align-items: baseline; gap: 8px; font-size: 20px; color: #0f172a; }
.entry strong em { font-style: normal; font-size: 12px; font-weight: 600; color: #94a3b8; }
.entry p { flex: 1; margin: 0; font-size: 13.5px; line-height: 1.7; color: #64748b; }
.e-go { display: inline-flex; align-items: center; gap: 4px; font-size: 13.5px; font-weight: 700; color: var(--accent); }
.hh-quick { width: min(1240px, 100% - 48px); margin: 32px auto 0; }
.hh-quick .hh-sub { color: #64748b; }
.hh-quick .quick { background: #fff; border-color: #e2e8f0; backdrop-filter: none; }
.hh-quick .quick:hover { background: #fff; border-color: #2563eb; box-shadow: 0 6px 18px rgba(37,99,235,.12); }
.hh-quick .quick strong { color: #0f172a; }
.hh-quick .quick span { color: #64748b; }
.hh-quick .q-ico { color: #2563eb; background: #eff6ff; }
.hh-quick .quick:hover .q-go { color: #2563eb; }
.hh-sub { margin: 0; font-size: 13px; font-weight: 700; letter-spacing: .08em; color: #94a3b8; }
.quick-grid { margin-top: 12px; }

@media (max-width: 700px) {
  .hh-hero { padding: 28px 16px 32px; }
  .hh-quick { width: calc(100% - 32px); }
}
</style>
