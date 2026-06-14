<template>
  <div class="log-layout">

    <!-- ── Toolbar ── -->
    <div class="toolbar">
      <div class="toolbar-left">
        <span class="toolbar-title">Detection Log</span>
        <span class="toolbar-sub">{{ total }} records</span>
      </div>

      <div class="toolbar-filters">
        <!-- Verdict -->
        <div class="filter-group">
          <button
            v-for="v in VERDICTS" :key="v.value"
            class="filter-btn" :class="{ active: verdict === v.value }"
            @click="verdict = v.value; reload()"
          >{{ v.label }}</button>
        </div>

        <!-- Attack type -->
        <select class="filter-select" v-model="filterAttackType" @change="reload()">
          <option value="">All types</option>
          <option v-for="t in ATTACK_TYPES" :key="t" :value="t">{{ t }}</option>
        </select>

        <!-- Time from -->
        <input class="filter-input" type="datetime-local" v-model="timeFrom" @change="reload()" />
        <span class="filter-sep">~</span>
        <input class="filter-input" type="datetime-local" v-model="timeTo" @change="reload()" />

        <button class="filter-btn active" @click="clearTime()">Clear time</button>
        <button class="refresh-btn" :class="{ spinning: loading }" @click="reload()">↻</button>
      </div>
    </div>

    <!-- ── Table ── -->
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Time</th>
            <th>Source</th>
            <th>Destination</th>
            <th>Proto</th>
            <th>Label</th>
            <th>Verdict</th>
            <th>Confidence</th>
            <th>Attack Type</th>
            <th>Cilium</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading && records.length === 0">
            <td colspan="10"><div class="skeleton" /></td>
          </tr>
          <tr v-else-if="!loading && records.length === 0">
            <td colspan="10" class="table-empty">No records match the current filters.</td>
          </tr>
          <tr
            v-for="r in records" :key="r.id"
            :class="{ 'row-attack': r.is_attack, 'row-clickable': true }"
            @click="openDetail(r.id)"
          >
            <td class="col-id">{{ r.id }}</td>
            <td class="col-time">{{ fmtTime(r.created_at) }}</td>
            <td class="col-addr"><span class="addr-ip">{{ r.src_ip }}</span><span class="addr-port">:{{ r.src_port }}</span></td>
            <td class="col-addr"><span class="addr-ip">{{ r.dst_ip }}</span><span class="addr-port">:{{ r.dst_port }}</span></td>
            <td><span class="proto-tag">{{ r.protocol }}</span></td>
            <td class="col-label">
              <span v-if="r.label" class="label-tag" :class="r.label === 'Normal' ? 'label-normal' : 'label-attack'">
                {{ r.label }}
              </span>
              <span v-else class="col-empty">—</span>
            </td>
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
            <td><span class="action-tag" :class="`action-${r.cilium_action || 'ignore'}`">{{ r.cilium_action || '—' }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── Pagination ── -->
    <div class="pagination">
      <button class="page-btn" :disabled="offset === 0" @click="prevPage()">← Prev</button>
      <span class="page-info">{{ offset + 1 }}–{{ Math.min(offset + limit, total) }} / {{ total }}</span>
      <button class="page-btn" :disabled="offset + limit >= total" @click="nextPage()">Next →</button>
      <select class="page-size" v-model="limit" @change="offset = 0; reload()">
        <option :value="50">50 / page</option>
        <option :value="100">100 / page</option>
        <option :value="200">200 / page</option>
        <option :value="500">500 / page</option>
      </select>
    </div>

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
          <div class="detail-section">
            <div class="detail-section-title">Flow</div>
            <div class="detail-grid">
              <div class="detail-row"><span class="dk">Source</span><span class="dv mono">{{ detailRecord.src_ip }}:{{ detailRecord.src_port }}</span></div>
              <div class="detail-row"><span class="dk">Destination</span><span class="dv mono">{{ detailRecord.dst_ip }}:{{ detailRecord.dst_port }}</span></div>
              <div class="detail-row"><span class="dk">Protocol</span><span class="dv"><span class="proto-tag">{{ detailRecord.protocol }}</span></span></div>
              <div class="detail-row"><span class="dk">Time</span><span class="dv">{{ detailRecord.created_at }}</span></div>
              <div v-if="detailRecord.label" class="detail-row">
                <span class="dk">Ground Truth</span>
                <span class="dv"><span class="label-tag" :class="detailRecord.label === 'Normal' ? 'label-normal' : 'label-attack'">{{ detailRecord.label }}</span></span>
              </div>
            </div>
          </div>
          <div class="detail-section">
            <div class="detail-section-title">Detection Result</div>
            <div class="detail-grid">
              <div class="detail-row"><span class="dk">Model</span><span class="dv mono blue">{{ detailRecord.model_name }}</span></div>
              <div class="detail-row"><span class="dk">Confidence</span><span class="dv">{{ (detailRecord.confidence * 100).toFixed(1) }}%</span></div>
              <div class="detail-row"><span class="dk">Attack Type</span><span class="dv orange">{{ detailRecord.attack_type || '—' }}</span></div>
              <div class="detail-row"><span class="dk">Explanation</span><span class="dv">{{ detailRecord.explanation || '—' }}</span></div>
            </div>
          </div>
          <div v-if="detailRecord.raw_output && Object.keys(detailRecord.raw_output).length" class="detail-section">
            <div class="detail-section-title">ZSL Similarity Ranking</div>
            <div class="zsl-list">
              <div v-for="(sim, lbl) in sortedZsl" :key="lbl" class="zsl-row">
                <span class="zsl-label">{{ lbl }}</span>
                <div class="zsl-track"><div class="zsl-fill" :style="{ width: (sim * 100).toFixed(1) + '%' }" /></div>
                <span class="zsl-val">{{ (sim * 100).toFixed(1) }}%</span>
              </div>
            </div>
          </div>
          <div class="detail-section">
            <div class="detail-section-title">Cilium Response</div>
            <div class="detail-grid">
              <div class="detail-row"><span class="dk">Action</span><span class="dv"><span class="action-tag" :class="`action-${detailRecord.cilium_action || 'ignore'}`">{{ detailRecord.cilium_action || '—' }}</span></span></div>
              <div class="detail-row"><span class="dk">Reason</span><span class="dv">{{ detailRecord.cilium_reason || '—' }}</span></div>
            </div>
          </div>
          <div v-if="detailRecord.flow_input" class="detail-section">
            <div class="detail-section-title">Flow Features</div>
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const VERDICTS = [
  { label: 'All',    value: '' },
  { label: 'Attack', value: 'attack' },
  { label: 'Normal', value: 'normal' },
]

const ATTACK_TYPES = [
  'Dos-TCP SYN flood', 'ddos-TCP SYN flood', 'DoS Get', 'TCP sequence prediction',
  'Slowloris', 'Slow-body', 'Slow-read', 'Slow-range', 'Credentials hijacking',
]

const FLOW_META_KEYS = new Set(['src_ip', 'dst_ip', 'src_port', 'dst_port', 'protocol', 'label'])

// ── Filters ──────────────────────────────────────────────────────────────────
const verdict         = ref('')
const filterAttackType = ref('')
const timeFrom        = ref('')
const timeTo          = ref('')

// ── Pagination ────────────────────────────────────────────────────────────────
const limit  = ref(100)
const offset = ref(0)
const total  = ref(0)

// ── Data ──────────────────────────────────────────────────────────────────────
const records      = ref<any[]>([])
const loading      = ref(false)
const detailRecord = ref<any>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const sortedZsl = computed(() => {
  if (!detailRecord.value?.raw_output) return {}
  const entries = Object.entries(detailRecord.value.raw_output) as [string, number][]
  return Object.fromEntries(entries.sort((a, b) => b[1] - a[1]))
})

const flowFeatures = computed(() => {
  if (!detailRecord.value?.flow_input) return {}
  return Object.fromEntries(
    Object.entries(detailRecord.value.flow_input).filter(([k]) => !FLOW_META_KEYS.has(k))
  )
})

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtTime(iso: string) {
  if (!iso) return '—'
  const d = new Date(iso)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

function clearTime() {
  timeFrom.value = ''
  timeTo.value   = ''
  reload()
}

// ── API ───────────────────────────────────────────────────────────────────────
async function apiFetch(path: string) {
  const res  = await auth.apiFetch(path)
  const json = await res.json()
  return json.data ?? json
}

async function loadRecords() {
  loading.value = true
  try {
    const p = new URLSearchParams({
      limit:  String(limit.value),
      offset: String(offset.value),
    })
    if (verdict.value === 'attack') p.set('only_attacks', 'true')
    if (verdict.value === 'normal') p.set('only_normal',  'true')
    if (filterAttackType.value)     p.set('attack_type',  filterAttackType.value)
    if (timeFrom.value) p.set('time_from', new Date(timeFrom.value).toISOString())
    if (timeTo.value)   p.set('time_to',   new Date(timeTo.value).toISOString())

    const d = await apiFetch(`/api/vigil/records/?${p}`)
    records.value = d.records ?? []
    total.value   = d.total   ?? 0
  } catch { /* keep stale */ }
  finally { loading.value = false }
}

async function openDetail(id: number) {
  try {
    const d = await apiFetch(`/api/vigil/records/${id}/`)
    detailRecord.value = d
  } catch { /* ignore */ }
}

function reload() {
  offset.value = 0
  loadRecords()
}

function prevPage() {
  offset.value = Math.max(0, offset.value - limit.value)
  loadRecords()
}

function nextPage() {
  offset.value = offset.value + limit.value
  loadRecords()
}

onMounted(() => {
  loadRecords()
  pollTimer = setInterval(loadRecords, 15000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.log-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0d1117;
  color: #e6edf3;
  font-family: 'JetBrains Mono', monospace;
  overflow: hidden;
}

/* ── Toolbar ── */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  background: #161b22;
  border-bottom: 1px solid #21262d;
  flex-shrink: 0;
  gap: 12px;
  flex-wrap: wrap;
}
.toolbar-left { display: flex; align-items: baseline; gap: 12px; }
.toolbar-title { font-size: 16px; font-weight: 600; color: #58a6ff; }
.toolbar-sub   { font-size: 12px; color: #8b949e; }

.toolbar-filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.filter-group { display: flex; gap: 4px; }

.filter-btn {
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid #30363d;
  background: #21262d;
  color: #8b949e;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.filter-btn:hover { border-color: #58a6ff; color: #e6edf3; }
.filter-btn.active { background: #1f6feb; border-color: #388bfd; color: #fff; }

.filter-select, .filter-input {
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid #30363d;
  background: #21262d;
  color: #e6edf3;
  font-size: 12px;
  font-family: inherit;
}
.filter-sep { color: #8b949e; font-size: 12px; }

.refresh-btn {
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid #30363d;
  background: #21262d;
  color: #8b949e;
  font-size: 14px;
  cursor: pointer;
  transition: transform 0.3s;
}
.refresh-btn.spinning { animation: spin 0.6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Table ── */
.table-wrap {
  flex: 1;
  overflow: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
thead th {
  position: sticky;
  top: 0;
  background: #161b22;
  color: #8b949e;
  font-weight: 500;
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid #21262d;
  white-space: nowrap;
  z-index: 1;
}
tbody tr {
  border-bottom: 1px solid #21262d;
  transition: background 0.1s;
}
tbody tr:hover { background: #1c2128; }
tbody tr.row-attack { background: rgba(248,81,73,0.05); }
tbody tr.row-attack:hover { background: rgba(248,81,73,0.1); }
tbody tr.row-clickable { cursor: pointer; }
td { padding: 8px 12px; color: #e6edf3; vertical-align: middle; }

.table-empty { text-align: center; color: #8b949e; padding: 40px; }
.skeleton { height: 14px; background: linear-gradient(90deg,#21262d 25%,#30363d 50%,#21262d 75%); border-radius: 4px; animation: shimmer 1.2s infinite; background-size: 200%; }
@keyframes shimmer { to { background-position: -200%; } }

.col-id    { color: #8b949e; width: 60px; }
.col-time  { white-space: nowrap; color: #8b949e; }
.col-addr  { white-space: nowrap; }
.col-model { color: #8b949e; font-size: 11px; }
.col-type  { color: #f0883e; }
.col-empty { color: #30363d; }
.col-label { max-width: 160px; }

.addr-ip   { color: #e6edf3; }
.addr-port { color: #8b949e; font-size: 11px; }

.proto-tag {
  padding: 2px 7px;
  border-radius: 4px;
  background: #21262d;
  color: #79c0ff;
  font-size: 11px;
}
.verdict {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}
.verdict-attack { background: rgba(248,81,73,0.15); color: #f85149; }
.verdict-normal { background: rgba(63,185,80,0.15); color: #3fb950; }

.label-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  white-space: nowrap;
  display: inline-block;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.label-normal { background: rgba(63,185,80,0.12); color: #3fb950; }
.label-attack { background: rgba(240,136,62,0.15); color: #f0883e; }

.conf-wrap { display: flex; align-items: center; gap: 6px; }
.conf-bar  { width: 48px; height: 5px; background: #21262d; border-radius: 3px; overflow: hidden; }
.conf-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.cf-danger { background: #f85149; }
.cf-ok     { background: #3fb950; }
.conf-text { font-size: 11px; color: #8b949e; min-width: 30px; }

.action-tag {
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}
.action-alert  { background: rgba(248,81,73,0.15); color: #f85149; }
.action-ignore { background: #21262d; color: #8b949e; }
.action-drop   { background: rgba(210,153,34,0.15); color: #d2a21f; }

/* ── Pagination ── */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 12px 24px;
  background: #161b22;
  border-top: 1px solid #21262d;
  flex-shrink: 0;
}
.page-btn {
  padding: 5px 14px;
  border-radius: 6px;
  border: 1px solid #30363d;
  background: #21262d;
  color: #e6edf3;
  font-size: 12px;
  cursor: pointer;
}
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-btn:not(:disabled):hover { border-color: #58a6ff; }
.page-info { font-size: 12px; color: #8b949e; min-width: 140px; text-align: center; }
.page-size {
  padding: 5px 8px;
  border-radius: 6px;
  border: 1px solid #30363d;
  background: #21262d;
  color: #e6edf3;
  font-size: 12px;
  font-family: inherit;
}

/* ── Modal ── */
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(1,4,9,0.7);
  display: flex; align-items: center; justify-content: center;
  z-index: 100;
}
.modal {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 12px;
  width: 640px;
  max-width: 95vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #21262d;
}
.modal-title { font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 10px; }
.modal-close {
  background: none; border: none; color: #8b949e;
  font-size: 16px; cursor: pointer; padding: 4px 8px; border-radius: 4px;
}
.modal-close:hover { background: #21262d; color: #e6edf3; }
.modal-body { overflow-y: auto; padding: 16px 20px; display: flex; flex-direction: column; gap: 16px; }

.detail-section { display: flex; flex-direction: column; gap: 8px; }
.detail-section-title { font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: #8b949e; }
.detail-grid { display: flex; flex-direction: column; gap: 6px; }
.detail-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.dk { font-size: 12px; color: #8b949e; min-width: 120px; }
.dv { font-size: 12px; color: #e6edf3; text-align: right; }
.mono { font-family: 'JetBrains Mono', monospace; }
.blue { color: #58a6ff; }
.orange { color: #f0883e; }
.ml-8 { margin-left: 8px; }

.zsl-list { display: flex; flex-direction: column; gap: 6px; }
.zsl-row  { display: flex; align-items: center; gap: 8px; }
.zsl-label { font-size: 11px; color: #8b949e; min-width: 160px; }
.zsl-track { flex: 1; height: 5px; background: #21262d; border-radius: 3px; overflow: hidden; }
.zsl-fill  { height: 100%; background: #58a6ff; border-radius: 3px; }
.zsl-val   { font-size: 11px; color: #e6edf3; min-width: 40px; text-align: right; }

.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 6px;
}
.feature-cell {
  display: flex;
  justify-content: space-between;
  padding: 4px 8px;
  background: #0d1117;
  border-radius: 4px;
}
.fk { font-size: 11px; color: #8b949e; }
.fv { font-size: 11px; color: #e6edf3; }

.modal-fade-enter-active { transition: opacity 0.2s ease; }
.modal-fade-enter-from   { opacity: 0; }
.modal-fade-leave-active { transition: opacity 0.15s ease; }
.modal-fade-leave-to     { opacity: 0; }
</style>
