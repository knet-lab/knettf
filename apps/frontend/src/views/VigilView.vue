<template>
  <div class="vg-root dash">

    <!-- ── Header ── -->
    <header class="dash-head">
      <div>
        <h1 class="title">Network Anomaly Detection</h1>
        <p class="subtitle">Flows observed by Cilium / Hubble, classified by the platform models</p>
      </div>
      <div class="head-actions">
        <span class="vg-status" :class="statusClass" :title="lastError || ''">
          <span class="dot" />{{ statusText }}
        </span>
        <button class="vg-btn" :disabled="refreshing" title="Refresh now" @click="loadAll(true)">
          <el-icon :class="{ spin: refreshing }"><Refresh /></el-icon>
          <span class="hide-sm">Refresh</span>
        </button>
        <button class="vg-btn primary" @click="router.push('/vigil/log')">
          <el-icon><Tickets /></el-icon><span>Full log</span>
        </button>
      </div>
    </header>

    <div v-if="lastError && !hasData" class="vg-alert">
      <el-icon><WarningFilled /></el-icon>
      Could not load detection data ({{ lastError }}).
      <button class="vg-btn" @click="loadAll(true)">Retry</button>
    </div>

    <!-- ── KPIs ── -->
    <section class="kpis" aria-label="Summary">
      <div class="kpi">
        <div class="kpi-l">Flows inspected</div>
        <div class="kpi-v"><RollingNumber :value="stats.total ?? null" /></div>
        <div class="kpi-s">all time</div>
      </div>
      <div class="kpi danger">
        <div class="kpi-l">Attacks</div>
        <div class="kpi-v"><RollingNumber :value="stats.attacks ?? null" /></div>
        <div class="kpi-s">{{ fmtPct(stats.attack_rate, 1) }} of flows</div>
      </div>
      <div class="kpi ok">
        <div class="kpi-l">Normal</div>
        <div class="kpi-v"><RollingNumber :value="stats.normal ?? null" /></div>
        <div class="kpi-s">{{ stats.attack_rate != null ? fmtPct(1 - stats.attack_rate, 1) : '—' }} of flows</div>
      </div>
      <div class="kpi">
        <div class="kpi-l">Latest detection</div>
        <div class="kpi-v small vg-mono">{{ latestAt ? fmtAgo(latestAt, now) : '—' }}</div>
        <div class="kpi-s">{{ latestAt ? fmtTime(new Date(latestAt).toISOString()) : 'no records yet' }}</div>
      </div>
    </section>

    <!-- ── Middle ── -->
    <section class="mid">
      <div class="side-col">
        <div class="vg-card">
          <div class="vg-card-h">
            <span class="vg-card-t">Attack types</span>
            <span class="vg-card-s">click to filter log</span>
          </div>
          <div class="vg-card-b">
            <div v-if="!typeRows.length" class="vg-empty">No attacks recorded yet</div>
            <ul v-else class="bars">
              <li v-for="row in typeRows" :key="row.name">
                <button class="bar-row" @click="openLog({ verdict: 'attack', type: row.raw ?? undefined })">
                  <span class="bar-meta">
                    <span class="vg-type"><span class="sw" :style="{ background: typeColor(row.name) }" />{{ row.name }}</span>
                    <span class="bar-n vg-mono">{{ row.count.toLocaleString() }} <span class="vg-muted">· {{ row.pct }}</span></span>
                  </span>
                  <span class="bar-track"><span class="bar-fill" :style="{ width: row.width + '%', background: typeColor(row.name) }" /></span>
                </button>
              </li>
            </ul>
          </div>
        </div>

        <div class="vg-card">
          <div class="vg-card-h"><span class="vg-card-t">Models</span></div>
          <div class="vg-card-b">
            <div v-if="!modelRows.length" class="vg-empty">No models registered</div>
            <ul v-else class="models">
              <li v-for="m in modelRows" :key="m.name">
                <span class="vg-mono model-name">{{ m.name }}</span>
                <span class="vg-mono vg-muted">{{ m.count != null ? m.count.toLocaleString() + ' flows' : 'no records' }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      <div class="vg-card feed-card">
        <div class="vg-card-h">
          <span class="vg-card-t">Recent attacks</span>
          <span class="vg-card-s">latest {{ attacks.length }}</span>
        </div>
        <div v-if="!attacks.length" class="vg-empty">
          <template v-if="loading">Loading…</template>
          <template v-else>No attacks among the latest detections</template>
        </div>
        <TransitionGroup v-else tag="ul" name="feed" class="feed">
          <li v-for="(r, i) in attacks" :key="r.id">
            <button class="feed-item" :class="{ selected: detail?.id === r.id }" @click="openDetail(attacks, i)">
              <span class="feed-bar" :style="{ background: typeColor(r.attack_type) }" />
              <span class="feed-main">
                <span class="feed-top">
                  <span class="vg-type">{{ r.attack_type || 'anomaly' }}</span>
                  <span v-if="r.cilium_action" class="vg-badge" :class="`act-${r.cilium_action}`">{{ r.cilium_action }}</span>
                  <span class="feed-time vg-mono" :title="fmtTime(r.created_at)">{{ fmtTimeSmart(r.created_at) }}</span>
                </span>
                <span class="feed-flow vg-mono">
                  {{ r.src_ip }}<span class="vg-muted">:{{ r.src_port }}</span>
                  <span class="vg-muted"> → </span>
                  {{ r.dst_ip }}<span class="vg-muted">:{{ r.dst_port }}</span>
                  <span class="vg-badge proto">{{ r.protocol }}</span>
                </span>
                <span class="feed-meta">
                  <span class="vg-mono">{{ r.model_name }}</span>
                  <span>conf {{ fmtPct(r.confidence) }}</span>
                  <span v-if="r.explanation" class="feed-explain">{{ r.explanation }}</span>
                </span>
              </span>
            </button>
          </li>
        </TransitionGroup>
      </div>
    </section>

    <!-- ── Recent detections ── -->
    <section class="vg-card">
      <div class="vg-card-h wrap">
        <div class="h-left">
          <span class="vg-card-t">Recent detections</span>
          <span class="vg-card-s">latest {{ records.length }}</span>
        </div>
        <div class="h-right">
          <select v-if="models.length > 1" v-model="selectedModel" class="vg-input" aria-label="Model" @change="loadRecords(true)">
            <option :value="null">All models</option>
            <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
          </select>
          <div class="vg-seg" role="group" aria-label="Verdict">
            <button :class="{ active: !onlyAttacks }" @click="setOnlyAttacks(false)">All</button>
            <button :class="{ active: onlyAttacks }" @click="setOnlyAttacks(true)">Attacks</button>
          </div>
        </div>
      </div>
      <div class="vg-table-wrap recent-table">
        <table class="vg-table">
          <thead>
            <tr>
              <th>Time</th><th>Source</th><th>Destination</th><th>Proto</th>
              <th>Verdict</th><th>Type</th><th>Confidence</th><th>Cilium</th><th class="hide-md">Model</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading && !records.length"><td colspan="9"><div class="vg-skel" /></td></tr>
            <tr v-else-if="!records.length">
              <td colspan="9" class="vg-empty">No detection records yet — waiting for traffic to be analysed</td>
            </tr>
            <tr v-for="(r, i) in records" :key="r.id" :class="{ attack: r.is_attack, selected: detail?.id === r.id }" @click="openDetail(records, i)">
              <td class="vg-mono" :title="fmtTime(r.created_at)">{{ fmtTimeSmart(r.created_at) }}</td>
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
              <td><span class="vg-badge" :class="`act-${r.cilium_action || 'ignore'}`">{{ r.cilium_action || '—' }}</span></td>
              <td class="vg-mono hide-md">{{ r.model_name }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <RecordDetailModal
      :record="detail" has-nav
      :can-prev="detailIdx > 0" :can-next="detailIdx >= 0 && detailIdx < detailList.length - 1"
      @close="closeDetail" @prev="stepDetail(-1)" @next="stepDetail(1)"
    />
  </div>
</template>

<script lang="ts" setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import RollingNumber from '@/components/RollingNumber.vue'
import RecordDetailModal from './vigil/RecordDetailModal.vue'
import {
  type VigilRecord, type VigilStats, useVigilApi,
  fmtTime, fmtTimeSmart, fmtAgo, fmtPct, typeColor, startVisiblePolling,
} from './vigil/vigil'
import './vigil/vigil.css'

const router = useRouter()
const apiGet = useVigilApi()

const POLL_MS = 15000
const RECENT_LIMIT = 100

// ── State ──
const models = ref<string[]>([])
const selectedModel = ref<string | null>(null)
const onlyAttacks = ref(false)
const stats = reactive<VigilStats>({})
const records = ref<VigilRecord[]>([])
const loading = ref(true)
const refreshing = ref(false)
const lastOk = ref<number | null>(null)
const lastError = ref<string | null>(null)
const now = ref(Date.now())

const hasData = computed(() => lastOk.value != null)

// ── Status ──
const statusClass = computed(() => {
  if (lastError.value) return 'err'
  if (!lastOk.value) return ''
  return now.value - lastOk.value > POLL_MS * 3 ? 'paused' : 'ok'
})
const statusText = computed(() => {
  if (lastError.value) return hasData.value ? `Update failed · data from ${fmtAgo(lastOk.value, now.value)}` : 'Connection error'
  if (!lastOk.value) return 'Connecting…'
  return `Live · updated ${fmtAgo(lastOk.value, now.value)}`
})

// ── Derived ──
const attacks = computed(() =>
  (onlyAttacks.value ? records.value : records.value.filter(r => r.is_attack)).slice(0, 30),
)
const latestAt = computed(() => {
  const t = records.value[0]?.created_at
  return t ? new Date(t).getTime() : null
})

const typeRows = computed(() => {
  const rows = stats.by_attack_type ?? []
  const max = Math.max(...rows.map(r => r.count), 1)
  const sum = rows.reduce((s, r) => s + r.count, 0) || 1
  return rows.map(r => ({
    raw: r.attack_type,
    name: r.attack_type || 'anomaly',
    count: r.count,
    width: (r.count / max) * 100,
    pct: fmtPct(r.count / sum),
  }))
})

const modelRows = computed(() => {
  const counts = new Map((stats.by_model ?? []).map(m => [m.model_name, m.count]))
  const names = new Set([...models.value, ...counts.keys()])
  return [...names].map(name => ({ name, count: counts.get(name) ?? null }))
})

// ── API ──
async function loadModels() {
  try { models.value = (await apiGet<{ models: string[] }>('/api/vigil/models/')).models ?? [] } catch { /* optional */ }
}

async function loadStats() {
  Object.assign(stats, await apiGet<VigilStats>('/api/vigil/stats/'))
}

async function loadRecords(replace = false) {
  const p = new URLSearchParams({ limit: String(RECENT_LIMIT), only_attacks: String(onlyAttacks.value) })
  if (selectedModel.value) p.set('model_name', selectedModel.value)
  const d = await apiGet<{ records: VigilRecord[] }>(`/api/vigil/records/?${p}`)
  const incoming = d.records ?? []
  if (replace || !records.value.length) {
    records.value = incoming
  } else {
    // 只把新记录插到前面，已有行保持不动，避免列表跳动
    const known = new Set(records.value.map(r => r.id))
    const fresh = incoming.filter(r => !known.has(r.id))
    if (fresh.length) records.value = [...fresh, ...records.value].slice(0, RECENT_LIMIT)
  }
}

async function loadAll(manual = false) {
  if (manual) refreshing.value = true
  try {
    await Promise.all([loadStats(), loadRecords()])
    lastOk.value = Date.now()
    lastError.value = null
  } catch (e: any) {
    lastError.value = e?.name === 'AbortError' ? 'timeout' : (e?.message || 'network error')
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function setOnlyAttacks(v: boolean) {
  if (onlyAttacks.value === v) return
  onlyAttacks.value = v
  loading.value = true
  records.value = []
  try { await loadRecords(true) } catch { /* status shows on next poll */ } finally { loading.value = false }
}

function openLog(q: { verdict?: string; type?: string }) {
  router.push({ path: '/vigil/log', query: Object.fromEntries(Object.entries(q).filter(([, v]) => v)) })
}

// ── Detail modal (with prev/next through the list it was opened from) ──
const detailList = ref<VigilRecord[]>([])
const detailIdx = ref(-1)
const detail = computed(() => detailList.value[detailIdx.value] ?? null)

function openDetail(list: VigilRecord[], i: number) {
  detailList.value = [...list]
  detailIdx.value = i
}
function stepDetail(d: number) {
  const n = detailIdx.value + d
  if (n >= 0 && n < detailList.value.length) detailIdx.value = n
}
function closeDetail() { detailIdx.value = -1; detailList.value = [] }

// ── Lifecycle ──
let stopPolling: (() => void) | null = null
let clock: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  clock = setInterval(() => { now.value = Date.now() }, 1000)
  await Promise.all([loadModels(), loadAll()])
  stopPolling = startVisiblePolling(() => loadAll(), POLL_MS)
})
onUnmounted(() => {
  stopPolling?.()
  if (clock) clearInterval(clock)
})
</script>

<style scoped>
.dash {
  height: 100%; overflow-y: auto;
  padding: 22px 28px 32px;
  display: flex; flex-direction: column; gap: 18px;
  font-size: 14px;
}

.dash-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.title { margin: 0 0 4px; font-size: 22px; font-weight: 700; color: #f1f5f9; letter-spacing: -.2px; }
.subtitle { margin: 0; font-size: 13px; color: var(--vg-text-3); }
.head-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

/* KPIs */
.kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.kpi {
  background: var(--vg-surface); border: 1px solid var(--vg-border); border-radius: 12px;
  padding: 14px 18px; position: relative; overflow: hidden;
}
.kpi::before { content: ''; position: absolute; inset: 0 auto 0 0; width: 3px; background: var(--vg-border-strong); }
.kpi.danger::before { background: var(--vg-danger); }
.kpi.ok::before { background: var(--vg-ok); }
.kpi-l { font-size: 12px; color: var(--vg-text-3); margin-bottom: 6px; }
.kpi-v { font-size: 26px; font-weight: 700; color: #f1f5f9; line-height: 1.1; font-variant-numeric: tabular-nums; }
.kpi-v.small { font-size: 20px; line-height: 1.4; }
.kpi-s { margin-top: 4px; font-size: 12px; color: var(--vg-text-3); font-variant-numeric: tabular-nums; }

/* Middle */
.mid { display: grid; grid-template-columns: minmax(260px, 340px) minmax(0, 1fr); gap: 14px; align-items: start; }
.side-col { display: flex; flex-direction: column; gap: 14px; }

.bars { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.bar-row {
  width: 100%; display: flex; flex-direction: column; gap: 6px;
  padding: 7px 8px; margin: 0 -8px; box-sizing: content-box;
  background: none; border: none; border-radius: 8px; cursor: pointer; text-align: left; font: inherit; color: var(--vg-text-2);
}
.bar-row:hover { background: var(--vg-surface-2); }
.bar-row:focus-visible { outline: 2px solid var(--vg-accent); }
.bar-meta { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.bar-n { font-size: 12px; color: var(--vg-text-2); white-space: nowrap; }
.bar-track { height: 5px; background: var(--vg-border); border-radius: 4px; overflow: hidden; }
.bar-fill { display: block; height: 100%; border-radius: 4px; transition: width .5s cubic-bezier(.4, 0, .2, 1); }

.models { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.models li { display: flex; justify-content: space-between; gap: 12px; font-size: 12px; }
.model-name { color: var(--vg-accent); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Feed */
.feed-card { display: flex; flex-direction: column; }
.feed { list-style: none; margin: 0; padding: 0; max-height: 520px; overflow-y: auto; position: relative; }
.feed li + li { border-top: 1px solid var(--vg-border); }
.feed-item {
  width: 100%; display: flex; gap: 12px; padding: 10px 16px;
  background: none; border: none; cursor: pointer; text-align: left; font: inherit; color: inherit;
}
.feed-item:hover, .feed-item.selected { background: var(--vg-surface-2); }
.feed-item:focus-visible { outline: 2px solid var(--vg-accent); outline-offset: -2px; }
.feed-bar { width: 3px; border-radius: 2px; flex-shrink: 0; }
.feed-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.feed-top { display: flex; align-items: center; gap: 8px; }
.feed-time { margin-left: auto; font-size: 12px; color: var(--vg-text-3); }
.feed-flow { font-size: 12px; color: var(--vg-text); display: flex; align-items: center; gap: 2px; flex-wrap: wrap; }
.feed-flow .vg-badge { margin-left: 6px; }
.feed-meta { display: flex; gap: 10px; font-size: 12px; color: var(--vg-text-3); min-width: 0; }
.feed-explain { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }

.feed-enter-active { transition: transform .35s ease, opacity .3s ease; }
.feed-enter-from { transform: translateY(-8px); opacity: 0; }
.feed-move { transition: transform .3s ease; }

/* Recent table */
.vg-card-h.wrap { flex-wrap: wrap; }
.h-left { display: flex; align-items: baseline; gap: 10px; }
.h-right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.recent-table { max-height: 460px; }

@media (max-width: 1100px) {
  .mid { grid-template-columns: 1fr; }
  .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .hide-md { display: none; }
}
@media (max-width: 640px) {
  .dash { padding: 14px 16px 24px; gap: 14px; }
  .title { font-size: 18px; }
  .kpi { padding: 12px 14px; }
  .kpi-v { font-size: 22px; }
  .hide-sm { display: none; }
}
</style>
