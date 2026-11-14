<template>
  <div class="kcore-layout">
    <!-- Left Sidebar (wide) -->
    <aside class="sidebar wide-sidebar">
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
      <div v-else-if="clusters.length === 0" class="sidebar-empty">No clusters yet</div>
      <div v-else class="cluster-list">
        <div v-for="cluster in clusters" :key="cluster.id" class="cluster-card"
          :class="{ active: selectedCluster?.id === cluster.id }" @click="selectCluster(cluster)">
          <div class="cluster-card-name">{{ cluster.name }}</div>
          <el-tag :type="cluster.is_active ? 'success' : 'danger'" size="small" effect="dark">
            {{ cluster.is_active ? 'Active' : 'Inactive' }}
          </el-tag>
          <el-tag style="margin-left: 0.2rem" size="small" type="danger" effect="dark"
            @click.stop="deleteCluster(cluster.id)">Delete</el-tag>
        </div>
      </div>
    </aside>

    <!-- Sidebar drawer (narrow) -->
    <el-drawer v-model="sidebarOpen" direction="ltr" size="80%"
        :show-close="false" :with-header="false" class="sidebar-drawer">
      <div class="sidebar drawer-sidebar">
        <div class="sidebar-header">
          <span class="sidebar-title">My Clusters</span>
          <el-button size="small" type="primary" @click="openAddCluster(); sidebarOpen = false">
            <el-icon><Plus /></el-icon>
            Add
          </el-button>
        </div>
        <div v-if="loadingClusters" class="sidebar-loading">
          <el-icon class="is-loading"><Loading /></el-icon>
        </div>
        <div v-else-if="clusters.length === 0" class="sidebar-empty">No clusters yet</div>
        <div v-else class="cluster-list">
          <div v-for="cluster in clusters" :key="cluster.id" class="cluster-card"
            :class="{ active: selectedCluster?.id === cluster.id }"
            @click="selectCluster(cluster); sidebarOpen = false">
            <div class="cluster-card-name">{{ cluster.name }}</div>
            <el-tag :type="cluster.is_active ? 'success' : 'danger'" size="small" effect="dark">
              {{ cluster.is_active ? 'Active' : 'Inactive' }}
            </el-tag>
            <el-tag style="margin-left: 0.2rem" size="small" type="danger" effect="dark"
              @click.stop="deleteCluster(cluster.id)">Delete</el-tag>
          </div>
        </div>
      </div>
    </el-drawer>

    <!-- Right Content -->
    <main class="content">
      <div v-if="!selectedCluster" class="content-empty">
        <div class="empty-ico"><el-icon><Cpu /></el-icon></div>
        <h3>Select a cluster</h3>
        <p>Pick a cluster on the left to see its nodes, pods and logs, or click <b>Add</b> to register a new one.</p>
        <el-button class="narrow-only" type="primary" @click="sidebarOpen = true">
          <el-icon><List /></el-icon>
          My Clusters
        </el-button>
      </div>

      <template v-else>
        <div class="content-header">
          <div style="display:flex;align-items:center;gap:10px">
            <el-button class="narrow-only" size="small" plain @click="sidebarOpen = true">
              <el-icon><List /></el-icon>
            </el-button>
            <span class="content-title">{{ selectedCluster.name }}</span>
          </div>
          <el-tag :type="selectedCluster.is_active ? 'success' : 'danger'" effect="plain">
            {{ selectedCluster.is_active ? 'Active' : 'Inactive' }}
          </el-tag>
          <div style="flex:1" />
          <el-button size="small" type="primary" @click="openApplyDialog">
            <el-icon>
              <Upload />
            </el-icon>
            Apply YAML
          </el-button>
        </div>

        <el-tabs v-model="activeTab" class="resource-tabs" @tab-click="onTabChange">

          <!-- Namespaces -->
          <el-tab-pane label="Namespaces" name="namespaces">
            <div class="tab-toolbar">
              <el-button size="small" :loading="loadingResources" @click="loadResources">
                <el-icon>
                  <Refresh />
                </el-icon>Refresh
              </el-button>
            </div>
            <el-table :data="resources" v-loading="loadingResources" size="small" stripe>
              <el-table-column label="Name" min-width="200">
                <template #default="{ row }">{{ row.metadata?.name }}</template>
              </el-table-column>
              <el-table-column label="Status" width="120">
                <template #default="{ row }">
                  <el-tag :type="row.status?.phase === 'Active' ? 'success' : 'warning'" size="small">
                    {{ row.status?.phase ?? '—' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="Created" min-width="180">
                <template #default="{ row }">{{ formatTime(row.metadata?.creation_timestamp)
                  }}</template>
              </el-table-column>
              <el-table-column label="Actions" width="130" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" text type="primary"
                    @click="openYaml(row, 'namespaces', true)">YAML</el-button>
                  <el-button size="small" text type="danger"
                    @click="openDeleteDialog(row, 'namespaces')">Delete</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- Pods -->
          <el-tab-pane label="Pods" name="pods">
            <div class="tab-toolbar">
              <el-select v-model="selectedNamespace" placeholder="Select Namespace" size="small" style="width: 200px"
                @change="loadResources">
                <el-option v-for="ns in namespaceList" :key="ns" :label="ns" :value="ns" />
              </el-select>
              <el-button size="small" :loading="loadingResources" @click="loadResources">
                <el-icon>
                  <Refresh />
                </el-icon>Refresh
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
                <template #default="{ row }">{{ formatTime(row.metadata?.creation_timestamp)
                  }}</template>
              </el-table-column>
              <el-table-column label="Actions" width="170" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" text type="primary" @click="openLogs(row)">Logs</el-button>
                  <el-button size="small" text type="primary" @click="openYaml(row, 'pods', true)">YAML</el-button>
                  <el-button size="small" text type="danger" @click="openDeleteDialog(row, 'pods')">Delete</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- Deployments -->
          <el-tab-pane label="Deployments" name="deployments">
            <div class="tab-toolbar">
              <el-select v-model="selectedNamespace" placeholder="Select Namespace" size="small" style="width: 200px"
                @change="loadResources">
                <el-option v-for="ns in namespaceList" :key="ns" :label="ns" :value="ns" />
              </el-select>
              <el-button size="small" :loading="loadingResources" @click="loadResources">
                <el-icon>
                  <Refresh />
                </el-icon>Refresh
              </el-button>
            </div>
            <el-table :data="resources" v-loading="loadingResources" size="small" stripe>
              <el-table-column label="Name" min-width="200">
                <template #default="{ row }">{{ row.metadata?.name }}</template>
              </el-table-column>
              <el-table-column label="Desired" width="80">
                <template #default="{ row }">{{ row.spec?.replicas ?? '—' }}</template>
              </el-table-column>
              <el-table-column label="Ready" width="70">
                <template #default="{ row }">{{ row.status?.ready_replicas ?? 0 }}</template>
              </el-table-column>
              <el-table-column label="Available" width="80">
                <template #default="{ row }">{{ row.status?.available_replicas ?? 0 }}</template>
              </el-table-column>
              <el-table-column label="Created" min-width="160">
                <template #default="{ row }">{{ formatTime(row.metadata?.creation_timestamp)
                  }}</template>
              </el-table-column>
              <el-table-column label="Actions" width="240" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" text type="primary"
                    @click="openYaml(row, 'deployments', true)">YAML</el-button>
                  <el-button size="small" text type="success"
                    @click="openYaml(row, 'deployments', false)">Edit</el-button>
                  <el-dropdown size="small"
                    @command="(cmd: string) => submitRestart(row, 'deployments', cmd === 'force')">
                    <el-button size="small" text type="warning">
                      Restart<el-icon class="el-icon--right">
                        <ArrowDown />
                      </el-icon>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="normal">Normal (Rolling)</el-dropdown-item>
                        <el-dropdown-item command="force">Force (Delete Pods)</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                  <el-button size="small" text type="danger"
                    @click="openDeleteDialog(row, 'deployments')">Delete</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- Services -->
          <el-tab-pane label="Services" name="services">
            <div class="tab-toolbar">
              <el-select v-model="selectedNamespace" placeholder="Select Namespace" size="small" style="width: 200px"
                @change="loadResources">
                <el-option v-for="ns in namespaceList" :key="ns" :label="ns" :value="ns" />
              </el-select>
              <el-button size="small" :loading="loadingResources" @click="loadResources">
                <el-icon>
                  <Refresh />
                </el-icon>Refresh
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
                <template #default="{ row }">{{ formatPorts(row.spec?.ports) }}</template>
              </el-table-column>
              <el-table-column label="Created" min-width="160">
                <template #default="{ row }">{{ formatTime(row.metadata?.creation_timestamp)
                  }}</template>
              </el-table-column>
              <el-table-column label="Actions" width="180" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" text type="primary" @click="openYaml(row, 'services', true)">YAML</el-button>
                  <el-button size="small" text type="success" @click="openYaml(row, 'services', false)">Edit</el-button>
                  <el-button size="small" text type="danger"
                    @click="openDeleteDialog(row, 'services')">Delete</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- ConfigMaps -->
          <el-tab-pane label="ConfigMaps" name="configmaps">
            <div class="tab-toolbar">
              <el-select v-model="selectedNamespace" placeholder="Select Namespace" size="small" style="width: 200px"
                @change="loadResources">
                <el-option v-for="ns in namespaceList" :key="ns" :label="ns" :value="ns" />
              </el-select>
              <el-button size="small" :loading="loadingResources" @click="loadResources">
                <el-icon>
                  <Refresh />
                </el-icon>Refresh
              </el-button>
            </div>
            <el-table :data="resources" v-loading="loadingResources" size="small" stripe>
              <el-table-column label="Name" min-width="220">
                <template #default="{ row }">{{ row.metadata?.name }}</template>
              </el-table-column>
              <el-table-column label="Keys" width="80">
                <template #default="{ row }">{{ row.data ? Object.keys(row.data).length : 0
                  }}</template>
              </el-table-column>
              <el-table-column label="Created" min-width="160">
                <template #default="{ row }">{{ formatTime(row.metadata?.creation_timestamp)
                  }}</template>
              </el-table-column>
              <el-table-column label="Actions" width="180" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" text type="primary"
                    @click="openYaml(row, 'configmaps', true)">YAML</el-button>
                  <el-button size="small" text type="success"
                    @click="openYaml(row, 'configmaps', false)">Edit</el-button>
                  <el-button size="small" text type="danger"
                    @click="openDeleteDialog(row, 'configmaps')">Delete</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- DaemonSets -->
          <el-tab-pane label="DaemonSets" name="daemonsets">
            <div class="tab-toolbar">
              <el-select v-model="selectedNamespace" placeholder="Select Namespace" size="small" style="width: 200px"
                @change="loadResources">
                <el-option v-for="ns in namespaceList" :key="ns" :label="ns" :value="ns" />
              </el-select>
              <el-button size="small" :loading="loadingResources" @click="loadResources">
                <el-icon>
                  <Refresh />
                </el-icon>Refresh
              </el-button>
            </div>
            <el-table :data="resources" v-loading="loadingResources" size="small" stripe>
              <el-table-column label="Name" min-width="220">
                <template #default="{ row }">{{ row.metadata?.name }}</template>
              </el-table-column>
              <el-table-column label="Desired" width="80">
                <template #default="{ row }">{{ row.status?.desired_number_scheduled ?? '—'
                  }}</template>
              </el-table-column>
              <el-table-column label="Ready" width="70">
                <template #default="{ row }">{{ row.status?.number_ready ?? 0 }}</template>
              </el-table-column>
              <el-table-column label="Created" min-width="160">
                <template #default="{ row }">{{ formatTime(row.metadata?.creation_timestamp)
                  }}</template>
              </el-table-column>
              <el-table-column label="Actions" width="240" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" text type="primary"
                    @click="openYaml(row, 'daemonsets', true)">YAML</el-button>
                  <el-button size="small" text type="success"
                    @click="openYaml(row, 'daemonsets', false)">Edit</el-button>
                  <el-dropdown size="small"
                    @command="(cmd: string) => submitRestart(row, 'daemonsets', cmd === 'force')">
                    <el-button size="small" text type="warning">
                      Restart<el-icon class="el-icon--right">
                        <ArrowDown />
                      </el-icon>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="normal">Normal (Rolling)</el-dropdown-item>
                        <el-dropdown-item command="force">Force (Delete Pods)</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                  <el-button size="small" text type="danger"
                    @click="openDeleteDialog(row, 'daemonsets')">Delete</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

        </el-tabs>
      </template>
    </main>

    <!-- ── Add Cluster Dialog ── -->
    <el-dialog v-model="showAddCluster" title="Add Cluster" width="600px" :close-on-click-modal="false">
      <el-form :model="newCluster" label-width="100px">
        <el-form-item label="Name">
          <el-input v-model="newCluster.name" placeholder="Enter cluster name" />
        </el-form-item>
        <el-form-item label="KubeConfig">
          <el-input v-model="newCluster.kubeconfig" type="textarea" :rows="12"
            placeholder="Paste kubeconfig content (YAML)" style="font-family: monospace; font-size: 12px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddCluster = false">Cancel</el-button>
        <el-button type="primary" :loading="addingCluster" @click="addCluster">Add Cluster</el-button>
      </template>
    </el-dialog>

    <!-- ── YAML View / Edit Dialog ── -->
    <el-dialog v-model="yamlDialog.visible" :title="yamlDialog.title" width="760px" :close-on-click-modal="false">
      <div v-if="yamlDialog.loading" class="yaml-loading">
        <el-icon class="is-loading" size="24">
          <Loading />
        </el-icon>
        <span>Loading YAML…</span>
      </div>
      <textarea v-else v-model="yamlDialog.content" class="yaml-editor" :readonly="yamlDialog.readonly"
        :class="{ 'yaml-readonly': yamlDialog.readonly }" spellcheck="false" />
      <template #footer>
        <el-button @click="yamlDialog.visible = false">Close</el-button>
        <el-button v-if="!yamlDialog.readonly" type="primary" :loading="yamlDialog.applying"
          @click="submitYamlEdit">Apply</el-button>
      </template>
    </el-dialog>

    <!-- ── Apply YAML Dialog (blank editor) ── -->
    <el-dialog v-model="applyDialog.visible" title="Apply YAML" width="760px" :close-on-click-modal="false">
      <div class="yaml-hint">Paste one or more Kubernetes manifests (separate with <code>---</code>).</div>
      <textarea v-model="applyDialog.content" class="yaml-editor"
        placeholder="apiVersion: apps/v1&#10;kind: Deployment&#10;..." spellcheck="false" />
      <template #footer>
        <el-button @click="applyDialog.visible = false">Cancel</el-button>
        <el-button type="primary" :loading="applyDialog.applying" @click="submitApply">Apply</el-button>
      </template>
    </el-dialog>

    <!-- ── Delete Confirm Dialog ── -->
    <el-dialog v-model="deleteDialog.visible" title="Confirm Delete" width="420px">
      <p>
        Delete <strong>{{ deleteDialog.resourceType?.slice(0, -1) }}</strong>
        <code>{{ deleteDialog.name }}</code>
        <span v-if="deleteDialog.namespace"> in namespace <code>{{ deleteDialog.namespace }}</code></span>?
      </p>
      <p style="color:#ef4444;font-size:13px;margin-top:8px">This action cannot be undone.</p>
      <template #footer>
        <el-button @click="deleteDialog.visible = false">Cancel</el-button>
        <el-button type="danger" :loading="deleteDialog.loading" @click="submitDelete">Delete</el-button>
      </template>
    </el-dialog>

    <!-- ── Pod Logs Drawer ── -->
    <el-drawer v-model="showLogs" :title="`Logs — ${logPod?.metadata?.name ?? ''}`" direction="rtl" size="55%"
      :before-close="closeLogs">
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
import { Plus, Loading, Folder, Refresh, Upload, ArrowDown, List } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useKcoreStore } from '@/stores/kcore'

const BASE = import.meta.env.VITE_API_BASE
const sidebarOpen = ref(false)
const WS_BASE = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`

const auth = useAuthStore()
const kcore = useKcoreStore()

// ─── Types ───────────────────────────────────────────────────
interface Cluster { id: number; name: string; is_active: boolean; owner: { id: number } }
type K8sRow = Record<string, unknown> & { metadata?: { name?: string; namespace?: string } }

// ─── Clusters ────────────────────────────────────────────────
const clusters = ref<Cluster[]>([])
const loadingClusters = ref(false)
const selectedCluster = ref<Cluster | null>(null)

async function fetchClusters() {
  if (!auth.user) return
  loadingClusters.value = true
  try {
    const res = await auth.apiFetch(`${BASE}/kcore/users/${auth.user.id}/clusters/`)
    const json = await res.json()
    clusters.value = json.data ?? []
  } catch { ElMessage.error('Failed to fetch clusters') }
  finally { loadingClusters.value = false }
}

async function selectCluster(cluster: Cluster) {
  selectedCluster.value = cluster
  activeTab.value = 'namespaces'
  resources.value = []
  selectedNamespace.value = 'default'
  await onTabChange()
}

// ─── Add / Delete Cluster ────────────────────────────────────
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
    const res = await auth.apiFetch(`${BASE}/kcore/users/${auth.user.id}/clusters/`, {
      method: 'POST',
      body: JSON.stringify(newCluster.value),
    })
    if (!res.ok) { ElMessage.error((await res.json()).message ?? 'Failed to add'); return }
    ElMessage.success('Cluster added')
    showAddCluster.value = false
    await fetchClusters()
  } catch { ElMessage.error('Network error') }
  finally { addingCluster.value = false }
}

async function deleteCluster(clusterId: number) {
  try {
    const res = await auth.apiFetch(`${BASE}/kcore/clusters/${clusterId}/`, { method: 'DELETE' })
    if (!res.ok) { ElMessage.error((await res.json()).message ?? 'Failed to delete'); return }
    ElMessage.success('Cluster deleted')
    if (selectedCluster.value?.id === clusterId) selectedCluster.value = null
    await fetchClusters()
  } catch { ElMessage.error('Network error') }
}

// ─── Resources ───────────────────────────────────────────────
const activeTab = ref('namespaces')
const resources = ref<K8sRow[]>([])
const loadingResources = ref(false)
const selectedNamespace = ref('default')
const namespaceList = computed(() =>
  selectedCluster.value ? kcore.getNamespaces(selectedCluster.value.id) : [],
)

async function loadResources() {
  if (!selectedCluster.value) return
  // 快照当前状态，用于请求返回后校验是否过时
  const clusterId = selectedCluster.value.id
  const type = activeTab.value
  const ns = selectedNamespace.value

  loadingResources.value = true
  resources.value = []
  try {
    let url = `${BASE}/kcore/clusters/${clusterId}/resources/${type}/`
    if (type !== 'namespaces') {
      if (!ns) return
      url += `?namespace=${ns}`
    }
    const res = await auth.apiFetch(url)
    const json = await res.json()
    // 如果期间 tab 或 cluster 已切换，丢弃这次响应
    if (activeTab.value !== type || selectedCluster.value?.id !== clusterId) return
    resources.value = json.data?.resources ?? []
  } catch { ElMessage.error('Failed to fetch resources') }
  finally { loadingResources.value = false }
}

async function onTabChange() {
  resources.value = []
  if (!selectedCluster.value) return
  const clusterId = selectedCluster.value.id
  const tab = activeTab.value

  // 保证 namespace 列表始终可用
  await kcore.fetchNamespaces(clusterId)

  // 期间 cluster 已切换，丢弃
  if (selectedCluster.value?.id !== clusterId) return

  if (tab !== 'namespaces') selectedNamespace.value = 'default'
  await loadResources()
}

// ─── YAML View / Edit ────────────────────────────────────────
const yamlDialog = ref({
  visible: false,
  loading: false,
  applying: false,
  readonly: true,
  title: '',
  content: '',
  resourceType: '',
  name: '',
  namespace: '' as string | undefined,
})

async function openYaml(row: K8sRow, resourceType: string, readonly: boolean) {
  const name = row.metadata?.name ?? ''
  const namespace = (row.metadata?.namespace ?? selectedNamespace.value) || undefined
  yamlDialog.value = {
    visible: true,
    loading: true,
    applying: false,
    readonly,
    title: readonly ? `${name} — YAML` : `Edit ${name}`,
    content: '',
    resourceType,
    name,
    namespace,
  }
  try {
    const nsParam = namespace ? `?namespace=${namespace}` : ''
    const url = `${BASE}/kcore/clusters/${selectedCluster.value!.id}/resources/${resourceType}/${name}/${nsParam}`
    const res = await fetch(url, { headers: auth.authHeaders() })
    const json = await res.json()
    if (!res.ok) { ElMessage.error(json.message ?? 'Failed to load YAML'); yamlDialog.value.visible = false; return }
    yamlDialog.value.content = json.data?.yaml ?? ''
  } catch { ElMessage.error('Network error'); yamlDialog.value.visible = false }
  finally { yamlDialog.value.loading = false }
}

async function submitYamlEdit() {
  yamlDialog.value.applying = true
  try {
    const res = await auth.apiFetch(
      `${BASE}/kcore/clusters/${selectedCluster.value!.id}/apply/`,
      { method: 'POST', body: JSON.stringify({ yaml: yamlDialog.value.content }) },
    )
    const json = await res.json()
    if (!res.ok) { ElMessage.error(json.message ?? 'Apply failed'); return }
    ElMessage.success('Applied successfully')
    yamlDialog.value.visible = false
    await loadResources()
  } catch { ElMessage.error('Network error') }
  finally { yamlDialog.value.applying = false }
}

// ─── Apply YAML (blank) ──────────────────────────────────────
const applyDialog = ref({ visible: false, applying: false, content: '' })

function openApplyDialog() {
  applyDialog.value = { visible: true, applying: false, content: '' }
}

async function submitApply() {
  if (!applyDialog.value.content.trim()) { ElMessage.warning('Please enter YAML content'); return }
  applyDialog.value.applying = true
  try {
    const res = await auth.apiFetch(
      `${BASE}/kcore/clusters/${selectedCluster.value!.id}/apply/`,
      { method: 'POST', body: JSON.stringify({ yaml: applyDialog.value.content }) },
    )
    const json = await res.json()
    if (!res.ok) { ElMessage.error(json.message ?? 'Apply failed'); return }
    const results: Array<{ kind: string; name: string; status: string }> = json.data?.results ?? []
    const ok = results.filter(r => r.status === 'applied').length
    const err = results.filter(r => r.status === 'error').length
    ElMessage.success(`Applied: ${ok} resource(s)${err ? `, ${err} error(s)` : ''}`)
    applyDialog.value.visible = false
    await loadResources()
  } catch { ElMessage.error('Network error') }
  finally { applyDialog.value.applying = false }
}

// ─── Restart ─────────────────────────────────────────────────
async function submitRestart(row: K8sRow, resourceType: string, force: boolean) {
  const name = row.metadata?.name ?? ''
  const namespace = row.metadata?.namespace ?? selectedNamespace.value
  const label = force ? 'Force restart' : 'Restart'
  try {
    const res = await auth.apiFetch(
      `${BASE}/kcore/clusters/${selectedCluster.value!.id}/resources/${resourceType}/${name}/`,
      { method: 'POST', body: JSON.stringify({ namespace, force }) },
    )
    const json = await res.json()
    if (!res.ok) { ElMessage.error(json.message ?? `${label} failed`); return }
    ElMessage.success(json.data?.message ?? `${label} triggered`)
    await loadResources()
  } catch { ElMessage.error('Network error') }
}

// ─── Delete ──────────────────────────────────────────────────
const deleteDialog = ref({
  visible: false,
  loading: false,
  resourceType: '',
  name: '',
  namespace: '' as string | undefined,
})

function openDeleteDialog(row: K8sRow, resourceType: string) {
  deleteDialog.value = {
    visible: true,
    loading: false,
    resourceType,
    name: row.metadata?.name ?? '',
    namespace: resourceType === 'namespaces' ? undefined : (row.metadata?.namespace ?? selectedNamespace.value),
  }
}

async function submitDelete() {
  deleteDialog.value.loading = true
  const { resourceType, name, namespace } = deleteDialog.value
  try {
    const res = await auth.apiFetch(
      `${BASE}/kcore/clusters/${selectedCluster.value!.id}/resources/${resourceType}/${name}/`,
      { method: 'DELETE', body: JSON.stringify({ namespace }) },
    )
    const json = await res.json()
    if (!res.ok) { ElMessage.error(json.message ?? 'Delete failed'); return }
    ElMessage.success(json.data?.message ?? 'Deleted')
    deleteDialog.value.visible = false
    await loadResources()
  } catch { ElMessage.error('Network error') }
  finally { deleteDialog.value.loading = false }
}

// ─── Pod Logs ────────────────────────────────────────────────
interface Pod { metadata?: { namespace?: string; name?: string } }
const showLogs = ref(false)
const logPod = ref<Pod | null>(null)
const logContent = ref('')
const wsConnected = ref(false)
const logBox = ref<HTMLPreElement | null>(null)
let socket: WebSocket | null = null

function openLogs(pod: unknown) {
  logPod.value = pod as Pod
  logContent.value = ''
  showLogs.value = true
  connectWs(pod)
}

function connectWs(pod: unknown) {
  disconnectWs()
  const p = pod as Pod
  console.log('pod:', p.metadata?.namespace, p.metadata?.name)
  const ns = (p.metadata?.namespace || selectedNamespace.value) || null
  const name = p.metadata?.name
  if (!selectedCluster.value || !name || !ns) {
    logContent.value = '[Error] Could not determine pod namespace. Please select a namespace first.'
    return
  }
  socket = new WebSocket(`${WS_BASE}/ws/clusters/${selectedCluster.value.id}/pods/${ns}/${name}/logs/`)
  socket.onopen = () => { wsConnected.value = true }
  socket.onmessage = async (e) => {
    const { log } = JSON.parse(e.data)
    logContent.value += log
    await nextTick()
    if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
  }
  socket.onclose = () => { wsConnected.value = false }
  socket.onerror = () => { wsConnected.value = false; logContent.value += '\n[connection error]' }
}

function disconnectWs() { socket?.close(); socket = null; wsConnected.value = false }
function closeLogs() { disconnectWs(); showLogs.value = false }
function clearLogs() { logContent.value = '' }

// ─── Helpers ─────────────────────────────────────────────────
function formatTime(ts: string | null | undefined) {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('zh-CN', { hour12: false })
}

function formatPorts(ports: unknown[] | null | undefined) {
  if (!ports || ports.length === 0) return '—'
  return ports.map(p => {
    const port = p as { port: number; protocol?: string }
    return `${port.port}/${port.protocol ?? 'TCP'}`
  }).join(', ')
}

function podStatusType(phase: string | undefined) {
  if (phase === 'Running') return 'success'
  if (phase === 'Pending') return 'warning'
  if (phase === 'Failed') return 'danger'
  return 'info'
}

onMounted(fetchClusters)
onUnmounted(disconnectWs)
</script>

<style scoped>
.kcore-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
}

.narrow-only { display: none; }

@media (max-width: 680px) {
  .wide-sidebar { display: none !important; }
  .narrow-only  { display: flex !important; }

  .content-header {
    padding: 10px 12px;
    gap: 8px;
    flex-wrap: wrap;
  }

  .resource-tabs {
    padding: 0 8px;
  }

  :deep(.el-table) {
    font-size: 12px;
  }

  :deep(.el-table td),
  :deep(.el-table th) {
    padding: 6px 4px;
  }
}

:deep(.sidebar-drawer .el-drawer__body) {
  padding: 0;
  background: #0f172a;
}

.drawer-sidebar {
  width: 100% !important;
  height: 100%;
  border-right: none;
}

/* ── Sidebar ── */
.sidebar {
  width: 240px;
  flex-shrink: 0;
  background: #0f172a;
  border-right: 1px solid #1e293b;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 14px;
  border-bottom: 1px solid #1e293b;
}

.sidebar-title {
  font-size: 13px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.sidebar-loading,
.sidebar-empty {
  padding: 24px 16px;
  color: #475569;
  font-size: 13px;
  text-align: center;
}

.cluster-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.cluster-card {
  padding: 10px 14px;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: background 0.15s;
}

.cluster-card:hover {
  background: #1e293b;
}

.cluster-card.active {
  background: #1e3a8a;
  border-left-color: #3b82f6;
}

.cluster-card-name {
  font-size: 13px;
  font-weight: 500;
  color: #e2e8f0;
  margin-bottom: 4px;
}

/* ── Content ── */
.content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f1f5f9;
}

.content-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #64748b;
  font-size: 14px;
}

.content-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.content-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

.resource-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0 20px;
}

:deep(.el-tabs__content) {
  flex: 1;
  overflow: auto;
}

:deep(.el-tab-pane) {
  height: 100%;
}

.tab-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

/* ── YAML Editor ── */
.yaml-editor {
  width: 100%;
  height: 400px;
  font-family: 'Courier New', 'Consolas', monospace;
  font-size: 12.5px;
  line-height: 1.6;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #0f172a;
  color: #e2e8f0;
  resize: vertical;
  outline: none;
  box-sizing: border-box;
}

.yaml-editor.yaml-readonly {
  background: #1e293b;
  color: #cbd5e1;
  cursor: default;
}

.yaml-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 40px;
  justify-content: center;
  color: #64748b;
}

.yaml-hint {
  font-size: 12.5px;
  color: #64748b;
  margin-bottom: 8px;
}

.yaml-hint code {
  background: #f1f5f9;
  padding: 1px 6px;
  border-radius: 3px;
}

/* ── Logs ── */
.log-controls {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

.log-terminal {
  background: #0f172a;
  color: #e2e8f0;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  padding: 16px;
  border-radius: 8px;
  overflow-y: auto;
  height: calc(100vh - 160px);
  white-space: pre-wrap;
  word-break: break-all;
}

/* ── 新 UI：统一工作区外观 ── */
.sidebar { width: 264px; background: #0f172a; border-right: 1px solid rgba(255,255,255,.06); }
.sidebar-header { padding: 20px 16px 16px; border-bottom: 1px solid rgba(255,255,255,.06); }
.sidebar-title { font-size: 11.5px; font-weight: 700; letter-spacing: .12em; color: #94a3b8; }
.sidebar-empty { color: #64748b; }
.cluster-list { padding: 10px; display: flex; flex-direction: column; gap: 4px; }
.cluster-card { padding: 12px 14px; border-radius: 10px; border-left: none; transition: background .15s, box-shadow .15s; }
.cluster-card:hover { background: rgba(255,255,255,.05); }
.cluster-card.active { background: rgba(37,99,235,.18); box-shadow: inset 3px 0 0 #60a5fa; }
.cluster-card-name { font-size: 14px; font-weight: 600; color: #f1f5f9; margin-bottom: 6px; }
.content { background: #f1f5f9; }
.content-header { padding: 20px 28px; border-bottom: 1px solid #e2e8f0; background: #fff; }
.content-title { font-size: 20px; font-weight: 800; letter-spacing: -0.01em; color: #0f172a; }
.content-empty { text-align: center; padding: 24px; }
.content-empty h3 { font-size: 20px; font-weight: 800; color: #0f172a; }
.content-empty p { max-width: 44ch; font-size: 14px; line-height: 1.7; color: #64748b; }
.empty-ico { width: 72px; height: 72px; border-radius: 20px; display: flex; align-items: center; justify-content: center; font-size: 34px; color: #2563eb; background: #eff6ff; box-shadow: 0 10px 24px rgba(37,99,235,.15); }
</style>
