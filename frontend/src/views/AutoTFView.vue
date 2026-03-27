<template>
  <div style="padding: 24px; font-family: monospace">
    <h2>autotf API Test</h2>

    <!-- Auth -->
    <section>
      <h3>1. Login</h3>
      <input v-model="login.username" placeholder="username" />
      <input v-model="login.password" placeholder="password" type="password" />
      <button @click="getToken">Login</button>
      <div v-if="token">
        <span style="color: green">✓ Token acquired</span>
        <br />
        <small>{{ token.slice(0, 40) }}...</small>
      </div>
    </section>

    <!-- Tools -->
    <section>
      <h3>2. Tools</h3>
      <button @click="getTools">GET /autotf/tf-tools/</button>
    </section>

    <!-- Config List + Create -->
    <section>
      <h3>3. Configs</h3>
      user id: <input v-model="userId" placeholder="user id" style="width: 60px" />
      <button @click="getConfigs">GET /users/{{ userId }}/tf-configs/</button>
      <br /><br />

      <b>Upload file</b><br />
      <input v-model="configName" placeholder="config name" />
      <input type="file" @change="onFileChange" accept=".tf" />
      <button @click="uploadConfig">POST /users/{{ userId }}/tf-configs/</button>
      <br /><br />

      <b>Write text</b><br />
      <input v-model="textName" placeholder="config name" />
      <br />
      <textarea v-model="textContent" placeholder="terraform config content" rows="6" cols="60" />
      <br />
      <button @click="writeConfig">POST /users/{{ userId }}/tf-configs/text/</button>
    </section>

    <!-- Config Detail / Content / Update / Delete -->
    <section>
      <h3>4. Config Detail / Content / Update / Delete</h3>
      config id: <input v-model="configId" placeholder="config id" style="width: 60px" />
      <button @click="getConfigDetail">GET /tf-configs/{{ configId }}/</button>
      <button @click="getConfigContent">GET /tf-configs/{{ configId }}/content/</button>
      <button @click="deleteConfig">DELETE /tf-configs/{{ configId }}/</button>
      <br /><br />

      <b>Update — upload new file</b><br />
      <input type="file" @change="onUpdateFileChange" accept=".tf" />
      <button @click="updateConfigFile">PUT /tf-configs/{{ configId }}/ (file)</button>
      <br /><br />

      <b>Update — edit text</b><br />
      <textarea v-model="updateContent" placeholder="new terraform content" rows="6" cols="60" />
      <br />
      <button @click="updateConfigText">PUT /tf-configs/{{ configId }}/ (text)</button>
    </section>

    <!-- Scan -->
    <section>
      <h3>5. Scan</h3>
      config id: <input v-model="configId" placeholder="config id" style="width: 60px" />
      <br /><br />
      <button @click="runFullScan">POST /tf-configs/{{ configId }}/scan/ (full)</button>
      <br /><br />
      <b>Manual scan</b> — tool ids (comma-separated):
      <input v-model="toolIds" placeholder="e.g. 1" style="width: 120px" />
      <button @click="runManualScan">POST /tf-configs/{{ configId }}/scan/manual/</button>
    </section>

    <!-- Report -->
    <section>
      <h3>6. Report</h3>
      config id: <input v-model="configId" placeholder="config id" style="width: 60px" />
      <button @click="getReport">GET /tf-configs/{{ configId }}/report/</button>
      <button @click="deleteReport">DELETE /tf-configs/{{ configId }}/report/</button>
      <br /><br />
      <a :href="reportHtmlUrl" target="_blank" rel="noopener"> ↗ View report (HTML) </a>
      &nbsp;
      <a :href="reportPdfUrl" target="_blank" rel="noopener"> ↓ Download PDF </a>
    </section>

    <!-- Response -->
    <section>
      <h3>Response</h3>
      <pre style="background: #1e1e1e; color: #d4d4d4; padding: 16px; border-radius: 6px">{{
        result
      }}</pre>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const BASE = 'http://127.0.0.1:8000/api'

const token = ref('')
const userId = ref('1')
const configId = ref('')
const result = ref('— no request yet —')

const reportHtmlUrl = computed(
  () => `${BASE}/autotf/tf-configs/${configId.value}/report/html/?token=${token.value}`,
)
const reportPdfUrl = computed(
  () => `${BASE}/autotf/tf-configs/${configId.value}/report/pdf/?token=${token.value}`,
)

const login = ref({ username: '', password: '' })
const configName = ref('')
const textName = ref('')
const textContent = ref('')
const updateContent = ref('')
const toolIds = ref('1')

let selectedFile: File | null = null
let updateFile: File | null = null

function onFileChange(e: Event) {
  selectedFile = (e.target as HTMLInputElement).files?.[0] ?? null
}

function onUpdateFileChange(e: Event) {
  updateFile = (e.target as HTMLInputElement).files?.[0] ?? null
}

function authHeaders() {
  return { Authorization: `Bearer ${token.value}` }
}

function jsonHeaders() {
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${token.value}` }
}

async function req(url: string, options: RequestInit = {}) {
  try {
    const res = await fetch(url, options)
    const data = await res.json()
    result.value = JSON.stringify(data, null, 2)
  } catch (e) {
    result.value = String(e)
  }
}

async function getToken() {
  const res = await fetch(`${BASE}/auth/token/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(login.value),
  })
  const data = await res.json()
  result.value = JSON.stringify(data, null, 2)
  if (data.access) token.value = data.access
}

async function getTools() {
  await req(`${BASE}/autotf/tf-tools/`, { headers: authHeaders() })
}

async function getConfigs() {
  await req(`${BASE}/autotf/users/${userId.value}/tf-configs/`, { headers: authHeaders() })
}

async function uploadConfig() {
  if (!selectedFile) {
    result.value = 'No file selected'
    return
  }
  const form = new FormData()
  form.append('name', configName.value)
  form.append('file', selectedFile)
  await req(`${BASE}/autotf/users/${userId.value}/tf-configs/`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  })
}

async function writeConfig() {
  await req(`${BASE}/autotf/users/${userId.value}/tf-configs/text/`, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ name: textName.value, content: textContent.value }),
  })
}

async function getConfigDetail() {
  await req(`${BASE}/autotf/tf-configs/${configId.value}/`, { headers: authHeaders() })
}

async function getConfigContent() {
  await req(`${BASE}/autotf/tf-configs/${configId.value}/content/`, { headers: authHeaders() })
}

async function deleteConfig() {
  await req(`${BASE}/autotf/tf-configs/${configId.value}/`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
}

async function updateConfigFile() {
  if (!updateFile) {
    result.value = 'No file selected'
    return
  }
  const form = new FormData()
  form.append('file', updateFile)
  await req(`${BASE}/autotf/tf-configs/${configId.value}/`, {
    method: 'PUT',
    headers: authHeaders(),
    body: form,
  })
}

async function updateConfigText() {
  await req(`${BASE}/autotf/tf-configs/${configId.value}/`, {
    method: 'PUT',
    headers: jsonHeaders(),
    body: JSON.stringify({ content: updateContent.value }),
  })
}

async function runFullScan() {
  await req(`${BASE}/autotf/tf-configs/${configId.value}/scan/`, {
    method: 'POST',
    headers: authHeaders(),
  })
}

async function runManualScan() {
  const ids = toolIds.value
    .split(',')
    .map((s) => parseInt(s.trim()))
    .filter(Boolean)
  await req(`${BASE}/autotf/tf-configs/${configId.value}/scan/manual/`, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ tool_ids: ids }),
  })
}

async function getReport() {
  await req(`${BASE}/autotf/tf-configs/${configId.value}/report/`, { headers: authHeaders() })
}

async function deleteReport() {
  await req(`${BASE}/autotf/tf-configs/${configId.value}/report/`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
}
</script>

<style scoped>
section {
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid #333;
}
input,
textarea {
  margin: 4px;
}
button {
  margin: 4px;
  cursor: pointer;
}
</style>
