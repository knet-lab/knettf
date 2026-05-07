<template>
  <div class="autotf-layout">
    <!-- ── 左侧 Sidebar ── -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">My Configs</span>
        <el-button size="small" type="primary" @click="openAddDialog">
          <el-icon><Plus /></el-icon>
          New
        </el-button>
      </div>

      <div v-if="loadingConfigs" class="sidebar-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
      </div>
      <div v-else-if="configs.length === 0" class="sidebar-empty">
        No configs yet
      </div>
      <div v-else class="config-list">
        <div
          v-for="cfg in configs"
          :key="cfg.id"
          class="config-card"
          :class="{ active: selectedConfig?.id === cfg.id }"
          @click="selectConfig(cfg)"
        >
          <div class="config-card-name">{{ cfg.name }}</div>
          <el-tag
            :type="cfg.is_scanned ? 'success' : 'info'"
            size="small"
            effect="dark"
          >
            {{ cfg.is_scanned ? 'Scanned' : 'Not scanned' }}
          </el-tag>
        </div>
      </div>
    </aside>

    <!-- ── 右侧内容区 ── -->
    <main class="content">
      <div v-if="!selectedConfig" class="content-empty">
        <el-icon size="48" color="#4a5568"><Document /></el-icon>
        <p>Select a config from the left</p>
      </div>

      <div v-else class="content-body">
        <!-- 标题栏 -->
        <div class="content-header">
          <span class="content-title">{{ selectedConfig.name }}</span>
          <div class="header-actions">
            <el-button size="small" plain type="danger" @click="confirmDelete">
              <el-icon><Delete /></el-icon>
              Delete Config
            </el-button>
          </div>
        </div>

        <!-- 配置内容 -->
        <el-card class="section-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>Config Content</span>
              <div class="card-header-actions">
                <el-button
                  v-if="!editingContent"
                  size="small"
                  @click="startEditContent"
                  :loading="loadingContent"
                >
                  <el-icon><Edit /></el-icon>
                  Edit
                </el-button>
                <template v-else>
                  <el-button size="small" type="primary" :loading="savingContent" @click="saveContent">
                    Save
                  </el-button>
                  <el-button size="small" @click="cancelEdit">Cancel</el-button>
                </template>
              </div>
            </div>
          </template>
          <div v-if="loadingContent && !editingContent" class="loading-placeholder">
            <el-icon class="is-loading"><Loading /></el-icon> Loading...
          </div>
          <el-input
            v-else
            v-model="configContent"
            type="textarea"
            :rows="12"
            :readonly="!editingContent"
            resize="none"
            style="font-family: 'Courier New', monospace; font-size: 13px"
            :class="{ 'code-readonly': !editingContent }"
          />
        </el-card>

        <!-- 扫描 -->
        <el-card class="section-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>Security Scan</span>
            </div>
          </template>
          <div class="scan-actions">
            <el-button type="primary" :loading="scanning" @click="runFullScan">
              <el-icon><VideoPlay /></el-icon>
              Full Scan
            </el-button>
            <el-button :loading="scanning" @click="openManualScan">
              <el-icon><Setting /></el-icon>
              Manual Scan
            </el-button>
          </div>
          <div v-if="scanning" class="scan-progress">
            <el-icon class="is-loading"><Loading /></el-icon>
            Scanning, please wait...
          </div>
        </el-card>

        <!-- 扫描报告 -->
        <el-card class="section-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>Scan Report</span>
              <div class="card-header-actions" v-if="report">
                <el-button size="small" type="primary" plain @click="viewHtmlReport">
                  <el-icon><View /></el-icon>
                  View Report
                </el-button>
                <el-button size="small" @click="downloadPdf">
                  <el-icon><Download /></el-icon>
                  Download PDF
                </el-button>
                <el-button size="small" type="danger" plain @click="deleteReport">
                  <el-icon><Delete /></el-icon>
                  Delete Report
                </el-button>
              </div>
            </div>
          </template>

          <div v-if="loadingReport" class="loading-placeholder">
            <el-icon class="is-loading"><Loading /></el-icon> Loading...
          </div>
          <div v-else-if="!report" class="report-empty">
            No report yet. Run a scan first.
          </div>
          <template v-else>
            <!-- 报告摘要 -->
            <div class="report-meta">
              <el-descriptions :column="4" size="small" border>
                <el-descriptions-item label="Status">
                  <el-tag :type="reportStatusType(report.status)" size="small">
                    {{ reportStatusLabel(report.status) }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="Tools">
                  {{ report.tools?.map((t) => t.name).join(', ') || '—' }}
                </el-descriptions-item>
                <el-descriptions-item label="Scanned At">
                  {{ formatTime(report.scanned_at) }}
                </el-descriptions-item>
                <el-descriptions-item label="Risk Summary">
                  <el-tag type="danger" size="small" style="margin-right:4px">
                    HIGH {{ report.result?.summary?.high ?? 0 }}
                  </el-tag>
                  <el-tag type="warning" size="small" style="margin-right:4px">
                    MED {{ report.result?.summary?.medium ?? 0 }}
                  </el-tag>
                  <el-tag type="info" size="small">
                    LOW {{ report.result?.summary?.low ?? 0 }}
                  </el-tag>
                </el-descriptions-item>
              </el-descriptions>
            </div>

            <!-- 发现问题列表（按工具分组） -->
            <div v-if="hasFindings" class="findings">
              <div
                v-for="(toolResult, toolName) in report.result?.tools"
                :key="toolName"
                class="tool-findings"
              >
                <div class="tool-name">{{ toolName }}</div>
                <div v-if="!toolResult.items || toolResult.items.length === 0" class="report-empty" style="padding: 8px 0">
                  No findings
                </div>
                <el-table v-else :data="toolResult.items" size="small" stripe style="margin-top: 6px">
                  <el-table-column label="Rule ID" prop="rule_id" min-width="140" />
                  <el-table-column label="Severity" width="100">
                    <template #default="{ row }">
                      <el-tag :type="severityType(row.severity)" size="small">
                        {{ row.severity }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="Description" prop="description" min-width="240" show-overflow-tooltip />
                  <el-table-column label="Location" prop="location" min-width="180" show-overflow-tooltip />
                </el-table>
              </div>
            </div>
            <div v-else class="report-empty">
              No security issues found
            </div>
          </template>
        </el-card>
      </div>
    </main>

    <!-- ── 新建配置 Dialog ── -->
    <el-dialog
      v-model="showAddDialog"
      title="New Terraform Config"
      width="580px"
      :close-on-click-modal="false"
    >
      <el-tabs v-model="addMode">
        <el-tab-pane label="Upload File" name="file">
          <el-form label-width="90px" style="margin-top: 12px">
            <el-form-item label="Name">
              <el-input v-model="newFile.name" placeholder="Enter config name" />
            </el-form-item>
            <el-form-item label="File">
              <el-upload
                ref="uploadRef"
                :auto-upload="false"
                :limit="1"
                accept=".tf"
                :on-change="onFileChange"
              >
                <el-button size="small">
                  <el-icon><Upload /></el-icon>
                  Choose .tf file
                </el-button>
              </el-upload>
            </el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="Write Online" name="text">
          <el-form label-width="90px" style="margin-top: 12px">
            <el-form-item label="Name">
              <el-input v-model="newText.name" placeholder="Enter config name" />
            </el-form-item>
            <el-form-item label="Content">
              <el-input
                v-model="newText.content"
                type="textarea"
                :rows="12"
                placeholder="Paste or write Terraform config content"
                style="font-family: 'Courier New', monospace; font-size: 13px"
              />
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="showAddDialog = false">Cancel</el-button>
        <el-button type="primary" :loading="adding" @click="submitAdd">Create</el-button>
      </template>
    </el-dialog>

    <!-- ── 手动扫描 Dialog ── -->
    <el-dialog
      v-model="showManualScan"
      title="Manual Scan — Select Tools"
      width="420px"
    >
      <div v-if="loadingTools" class="loading-placeholder">
        <el-icon class="is-loading"><Loading /></el-icon> Loading tools...
      </div>
      <el-checkbox-group v-else v-model="selectedToolIds">
        <div v-for="tool in tools" :key="tool.id" style="margin-bottom: 8px">
          <el-checkbox :value="tool.id">
            {{ tool.name }} <el-tag size="small" style="margin-left: 6px">v{{ tool.version }}</el-tag>
          </el-checkbox>
        </div>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="showManualScan = false">Cancel</el-button>
        <el-button
          type="primary"
          :loading="scanning"
          :disabled="selectedToolIds.length === 0"
          @click="runManualScan"
        >
          Start Scan
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  Plus, Loading, Document, Delete, Edit, VideoPlay,
  Setting, Download, Upload, View,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

interface Tool {
  id: number
  name: string
  version: string
}

interface FindingItem {
  rule_id: string
  severity: string
  description: string
  location: string
}

interface ToolResult {
  items: FindingItem[]
}

interface Report {
  status: string
  tools: Tool[]
  scanned_at: string | null
  result: {
    summary: { high: number; medium: number; low: number }
    tools: Record<string, ToolResult>
  } | null
}

const BASE = 'http://127.0.0.1:8000/api'
const auth = useAuthStore()

// ─── Config list ─────────────────────────────────────────────
interface Config {
  id: number
  name: string
  is_scanned: boolean
}

const configs = ref<Config[]>([])
const loadingConfigs = ref(false)
const selectedConfig = ref<Config | null>(null)

async function fetchConfigs() {
  if (!auth.user) return
  loadingConfigs.value = true
  try {
    const res = await auth.apiFetch(`${BASE}/autotf/users/${auth.user.id}/tf-configs/`)
    const json = await res.json()
    configs.value = json.data ?? []
  } catch {
    ElMessage.error('Failed to fetch configs')
  } finally {
    loadingConfigs.value = false
  }
}

async function selectConfig(cfg: Config) {
  selectedConfig.value = cfg
  configContent.value = ''
  report.value = null
  editingContent.value = false
  await Promise.all([loadContent(), loadReport()])
}

// ─── Config content ───────────────────────────────────────────
const configContent = ref('')
const loadingContent = ref(false)
const editingContent = ref(false)
const savingContent = ref(false)
let originalContent = ''

async function loadContent() {
  if (!selectedConfig.value) return
  loadingContent.value = true
  try {
    const res = await auth.apiFetch(`${BASE}/autotf/tf-configs/${selectedConfig.value.id}/content/`)
    const json = await res.json()
    configContent.value = json.data?.content ?? ''
    originalContent = configContent.value
  } catch {
    ElMessage.error('Failed to fetch config content')
  } finally {
    loadingContent.value = false
  }
}

function startEditContent() {
  originalContent = configContent.value
  editingContent.value = true
}

function cancelEdit() {
  configContent.value = originalContent
  editingContent.value = false
}

async function saveContent() {
  if (!selectedConfig.value) return
  savingContent.value = true
  try {
    const res = await auth.apiFetch(`${BASE}/autotf/tf-configs/${selectedConfig.value.id}/`, {
      method: 'PUT',
      body: JSON.stringify({ content: configContent.value }),
    })
    if (!res.ok) {
      const err = await res.json()
      ElMessage.error(err.message ?? 'Failed to save')
      return
    }
    ElMessage.success('Saved')
    editingContent.value = false
    originalContent = configContent.value
  } catch {
    ElMessage.error('Network error')
  } finally {
    savingContent.value = false
  }
}

// ─── Delete config ────────────────────────────────────────────
async function confirmDelete() {
  if (!selectedConfig.value) return
  try {
    await ElMessageBox.confirm(
      `Delete config "${selectedConfig.value.name}"? This cannot be undone.`,
      'Confirm Delete',
      { type: 'warning', confirmButtonText: 'Delete', cancelButtonText: 'Cancel' },
    )
  } catch {
    return
  }
  try {
    const res = await auth.apiFetch(`${BASE}/autotf/tf-configs/${selectedConfig.value.id}/`, {
      method: 'DELETE',
    })
    if (res.ok) {
      ElMessage.success('Deleted')
      selectedConfig.value = null
      await fetchConfigs()
    }
  } catch {
    ElMessage.error('Failed to delete')
  }
}

// ─── Add config ───────────────────────────────────────────────
const showAddDialog = ref(false)
const addMode = ref<'file' | 'text'>('file')
const adding = ref(false)
const newFile = ref({ name: '' })
const newText = ref({ name: '', content: '' })
let selectedFile: File | null = null

function openAddDialog() {
  addMode.value = 'file'
  newFile.value = { name: '' }
  newText.value = { name: '', content: '' }
  selectedFile = null
  showAddDialog.value = true
}

function onFileChange(file: UploadFile) {
  selectedFile = file.raw ?? null
}

async function submitAdd() {
  if (!auth.user) return
  if (addMode.value === 'file') {
    if (!newFile.value.name.trim() || !selectedFile) {
      ElMessage.warning('Please enter a name and select a file')
      return
    }
    adding.value = true
    try {
      const form = new FormData()
      form.append('name', newFile.value.name)
      form.append('file', selectedFile)
      const res = await auth.apiFetch(`${BASE}/autotf/users/${auth.user.id}/tf-configs/`, {
        method: 'POST',
        body: form,
      })
      if (!res.ok) {
        const err = await res.json()
        ElMessage.error(err.message ?? 'Failed to create')
        return
      }
      ElMessage.success('Config created')
      showAddDialog.value = false
      await fetchConfigs()
    } catch {
      ElMessage.error('Network error')
    } finally {
      adding.value = false
    }
  } else {
    if (!newText.value.name.trim() || !newText.value.content.trim()) {
      ElMessage.warning('Please enter a name and config content')
      return
    }
    adding.value = true
    try {
      const res = await auth.apiFetch(`${BASE}/autotf/users/${auth.user.id}/tf-configs/text/`, {
        method: 'POST',
        body: JSON.stringify(newText.value),
      })
      if (!res.ok) {
        const err = await res.json()
        ElMessage.error(err.message ?? 'Failed to create')
        return
      }
      ElMessage.success('Config created')
      showAddDialog.value = false
      await fetchConfigs()
    } catch {
      ElMessage.error('Network error')
    } finally {
      adding.value = false
    }
  }
}

// ─── Scan ─────────────────────────────────────────────────────
const scanning = ref(false)

async function runFullScan() {
  if (!selectedConfig.value) return
  scanning.value = true
  try {
    const res = await auth.apiFetch(`${BASE}/autotf/tf-configs/${selectedConfig.value.id}/scan/`, {
      method: 'POST',
    })
    if (!res.ok) {
      const err = await res.json()
      ElMessage.error(err.message ?? 'Scan failed')
      return
    }
    ElMessage.success('Scan complete')
    await Promise.all([fetchConfigs(), loadReport()])
    // refresh selected config scanned status
    const updated = configs.value.find((c) => c.id === selectedConfig.value!.id)
    if (updated) selectedConfig.value = updated
  } catch {
    ElMessage.error('Scan error')
  } finally {
    scanning.value = false
  }
}

// ─── Manual scan ──────────────────────────────────────────────
const showManualScan = ref(false)
const tools = ref<Tool[]>([])
const loadingTools = ref(false)
const selectedToolIds = ref<number[]>([])

async function openManualScan() {
  selectedToolIds.value = []
  showManualScan.value = true
  loadingTools.value = true
  try {
    const res = await auth.apiFetch(`${BASE}/autotf/tf-tools/`)
    const json = await res.json()
    tools.value = json.data ?? []
  } catch {
    ElMessage.error('Failed to fetch tools')
  } finally {
    loadingTools.value = false
  }
}

async function runManualScan() {
  if (!selectedConfig.value || selectedToolIds.value.length === 0) return
  scanning.value = true
  showManualScan.value = false
  try {
    const res = await auth.apiFetch(`${BASE}/autotf/tf-configs/${selectedConfig.value.id}/scan/manual/`, {
      method: 'POST',
      body: JSON.stringify({ tool_ids: selectedToolIds.value }),
    })
    if (!res.ok) {
      const err = await res.json()
      ElMessage.error(err.message ?? 'Scan failed')
      return
    }
    ElMessage.success('Scan complete')
    await Promise.all([fetchConfigs(), loadReport()])
    const updated = configs.value.find((c) => c.id === selectedConfig.value!.id)
    if (updated) selectedConfig.value = updated
  } catch {
    ElMessage.error('Scan error')
  } finally {
    scanning.value = false
  }
}

// ─── Report ───────────────────────────────────────────────────
const report = ref<Report | null>(null)
const loadingReport = ref(false)

async function loadReport() {
  if (!selectedConfig.value) return
  loadingReport.value = true
  try {
    const res = await auth.apiFetch(`${BASE}/autotf/tf-configs/${selectedConfig.value.id}/report/`)
    if (res.status === 404) {
      report.value = null
      return
    }
    const json = await res.json()
    report.value = json.data ?? null
  } catch {
    report.value = null
  } finally {
    loadingReport.value = false
  }
}

async function deleteReport() {
  if (!selectedConfig.value) return
  try {
    await ElMessageBox.confirm('Delete this scan report?', 'Confirm Delete', {
      type: 'warning',
      confirmButtonText: 'Delete',
      cancelButtonText: 'Cancel',
    })
  } catch {
    return
  }
  await auth.apiFetch(`${BASE}/autotf/tf-configs/${selectedConfig.value.id}/report/`, {
    method: 'DELETE',
  })
  report.value = null
  ElMessage.success('Report deleted')
  await fetchConfigs()
}

function downloadPdf() {
  if (!selectedConfig.value) return
  const url = `${BASE}/autotf/tf-configs/${selectedConfig.value.id}/report/pdf/?token=${auth.token}`
  window.open(url, '_blank')
}

function viewHtmlReport() {
  if (!selectedConfig.value) return
  const url = `${BASE}/autotf/tf-configs/${selectedConfig.value.id}/report/html/?token=${auth.token}`
  window.open(url, '_blank')
}

const hasFindings = computed(() => {
  const tools = report.value?.result?.tools
  if (!tools) return false
  return Object.values(tools).some((t) => t.items?.length > 0)
})

// ─── Helpers ─────────────────────────────────────────────────
function formatTime(ts: string | null | undefined) {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('zh-CN', { hour12: false })
}

function reportStatusType(s: string) {
  if (s === 'done') return 'success'
  if (s === 'running') return 'warning'
  if (s === 'failed') return 'danger'
  return 'info'
}

function reportStatusLabel(s: string) {
  const map: Record<string, string> = { pending: 'Pending', running: 'Running', done: 'Done', failed: 'Failed' }
  return map[s] ?? s
}

function severityType(s: string) {
  if (s === 'HIGH' || s === 'CRITICAL') return 'danger'
  if (s === 'MEDIUM') return 'warning'
  return 'info'
}

onMounted(fetchConfigs)
</script>

<style scoped>
.autotf-layout {
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

.config-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.config-card {
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

.config-card:hover {
  background: #2d3748;
}

.config-card.active {
  background: #1e3a5f;
  border-color: #2563eb;
}

.config-card-name {
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

.content-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.content-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.content-title {
  font-size: 18px;
  font-weight: 600;
  color: #1a202c;
}

/* ── Cards ── */
.section-card {
  border: 1px solid #e2e8f0;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  font-size: 14px;
}

.card-header-actions {
  display: flex;
  gap: 8px;
}

.loading-placeholder {
  color: #718096;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0;
}

.code-readonly :deep(.el-textarea__inner) {
  background: #f8fafc;
  color: #2d3748;
}

/* ── Scan ── */
.scan-actions {
  display: flex;
  gap: 12px;
}

.scan-progress {
  margin-top: 12px;
  color: #718096;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}

/* ── Report ── */
.report-empty {
  color: #718096;
  font-size: 13px;
  padding: 8px 0;
}

.report-meta {
  margin-bottom: 16px;
}

.tool-findings {
  margin-bottom: 20px;
}

.tool-name {
  font-size: 14px;
  font-weight: 600;
  color: #2d3748;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid #e2e8f0;
}

.severity-group {
  margin-bottom: 12px;
}

.severity-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.finding-count {
  font-size: 12px;
  color: #718096;
}
</style>
