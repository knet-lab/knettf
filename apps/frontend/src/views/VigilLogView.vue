<template>
  <div class="vg-root logv">

    <!-- ── Header ── -->
    <header class="log-head">
      <div class="head-l">
        <button class="vg-btn icon" title="Back to overview" @click="router.push('/vigil')"><el-icon><ArrowLeft /></el-icon></button>
        <h1 class="title">Detection log</h1>
        <span class="count vg-mono">{{ total.toLocaleString() }} records</span>
      </div>
      <div class="head-r">
        <span class="vg-status" :class="statusClass" :title="lastError || ''"><span class="dot" />{{ statusText }}</span>
        <button class="vg-btn" :disabled="loading" title="Refresh" @click="loadRecords()">
          <el-icon :class="{ spin: loading }"><Refresh /></el-icon>
        </button>
      </div>
    </header>

    <!-- ── Filters ── -->
    <div class="filters">
      <div class="vg-seg" role="group" aria-label="Verdict">
        <button v-for="v in VERDICTS" :key="v.value" :class="{ active: f.verdict === v.value }" @click="setFilter('verdict', v.value)">{{ v.label }}</button>
      </div>

      <select v-model="f.type" class="vg-input" aria-label="Attack type" @change="applyFilters()">
        <option value="">All attack types</option>
        <option v-for="t in attackTypes" :key="t" :value="t">{{ t }}</option>
      </select>

      <select v-if="models.length > 1 || f.model" v-model="f.model" class="vg-input" aria-label="Model" @change="applyFilters()">
        <option value="">All models</option>
        <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
      </select>

      <div class="range">
        <input v-model="f.from" class="vg-input" :class="{ invalid: rangeInvalid }" type="datetime-local" step="1" aria-label="From" @change="applyFilters()" />
        <span class="vg-muted">to</span>
        <input v-model="f.to" class="vg-input" :class="{ invalid: rangeInvalid }" type="datetime-local" step="1" aria-label="To" @change="applyFilters()" />
        <div class="presets">
          <button v-for="p in PRESETS" :key="p.label" class="vg-btn small" @click="presetRange(p.minutes)">{{ p.label }}</button>
        </div>
      </div>

      <button v-if="hasFilters" class="vg-btn clear" @click="clearFilters()"><el-icon><Close /></el-icon>Clear filters</button>
    </div>

    <div v-if="rangeInvalid" class="vg-alert">The start time is after the end time — no records can match.</div>
    <div v-else-if="lastError" class="vg-alert">
      <el-icon><WarningFilled /></el-icon>Could not load records ({{ lastError }}).
      <button class="vg-btn" @click="loadRecords()">Retry</button>
    </div>

    <!-- ── Table ── -->
    <div class="vg-card table-card">
      <div class="vg-table-wrap fill">
        <table class="vg-table">
          <thead>
            <tr>
              <th class="num">ID</th><th>Time</th><th>Source</th><th>Destination</th><th>Proto</th>
              <th>Verdict</th><th>Type</th><th>Confidence</th>
              <th title="Model verdict compared with the dataset label (only for labelled traffic)">Ground truth</th>
              <th>Cilium</th><th class="hide-md">Model</th>
            </tr>
          </thead>
          <tbody>
            <template v-if="loading && !records.length">
              <tr v-for="i in 6" :key="'s' + i"><td colspan="11"><div class="vg-skel" /></td></tr>
            </template>
            <tr v-else-if="!records.length">
              <td colspan="11" class="vg-empty">
                No records match the current filters.
                <button v-if="hasFilters" class="vg-btn small inline" @click="clearFilters()">Clear filters</button>
              </td>
            </tr>
            <tr v-for="(r, i) in records" :key="r.id" :class="{ attack: r.is_attack, selected: detailIdx === i }" @click="detailIdx = i">
              <td class="num vg-mono vg-muted">{{ r.id }}</td>
              <td class="vg-mono">{{ fmtTime(r.created_at) }}</td>
              <td class="addr">{{ r.src_ip }}<span class="port">:{{ r.src_port }}</span></td>
              <td class="addr">{{ r.dst_ip }}<span class="port">:{{ r.dst_port }}</span></td>
              <td><span class="vg-badge proto">{{ r.protocol }}</span></td>
              <td><span class="vg-badge" :class="r.is_attack ? 'attack' : 'normal'">{{ r.is_attack ? 'ATTACK' : 'NORMAL' }}</span></td>
              <td>
                <span v-if="r.is_attack" class="vg-type"><span class="sw" :style="{ background: typeColor(r.attack_type) }" />{{ r.attack_type || 'anomaly' }}</span>
                <span v-else class="vg-muted">—</span>
              </td>
              <td>
                <span class="vg-conf">
                  <span class="bar"><span class="fill" :class="r.is_attack ? 'attack' : 'normal'" :style="{ width: ((r.confidence ?? 0) * 100) + '%' }" /></span>
                  <span class="txt">{{ fmtPct(r.confidence) }}</span>
                </span>
              </td>
              <td>
                <span v-if="outcomeOf(r)" class="vg-badge" :class="`out-${outcomeOf(r)}`">{{ OUTCOME_TEXT[outcomeOf(r)!] }}</span>
                <span v-else class="vg-muted">—</span>
              </td>
              <td><span class="vg-badge" :class="`act-${r.cilium_action || 'ignore'}`">{{ r.cilium_action || '—' }}</span></td>
              <td class="vg-mono hide-md">{{ r.model_name }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Page summary (labelled rows on this page) -->
      <div v-if="pageEval" class="page-eval">
        <span class="vg-muted">This page (labelled rows):</span>
        <span class="vg-badge out-TP">{{ pageEval.TP }} caught</span>
        <span class="vg-badge out-FN">{{ pageEval.FN }} missed</span>
        <span class="vg-badge out-FP">{{ pageEval.FP }} false alarms</span>
        <span class="vg-badge out-TN">{{ pageEval.TN }} correct normal</span>
      </div>

      <!-- Pagination -->
      <footer class="pager">
        <span class="vg-muted range-txt">
          {{ total ? `${(offset + 1).toLocaleString()}–${Math.min(offset + limit, total).toLocaleString()} of ${total.toLocaleString()}` : '0 records' }}
        </span>
        <div class="pager-ctl">
          <button class="vg-btn icon" :disabled="offset === 0" title="First page" @click="goPage(0)"><el-icon><DArrowLeft /></el-icon></button>
          <button class="vg-btn icon" :disabled="offset === 0" title="Previous page" @click="goPage(page - 1)"><el-icon><ArrowLeft /></el-icon></button>
          <span class="page-n vg-mono">{{ page + 1 }} / {{ pages }}</span>
          <button class="vg-btn icon" :disabled="page + 1 >= pages" title="Next page" @click="goPage(page + 1)"><el-icon><ArrowRight /></el-icon></button>
          <button class="vg-btn icon" :disabled="page + 1 >= pages" title="Last page" @click="goPage(pages - 1)"><el-icon><DArrowRight /></el-icon></button>
          <select v-model.number="limit" class="vg-input" aria-label="Rows per page" @change="goPage(0)">
            <option v-for="n in [50, 100, 200, 500]" :key="n" :value="n">{{ n }} / page</option>
          </select>
        </div>
      </footer>
    </div>

    <RecordDetailModal
      :record="detail" has-nav
      :can-prev="detailIdx > 0" :can-next="detailIdx >= 0 && detailIdx < records.length - 1"
      @close="detailIdx = -1" @prev="detailIdx--" @next="detailIdx++"
    />
  </div>
</template>

<script lang="ts" setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter, type LocationQuery } from 'vue-router'
import RecordDetailModal from './vigil/RecordDetailModal.vue'
import {
  type VigilRecord, type VigilStats, useVigilApi,
  fmtTime, fmtAgo, fmtPct, typeColor, outcomeOf, OUTCOME_TEXT, startVisiblePolling,
} from './vigil/vigil'
import './vigil/vigil.css'

const route = useRoute()
const router = useRouter()
const apiGet = useVigilApi()

const POLL_MS = 15000
const VERDICTS = [
  { label: 'All', value: '' },
  { label: 'Attacks', value: 'attack' },
  { label: 'Normal', value: 'normal' },
]
const PRESETS = [
  { label: '15m', minutes: 15 },
  { label: '1h', minutes: 60 },
  { label: '24h', minutes: 1440 },
]

// ── Filters (mirrored in the URL query) ──
const f = reactive({ verdict: '', type: '', model: '', from: '', to: '' })
const limit = ref(100)
const offset = ref(0)

const hasFilters = computed(() => Object.values(f).some(Boolean))
const rangeInvalid = computed(() => !!(f.from && f.to && new Date(f.from) > new Date(f.to)))

function readQuery(q: LocationQuery) {
  const s = (k: string) => (typeof q[k] === 'string' ? (q[k] as string) : '')
  f.verdict = ['attack', 'normal'].includes(s('verdict')) ? s('verdict') : ''
  f.type = s('type')
  f.model = s('model')
  f.from = s('from')
  f.to = s('to')
  const size = Number(s('size'))
  limit.value = [50, 100, 200, 500].includes(size) ? size : 100
  offset.value = Math.max(0, (Number(s('page')) || 1) - 1) * limit.value
}

function writeQuery() {
  const q: Record<string, string> = {}
  for (const [k, v] of Object.entries(f)) if (v) q[k] = v
  if (offset.value) q.page = String(page.value + 1)
  if (limit.value !== 100) q.size = String(limit.value)
  router.replace({ query: q })
}

function setFilter<K extends keyof typeof f>(k: K, v: (typeof f)[K]) { f[k] = v; applyFilters() }
function applyFilters() { offset.value = 0; writeQuery() }
function clearFilters() { Object.assign(f, { verdict: '', type: '', model: '', from: '', to: '' }); applyFilters() }

function toLocalInput(d: Date) {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
function presetRange(minutes: number) {
  f.from = toLocalInput(new Date(Date.now() - minutes * 60_000))
  f.to = ''
  applyFilters()
}

// ── Pagination ──
const total = ref(0)
const page = computed(() => Math.floor(offset.value / limit.value))
const pages = computed(() => Math.max(1, Math.ceil(total.value / limit.value)))
function goPage(n: number) {
  offset.value = Math.min(Math.max(0, n), pages.value - 1) * limit.value
  writeQuery()
}

// ── Data ──
const records = ref<VigilRecord[]>([])
const loading = ref(false)
const lastOk = ref<number | null>(null)
const lastError = ref<string | null>(null)
const now = ref(Date.now())
const models = ref<string[]>([])
const statTypes = ref<string[]>([])

const attackTypes = computed(() => {
  const s = new Set(statTypes.value)
  if (f.type) s.add(f.type)
  return [...s].sort()
})

const statusClass = computed(() => (lastError.value ? 'err' : lastOk.value ? (page.value === 0 ? 'ok' : 'paused') : ''))
const statusText = computed(() => {
  if (lastError.value) return 'Update failed'
  if (!lastOk.value) return 'Loading…'
  if (page.value !== 0) return `Auto-refresh paused (page ${page.value + 1}) · ${fmtAgo(lastOk.value, now.value)}`
  return `Live · updated ${fmtAgo(lastOk.value, now.value)}`
})

const pageEval = computed(() => {
  const c = { TP: 0, TN: 0, FP: 0, FN: 0 }
  let n = 0
  for (const r of records.value) {
    const o = outcomeOf(r)
    if (o) { c[o]++; n++ }
  }
  return n ? c : null
})

let reqSeq = 0
async function loadRecords(silent = false) {
  if (rangeInvalid.value) { records.value = []; total.value = 0; return }
  const seq = ++reqSeq
  if (!silent) loading.value = true
  try {
    const p = new URLSearchParams({ limit: String(limit.value), offset: String(offset.value) })
    if (f.verdict === 'attack') p.set('only_attacks', 'true')
    if (f.verdict === 'normal') p.set('only_normal', 'true')
    if (f.type) p.set('attack_type', f.type)
    if (f.model) p.set('model_name', f.model)
    if (f.from) p.set('time_from', new Date(f.from).toISOString())
    if (f.to) p.set('time_to', new Date(f.to).toISOString())
    const d = await apiGet<{ records: VigilRecord[]; total: number }>(`/api/vigil/records/?${p}`)
    if (seq !== reqSeq) return // 过期响应（筛选已变）
    const selectedId = detail.value?.id
    records.value = d.records ?? []
    total.value = d.total ?? 0
    // 刷新后保持弹窗停留在同一条记录
    if (selectedId != null) detailIdx.value = records.value.findIndex(r => r.id === selectedId)
    lastOk.value = Date.now()
    lastError.value = null
  } catch (e: unknown) {
    const err = e as { name?: string; message?: string }
    if (seq === reqSeq) lastError.value = err?.name === 'AbortError' ? 'timeout' : (err?.message || 'network error')
  } finally {
    if (seq === reqSeq) loading.value = false
  }
}

async function loadOptions() {
  const [m, s] = await Promise.allSettled([
    apiGet<{ models: string[] }>('/api/vigil/models/'),
    apiGet<VigilStats>('/api/vigil/stats/'),
  ])
  if (m.status === 'fulfilled') models.value = m.value.models ?? []
  if (s.status === 'fulfilled') {
    statTypes.value = (s.value.by_attack_type ?? []).map(t => t.attack_type).filter((t): t is string => !!t)
  }
}

// ── Detail ──
const detailIdx = ref(-1)
const detail = computed(() => records.value[detailIdx.value] ?? null)

// ── URL → state → fetch ──
watch(() => route.query, q => {
  if (route.path !== '/vigil/log') return
  readQuery(q)
  detailIdx.value = -1
  loadRecords()
}, { immediate: true })

let stopPolling: (() => void) | null = null
let clock: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  loadOptions()
  clock = setInterval(() => { now.value = Date.now() }, 1000)
  // 只在第一页自动刷新：翻页查看时数据不应在眼前移动
  stopPolling = startVisiblePolling(() => { if (page.value === 0) loadRecords(true) }, POLL_MS)
})
onUnmounted(() => {
  stopPolling?.()
  if (clock) clearInterval(clock)
})
</script>

<style scoped>
.logv {
  height: 100%; display: flex; flex-direction: column; gap: 12px;
  padding: 18px 24px 20px; overflow: hidden; font-size: 14px;
}

.log-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.head-l, .head-r { display: flex; align-items: center; gap: 10px; }
.title { margin: 0; font-size: 20px; font-weight: 700; color: #f1f5f9; }
.count { font-size: 13px; color: var(--vg-text-3); }
.vg-btn.icon { width: 32px; padding: 0; justify-content: center; }
.vg-btn.small { height: 28px; padding: 0 9px; font-size: 12px; }
.vg-btn.inline { margin-left: 8px; vertical-align: middle; }

.filters { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.range { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.presets { display: flex; gap: 4px; }
.clear { color: var(--vg-text-3); border-color: transparent; background: none; }

.table-card { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.vg-table-wrap.fill { flex: 1; min-height: 0; }

.page-eval {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 8px 14px; border-top: 1px solid var(--vg-border); font-size: 12px;
}

.pager {
  display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
  padding: 10px 14px; border-top: 1px solid var(--vg-border);
}
.range-txt { font-size: 12px; font-variant-numeric: tabular-nums; }
.pager-ctl { display: flex; align-items: center; gap: 6px; }
.page-n { min-width: 72px; text-align: center; font-size: 13px; color: var(--vg-text-2); }

@media (max-width: 1100px) { .hide-md { display: none; } }
@media (max-width: 640px) {
  .logv { padding: 12px 16px 14px; }
  .title { font-size: 17px; }
  .range-txt { width: 100%; }
}
</style>
