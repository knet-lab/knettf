<template>
  <div class="vigil-layout">

    <!-- ── Sidebar ── -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="sidebar-brand">
          <span class="brand-icon">⬡</span>
          <span class="sidebar-title">AI Vigil</span>
        </div>
        <span class="live-pill" :class="wsStatus">
          {{ wsStatus === 'live' ? 'WS' : 'POLL' }}
        </span>
      </div>

      <div class="sidebar-group">
        <div class="sidebar-label">Detection model</div>
        <div class="model-list">
          <div
            v-for="m in models" :key="m"
            class="model-item"
            :class="{ active: selectedModel === m }"
            @click="selectedModel = selectedModel === m ? null : m; loadRecords()"
          >
            <span class="model-dot" />
            {{ m }}
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
          <div class="toggle-switch" :class="{ on: onlyAttacks }" @click="onlyAttacks = !onlyAttacks; loadRecords()">
            <div class="toggle-knob" />
          </div>
        </label>
      </div>

      <div class="sidebar-group" style="margin-top: auto;">
        <div class="sidebar-label">Last updated</div>
        <div class="last-updated">{{ lastRefreshed }}</div>
        <button class="refresh-btn" @click="loadAll">Refresh now</button>
      </div>
    </aside>

    <!-- ── Content ── -->
    <main class="content">

      <!-- Page header -->
      <div class="page-header">
        <div>
          <h1 class="page-title">Network Anomaly Detection</h1>
          <p class="page-subtitle">Real-time AI-powered traffic analysis via Cilium / Hubble</p>
        </div>
      </div>

      <!-- Stats row -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-icon total">⬡</div>
          <div class="stat-body">
            <div class="stat-label">Total Inspected</div>
            <div class="stat-value">{{ stats.total ?? '—' }}</div>
          </div>
        </div>
        <div class="stat-card danger">
          <div class="stat-icon attack">⚠</div>
          <div class="stat-body">
            <div class="stat-label">Attacks Detected</div>
            <div class="stat-value">{{ stats.attacks ?? '—' }}</div>
          </div>
        </div>
        <div class="stat-card ok">
          <div class="stat-icon normal">✓</div>
          <div class="stat-body">
            <div class="stat-label">Normal Flows</div>
            <div class="stat-value">{{ stats.normal ?? '—' }}</div>
          </div>
        </div>
        <div class="stat-card warn">
          <div class="stat-icon rate">%</div>
          <div class="stat-body">
            <div class="stat-label">Attack Rate</div>
            <div class="stat-value">
              {{ stats.attack_rate != null ? (stats.attack_rate * 100).toFixed(1) + '%' : '—' }}
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
              <div v-else class="breakdown-list">
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
              </div>
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
              <div v-else class="model-coverage-list">
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
              </div>
            </div>
          </div>
        </div>

        <!-- Right col: recent attacks feed -->
        <div class="card">
          <div class="card-header">
            <span class="card-title">Recent Attack Events</span>
            <span class="card-subtitle">Latest {{ displayAttacks.length }} detected</span>
          </div>
          <div class="card-body no-pad">
            <div v-if="!displayAttacks.length" class="empty-state" style="padding:32px 0">
              <div class="empty-icon">🛡</div>
              <div>No attacks detected</div>
            </div>
            <div v-else class="attack-feed">
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
            </div>
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
            <tbody>
              <tr v-if="recordsLoading" class="skeleton-row">
                <td colspan="10"><div class="skeleton" /></td>
              </tr>
              <tr v-else-if="records.length === 0">
                <td colspan="10" class="table-empty">
                  No detection records yet — waiting for traffic analysis results
                </td>
              </tr>
              <tr
                v-else
                v-for="r in displayRecords" :key="r.id"
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
            </tbody>
          </table>
        </div>
      </div>

    </main>

    <!-- ── Detail Modal ── -->
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

  </div>
</template>

<script lang="ts" setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

// ── State ──────────────────────────────────────────────────────────────────────
const models = ref<string[]>([])
const selectedModel = ref<string | null>(null)
const onlyAttacks = ref(false)
const lastRefreshed = ref('—')

const formatTime = (iso: string): string => {
  if (!iso) return '—'
  return iso.slice(0, 19).replace('T', ' ')
}

const stats = reactive<any>({})
const records = ref<any[]>([])
const recordsLoading = ref(true)

// 'live' = WS connected, 'poll' = WS down, falling back to polling
const wsStatus = ref<'live' | 'poll'>('poll')


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
async function apiFetch(path: string, opts: RequestInit = {}) {
  const res = await auth.apiFetch(path, opts)
  const json = await res.json()
  return json.data ?? json
}

async function loadModels() {
  const d = await apiFetch('/api/vigil/models/')
  models.value = d.models ?? []
}

async function loadStats() {
  const d = await apiFetch('/api/vigil/stats/')
  Object.assign(stats, d)
}

const loadRecords = async () => {
  recordsLoading.value = true
  const p = new URLSearchParams({ limit: '100', only_attacks: String(onlyAttacks.value) })
  if (selectedModel.value) p.set('model_name', selectedModel.value)
  const d = await apiFetch(`/api/vigil/records/?${p}`)
  records.value = d.records ?? []
  recordsLoading.value = false
}

const openDetail = async (id: number) => {
  const d = await apiFetch(`/api/vigil/records/${id}/`)
  detailRecord.value = d
}

const loadAll = async () => {
  await Promise.all([loadStats(), loadRecords()])
  lastRefreshed.value = formatTime(new Date().toISOString())
}

// ── WebSocket ──────────────────────────────────────────────────────────────────
let ws: WebSocket | null = null
let wsRetryTimer: ReturnType<typeof setTimeout> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null
let autoRefreshTimer: ReturnType<typeof setInterval> | null = null
const wsUrl = (): string => {
  const base = window.location.origin
  return base.replace(/^http/, 'ws') + '/ws/vigil/'
}

const applyLiveEvent = (event: any) => {
  // Prepend to records (max 200 in memory)
  records.value = [event, ...records.value].slice(0, 200)

  // Update stats counters in place
  stats.total = (stats.total ?? 0) + 1
  if (event.is_attack) {
    stats.attacks = (stats.attacks ?? 0) + 1
    // update by_attack_type
    const bt = stats.by_attack_type ?? []
    const idx = bt.findIndex((x: any) => x.attack_type === event.attack_type)
    if (idx >= 0) bt[idx].count++
    else bt.push({ attack_type: event.attack_type, count: 1 })
    stats.by_attack_type = [...bt]
  } else {
    stats.normal = (stats.normal ?? 0) + 1
  }
  stats.attack_rate = stats.total ? stats.attacks / stats.total : 0
  lastRefreshed.value = formatTime(new Date().toISOString())
}

const connectWs = () => {
  if (ws) ws.close()
  try {
    ws = new WebSocket(wsUrl())

    ws.onopen = () => {
      wsStatus.value = 'live'
      // Stop polling — WS is live
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    }

    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data)
        applyLiveEvent(data)
      } catch { /* ignore malformed */ }
    }

    ws.onclose = () => {
      ws = null
      wsStatus.value = 'poll'
      // Fallback to polling while WS is down
      if (!pollTimer) pollTimer = setInterval(loadAll, 10000)
      // Retry WS after 5s
      wsRetryTimer = setTimeout(connectWs, 5000)
    }

    ws.onerror = () => ws?.close()
  } catch {
    wsStatus.value = 'poll'
    if (!pollTimer) pollTimer = setInterval(loadAll, 10000)
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────────
const displayRecords = computed(() =>
  records.value.map(r => ({ ...r, _time: formatTime(r.created_at) }))
)

const displayAttacks = computed(() =>
  displayRecords.value.filter((r: any) => r.is_attack).slice(0, 15)
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
  connectWs()
  autoRefreshTimer = setInterval(loadAll, 30000)
})

onUnmounted(() => {
  ws?.close()
  if (wsRetryTimer) clearTimeout(wsRetryTimer)
  if (pollTimer) clearInterval(pollTimer)
  if (autoRefreshTimer) clearInterval(autoRefreshTimer)
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
  background: #f0f4f8;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* Page header */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.page-title {
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 2px;
}

.page-subtitle {
  font-size: 14px;
  color: #64748b;
  margin: 0;
}

/* ── Stat cards ── */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

@media (max-width: 1000px) {
  .stats-row { grid-template-columns: repeat(2, 1fr); }
}

.stat-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
  transition: box-shadow 0.15s;
}

.stat-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,.08); }

.stat-card.danger { border-left: 3px solid #ef4444; }
.stat-card.ok     { border-left: 3px solid #22c55e; }
.stat-card.warn   { border-left: 3px solid #f59e0b; }

.stat-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}

.stat-icon.total  { background: #eff6ff; color: #3b82f6; }
.stat-icon.attack { background: #fef2f2; color: #ef4444; }
.stat-icon.normal { background: #f0fdf4; color: #22c55e; }
.stat-icon.rate   { background: #fffbeb; color: #f59e0b; font-size: 13px; font-weight: 700; }

.stat-label {
  font-size: 13px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 2px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
  line-height: 1;
}

/* ── Mid row ── */
.mid-row {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  align-items: start;
}

@media (max-width: 1100px) {
  .mid-row { grid-template-columns: 1fr; }
}

.left-col { display: flex; flex-direction: column; }

/* ── Card ── */
.card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
  background: #fafbfc;
}

.card-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.card-subtitle {
  font-size: 13px;
  color: #94a3b8;
}

.card-body { padding: 14px 16px; }

/* Header action chips */
.header-actions { display: flex; gap: 6px; }

.chip-btn {
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  color: #475569;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.12s;
}

.chip-btn:hover { background: #e2e8f0; }
.chip-btn.danger { border-color: #fca5a5; background: #fff1f2; color: #dc2626; }
.chip-btn.danger:hover { background: #fee2e2; }

/* ── Breakdown chart ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 24px 0;
  color: #94a3b8;
  font-size: 14px;
}

.empty-icon { font-size: 28px; opacity: 0.4; }

.breakdown-list { display: flex; flex-direction: column; gap: 10px; }


.breakdown-meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.breakdown-name {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.breakdown-count {
  font-size: 14px;
  color: #6b7280;
  font-variant-numeric: tabular-nums;
}

.breakdown-track {
  height: 6px;
  background: #f1f5f9;
  border-radius: 6px;
  overflow: hidden;
}

.breakdown-fill {
  height: 100%;
  border-radius: 6px;
  background: #ef4444;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.breakdown-fill[data-type="syn_flood"] { background: #ef4444; }
.breakdown-fill[data-type="flood"]     { background: #f97316; }
.breakdown-fill[data-type="port_scan"] { background: #eab308; }
.breakdown-fill[data-type="anomaly"]   { background: #8b5cf6; }

.model-stats {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #f1f5f9;
}

.model-stat-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 3px 0;
}

.model-name-tag {
  font-size: 13px;
  font-family: 'Courier New', monospace;
  color: #3b82f6;
  background: #eff6ff;
  padding: 1px 7px;
  border-radius: 8px;
}

.model-stat-count { font-size: 13px; color: #94a3b8; }

/* ── Model coverage ── */
.model-coverage-list { display: flex; flex-direction: column; gap: 10px; }


.model-coverage-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.model-bar { background: #3b82f6; }

/* ── Attack feed ── */
.card-body.no-pad { padding: 0; }

.attack-feed {
  display: flex;
  flex-direction: column;
  max-height: 420px;
  overflow-y: auto;
}

.attack-event {
  display: flex;
  gap: 0;
  padding: 10px 16px;
  border-bottom: 1px solid #f1f5f9;
  transition: background 0.1s;
}

.attack-event:last-child { border-bottom: none; }
.attack-event:hover { background: #fff8f8; }

.event-indicator {
  width: 3px;
  border-radius: 2px;
  margin-right: 12px;
  flex-shrink: 0;
  background: #ef4444;
}

.event-indicator[data-type="syn_flood"] { background: #ef4444; }
.event-indicator[data-type="flood"]     { background: #f97316; }
.event-indicator[data-type="port_scan"] { background: #eab308; }
.event-indicator[data-type="anomaly"]   { background: #8b5cf6; }

.event-body { flex: 1; min-width: 0; }

.event-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.event-type {
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #dc2626;
}

.event-time {
  margin-left: auto;
  font-size: 14px;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.event-flow {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 3px;
  font-family: 'Courier New', monospace;
  font-size: 14px;
  color: #374151;
}

.flow-arrow { color: #94a3b8; font-size: 14px; }

.flow-proto {
  font-size: 14px;
  font-weight: 600;
  background: #eff6ff;
  color: #3b82f6;
  padding: 0 5px;
  border-radius: 6px;
  margin-left: 2px;
}

.event-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.event-model {
  font-size: 14px;
  font-family: 'Courier New', monospace;
  color: #3b82f6;
  background: #eff6ff;
  padding: 0 6px;
  border-radius: 6px;
}

.event-conf {
  font-size: 14px;
  color: #64748b;
}

.event-explain {
  font-size: 14px;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px;
}

/* ── Log table ── */
.log-card { overflow: hidden; }

.table-wrap { overflow-x: auto; }

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

thead { position: sticky; top: 0; z-index: 1; }

th {
  background: #f8fafc;
  color: #64748b;
  font-size: 14px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 9px 12px;
  text-align: left;
  border-bottom: 1px solid #e2e8f0;
  white-space: nowrap;
}

td {
  padding: 8px 12px;
  border-bottom: 1px solid #f1f5f9;
  color: #374151;
  vertical-align: middle;
}

tr:last-child td { border-bottom: none; }

tr:hover td { background: #f8fafc; }

tr.row-attack td { background: #fff8f8; }
tr.row-attack:hover td { background: #fef2f2; }

.table-empty {
  text-align: center;
  color: #94a3b8;
  padding: 32px;
  font-size: 13px;
}

/* Skeleton loader */
.skeleton-row td { padding: 12px; }
.skeleton {
  height: 12px;
  background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
  background-size: 200% 100%;
  border-radius: 6px;
  animation: shimmer 1.4s infinite;
}

@keyframes shimmer { to { background-position: -200% 0; } }

/* Table cell styles */
.col-id    { color: #94a3b8; font-size: 13px; width: 40px; }
.col-time  { color: #94a3b8; font-variant-numeric: tabular-nums; white-space: nowrap; }
.col-addr  { font-family: 'Courier New', monospace; white-space: nowrap; }
.col-model { color: #3b82f6; font-size: 13px; font-family: 'Courier New', monospace; }
.col-type  { color: #d97706; font-size: 13px; }

.addr-ip   { color: #374151; }
.addr-port { color: #94a3b8; font-size: 13px; }

.proto-tag {
  display: inline-block;
  padding: 1px 7px;
  background: #eff6ff;
  color: #3b82f6;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
}

/* Verdict badge */
.verdict {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.verdict-attack {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fca5a5;
}

.verdict-normal {
  background: #f0fdf4;
  color: #16a34a;
  border: 1px solid #86efac;
}

/* Confidence bar */
.conf-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}

.conf-bar {
  width: 48px;
  height: 4px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
}

.conf-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}

.cf-danger { background: #ef4444; }
.cf-ok     { background: #22c55e; }

.conf-text { font-size: 13px; color: #64748b; font-variant-numeric: tabular-nums; }

/* Cilium action tag */
.action-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.action-drop       { background: #fef2f2; color: #dc2626; border: 1px solid #fca5a5; }
.action-rate_limit { background: #fffbeb; color: #d97706; border: 1px solid #fcd34d; }
.action-alert      { background: #eff6ff; color: #2563eb; border: 1px solid #93c5fd; }
.action-ignore     { background: #f8fafc; color: #94a3b8; border: 1px solid #e2e8f0; }

.event-action {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.row-clickable { cursor: pointer; }

/* ── Modal ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
}

.modal {
  background: #fff;
  border-radius: 18px;
  box-shadow: 0 20px 60px rgba(0,0,0,.25);
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
  padding: 14px 20px;
  border-bottom: 1px solid #e2e8f0;
  background: #fafbfc;
  flex-shrink: 0;
}

.modal-title {
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 10px;
}

.ml-8 { margin-left: 8px; }

.modal-close {
  background: none;
  border: none;
  color: #94a3b8;
  font-size: 16px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
  transition: background 0.1s;
}
.modal-close:hover { background: #f1f5f9; color: #475569; }

.modal-body {
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}


.detail-section-title {
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: #64748b;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid #f1f5f9;
}

.detail-grid { display: flex; flex-direction: column; gap: 5px; }

.detail-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  font-size: 14px;
}

.dk {
  width: 120px;
  flex-shrink: 0;
  color: #94a3b8;
  font-size: 13px;
}

.dv { color: #1e293b; word-break: break-all; }
.dv.mono { font-family: 'Courier New', monospace; }
.dv.blue { color: #3b82f6; font-family: 'Courier New', monospace; }
.dv.orange { color: #d97706; font-weight: 600; }

/* ZSL */
.zsl-list { display: flex; flex-direction: column; gap: 6px; }
.zsl-row { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.zsl-label { width: 140px; flex-shrink: 0; color: #374151; font-weight: 500; }
.zsl-track {
  flex: 1;
  height: 6px;
  background: #f1f5f9;
  border-radius: 6px;
  overflow: hidden;
}
.zsl-fill { height: 100%; background: #3b82f6; border-radius: 6px; }
.zsl-val { width: 44px; text-align: right; color: #64748b; font-variant-numeric: tabular-nums; }

/* Feature grid */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px 12px;
}

.feature-cell {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px 6px;
  background: #f8fafc;
  border-radius: 8px;
  font-size: 13px;
}

.fk { color: #64748b; }
.fv { color: #1e293b; font-variant-numeric: tabular-nums; font-family: 'Courier New', monospace; }
</style>
