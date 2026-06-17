<template>
    <div class="autotf-layout">
        <!-- ── Sidebar (wide screens) ── -->
        <aside class="sidebar wide-sidebar">
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
            <div v-else-if="configs.length === 0" class="sidebar-empty">No configs yet</div>
            <div v-else class="config-list">
                <div v-for="cfg in configs" :key="cfg.id" class="config-card"
                    :class="{ active: selectedConfig?.id === cfg.id }" @click="selectConfig(cfg)">
                    <div class="config-card-name">{{ cfg.name }}</div>
                    <el-tag :type="cfg.is_scanned ? 'success' : 'info'" size="small" effect="dark">
                        {{ cfg.is_scanned ? 'Scanned' : 'Not scanned' }}
                    </el-tag>
                </div>
            </div>
        </aside>

        <!-- ── Sidebar drawer (narrow screens) ── -->
        <el-drawer v-model="sidebarOpen" direction="ltr" size="80%"
            :show-close="false" :with-header="false" class="sidebar-drawer">
            <div class="sidebar drawer-sidebar">
                <div class="sidebar-header">
                    <span class="sidebar-title">My Configs</span>
                    <el-button size="small" type="primary" @click="openAddDialog(); sidebarOpen = false">
                        <el-icon><Plus /></el-icon>
                        New
                    </el-button>
                </div>
                <div v-if="loadingConfigs" class="sidebar-loading">
                    <el-icon class="is-loading"><Loading /></el-icon>
                </div>
                <div v-else-if="configs.length === 0" class="sidebar-empty">No configs yet</div>
                <div v-else class="config-list">
                    <div v-for="cfg in configs" :key="cfg.id" class="config-card"
                        :class="{ active: selectedConfig?.id === cfg.id }"
                        @click="selectConfig(cfg); sidebarOpen = false">
                        <div class="config-card-name">{{ cfg.name }}</div>
                        <el-tag :type="cfg.is_scanned ? 'success' : 'info'" size="small" effect="dark">
                            {{ cfg.is_scanned ? 'Scanned' : 'Not scanned' }}
                        </el-tag>
                    </div>
                </div>
            </div>
        </el-drawer>

        <!-- ── Main content ── -->
        <main class="content">
            <div v-if="!selectedConfig" class="content-empty">
                <el-icon size="48" color="#4a5568"><Document /></el-icon>
                <p>Select a config from the left</p>
                <!-- narrow: show open button -->
                <el-button class="narrow-only" type="primary" @click="sidebarOpen = true">
                    <el-icon><List /></el-icon>
                    My Configs
                </el-button>
            </div>

            <div v-else class="content-body">
                <!-- 标题栏 -->
                <div class="content-header">
                    <div style="display:flex;align-items:center;gap:10px">
                        <el-button class="narrow-only sidebar-toggle" size="small" plain
                            @click="sidebarOpen = true">
                            <el-icon><List /></el-icon>
                        </el-button>
                        <span class="content-title">{{ selectedConfig.name }}</span>
                    </div>
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
                                <el-button v-if="!editingContent" size="small" @click="startEditContent"
                                    :loading="loadingContent">
                                    <el-icon>
                                        <Edit />
                                    </el-icon>
                                    Edit
                                </el-button>
                                <template v-else>
                                    <el-button size="small" type="primary" :loading="savingContent"
                                        @click="saveContent">
                                        Save
                                    </el-button>
                                    <el-button size="small" @click="cancelEdit">Cancel</el-button>
                                </template>
                            </div>
                        </div>
                    </template>
                    <div v-if="loadingContent && !editingContent" class="loading-placeholder">
                        <el-icon class="is-loading">
                            <Loading />
                        </el-icon> Loading...
                    </div>
                    <el-input v-else v-model="configContent" type="textarea" :rows="12" :readonly="!editingContent"
                        resize="none" style="font-family: 'Courier New', monospace; font-size: 13px"
                        :class="{ 'code-readonly': !editingContent }" />
                </el-card>

                <!-- 扫描 -->
                <el-card class="section-card scan-card" shadow="never">
                    <template #header>
                        <div class="card-header">
                            <span>Security Scan</span>
                        </div>
                    </template>
                    <div class="scan-actions">
                        <el-button type="primary" :loading="scanning" @click="runFullScan">
                            <el-icon>
                                <VideoPlay />
                            </el-icon>
                            Full Scan
                        </el-button>
                        <el-button :loading="scanning" @click="openManualScan">
                            <el-icon>
                                <Setting />
                            </el-icon>
                            Manual Scan
                        </el-button>
                    </div>
                    <div v-if="scanning" class="scan-progress">
                        <el-icon class="is-loading">
                            <Loading />
                        </el-icon>
                        Scanning, please wait...
                    </div>
                </el-card>

                <!-- Apply -->
                <el-card class="section-card deploy-card" shadow="never">
                    <template #header>
                        <div class="card-header">
                            <span>Deploy (Terraform Apply)</span>
                        </div>
                    </template>
                    <div class="scan-actions">
                        <el-tooltip :content="applyBlockReason" :disabled="canApply" placement="top">
                            <span>
                                <el-button type="success" :loading="applying" :disabled="!canApply" @click="runApply">
                                    <el-icon>
                                        <Promotion />
                                    </el-icon>
                                    Apply
                                </el-button>
                            </span>
                        </el-tooltip>
                        <span v-if="selectedConfig?.last_apply_at" class="apply-meta">
                            Last apply:
                            <el-tag :type="selectedConfig.last_apply_status === 'success' ? 'success' : 'danger'"
                                size="small" style="margin: 0 6px">
                                {{ selectedConfig.last_apply_status }}
                            </el-tag>
                            {{ formatTime(selectedConfig.last_apply_at) }}
                        </span>
                    </div>
                    <div v-if="applying" class="scan-progress">
                        <el-icon class="is-loading">
                            <Loading />
                        </el-icon>
                        Applying, please wait...
                    </div>
                    <el-input v-if="selectedConfig?.last_apply_output" v-model="selectedConfig.last_apply_output"
                        type="textarea" :rows="10" readonly resize="none"
                        style="margin-top: 12px; font-family: 'Courier New', monospace; font-size: 12px" />
                </el-card>

                <!-- 扫描报告 -->
                <el-card class="section-card" shadow="never">
                    <template #header>
                        <div class="card-header">
                            <span>Scan Report</span>
                            <div class="card-header-actions" v-if="report">
                                <el-button size="small" type="primary" plain @click="viewHtmlReport">
                                    <el-icon>
                                        <View />
                                    </el-icon>
                                    View Report
                                </el-button>
                                <el-button size="small" @click="downloadPdf">
                                    <el-icon>
                                        <Download />
                                    </el-icon>
                                    Download PDF
                                </el-button>
                                <el-button size="small" type="danger" plain @click="deleteReport">
                                    <el-icon>
                                        <Delete />
                                    </el-icon>
                                    Delete Report
                                </el-button>
                            </div>
                        </div>
                    </template>

                    <div v-if="loadingReport" class="loading-placeholder">
                        <el-icon class="is-loading">
                            <Loading />
                        </el-icon> Loading...
                    </div>
                    <div v-else-if="!report" class="report-empty">
                        No report yet. Run a scan first.
                    </div>
                    <template v-else>
                        <!-- ── Overview ── -->
                        <div class="report-overview">
                            <div class="overview-meta">
                                <span class="overview-time">Scanned {{ formatTime(report.scanned_at) }}</span>
                                <el-tag :type="reportStatusType(report.status)" size="small" style="margin-left:8px">
                                    {{ reportStatusLabel(report.status) }}
                                </el-tag>
                            </div>

                            <div class="sev-counters">
                                <div class="sev-counter sev-high">
                                    <span class="sev-num">{{ report.result?.summary?.high ?? 0 }}</span>
                                    <span class="sev-lbl">HIGH</span>
                                </div>
                                <div class="sev-counter sev-med">
                                    <span class="sev-num">{{ report.result?.summary?.medium ?? 0 }}</span>
                                    <span class="sev-lbl">MEDIUM</span>
                                </div>
                                <div class="sev-counter sev-low">
                                    <span class="sev-num">{{ report.result?.summary?.low ?? 0 }}</span>
                                    <span class="sev-lbl">LOW</span>
                                </div>
                                <div class="sev-counter sev-total">
                                    <span class="sev-num">{{ totalFindings }}</span>
                                    <span class="sev-lbl">TOTAL</span>
                                </div>
                            </div>

                            <!-- severity 分布条 -->
                            <div v-if="totalFindings > 0" class="sev-bar-wrap">
                                <div class="sev-bar">
                                    <div v-if="(report.result?.summary?.high ?? 0) > 0"
                                        class="sev-bar-seg seg-high"
                                        :style="{ width: sevPct('high') + '%' }"
                                        :title="`HIGH: ${report.result?.summary?.high}`" />
                                    <div v-if="(report.result?.summary?.medium ?? 0) > 0"
                                        class="sev-bar-seg seg-med"
                                        :style="{ width: sevPct('medium') + '%' }"
                                        :title="`MEDIUM: ${report.result?.summary?.medium}`" />
                                    <div v-if="(report.result?.summary?.low ?? 0) > 0"
                                        class="sev-bar-seg seg-low"
                                        :style="{ width: sevPct('low') + '%' }"
                                        :title="`LOW: ${report.result?.summary?.low}`" />
                                </div>
                                <div class="sev-bar-legend">
                                    <span class="legend-dot dot-high" /> HIGH {{ sevPct('high') }}%
                                    <span class="legend-dot dot-med" style="margin-left:12px" /> MED {{ sevPct('medium') }}%
                                    <span class="legend-dot dot-low" style="margin-left:12px" /> LOW {{ sevPct('low') }}%
                                </div>
                            </div>
                            <div v-else class="all-clear">
                                ✓ No security issues found across all tools
                            </div>
                        </div>

                        <!-- ── Per-tool sections ── -->
                        <div v-for="(toolResult, toolName) in report.result?.tools" :key="toolName"
                            class="tool-section">
                            <!-- 工具头部 -->
                            <div class="tool-header">
                                <div class="tool-header-left">
                                    <span class="tool-title">{{ toolName }}</span>
                                    <el-tag v-if="toolMeta(toolName)?.version" size="small" type="info" effect="plain"
                                        style="font-family:monospace;font-size:11px">
                                        {{ toolMeta(toolName)?.version }}
                                    </el-tag>
                                    <el-tag size="small" effect="plain"
                                        :type="toolMeta(toolName)?.output_format === 'sarif' ? 'warning' : 'success'">
                                        {{ (toolMeta(toolName)?.output_format ?? 'json').toUpperCase() }}
                                    </el-tag>
                                </div>
                                <div class="tool-header-right">
                                    <el-tag v-if="toolResult.items?.length > 0"
                                        :type="toolFindingsBadgeType(toolResult.items)"
                                        size="small" effect="dark">
                                        {{ toolResult.items.length }} finding{{ toolResult.items.length !== 1 ? 's' : '' }}
                                    </el-tag>
                                    <el-tag v-else type="success" size="small" effect="dark">✓ Clean</el-tag>
                                </div>
                            </div>

                            <!-- 工具检查方式说明 -->
                            <div class="tool-info-grid">
                                <div class="tool-info-row">
                                    <span class="info-label">Checks</span>
                                    <span class="info-value">{{ toolCheckDesc(String(toolName)) }}</span>
                                </div>
                                <div class="tool-info-row" v-if="toolMeta(toolName)?.cmd">
                                    <span class="info-label">Command</span>
                                    <code class="info-cmd">{{ simplifyCmd(toolMeta(toolName)?.cmd ?? '') }}</code>
                                </div>
                                <div class="tool-info-row" v-if="toolMeta(toolName)?.init_cmd">
                                    <span class="info-label">Init</span>
                                    <code class="info-cmd">{{ simplifyCmd(toolMeta(toolName)?.init_cmd ?? '') }}</code>
                                </div>
                                <div class="tool-info-row">
                                    <span class="info-label">Output</span>
                                    <span class="info-value">
                                        {{ toolMeta(toolName)?.output_format === 'sarif'
                                            ? 'SARIF — Static Analysis Results Interchange Format (industry standard)'
                                            : 'JSON — parsed via custom field mapping' }}
                                    </span>
                                </div>
                            </div>

                            <!-- checklist -->
                            <div class="check-list">
                                <div v-if="!toolResult.items || toolResult.items.length === 0"
                                    class="check-row check-pass">
                                    <span class="check-bullet">—</span>
                                    <span class="check-desc">All checks passed</span>
                                    <span class="check-status status-pass">pass</span>
                                </div>
                                <div v-for="item in toolResult.items" :key="item.rule_id + item.location"
                                    class="check-row" :class="'check-' + item.severity.toLowerCase()">
                                    <span class="check-bullet">—</span>
                                    <span class="check-desc">
                                        <span class="check-detail">{{ item.description || item.rule_id }}</span>
                                        <span v-if="item.rule_id" class="check-item-name">[{{ item.rule_id }}]</span>
                                        <span v-if="item.location" class="check-loc">@ {{ item.location }}</span>
                                    </span>
                                    <span class="check-status" :class="'status-' + item.severity.toLowerCase()">
                                        risk[{{ item.severity.toLowerCase() }}]
                                    </span>
                                </div>
                            </div>

                            <!-- result summary line -->
                            <div class="tool-result-line">
                                <span class="result-label">result:</span>
                                <template v-if="!toolResult.items || toolResult.items.length === 0">
                                    <span class="result-clean">no issues found</span>
                                </template>
                                <template v-else>
                                    <span class="result-total">{{ toolResult.items.length }} finding{{ toolResult.items.length !== 1 ? 's' : '' }}</span>
                                    <span v-if="toolSevCount(toolResult.items, 'HIGH') > 0" class="result-sev sev-high">
                                        {{ toolSevCount(toolResult.items, 'HIGH') }} high
                                    </span>
                                    <span v-if="toolSevCount(toolResult.items, 'CRITICAL') > 0" class="result-sev sev-high">
                                        {{ toolSevCount(toolResult.items, 'CRITICAL') }} critical
                                    </span>
                                    <span v-if="toolSevCount(toolResult.items, 'MEDIUM') > 0" class="result-sev sev-med">
                                        {{ toolSevCount(toolResult.items, 'MEDIUM') }} medium
                                    </span>
                                    <span v-if="toolSevCount(toolResult.items, 'LOW') > 0" class="result-sev sev-low">
                                        {{ toolSevCount(toolResult.items, 'LOW') }} low
                                    </span>
                                </template>
                            </div>
                        </div>
                    </template>
                </el-card>
            </div>
        </main>

        <!-- ── 新建配置 Dialog ── -->
        <el-dialog v-model="showAddDialog" title="New Terraform Config" width="580px" :close-on-click-modal="false">
            <el-tabs v-model="addMode">
                <el-tab-pane label="Upload File" name="file">
                    <el-form label-width="90px" style="margin-top: 12px">
                        <el-form-item label="Name">
                            <el-input v-model="newFile.name" placeholder="Enter config name" />
                        </el-form-item>
                        <el-form-item label="File">
                            <el-upload ref="uploadRef" :auto-upload="false" :limit="1" accept=".tf"
                                :on-change="onFileChange">
                                <el-button size="small">
                                    <el-icon>
                                        <Upload />
                                    </el-icon>
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
                            <el-input v-model="newText.content" type="textarea" :rows="12"
                                placeholder="Paste or write Terraform config content"
                                style="font-family: 'Courier New', monospace; font-size: 13px" />
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
        <el-dialog v-model="showManualScan" title="Manual Scan — Select Tools" width="420px">
            <div v-if="loadingTools" class="loading-placeholder">
                <el-icon class="is-loading">
                    <Loading />
                </el-icon> Loading tools...
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
                <el-button type="primary" :loading="scanning" :disabled="selectedToolIds.length === 0"
                    @click="runManualScan">
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
    Setting, Download, Upload, View, Promotion, List,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

interface Tool {
    id: number
    name: string
    version: string
    cmd?: string
    init_cmd?: string
    output_format?: string
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

const BASE = import.meta.env.VITE_API_BASE
const auth = useAuthStore()
const sidebarOpen = ref(false)

// ─── Config list ─────────────────────────────────────────────
interface Config {
    id: number
    name: string
    is_scanned: boolean
    last_apply_at: string | null
    last_apply_status: string | null
    last_apply_output: string
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

// ─── Apply ───────────────────────────────────────────────────
const applying = ref(false)

const canApply = computed(() => {
    if (!selectedConfig.value?.is_scanned) return false
    if (!report.value || report.value.status !== 'done') return false
    if ((report.value.result?.summary?.high ?? 0) > 0) return false
    return true
})

const applyBlockReason = computed(() => {
    if (!selectedConfig.value?.is_scanned) return 'Run a scan first'
    if (!report.value || report.value.status !== 'done') return 'Scan must be complete'
    if ((report.value.result?.summary?.high ?? 0) > 0) return 'Fix all HIGH severity issues first'
    return ''
})

async function runApply() {
    if (!selectedConfig.value) return
    applying.value = true
    try {
        const res = await auth.apiFetch(
            `${BASE}/autotf/tf-configs/${selectedConfig.value.id}/apply/`,
            { method: 'POST' },
        )
        const json = await res.json()
        if (!res.ok) {
            ElMessage.error(json.message ?? 'Apply failed')
            return
        }
        const updated: Config = json.data
        // update selectedConfig in-place so apply output is visible immediately
        selectedConfig.value = { ...selectedConfig.value, ...updated }
        // also sync configs list
        const idx = configs.value.findIndex((c) => c.id === updated.id)
        if (idx !== -1) configs.value[idx] = { ...configs.value[idx], ...updated }

        if (updated.last_apply_status === 'success') {
            ElMessage.success('Apply succeeded')
        } else {
            ElMessage.error('Apply failed — check output below')
        }
    } catch {
        ElMessage.error('Network error during apply')
    } finally {
        applying.value = false
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

// ─── All tools metadata (for report display) ─────────────────
const allToolsMeta = ref<Tool[]>([])

async function fetchAllTools() {
    try {
        const res = await auth.apiFetch(`${BASE}/autotf/tf-tools/`)
        const json = await res.json()
        allToolsMeta.value = json.data ?? []
    } catch { /* non-critical */ }
}

function toolMeta(name: string): Tool | undefined {
    return allToolsMeta.value.find((t) => t.name === name)
}

const TOOL_CHECK_DESC: Record<string, string> = {
    terraform_validate: 'Syntax validation & schema check — verifies resource types, required attributes, and HCL structure against provider schemas',
    tflint: 'Linting & best practices — detects deprecated syntax, unused variables, naming conventions, and provider-specific rule violations',
    checkov: 'Policy-as-code security scan — 1000+ CIS benchmark checks covering IAM, encryption, network exposure, logging, and compliance (AWS/GCP/Azure/K8s)',
    tfsec: 'Security misconfiguration detection — static analysis for insecure defaults: open security groups, unencrypted storage, public S3 buckets, missing TLS',
    trivy: 'Vulnerability & misconfiguration scanner — checks CVE databases, secret detection, and IaC misconfigurations across cloud providers',
}

function simplifyCmd(cmd: string): string {
    // replace absolute paths like /usr/bin/foo or /home/.../foo with just the binary name
    return cmd.replace(/(?:\/[^\s/]+)+\/([^\s/]+)/g, '$1')
}

function toolCheckDesc(name: string): string {
    const key = Object.keys(TOOL_CHECK_DESC).find((k) => name.toLowerCase().includes(k))
    return key ? TOOL_CHECK_DESC[key]! : 'Static analysis scan for security issues and misconfigurations'
}

function toolFindingsBadgeType(items: FindingItem[]): string {
    if (items.some((i) => i.severity === 'HIGH' || i.severity === 'CRITICAL')) return 'danger'
    if (items.some((i) => i.severity === 'MEDIUM')) return 'warning'
    return 'info'
}

function toolSevCount(items: FindingItem[], sev: string): number {
    return items.filter((i) => i.severity === sev).length
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

const totalFindings = computed(() => {
    const s = report.value?.result?.summary
    if (!s) return 0
    return (s.high ?? 0) + (s.medium ?? 0) + (s.low ?? 0)
})

function sevPct(level: 'high' | 'medium' | 'low'): number {
    const total = totalFindings.value
    if (total === 0) return 0
    const val = report.value?.result?.summary?.[level] ?? 0
    return Math.round((val / total) * 100)
}

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

onMounted(() => {
    fetchConfigs()
    fetchAllTools()
})
</script>

<style scoped>
.autotf-layout {
    display: flex;
    height: 100%;
    overflow: hidden;
}

.narrow-only { display: none; }

@media (max-width: 680px) {
    /* sidebar */
    .wide-sidebar { display: none !important; }
    .narrow-only  { display: flex !important; }

    /* content body — tighter padding */
    .content-body {
        padding: 12px 12px 16px;
        gap: 12px;
    }

    /* card body padding */
    .scan-card :deep(.el-card__body),
    .deploy-card :deep(.el-card__body) {
        padding: 14px 14px !important;
    }

    /* overview counters: 2x2 grid */
    .sev-counters {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
    }

    /* overview card padding */
    .report-overview {
        padding: 14px 12px;
    }

    /* tool section header wrap */
    .tool-header {
        flex-wrap: wrap;
        gap: 6px;
        padding: 10px 12px;
    }

    .tool-header-left {
        flex-wrap: wrap;
    }

    /* tool info grid: stack label + value */
    .tool-info-grid {
        padding: 10px 12px;
    }

    .tool-info-row {
        flex-direction: column;
        gap: 2px;
    }

    .info-label {
        width: auto;
    }

    /* cmd wraps instead of overflows */
    .info-cmd {
        word-break: break-all;
        white-space: pre-wrap;
    }

    /* check rows: allow status badge to wrap below */
    .check-list {
        padding: 6px 12px 4px;
    }

    .check-row {
        flex-wrap: wrap;
        gap: 4px;
    }

    .check-status {
        margin-left: 16px;
    }

    /* result line */
    .tool-result-line {
        padding: 6px 12px 10px;
    }

    /* scan action buttons stack */
    .scan-actions {
        flex-wrap: wrap;
    }

    /* header actions wrap */
    .header-actions {
        flex-wrap: wrap;
        gap: 6px;
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

.sidebar-toggle {
    padding: 4px 8px;
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
    padding: 20px 24px 20px 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    scrollbar-gutter: stable;
    scrollbar-width: thin;
    scrollbar-color: #cbd5e0 transparent;
}

.content-body::-webkit-scrollbar {
    width: 6px;
}

.content-body::-webkit-scrollbar-thumb {
    background: #cbd5e0;
    border-radius: 3px;
}

.content-body::-webkit-scrollbar-track {
    background: transparent;
}

.content-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
}

.content-title {
    font-size: 18px;
    font-weight: 600;
    color: #1a202c;
}

/* ── Cards ── */
.section-card {
    border: 1px solid #e2e8f0;
    flex-shrink: 0;
}

.scan-card :deep(.el-card__body),
.deploy-card :deep(.el-card__body) {
    min-height: 96px;
    padding: 20px 20px;
    overflow: visible;
    box-sizing: border-box;
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

/* ── Overview ── */
.report-overview {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 18px 20px;
}

.overview-meta {
    display: flex;
    align-items: center;
    margin-bottom: 16px;
    font-size: 12px;
    color: #718096;
}

.overview-time {
    font-size: 12px;
    color: #718096;
}

.sev-counters {
    display: flex;
    gap: 16px;
    margin-bottom: 16px;
}

.sev-counter {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 12px 8px;
    border-radius: 8px;
    border: 1px solid transparent;
}

.sev-counter.sev-high   { background: #fff5f5; border-color: #fed7d7; }
.sev-counter.sev-med    { background: #fffaf0; border-color: #feebc8; }
.sev-counter.sev-low    { background: #f0fff4; border-color: #c6f6d5; }
.sev-counter.sev-total  { background: #f7fafc; border-color: #e2e8f0; }

.sev-num {
    font-size: 28px;
    font-weight: 700;
    line-height: 1;
}
.sev-high .sev-num  { color: #e53e3e; }
.sev-med .sev-num   { color: #dd6b20; }
.sev-low .sev-num   { color: #38a169; }
.sev-total .sev-num { color: #2d3748; }

.sev-lbl {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    margin-top: 4px;
    color: #718096;
}

.sev-bar-wrap {
    margin-top: 4px;
}

.sev-bar {
    height: 10px;
    border-radius: 5px;
    overflow: hidden;
    display: flex;
    background: #edf2f7;
}

.sev-bar-seg {
    height: 100%;
    transition: width 0.3s;
}
.seg-high { background: #e53e3e; }
.seg-med  { background: #ed8936; }
.seg-low  { background: #48bb78; }

.sev-bar-legend {
    margin-top: 6px;
    font-size: 11px;
    color: #718096;
    display: flex;
    align-items: center;
}

.legend-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 4px;
}
.dot-high { background: #e53e3e; }
.dot-med  { background: #ed8936; }
.dot-low  { background: #48bb78; }

.all-clear {
    color: #38a169;
    font-size: 13px;
    font-weight: 500;
    padding: 8px 0 4px;
}

/* ── Tool sections ── */
.tool-section {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
}

.tool-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: #f7fafc;
    border-bottom: 1px solid #e2e8f0;
}

.tool-header-left {
    display: flex;
    align-items: center;
    gap: 8px;
}

.tool-title {
    font-size: 14px;
    font-weight: 600;
    color: #1a202c;
    font-family: 'Courier New', monospace;
}

.tool-header-right {
    display: flex;
    align-items: center;
    gap: 6px;
}

.tool-info-grid {
    padding: 12px 16px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    border-bottom: 1px solid #f0f4f8;
    background: #fdfdfe;
}

.tool-info-row {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    font-size: 12px;
}

.info-label {
    flex-shrink: 0;
    width: 62px;
    color: #a0aec0;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
    padding-top: 1px;
    letter-spacing: 0.3px;
}

.info-value {
    color: #4a5568;
    line-height: 1.5;
}

.info-cmd {
    font-family: 'Courier New', monospace;
    font-size: 12px;
    color: #2b6cb0;
    background: #ebf8ff;
    padding: 2px 6px;
    border-radius: 3px;
    word-break: break-all;
}

/* ── Checklist ── */
.check-list {
    padding: 8px 16px 4px;
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.check-row {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    font-size: 13px;
    font-family: 'Courier New', monospace;
    line-height: 1.5;
}

.check-bullet {
    flex-shrink: 0;
    color: #a0aec0;
    margin-top: 1px;
}

.check-desc {
    flex: 1;
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 6px;
    color: #2d3748;
}

.check-item-name {
    font-weight: 700;
    color: #2b6cb0;
    background: #ebf8ff;
    border: 1px solid #bee3f8;
    border-radius: 3px;
    padding: 0 5px;
    font-size: 12px;
    letter-spacing: 0.1px;
    white-space: nowrap;
}

.check-detail {
    color: #1a202c;
    font-size: 13px;
    font-weight: 500;
}

.check-loc {
    color: #718096;
    font-size: 11px;
}

.check-status {
    flex-shrink: 0;
    font-size: 12px;
    font-weight: 600;
    padding: 1px 8px;
    border-radius: 3px;
    font-family: 'Courier New', monospace;
    letter-spacing: 0.2px;
    margin-top: 2px;
}

.status-pass    { background: #f0fff4; color: #276749; border: 1px solid #c6f6d5; }
.status-low     { background: #ebf8ff; color: #2b6cb0; border: 1px solid #bee3f8; }
.status-medium  { background: #fffaf0; color: #c05621; border: 1px solid #feebc8; }
.status-high,
.status-critical { background: #fff5f5; color: #c53030; border: 1px solid #fed7d7; }

/* result line */
.tool-result-line {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px 12px;
    font-size: 13px;
    font-family: 'Courier New', monospace;
    border-top: 1px dashed #e2e8f0;
    margin-top: 6px;
    flex-wrap: wrap;
}

.result-label {
    color: #a0aec0;
    font-weight: 600;
}

.result-clean {
    color: #276749;
    font-weight: 600;
}

.result-total {
    color: #2d3748;
    font-weight: 600;
}

.result-sev {
    padding: 1px 8px;
    border-radius: 3px;
    font-size: 12px;
    font-weight: 600;
}

.result-sev.sev-high { background: #fff5f5; color: #c53030; border: 1px solid #fed7d7; }
.result-sev.sev-med  { background: #fffaf0; color: #c05621; border: 1px solid #feebc8; }
.result-sev.sev-low  { background: #ebf8ff; color: #2b6cb0; border: 1px solid #bee3f8; }
</style>
