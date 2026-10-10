<template>
  <div class="vigil-layout">

    <!-- ── Sidebar (wide) ── -->
    <aside class="sidebar wide-sidebar">
      <div class="sidebar-header">
        <div class="sidebar-brand">
          <span class="brand-icon">⬡</span>
          <span class="sidebar-title">AI Vigil</span>
        </div>
        <span class="live-pill live">LIVE</span>
      </div>
      <div class="sidebar-group">
        <div class="sidebar-label">Detection model</div>
        <div class="model-list">
          <div v-for="m in models" :key="m" class="model-item"
            :class="{ active: selectedModel === m }"
            @click="selectedModel = selectedModel === m ? null : m; loadRecords(true)">
            <span class="model-dot" />{{ m }}
          </div>
          <div v-if="!models.length" class="model-item-empty">No models registered</div>
        </div>
        <div v-if="selectedModel" class="model-active-hint">
          Filtering: <span class="model-active-name">{{ selectedModel }}</span>
        </div>
      </div>
      <div class="sidebar-group">
        <div class="sidebar-label">Display</div>
        <label class="toggle-row">
          <span>Attacks only</span>
          <div class="toggle-switch" :class="{ on: onlyAttacks }"
            @click="onlyAttacks = !onlyAttacks; loadRecords(true)">
            <div class="toggle-knob" />
          </div>
        </label>
      </div>
      <div class="sidebar-group" style="margin-top: auto;">
        <div class="sidebar-label">{{ tzOffset }} · {{ tz }}</div>
        <div class="last-updated clock">{{ nowClock }}</div>
      </div>
      <div class="sidebar-group">
        <div class="sidebar-label">Last updated</div>
        <div class="last-updated">{{ lastRefreshed }}</div>
        <button class="refresh-btn" @click="loadAll">Refresh now</button>
      </div>
    </aside>

    <!-- ── Sidebar drawer (narrow) ── -->
    <el-drawer v-model="sidebarOpen" direction="ltr" size="80%"
        :show-close="false" :with-header="false" class="sidebar-drawer">
      <div class="sidebar drawer-sidebar">
        <div class="sidebar-header">
          <div class="sidebar-brand">
            <span class="brand-icon">⬡</span>
            <span class="sidebar-title">AI Vigil</span>
          </div>
          <span class="live-pill live">LIVE</span>
        </div>
        <div class="sidebar-group">
          <div class="sidebar-label">Detection model</div>
          <div class="model-list">
            <div v-for="m in models" :key="m" class="model-item"
              :class="{ active: selectedModel === m }"
              @click="selectedModel = selectedModel === m ? null : m; loadRecords(true); sidebarOpen = false">
              <span class="model-dot" />{{ m }}
            </div>
            <div v-if="!models.length" class="model-item-empty">No models registered</div>
          </div>
        </div>
        <div class="sidebar-group">
          <div class="sidebar-label">Display</div>
          <label class="toggle-row">
            <span>Attacks only</span>
            <div class="toggle-switch" :class="{ on: onlyAttacks }"
              @click="onlyAttacks = !onlyAttacks; loadRecords(true)">
              <div class="toggle-knob" />
            </div>
          </label>
        </div>
        <div class="sidebar-group" style="margin-top: auto;">
          <div class="sidebar-label">Last updated</div>
          <div class="last-updated">{{ lastRefreshed }}</div>
          <button class="refresh-btn" @click="loadAll; sidebarOpen = false">Refresh now</button>
        </div>
      </div>
    </el-drawer>

    <!-- ── Content ── -->
    <main class="content">

      <!-- Page header -->
      <div class="page-header">
        <div style="display:flex;align-items:flex-start;gap:10px">
          <button class="narrow-only sidebar-open-btn" @click="sidebarOpen = true">☰</button>
          <div>
            <h1 class="page-title">Network Anomaly Detection</h1>
            <p class="page-subtitle">Real-time AI-powered traffic analysis via Cilium / Hubble</p>
          </div>
        </div>
      </div>

      <!-- Stats row -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-icon total">⬡</div>
          <div class="stat-body">
            <div class="stat-label">Total Inspected</div>
            <div class="stat-value"><RollingNumber :value="stats.total ?? null" /></div>
          </div>
        </div>
        <div class="stat-card danger">
          <div class="stat-icon attack">⚠</div>
          <div class="stat-body">
            <div class="stat-label">Attacks Detected</div>
            <div class="stat-value"><RollingNumber :value="stats.attacks ?? null" /></div>
          </div>
        </div>
        <div class="stat-card ok">
          <div class="stat-icon normal">✓</div>
          <div class="stat-body">
            <div class="stat-label">Normal Flows</div>
            <div class="stat-value"><RollingNumber :value="stats.normal ?? null" /></div>
          </div>
        </div>
        <div class="stat-card warn">
          <div class="stat-icon rate">%</div>
          <div class="stat-body">
            <div class="stat-label">Attack Rate</div>
            <div class="stat-value">
              <RollingNumber :value="stats.attack_rate != null ? stats.attack_rate * 100 : null" :decimals="1" suffix="%" />
            </div>
          </div>
        </div>
      </div>

      <!-- Middle row -->
      <div class="mid-row">

        <!-- Left col: attack breakdown + model coverage -->
        <div class="left-col">
          <div class="card">
            <div class="card-header">
              <span class="card-title">Attack Type Breakdown</span>
            </div>
            <div class="card-body">
              <div v-if="!stats.by_attack_type?.length" class="empty-state">
                <div class="empty-icon">◎</div>
                <div>No attacks recorded yet</div>
              </div>
              <TransitionGroup v-else tag="div" name="list-item" class="breakdown-list">
                <div v-for="row in stats.by_attack_type" :key="row.attack_type" class="breakdown-row">
                  <div class="breakdown-meta">
                    <span class="breakdown-name">{{ row.attack_type || 'unknown' }}</span>
                    <span class="breakdown-count">{{ row.count }}</span>
                  </div>
                  <div class="breakdown-track">
                    <div
                      class="breakdown-fill"
                      :style="{ width: barWidth(row.count) + '%' }"
                      :data-type="row.attack_type"
                    />
                  </div>
                </div>
              </TransitionGroup>
            </div>
          </div>

          <div class="card" style="margin-top:14px">
            <div class="card-header">
              <span class="card-title">Model Coverage</span>
            </div>
            <div class="card-body">
              <div v-if="!stats.by_model?.length" class="empty-state">
                <div class="empty-icon">◎</div>
                <div>No data yet</div>
              </div>
              <TransitionGroup v-else tag="div" name="list-item" class="model-coverage-list">
                <div v-for="m in stats.by_model" :key="m.model_name" class="model-coverage-row">
                  <div class="model-coverage-meta">
                    <span class="model-name-tag">{{ m.model_name }}</span>
                    <span class="model-stat-count">{{ m.count }} flows</span>
                  </div>
                  <div class="breakdown-track">
                    <div
                      class="breakdown-fill model-bar"
                      :style="{ width: modelBarWidth(m.count) + '%' }"
                    />
                  </div>
                </div>
              </TransitionGroup>
            </div>
          </div>
        </div>

        <!-- Right col: recent attacks feed -->
        <div class="card">
          <div class="card-header">
            <span class="card-title">Recent Attack Events</span>
            <div style="display:flex;align-items:center;gap:12px">
              <span class="card-subtitle">Latest {{ displayAttacks.length }} detected</span>
              <button class="log-link-btn" @click="router.push('/vigil/log')">View log →</button>
            </div>
          </div>
          <div class="card-body no-pad">
            <div v-if="!displayAttacks.length" class="empty-state" style="padding:32px 0">
              <div class="empty-icon">🛡</div>
              <div>No attacks detected</div>
            </div>
            <TransitionGroup v-else tag="div" name="feed" class="attack-feed">
              <div
                v-for="r in displayAttacks" :key="r.id"
                class="attack-event row-clickable"
                @click="openDetail(r.id)"
              >
                <div class="event-indicator" :data-type="r.attack_type" />
                <div class="event-body">
                  <div class="event-top">
                    <span class="event-type">{{ r.attack_type || 'anomaly' }}</span>
                    <span class="event-action" :class="`action-${r.cilium_action || 'ignore'}`">
                      {{ r.cilium_action || '—' }}
                    </span>
                    <span class="event-time">{{ r._time }}</span>
                  </div>
                  <div class="event-flow">
                    <span class="flow-addr">{{ r.src_ip }}:{{ r.src_port }}</span>
                    <span class="flow-arrow">→</span>
                    <span class="flow-addr">{{ r.dst_ip }}:{{ r.dst_port }}</span>
                    <span class="flow-proto">{{ r.protocol }}</span>
                  </div>
                  <div class="event-meta">
                    <span class="event-model">{{ r.model_name }}</span>
                    <span class="event-conf">conf {{ (r.confidence * 100).toFixed(0) }}%</span>
                    <span v-if="r.explanation" class="event-explain">{{ r.explanation }}</span>
                  </div>
                </div>
              </div>
            </TransitionGroup>
          </div>
        </div>

      </div>

      <!-- Detection log -->
      <div class="card log-card">
        <div class="card-header">
          <span class="card-title">Detection Log</span>
          <span class="card-subtitle">{{ displayRecords.length }} records shown</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Time</th>
                <th>Source</th>
                <th>Destination</th>
                <th>Proto</th>
                <th>Model</th>
                <th>Verdict</th>
                <th>Confidence</th>
                <th>Attack type</th>
                <th>Cilium action</th>
              </tr>
            </thead>
            <TransitionGroup tag="tbody" name="log-row">
              <tr v-if="recordsLoading" key="__loading__" class="skeleton-row">
                <td colspan="10"><div class="skeleton" /></td>
              </tr>
              <tr v-if="!recordsLoading && displayRecords.length === 0" key="__empty__">
                <td colspan="10" class="table-empty">
                  No detection records yet — waiting for traffic analysis results
                </td>
              </tr>
              <tr
                v-for="r in (recordsLoading ? [] : displayRecords)" :key="r.id"
                :class="{ 'row-attack': r.is_attack, 'row-clickable': true }"
                @click="openDetail(r.id)"
              >
                <td class="col-id">{{ r.id }}</td>
                <td class="col-time">{{ r._time }}</td>
                <td class="col-addr">
                  <span class="addr-ip">{{ r.src_ip }}</span>
                  <span class="addr-port">:{{ r.src_port }}</span>
                </td>
                <td class="col-addr">
                  <span class="addr-ip">{{ r.dst_ip }}</span>
                  <span class="addr-port">:{{ r.dst_port }}</span>
                </td>
                <td><span class="proto-tag">{{ r.protocol }}</span></td>
                <td class="col-model">{{ r.model_name }}</td>
                <td>
                  <span class="verdict" :class="r.is_attack ? 'verdict-attack' : 'verdict-normal'">
                    {{ r.is_attack ? 'ATTACK' : 'NORMAL' }}
                  </span>
                </td>
                <td>
                  <div class="conf-wrap">
                    <div class="conf-bar">
                      <div class="conf-fill" :style="{ width: ((r.confidence ?? 0) * 100) + '%' }" :class="r.is_attack ? 'cf-danger' : 'cf-ok'" />
                    </div>
                    <span class="conf-text">{{ r.confidence != null ? (r.confidence * 100).toFixed(0) + '%' : '—' }}</span>
                  </div>
                </td>
                <td class="col-type">{{ r.attack_type || '—' }}</td>
                <td>
                  <span class="action-tag" :class="`action-${r.cilium_action || 'ignore'}`">
                    {{ r.cilium_action || '—' }}
                  </span>
                </td>
              </tr>
            </TransitionGroup>
          </table>
        </div>
      </div>

    </main>

    <!-- ── Detail Modal ── -->
    <Transition name="modal-fade">
    <div v-if="detailRecord" class="modal-overlay" @click.self="detailRecord = null">
      <div class="modal">
        <div class="modal-header">
          <span class="modal-title">
            Record #{{ detailRecord.id }}
            <span class="verdict ml-8" :class="detailRecord.is_attack ? 'verdict-attack' : 'verdict-normal'">
              {{ detailRecord.is_attack ? 'ATTACK' : 'NORMAL' }}
            </span>
          </span>
          <button class="modal-close" @click="detailRecord = null">✕</button>
        </div>

        <div class="modal-body">

          <!-- Flow -->
          <div class="detail-section">
            <div class="detail-section-title">Flow</div>
            <div class="detail-grid">
              <div class="detail-row"><span class="dk">Source</span><span class="dv mono">{{ detailRecord.src_ip }}:{{ detailRecord.src_port }}</span></div>
              <div class="detail-row"><span class="dk">Destination</span><span class="dv mono">{{ detailRecord.dst_ip }}:{{ detailRecord.dst_port }}</span></div>
              <div class="detail-row"><span class="dk">Protocol</span><span class="dv"><span class="proto-tag">{{ detailRecord.protocol }}</span></span></div>
              <div class="detail-row"><span class="dk">Time</span><span class="dv">{{ detailRecord.created_at }}</span></div>
              <div v-if="detailRecord.label != null" class="detail-row">
                <span class="dk">Ground Truth</span>
                <span class="dv"><span class="verdict" :class="detailRecord.label === 1 ? 'verdict-attack' : 'verdict-normal'">{{ detailRecord.label === 1 ? 'ATTACK' : 'NORMAL' }}</span></span>
              </div>
            </div>
          </div>

          <!-- Detection -->
          <div class="detail-section">
            <div class="detail-section-title">Detection Result</div>
            <div class="detail-grid">
              <div class="detail-row"><span class="dk">Model</span><span class="dv mono blue">{{ detailRecord.model_name }}</span></div>
              <div class="detail-row"><span class="dk">Confidence</span><span class="dv">{{ (detailRecord.confidence * 100).toFixed(1) }}%</span></div>
              <div class="detail-row"><span class="dk">Attack Type</span><span class="dv orange">{{ detailRecord.attack_type || '—' }}</span></div>
              <div class="detail-row"><span class="dk">Explanation</span><span class="dv">{{ detailRecord.explanation || '—' }}</span></div>
            </div>
          </div>

          <!-- ZSL similarities -->
          <div v-if="detailRecord.raw_output && Object.keys(detailRecord.raw_output).length" class="detail-section">
            <div class="detail-section-title">ZSL Similarity Ranking</div>
            <div class="zsl-list">
              <div v-for="(sim, label) in sortedZsl" :key="label" class="zsl-row">
                <span class="zsl-label">{{ label }}</span>
                <div class="zsl-track">
                  <div class="zsl-fill" :style="{ width: (sim * 100).toFixed(1) + '%' }" />
                </div>
                <span class="zsl-val">{{ (sim * 100).toFixed(1) }}%</span>
              </div>
            </div>
          </div>

          <!-- Cilium -->
          <div class="detail-section">
            <div class="detail-section-title">Cilium Response</div>
            <div class="detail-grid">
              <div class="detail-row"><span class="dk">Action</span><span class="dv"><span class="action-tag" :class="`action-${detailRecord.cilium_action || 'ignore'}`">{{ detailRecord.cilium_action || '—' }}</span></span></div>
              <div class="detail-row"><span class="dk">Reason</span><span class="dv">{{ detailRecord.cilium_reason || '—' }}</span></div>
            </div>
          </div>

          <!-- Flow features -->
          <div v-if="detailRecord.flow_input" class="detail-section">
            <div class="detail-section-title">Flow Features (30)</div>
            <div class="feature-grid">
              <div v-for="(val, key) in flowFeatures" :key="key" class="feature-cell">
                <span class="fk">{{ key }}</span>
                <span class="fv">{{ typeof val === 'number' ? val.toFixed(4) : val }}</span>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
    </Transition>

  </div>
</template>

<script lang="ts" setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import RollingNumber from '@/components/RollingNumber.vue'

const auth = useAuthStore()
const router = useRouter()
const sidebarOpen = ref(false)

// ── State ──────────────────────────────────────────────────────────────────────
const models = ref<string[]>([])
const selectedModel = ref<string | null>(null)
const onlyAttacks = ref(false)
const tz = Intl.DateTimeFormat().resolvedOptions().timeZone
const tzOffset = (() => {
  const o = -new Date().getTimezoneOffset() / 60
  return `UTC${o >= 0 ? '+' : ''}${o}`
})()

const formatTime = (iso: string): string => {
  if (!iso) return '—'
  return formatLocalTime(new Date(iso))
}

const nowClock = ref('')
const formatLocalTime = (d: Date): string => {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

const updateClock = () => {
  nowClock.value = formatLocalTime(new Date())
}
updateClock()
let clockTimer: ReturnType<typeof setInterval> | null = null

const lastRefreshed = ref('—')

const stats = reactive<any>({})
const records = ref<any[]>([])
const recordsLoading = ref(true)

const detailRecord = ref<any>(null)

const sortedZsl = computed(() => {
  if (!detailRecord.value?.raw_output) return {}
  const entries = Object.entries(detailRecord.value.raw_output) as [string, number][]
  return Object.fromEntries(entries.sort((a, b) => b[1] - a[1]))
})

const FLOW_META_KEYS = new Set(['src_ip', 'dst_ip', 'src_port', 'dst_port', 'protocol', 'label'])
const flowFeatures = computed(() => {
  if (!detailRecord.value?.flow_input) return {}
  return Object.fromEntries(
    Object.entries(detailRecord.value.flow_input).filter(([k]) => !FLOW_META_KEYS.has(k))
  )
})

// ── API ────────────────────────────────────────────────────────────────────────
async function apiFetch(path: string, opts: RequestInit = {}, timeoutMs = 8000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await auth.apiFetch(path, { ...opts, signal: controller.signal })
    const json = await res.json()
    return json.data ?? json
  } finally {
    clearTimeout(timer)
  }
}

async function loadModels() {
  try {
    const d = await apiFetch('/api/vigil/models/')
    models.value = d.models ?? []
  } catch { /* keep stale */ }
}

async function loadStats() {
  try {
    const d = await apiFetch('/api/vigil/stats/')
    Object.assign(stats, d)
  } catch { /* keep stale */ }
}

const loadRecords = async (force = false) => {
  if (records.value.length === 0) recordsLoading.value = true
  try {
    const p = new URLSearchParams({ limit: '100', only_attacks: String(onlyAttacks.value) })
    if (selectedModel.value) p.set('model_name', selectedModel.value)
    const d = await apiFetch(`/api/vigil/records/?${p}`)
    const incoming: any[] = d.records ?? []
    if (force || records.value.length === 0) {
      records.value = incoming
    } else {
      const knownIds = new Set(records.value.map((r: any) => r.id))
      const newRows = incoming.filter((r: any) => !knownIds.has(r.id))
      if (newRows.length > 0) {
        records.value = [...newRows, ...records.value].slice(0, 200)
      }
    }
  } catch { /* keep stale */ }
  finally { recordsLoading.value = false }
}

const openDetail = async (id: number) => {
  try {
    const d = await apiFetch(`/api/vigil/records/${id}/`)
    detailRecord.value = d
  } catch { /* ignore */ }
}

const loadAll = async () => {
  await Promise.all([loadStats(), loadRecords()])
  lastRefreshed.value = formatLocalTime(new Date())
}

// ── Polling ────────────────────────────────────────────────────────────────────
const POLL_INTERVAL_MS = 30000
let pollTimer: ReturnType<typeof setInterval> | null = null

// ── Helpers ────────────────────────────────────────────────────────────────────
const displayRecords = computed(() =>
  records.value.map(r => ({ ...r, _time: formatTime(r.created_at) }))
)

const displayAttacks = computed(() =>
  displayRecords.value.filter((r: any) => r.is_attack).slice(0, 30)
)

const barWidth = (count: number) => {
  const max = Math.max(...(stats.by_attack_type ?? []).map((x: any) => x.count), 1)
  return ((count / max) * 100).toFixed(1)
}

const modelBarWidth = (count: number) => {
  const max = Math.max(...(stats.by_model ?? []).map((x: any) => x.count), 1)
  return ((count / max) * 100).toFixed(1)
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────
onMounted(async () => {
  await loadModels()
  await loadAll()
  pollTimer = setInterval(loadAll, POLL_INTERVAL_MS)
  clockTimer = setInterval(updateClock, 1000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (clockTimer) clearInterval(clockTimer)
})
</script>

<style scoped>
/* ── Root layout ── */
.vigil-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
  font-size: 15px;
  font-family: Arial, Helvetica, sans-serif;
}

.narrow-only { display: none; }

@media (max-width: 680px) {
  .wide-sidebar { display: none !important; }
  .narrow-only  { display: flex !important; }

  .content {
    overflow-x: hidden;
  }

  .page-header {
    padding: 12px 12px 8px;
  }

  .page-title  { font-size: 16px; }
  .page-subtitle { font-size: 12px; }

  :deep(.el-table) { font-size: 12px; }

  :deep(.el-table td),
  :deep(.el-table th) { padding: 6px 4px; }

  .stats-row {
    flex-wrap: wrap;
    gap: 8px;
  }

  .stat-card {
    min-width: calc(50% - 4px);
  }
}

:deep(.sidebar-drawer .el-drawer__body) {
  padding: 0;
  background: #1a2233;
}

.drawer-sidebar {
  width: 100% !important;
  height: 100%;
  border-right: none;
}

.sidebar-open-btn {
  flex-shrink: 0;
  margin-top: 4px;
  background: none;
  border: 1px solid #2d3748;
  color: #a0aec0;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 16px;
  cursor: pointer;
  line-height: 1;
}

.sidebar-open-btn:hover { background: #2d3748; color: #e2e8f0; }

/* ───────────────────────── SIDEBAR ───────────────────────── */
.sidebar {
  width: 220px;
  flex-shrink: 0;
  background: #1a2233;
  border-right: 1px solid #2d3748;
  display: flex;
  flex-direction: column;
  gap: 0;
  overflow-y: auto;
  padding-bottom: 16px;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 14px 14px;
  border-bottom: 1px solid #2d3748;
  flex-shrink: 0;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 7px;
}

.brand-icon {
  font-size: 16px;
  color: #3b82f6;
  line-height: 1;
}

.sidebar-title {
  font-size: 14px;
  font-weight: 700;
  color: #e2e8f0;
  letter-spacing: 0.3px;
}

.live-pill {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  padding: 2px 7px;
  border-radius: 20px;
}

.live-pill.live {
  background: #14532d;
  color: #4ade80;
  border: 1px solid #166534;
  animation: pulse-bg 2s infinite;
}

.live-pill.paused {
  background: #1e2d42;
  color: #64748b;
  border: 1px solid #334155;
}

@keyframes pulse-bg {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.65; }
}

.sidebar-group {
  padding: 14px 14px 8px;
  border-bottom: 1px solid #2d3748;
}

.sidebar-label {
  font-size: 14px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: #64748b;
  margin-bottom: 8px;
}

/* Model selector */
.model-list { display: flex; flex-direction: column; gap: 2px; }

.model-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 8px;
  cursor: pointer;
  color: #94a3b8;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.12s, color 0.12s;
  border: 1px solid transparent;
}

.model-item:hover {
  background: #1e2d42;
  color: #cbd5e1;
}

.model-item.active {
  background: #1e3a5f;
  color: #93c5fd;
  border-color: #1d4ed8;
}

.model-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #3b82f6;
  flex-shrink: 0;
}

.model-item-empty {
  font-size: 13px;
  color: #475569;
  padding: 4px 8px;
  font-style: italic;
}

.model-active-hint {
  margin-top: 8px;
  font-size: 14px;
  color: #64748b;
}

.model-active-name {
  color: #93c5fd;
  font-family: 'Courier New', monospace;
}

/* Toggle switch */
.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
  cursor: pointer;
  color: #94a3b8;
  font-size: 14px;
}

.toggle-switch {
  width: 30px;
  height: 16px;
  border-radius: 8px;
  background: #2d3748;
  position: relative;
  cursor: pointer;
  transition: background 0.2s;
  flex-shrink: 0;
}

.toggle-switch.on { background: #2563eb; }

.toggle-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #94a3b8;
  transition: transform 0.2s, background 0.2s;
}

.toggle-switch.on .toggle-knob {
  transform: translateX(14px);
  background: #fff;
}

/* Refresh section */
.last-updated {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
  font-variant-numeric: tabular-nums;
}

.last-updated.clock {
  font-size: 14px;
  color: #cbd5e1;
  font-family: 'Courier New', monospace;
  letter-spacing: 0.04em;
}

.refresh-btn {
  width: 100%;
  padding: 6px;
  background: #1e2d42;
  border: 1px solid #2d3748;
  border-radius: 8px;
  color: #94a3b8;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.12s;
}

.refresh-btn:hover {
  background: #2d3e55;
  color: #cbd5e1;
}

/* ───────────────────────── CONTENT ───────────────────────── */
.content {
  flex: 1;
  background: #0d1117;
  overflow-y: auto;
  padding: 22px 28px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Page header */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: #f1f5f9;
  margin: 0 0 4px;
  letter-spacing: -0.3px;
}

.page-subtitle {
  font-size: 13px;
  color: #475569;
  margin: 0;
}

/* ── Stat cards ── */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

@media (max-width: 1000px) {
  .stats-row { grid-template-columns: repeat(2, 1fr); }
}

.stat-card {
  background: #161b22;
  border: 1px solid #21262d;
  border-radius: 14px;
  padding: 18px 20px;
  display: flex;
  align-items: center;
  gap: 14px;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.stat-card:hover {
  border-color: #30363d;
  box-shadow: 0 4px 20px rgba(0,0,0,.3);
}

.stat-card.danger { border-left: 3px solid #f85149; }
.stat-card.ok     { border-left: 3px solid #3fb950; }
.stat-card.warn   { border-left: 3px solid #d29922; }

.stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  flex-shrink: 0;
}

.stat-icon.total  { background: rgba(59,130,246,.15); color: #60a5fa; }
.stat-icon.attack { background: rgba(248,81,73,.15);  color: #f85149; }
.stat-icon.normal { background: rgba(63,185,80,.15);  color: #3fb950; }
.stat-icon.rate   { background: rgba(210,153,34,.15); color: #d29922; font-size: 13px; font-weight: 700; }

.stat-label {
  font-size: 11px;
  color: #6e7681;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: #e6edf3;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

/* ── Mid row ── */
.mid-row {
  display: grid;
  grid-template-columns: 290px 1fr;
  gap: 16px;
  align-items: start;
}

@media (max-width: 1100px) {
  .mid-row { grid-template-columns: 1fr; }
}

.left-col { display: flex; flex-direction: column; }

/* ── Card ── */
.card {
  background: #161b22;
  border: 1px solid #21262d;
  border-radius: 14px;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 13px 18px;
  border-bottom: 1px solid #21262d;
}

.card-title {
  font-size: 13px;
  font-weight: 600;
  color: #c9d1d9;
  letter-spacing: 0.01em;
}

.card-subtitle {
  font-size: 12px;
  color: #484f58;
}

.card-body { padding: 16px 18px; }

/* Header action chips */
.header-actions { display: flex; gap: 6px; }

.chip-btn {
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid #30363d;
  background: #21262d;
  color: #8b949e;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.chip-btn:hover { background: #30363d; color: #c9d1d9; }
.chip-btn.danger { border-color: #6e2a2a; background: #2a1515; color: #f85149; }
.chip-btn.danger:hover { background: #3a1a1a; }

/* ── Breakdown chart ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 28px 0;
  color: #484f58;
  font-size: 13px;
}

.empty-icon { font-size: 28px; opacity: 0.3; }

.breakdown-list { display: flex; flex-direction: column; gap: 12px; }

.breakdown-meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
}

.breakdown-name {
  font-size: 12px;
  font-weight: 600;
  color: #8b949e;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.breakdown-count {
  font-size: 13px;
  color: #6e7681;
  font-variant-numeric: tabular-nums;
}

.breakdown-track {
  height: 5px;
  background: #21262d;
  border-radius: 6px;
  overflow: hidden;
}

.breakdown-fill {
  height: 100%;
  border-radius: 6px;
  background: #f85149;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.breakdown-fill[data-type="syn_flood"] { background: #f85149; }
.breakdown-fill[data-type="flood"]     { background: #fb923c; }
.breakdown-fill[data-type="port_scan"] { background: #d29922; }
.breakdown-fill[data-type="anomaly"]   { background: #a78bfa; }

.model-stats {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #21262d;
}

.model-stat-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 3px 0;
}

.model-name-tag {
  font-size: 12px;
  font-family: 'Courier New', monospace;
  color: #60a5fa;
  background: rgba(59,130,246,.12);
  padding: 2px 8px;
  border-radius: 8px;
}

.model-stat-count { font-size: 12px; color: #484f58; }

/* ── Model coverage ── */
.model-coverage-list { display: flex; flex-direction: column; gap: 12px; }

.model-coverage-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 5px;
}

.model-bar { background: #1f6feb; }

/* ── Attack feed ── */
.card-body.no-pad { padding: 0; }

.log-link-btn {
  background: none;
  border: 1px solid #30363d;
  border-radius: 6px;
  color: #58a6ff;
  font-size: 12px;
  padding: 3px 10px;
  cursor: pointer;
  transition: background 0.12s;
}
.log-link-btn:hover { background: #1f6feb22; }

.attack-feed {
  display: flex;
  flex-direction: column;
  max-height: 640px;
  overflow-y: auto;
}

.attack-event {
  display: flex;
  gap: 0;
  padding: 11px 18px;
  border-bottom: 1px solid #21262d;
  transition: background 0.1s;
  cursor: pointer;
}

.attack-event:last-child { border-bottom: none; }
.attack-event:hover { background: #1c2128; }

/* ── Attack feed TransitionGroup ── */
.feed-enter-active {
  transition: transform 0.42s cubic-bezier(0.34, 1.3, 0.64, 1), opacity 0.3s ease;
}
.feed-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
  position: absolute;
  width: 100%;
}
.feed-move {
  transition: transform 0.38s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}
.feed-enter-from {
  transform: translateX(-56px);
  opacity: 0;
}
.feed-leave-to {
  opacity: 0;
  transform: translateX(24px);
}

.event-indicator {
  width: 3px;
  border-radius: 2px;
  margin-right: 13px;
  flex-shrink: 0;
  background: #f85149;
}

.event-indicator[data-type="syn_flood"] { background: #f85149; }
.event-indicator[data-type="flood"]     { background: #fb923c; }
.event-indicator[data-type="port_scan"] { background: #d29922; }
.event-indicator[data-type="anomaly"]   { background: #a78bfa; }

.event-body { flex: 1; min-width: 0; }

.event-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.event-type {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #f85149;
}

.event-time {
  margin-left: auto;
  font-size: 12px;
  color: #484f58;
  font-variant-numeric: tabular-nums;
  font-family: 'Courier New', monospace;
  flex-shrink: 0;
}

.event-flow {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 4px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: #8b949e;
}

.flow-arrow { color: #30363d; font-size: 13px; }

.flow-proto {
  font-size: 11px;
  font-weight: 700;
  background: rgba(31,111,235,.2);
  color: #60a5fa;
  padding: 1px 6px;
  border-radius: 6px;
  margin-left: 3px;
  letter-spacing: 0.04em;
}

.event-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.event-model {
  font-size: 12px;
  font-family: 'Courier New', monospace;
  color: #60a5fa;
  background: rgba(59,130,246,.1);
  padding: 1px 6px;
  border-radius: 6px;
}

.event-conf {
  font-size: 12px;
  color: #6e7681;
}

.event-explain {
  font-size: 12px;
  color: #484f58;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

/* ── Log table ── */
.log-card { overflow: hidden; }

.table-wrap { overflow-x: auto; overflow-y: auto; max-height: 480px; }

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

thead { position: sticky; top: 0; z-index: 1; }

th {
  background: #161b22;
  color: #6e7681;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 10px 14px;
  text-align: left;
  border-bottom: 1px solid #21262d;
  white-space: nowrap;
}

td {
  padding: 9px 14px;
  border-bottom: 1px solid #161b22;
  color: #8b949e;
  vertical-align: middle;
}

tr:last-child td { border-bottom: none; }

tr:hover td { background: #1c2128; }

tr.row-attack td { background: rgba(248,81,73,.05); }
tr.row-attack:hover td { background: rgba(248,81,73,.1); }

.table-empty {
  text-align: center;
  color: #484f58;
  padding: 40px;
  font-size: 13px;
}

/* Skeleton loader */
.skeleton-row td { padding: 14px; }
.skeleton {
  height: 10px;
  background: linear-gradient(90deg, #21262d 25%, #2d333b 50%, #21262d 75%);
  background-size: 200% 100%;
  border-radius: 6px;
  animation: shimmer 1.4s infinite;
}

@keyframes shimmer { to { background-position: -200% 0; } }

/* Table cell styles */
.col-id    { color: #484f58; font-size: 12px; width: 40px; font-variant-numeric: tabular-nums; }
.col-time  { color: #6e7681; font-variant-numeric: tabular-nums; white-space: nowrap; font-family: 'Courier New', monospace; font-size: 12px; }
.col-addr  { font-family: 'Courier New', monospace; white-space: nowrap; }
.col-model { color: #60a5fa; font-size: 12px; font-family: 'Courier New', monospace; }
.col-type  { color: #d29922; font-size: 12px; font-weight: 600; }

.addr-ip   { color: #c9d1d9; }
.addr-port { color: #484f58; font-size: 12px; }

.proto-tag {
  display: inline-block;
  padding: 2px 7px;
  background: rgba(31,111,235,.15);
  color: #60a5fa;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

/* Verdict badge */
.verdict {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.verdict-attack {
  background: rgba(248,81,73,.15);
  color: #f85149;
  border: 1px solid rgba(248,81,73,.3);
}

.verdict-normal {
  background: rgba(63,185,80,.12);
  color: #3fb950;
  border: 1px solid rgba(63,185,80,.3);
}

/* Confidence bar */
.conf-wrap {
  display: flex;
  align-items: center;
  gap: 7px;
}

.conf-bar {
  width: 52px;
  height: 4px;
  background: #21262d;
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
}

.conf-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}

.cf-danger { background: #f85149; }
.cf-ok     { background: #3fb950; }

.conf-text { font-size: 12px; color: #6e7681; font-variant-numeric: tabular-nums; }

/* Cilium action tag */
.action-tag, .event-action {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.action-drop       { background: rgba(248,81,73,.15);  color: #f85149; border: 1px solid rgba(248,81,73,.3); }
.action-rate_limit { background: rgba(210,153,34,.15); color: #d29922; border: 1px solid rgba(210,153,34,.3); }
.action-alert      { background: rgba(31,111,235,.15); color: #60a5fa; border: 1px solid rgba(31,111,235,.3); }
.action-ignore     { background: #21262d;              color: #6e7681; border: 1px solid #30363d; }

.row-clickable { cursor: pointer; }

/* ── Modal ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
  backdrop-filter: blur(2px);
}

.modal {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 18px;
  box-shadow: 0 24px 80px rgba(0,0,0,.6);
  width: 100%;
  max-width: 720px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 15px 22px;
  border-bottom: 1px solid #21262d;
  flex-shrink: 0;
}

.modal-title {
  font-size: 15px;
  font-weight: 700;
  color: #e6edf3;
  display: flex;
  align-items: center;
  gap: 10px;
}

.ml-8 { margin-left: 8px; }

.modal-close {
  background: none;
  border: none;
  color: #6e7681;
  font-size: 16px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
  transition: background 0.1s, color 0.1s;
}
.modal-close:hover { background: #21262d; color: #c9d1d9; }

.modal-body {
  overflow-y: auto;
  padding: 18px 22px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.detail-section-title {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  color: #6e7681;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid #21262d;
}

.detail-grid { display: flex; flex-direction: column; gap: 6px; }

.detail-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  font-size: 13px;
}

.dk {
  width: 120px;
  flex-shrink: 0;
  color: #484f58;
  font-size: 12px;
}

.dv { color: #c9d1d9; word-break: break-all; }
.dv.mono { font-family: 'Courier New', monospace; color: #8b949e; }
.dv.blue { color: #60a5fa; font-family: 'Courier New', monospace; }
.dv.orange { color: #d29922; font-weight: 600; }

/* ZSL */
.zsl-list { display: flex; flex-direction: column; gap: 7px; }
.zsl-row { display: flex; align-items: center; gap: 10px; font-size: 12px; }
.zsl-label { width: 140px; flex-shrink: 0; color: #8b949e; font-weight: 500; }
.zsl-track {
  flex: 1;
  height: 5px;
  background: #21262d;
  border-radius: 6px;
  overflow: hidden;
}
.zsl-fill { height: 100%; background: #1f6feb; border-radius: 6px; }
.zsl-val { width: 44px; text-align: right; color: #6e7681; font-variant-numeric: tabular-nums; }

/* Feature grid */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 5px 10px;
}

.feature-cell {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 8px;
  background: #0d1117;
  border: 1px solid #21262d;
  border-radius: 8px;
  font-size: 12px;
}

.fk { color: #6e7681; }
.fv { color: #8b949e; font-variant-numeric: tabular-nums; font-family: 'Courier New', monospace; }

/* ── log-row TransitionGroup (Detection Log) ── */
.log-row-enter-active { transition: opacity 0.35s ease; }
.log-row-enter-from   { opacity: 0; }
.log-row-move         { transition: transform 0.3s ease; }

/* ── list-item TransitionGroup (breakdown / model coverage) ── */
.list-item-enter-active { transition: opacity 0.3s ease, transform 0.3s ease; }
.list-item-leave-active { transition: opacity 0.2s ease; }
.list-item-enter-from   { opacity: 0; transform: translateX(-10px); }
.list-item-leave-to     { opacity: 0; }
.list-item-move         { transition: transform 0.3s ease; }

/* ── Modal Transition ── */
.modal-fade-enter-active { transition: opacity 0.22s ease; }
.modal-fade-leave-active { transition: opacity 0.18s ease; }
.modal-fade-enter-from,
.modal-fade-leave-to     { opacity: 0; }
.modal-fade-enter-active .modal {
  transition: transform 0.28s cubic-bezier(0.34, 1.4, 0.64, 1), opacity 0.22s ease;
}
.modal-fade-enter-from .modal { transform: scale(0.95) translateY(-8px); opacity: 0; }
</style>
