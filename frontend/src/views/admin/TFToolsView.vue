<template>
    <div>
        <el-card>
            <template #header>
                <div class="card-header">
                    <span>TF Tools</span>
                    <el-button type="primary" :icon="Plus" @click="openCreate">New Tool</el-button>
                </div>
            </template>

            <el-table :data="tools" v-loading="loading" stripe>
                <el-table-column prop="id" label="ID" width="60" />
                <el-table-column prop="name" label="Name" width="180" />
                <el-table-column prop="version" label="Version" width="100" />
                <el-table-column prop="output_format" label="Format" width="90">
                    <template #default="{ row }">
                        <el-tag size="small" :type="formatTagType(row.output_format)">
                            {{ row.output_format }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column prop="cmd" label="Command" show-overflow-tooltip />
                <el-table-column label="Status" width="90" align="center">
                    <template #default="{ row }">
                        <el-tag size="small" :type="row.is_enabled ? 'success' : 'info'">
                            {{ row.is_enabled ? 'Enabled' : 'Disabled' }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="Actions" width="150" align="center">
                    <template #default="{ row }">
                        <el-button type="primary" size="small" text @click="openEdit(row)">Edit</el-button>
                        <el-popconfirm title="Delete this tool?" @confirm="deleteTool(row.id)">
                            <template #reference>
                                <el-button type="danger" size="small" text>Delete</el-button>
                            </template>
                        </el-popconfirm>
                    </template>
                </el-table-column>
            </el-table>
        </el-card>

        <!-- Create / Edit Dialog -->
        <el-dialog v-model="dialogVisible" :title="editingId ? 'Edit Tool' : 'New Tool'" width="600px">
            <el-form :model="form" label-width="130px">
                <el-form-item label="Name">
                    <el-input v-model="form.name" :disabled="!!editingId" />
                </el-form-item>
                <el-form-item label="Version">
                    <el-input v-model="form.version" />
                </el-form-item>
                <el-form-item label="Enabled">
                    <el-switch v-model="form.is_enabled" />
                </el-form-item>
                <el-divider>Execution</el-divider>
                <el-form-item label="Command">
                    <el-input v-model="form.cmd" placeholder="tfsec {target_dir} --format sarif" />
                </el-form-item>
                <el-form-item label="Init Command">
                    <el-input v-model="form.init_cmd" placeholder="terraform init -backend=false (optional)" />
                </el-form-item>
                <el-divider>Output</el-divider>
                <el-form-item label="Output Format">
                    <el-select v-model="form.output_format" @change="onFormatChange">
                        <el-option label="JSON" value="json" />
                        <el-option label="SARIF" value="sarif" />
                    </el-select>
                </el-form-item>
                <template v-if="form.output_format === 'json'">
                    <el-form-item label="Items Path">
                        <el-input v-model="form.items_path" placeholder="e.g. results.failed_checks" />
                    </el-form-item>
                    <el-form-item label="Severity Field">
                        <el-input v-model="form.severity_field" placeholder="e.g. severity" />
                    </el-form-item>
                    <el-form-item label="Severity Map">
                        <el-input v-model="severityMapRaw" type="textarea" :rows="2"
                            placeholder='{"error":"HIGH","warning":"MEDIUM"}' @blur="parseSeverityMap" />
                        <div v-if="severityMapError" class="field-error">{{ severityMapError }}</div>
                    </el-form-item>
                    <el-form-item label="Rule ID Field">
                        <el-input v-model="form.rule_id_field" placeholder="e.g. check_id" />
                    </el-form-item>
                    <el-form-item label="Description Field">
                        <el-input v-model="form.description_field" placeholder="e.g. check.name" />
                    </el-form-item>
                    <el-form-item label="Location File">
                        <el-input v-model="form.location_file_field" placeholder="e.g. location.filename" />
                    </el-form-item>
                    <el-form-item label="Location Line">
                        <el-input v-model="form.location_line_field" placeholder="e.g. location.start_line" />
                    </el-form-item>
                </template>
            </el-form>
            <template #footer>
                <el-button @click="dialogVisible = false">Cancel</el-button>
                <el-button type="primary" :loading="submitting" @click="submitForm">
                    {{ editingId ? 'Save' : 'Create' }}
                </el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

interface TFTool {
    id: number
    name: string
    version: string
    is_enabled: boolean
    cmd: string
    init_cmd: string
    output_format: string
    items_path: string
    severity_field: string
    severity_map: Record<string, string>
    rule_id_field: string
    description_field: string
    location_file_field: string
    location_line_field: string
}

const BASE = import.meta.env.VITE_API_BASE
const auth = useAuthStore()

const tools = ref<TFTool[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)

const emptyForm = (): Omit<TFTool, 'id'> => ({
    name: '', version: '', is_enabled: true,
    cmd: '', init_cmd: '',
    output_format: 'sarif',
    items_path: '', severity_field: '', severity_map: {},
    rule_id_field: '', description_field: '',
    location_file_field: '', location_line_field: '',
})

const form = ref(emptyForm())
const severityMapRaw = ref('')
const severityMapError = ref('')

function formatTagType(fmt: string) {
    if (fmt === 'sarif') return 'success'
    return ''
}

function onFormatChange() {
    // clear json-only fields when switching away from json
    if (form.value.output_format !== 'json') {
        form.value.items_path = ''
        form.value.severity_field = ''
        form.value.severity_map = {}
        form.value.rule_id_field = ''
        form.value.description_field = ''
        form.value.location_file_field = ''
        form.value.location_line_field = ''
        severityMapRaw.value = ''
    }
}

function parseSeverityMap() {
    severityMapError.value = ''
    if (!severityMapRaw.value.trim()) {
        form.value.severity_map = {}
        return
    }
    try {
        form.value.severity_map = JSON.parse(severityMapRaw.value)
    } catch {
        severityMapError.value = 'Invalid JSON'
    }
}

async function fetchTools() {
    loading.value = true
    const res = await auth.apiFetch(`${BASE}/autotf/tf-tools/`)
    if (res.ok) {
        const data = await res.json()
        tools.value = data.data ?? []
    }
    loading.value = false
}

function openCreate() {
    editingId.value = null
    form.value = emptyForm()
    severityMapRaw.value = ''
    severityMapError.value = ''
    dialogVisible.value = true
}

function openEdit(tool: TFTool) {
    editingId.value = tool.id
    form.value = { ...tool }
    severityMapRaw.value = tool.severity_map && Object.keys(tool.severity_map).length
        ? JSON.stringify(tool.severity_map, null, 2)
        : ''
    severityMapError.value = ''
    dialogVisible.value = true
}

async function submitForm() {
    parseSeverityMap()
    if (severityMapError.value) return

    submitting.value = true
    const url = editingId.value
        ? `${BASE}/autotf/tf-tools/${editingId.value}/`
        : `${BASE}/autotf/tf-tools/`
    const method = editingId.value ? 'PATCH' : 'POST'

    const res = await auth.apiFetch(url, { method, body: JSON.stringify(form.value) })
    submitting.value = false

    if (res.ok) {
        ElMessage.success(editingId.value ? 'Tool updated' : 'Tool created')
        dialogVisible.value = false
        fetchTools()
    } else {
        const err = await res.json().catch(() => ({}))
        ElMessage.error(err.message ?? 'Failed to save tool')
    }
}

async function deleteTool(id: number) {
    const res = await auth.apiFetch(`${BASE}/autotf/tf-tools/${id}/`, { method: 'DELETE' })
    if (res.ok) {
        ElMessage.success('Deleted')
        fetchTools()
    } else {
        ElMessage.error('Failed to delete')
    }
}

onMounted(fetchTools)
</script>

<style scoped>
.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.field-error {
    color: #f56c6c;
    font-size: 12px;
    margin-top: 4px;
}
</style>
