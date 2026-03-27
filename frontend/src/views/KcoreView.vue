<template>
  <div class="kcore-layout">
    <!-- Left Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">My Clusters</span>
        <el-button size="small" type="primary" @click="openAddCluster">
          <el-icon><Plus /></el-icon>
          Add
        </el-button>
      </div>

      <div v-if="loadingClusters" class="sidebar-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
      </div>
      <div v-else-if="clusters.length === 0" class="sidebar-empty">
        No clusters yet
      </div>
      <div v-else class="cluster-list">
        <div
          v-for="cluster in clusters"
          :key="cluster.id"
          class="cluster-card"
          :class="{ active: selectedCluster?.id === cluster.id }"
          @click="selectCluster(cluster)"
        >
          <div class="cluster-card-name">{{ cluster.name }}</div>
          <el-tag :type="cluster.is_active ? 'success' : 'danger'" size="small" effect="dark">
            {{ cluster.is_active ? 'Active' : 'Inactive' }}
          </el-tag>
        </div>
      </div>
    </aside>

    <!-- Right Content -->
    <main class="content">
      <div v-if="!selectedCluster" class="content-empty">
        <el-icon size="48" color="#4a5568"><Folder /></el-icon>
        <p>Select a cluster from the left</p>
      </div>

      <template v-else>
        <div class="content-header">
          <span class="content-title">{{ selectedCluster.name }}</span>
          <el-tag :type="selectedCluster.is_active ? 'success' : 'danger'" effect="plain">
            {{ selectedCluster.is_active ? 'Active' : 'Inactive' }}
          </el-tag>
        </div>

        <el-tabs v-model="activeTab" class="resource-tabs" @tab-click="onTabChange">
          <!-- Namespaces -->
          <el-tab-pane label="Namespaces" name="namespaces">
            <div class="tab-toolbar">
              <el-button size="small" :loading="loadingResources" @click="loadResources">
                <el-icon><Refresh /></el-icon>
                Refresh
              </el-button>
            </div>
            <el-table :data="resources" v-loading="loadingResources" size="small" stripe>
              <el-table-column label="Name" min-width="200">
                <template #default="{ row }">{{ row.metadata?.name }}</template>
              </el-table-column>
              <el-table-column label="Status" width="120">
                <template #default="{ row }">
                  <el-tag
                    :type="row.status?.phase === 'Active' ? 'success' : 'warning'"
                    size="small"
                  >
                    {{ row.status?.phase ?? '—' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="Created" min-width="180">
                <template #default="{ row }">
                  {{ formatTime(row.metadata?.creation_timestamp) }}
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- Pods -->
          <el-tab-pane label="Pods" name="pods">
            <div class="tab-toolbar">
              <el-select
                v-model="selectedNamespace"
                placeholder="Select Namespace"
                size="small"
                style="width: 200px"
                @change="loadResources"
              >
                <el-option
                  v-for="ns in namespaceList"
                  :key="ns"
                  :label="ns"
                  :value="ns"
                />
              </el-select>
              <el-button size="small" :loading="loadingResources" @click="loadResources">
                <el-icon><Refresh /></el-icon>
                Refresh
              </el-button>
            </div>
            <el-table :data="resources" v-loading="loadingResources" size="small" stripe>
              <el-table-column label="Name" min-width="220">
                <template #default="{ row }">{{ row.metadata?.name }}</template>
              </el-table-column>
              <el-table-column label="Status" width="100">
                <template #default="{ row }">
                  <el-tag :type="podStatusType(row.status?.phase)" size="small">
                    {{ row.status?.phase ?? '—' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="Pod IP" width="130">
                <template #default="{ row }">{{ row.status?.pod_ip ?? '—' }}</template>
              </el-table-column>
              <el-table-column label="Node" min-width="150">
                <template #default="{ row }">{{ row.spec?.node_name ?? '—' }}</template>
              </el-table-column>
              <el-table-column label="Created" min-width="160">
                <template #default="{ row }">
                  {{ formatTime(row.metadata?.creation_timestamp) }}
                </template>
              </el-table-column>
              <el-table-column label="Actions" width="90" fixed="right">
                <template #default="{ row }">
                  <el-button
                    size="small"
                    text
                    type="primary"
                    @click="openLogs(row)"
                  >
                    Logs
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- Deployments -->
          <el-tab-pane label="Deployments" name="deployments">
            <div class="tab-toolbar">
              <el-select
                v-model="selectedNamespace"
                placeholder="Select Namespace"
                size="small"
                style="width: 200px"
                @change="loadResources"
              >
                <el-option v-for="ns in namespaceList" :key="ns" :label="ns" :value="ns" />
              </el-select>
              <el-button size="small" :loading="loadingResources" @click="loadResources">
                <el-icon><Refresh /></el-icon>
                Refresh
              </el-button>
            </div>
            <el-table :data="resources" v-loading="loadingResources" size="small" stripe>
              <el-table-column label="Name" min-width="220">
                <template #default="{ row }">{{ row.metadata?.name }}</template>
              </el-table-column>
              <el-table-column label="Desired" width="90">
                <template #default="{ row }">{{ row.spec?.replicas ?? '—' }}</template>
              </el-table-column>
              <el-table-column label="Ready" width="80">
                <template #default="{ row }">{{ row.status?.ready_replicas ?? 0 }}</template>
              </el-table-column>
              <el-table-column label="Available" width="80">
                <template #default="{ row }">{{ row.status?.available_replicas ?? 0 }}</template>
              </el-table-column>
              <el-table-column label="Created" min-width="160">
                <template #default="{ row }">
                  {{ formatTime(row.metadata?.creation_timestamp) }}
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- Services -->
          <el-tab-pane label="Services" name="services">
            <div class="tab-toolbar">
              <el-select
                v-model="selectedNamespace"
                placeholder="Select Namespace"
                size="small"
                style="width: 200px"
                @change="loadResources"
              >
                <el-option v-for="ns in namespaceList" :key="ns" :label="ns" :value="ns" />
              </el-select>
              <el-button size="small" :loading="loadingResources" @click="loadResources">
                <el-icon><Refresh /></el-icon>
                Refresh
              </el-button>
            </div>
            <el-table :data="resources" v-loading="loadingResources" size="small" stripe>
              <el-table-column label="Name" min-width="200">
                <template #default="{ row }">{{ row.metadata?.name }}</template>
              </el-table-column>
              <el-table-column label="Type" width="110">
                <template #default="{ row }">{{ row.spec?.type ?? '—' }}</template>
              </el-table-column>
              <el-table-column label="Cluster IP" width="140">
                <template #default="{ row }">{{ row.spec?.cluster_ip ?? '—' }}</template>
              </el-table-column>
              <el-table-column label="Ports" min-width="180">
                <template #default="{ row }">
                  {{ formatPorts(row.spec?.ports) }}
                </template>
              </el-table-column>
              <el-table-column label="Created" min-width="160">
                <template #default="{ row }">
                  {{ formatTime(row.metadata?.creation_timestamp) }}
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- ConfigMaps -->
          <el-tab-pane label="ConfigMaps" name="configmaps">
            <div class="tab-toolbar">
              <el-select
                v-model="selectedNamespace"
                placeholder="Select Namespace"
                size="small"
                style="width: 200px"
                @change="loadResources"
              >
                <el-option v-for="ns in namespaceList" :key="ns" :label="ns" :value="ns" />
              </el-select>
              <el-button size="small" :loading="loadingResources" @click="loadResources">
                <el-icon><Refresh /></el-icon>
                Refresh
              </el-button>
            </div>
            <el-table :data="resources" v-loading="loadingResources" size="small" stripe>
              <el-table-column label="Name" min-width="220">
                <template #default="{ row }">{{ row.metadata?.name }}</template>
              </el-table-column>
              <el-table-column label="Keys" width="100">
                <template #default="{ row }">
                  {{ row.data ? Object.keys(row.data).length : 0 }}
                </template>
              </el-table-column>
              <el-table-column label="Created" min-width="160">
                <template #default="{ row }">
                  {{ formatTime(row.metadata?.creation_timestamp) }}
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- DaemonSets -->
          <el-tab-pane label="DaemonSets" name="daemonsets">
            <div class="tab-toolbar">
              <el-select
                v-model="selectedNamespace"
                placeholder="Select Namespace"
                size="small"
                style="width: 200px"
                @change="loadResources"
              >
                <el-option v-for="ns in namespaceList" :key="ns" :label="ns" :value="ns" />
              </el-select>
              <el-button size="small" :loading="loadingResources" @click="loadResources">
                <el-icon><Refresh /></el-icon>
                Refresh
              </el-button>
            </div>
            <el-table :data="resources" v-loading="loadingResources" size="small" stripe>
              <el-table-column label="Name" min-width="220">
                <template #default="{ row }">{{ row.metadata?.name }}</template>
              </el-table-column>
              <el-table-column label="Desired" width="80">
                <template #default="{ row }">
                  {{ row.status?.desired_number_scheduled ?? '—' }}
                </template>
              </el-table-column>
              <el-table-column label="Ready" width="80">
                <template #default="{ row }">{{ row.status?.number_ready ?? 0 }}</template>
              </el-table-column>
              <el-table-column label="Created" min-width="160">
                <template #default="{ row }">
                  {{ formatTime(row.metadata?.creation_timestamp) }}
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </template>
    </main>

    <!-- Add Cluster Dialog -->
    <el-dialog v-model="showAddCluster" title="Add Cluster" width="600px" :close-on-click-modal="false">
      <el-form :model="newCluster" label-width="100px">
        <el-form-item label="Name">
          <el-input v-model="newCluster.name" placeholder="Enter cluster name" />
        </el-form-item>
        <el-form-item label="KubeConfig">
          <el-input
            v-model="newCluster.kubeconfig"
            type="textarea"
            :rows="12"
            placeholder="Paste kubeconfig content (YAML)"
            style="font-family: monospace; font-size: 12px"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddCluster = false">Cancel</el-button>
        <el-button type="primary" :loading="addingCluster" @click="addCluster">Add Cluster</el-button>
      </template>
    </el-dialog>

    <!-- Pod Logs Drawer -->
    <el-drawer
      v-model="showLogs"
      :title="`Logs — ${logPod?.metadata?.name ?? ''}`"
      direction="rtl"
      size="55%"
      :before-close="closeLogs"
    >
      <div class="log-controls">
        <el-tag v-if="wsConnected" type="success" size="small" effect="dark">● Connected</el-tag>
        <el-tag v-else type="info" size="small">○ Disconnected</el-tag>
        <el-button size="small" @click="clearLogs">Clear</el-button>
      </div>
      <pre ref="logBox" class="log-terminal">{{ logContent || '— waiting for logs —' }}</pre>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, onUnmounted } from 'vue'
import { Plus, Loading, Folder, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const BASE = 'http://127.0.0.1:8000/api'
const WS_BASE = 'ws://127.0.0.1:8000'

const auth = useAuthStore()

// ─── Clusters ───────────────────────────────────────────────
interface Cluster {
  id: number
  name: string
  is_active: boolean
  owner: { id: number }
}

const clusters = ref<Cluster[]>([])
const loadingClusters = ref(false)
const selectedCluster = ref<Cluster | null>(null)

async function fetchClusters() {
  if (!auth.user) return
  loadingClusters.value = true
  try {
    const res = await fetch(`${BASE}/kcore/users/${auth.user.id}/clusters/`, {
      headers: auth.authHeaders(),
    })
    const json = await res.json()
    clusters.value = json.data ?? []
  } catch {
    ElMessage.error('Failed to fetch clusters')
  } finally {
    loadingClusters.value = false
  }
}

async function selectCluster(cluster: Cluster) {
  selectedCluster.value = cluster
  activeTab.value = 'namespaces'
  resources.value = []
  namespaceList.value = []
  selectedNamespace.value = ''
  await loadResources()
}

// ─── Add Cluster ─────────────────────────────────────────────
const showAddCluster = ref(false)
const addingCluster = ref(false)
const newCluster = ref({ name: '', kubeconfig: '' })

function openAddCluster() {
  newCluster.value = { name: '', kubeconfig: '' }
  showAddCluster.value = true
}

async function addCluster() {
  if (!newCluster.value.name.trim() || !newCluster.value.kubeconfig.trim()) {
    ElMessage.warning('Please enter cluster name and kubeconfig')
    return
  }
  if (!auth.user) return
  addingCluster.value = true
  try {
    const res = await fetch(`${BASE}/kcore/users/${auth.user.id}/clusters/`, {
      method: 'POST',
      headers: auth.authHeaders(),
      body: JSON.stringify(newCluster.value),
    })
    if (!res.ok) {
      const err = await res.json()
      ElMessage.error(err.message ?? 'Failed to add')
      return
    }
    ElMessage.success('Cluster added')
    showAddCluster.value = false
    await fetchClusters()
  } catch {
    ElMessage.error('Network error')
  } finally {
    addingCluster.value = false
  }
}

// ─── Resources ───────────────────────────────────────────────
const activeTab = ref('namespaces')
const resources = ref<any[]>([])
const loadingResources = ref(false)
const namespaceList = ref<string[]>([])
const selectedNamespace = ref('')

async function loadResources() {
  if (!selectedCluster.value) return
  loadingResources.value = true
  resources.value = []
  try {
    const type = activeTab.value
    let url = `${BASE}/kcore/clusters/${selectedCluster.value.id}/resources/${type}/`
    if (type !== 'namespaces') {
      if (!selectedNamespace.value) return
      url += `?namespace=${selectedNamespace.value}`
    }
    const res = await fetch(url, { headers: auth.authHeaders() })
    const json = await res.json()
    resources.value = json.data?.resources ?? []
  } catch {
    ElMessage.error('Failed to fetch resources')
  } finally {
    loadingResources.value = false
  }
}

async function onTabChange() {
  resources.value = []
  if (activeTab.value === 'namespaces') {
    await loadResources()
    // populate namespace list from loaded namespaces
    namespaceList.value = resources.value.map((r) => r.metadata?.name).filter((n): n is string => !!n)
    if (namespaceList.value.length > 0 && !selectedNamespace.value) {
      selectedNamespace.value = namespaceList.value[0] ?? ''
    }
  } else {
    if (namespaceList.value.length === 0) {
      // need to load namespaces first
      const res = await fetch(
        `${BASE}/kcore/clusters/${selectedCluster.value!.id}/resources/namespaces/`,
        { headers: auth.authHeaders() },
      )
      const json = await res.json()
      namespaceList.value = (json.data?.resources ?? []).map((r: any) => r.metadata?.name).filter((n: unknown): n is string => !!n)
      if (namespaceList.value.length > 0 && !selectedNamespace.value) {
        selectedNamespace.value = namespaceList.value[0] ?? ''
      }
    }
    if (selectedNamespace.value) await loadResources()
  }
}

// ─── Pod Logs ────────────────────────────────────────────────
const showLogs = ref(false)
const logPod = ref<any>(null)
const logContent = ref('')
const wsConnected = ref(false)
const logBox = ref<HTMLPreElement | null>(null)
let socket: WebSocket | null = null

function openLogs(pod: any) {
  logPod.value = pod
  logContent.value = ''
  showLogs.value = true
  connectWs(pod)
}

function connectWs(pod: any) {
  disconnectWs()
  const ns = pod.metadata?.namespace ?? selectedNamespace.value
  const name = pod.metadata?.name
  if (!selectedCluster.value || !name) return
  const url = `${WS_BASE}/ws/clusters/${selectedCluster.value.id}/pods/${ns}/${name}/logs/`
  socket = new WebSocket(url)
  socket.onopen = () => { wsConnected.value = true }
  socket.onmessage = async (event) => {
    const { log } = JSON.parse(event.data)
    logContent.value += log
    await nextTick()
    if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
  }
  socket.onclose = () => { wsConnected.value = false }
  socket.onerror = () => {
    wsConnected.value = false
    logContent.value += '\n[connection error]'
  }
}

function disconnectWs() {
  socket?.close()
  socket = null
  wsConnected.value = false
}

function closeLogs() {
  disconnectWs()
  showLogs.value = false
}

function clearLogs() {
  logContent.value = ''
}

// ─── Helpers ────────────────────────────────────────────────
function formatTime(ts: string | null | undefined) {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('zh-CN', { hour12: false })
}

function formatPorts(ports: any[] | null | undefined) {
  if (!ports || ports.length === 0) return '—'
  return ports.map((p) => `${p.port}/${p.protocol ?? 'TCP'}`).join(', ')
}

function podStatusType(phase: string | undefined) {
  if (phase === 'Running') return 'success'
  if (phase === 'Pending') return 'warning'
  if (phase === 'Failed') return 'danger'
  return 'info'
}

computed(() => activeTab.value)

onMounted(fetchClusters)
onUnmounted(disconnectWs)
</script>

<style scoped>
.kcore-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
}

/* ── Sidebar ── */
.sidebar {
  width: 240px;
  flex-shrink: 0;
  background: #1a2233;
  border-right: 1px solid #2d3748;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 14px;
  border-bottom: 1px solid #2d3748;
}

.sidebar-title {
  font-size: 13px;
  font-weight: 600;
  color: #a0aec0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.sidebar-loading,
.sidebar-empty {
  padding: 24px 16px;
  text-align: center;
  color: #4a5568;
  font-size: 13px;
}

.cluster-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.cluster-card {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: background 0.15s;
  border: 1px solid transparent;
}

.cluster-card:hover {
  background: #2d3748;
}

.cluster-card.active {
  background: #1e3a5f;
  border-color: #2563eb;
}

.cluster-card-name {
  font-size: 13px;
  color: #e2e8f0;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  margin-right: 8px;
}

/* ── Content ── */
.content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f7f9fc;
}

.content-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #718096;
  gap: 12px;
}

.content-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px 0;
}

.content-title {
  font-size: 18px;
  font-weight: 600;
  color: #1a202c;
}

.resource-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0 20px 16px;
}

.resource-tabs :deep(.el-tabs__content) {
  flex: 1;
  overflow-y: auto;
}

.tab-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

/* ── Log Terminal ── */
.log-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.log-terminal {
  background: #0d1117;
  color: #00e676;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  padding: 16px;
  border-radius: 6px;
  height: calc(100vh - 180px);
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
