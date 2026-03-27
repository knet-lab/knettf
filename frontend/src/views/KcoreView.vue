<template>
  <div style="padding: 24px; font-family: monospace">
    <h2>kcore API Test</h2>

    <!-- Auth -->
    <section>
      <h3>1. Register</h3>
      <input v-model="reg.username" placeholder="username" />
      <input v-model="reg.email" placeholder="email" />
      <input v-model="reg.password" placeholder="password" type="password" />
      <button @click="register">Register</button>
    </section>

    <section>
      <h3>2. Login</h3>
      <input v-model="login.username" placeholder="username" />
      <input v-model="login.password" placeholder="password" type="password" />
      <button @click="getToken">Login</button>
      <div v-if="token">
        <span style="color: green">✓ Token acquired</span>
        <br />
        <small>{{ token.slice(0, 40) }}...</small>
      </div>
    </section>

    <!-- Users -->
    <section>
      <h3>3. Users</h3>
      <button @click="getUsers">GET /users/</button>
      <button @click="getUserDetail">GET /users/{{ userId }}/</button>
      <input v-model="userId" placeholder="user id" style="width: 60px" />
    </section>

    <!-- Clusters -->
    <section>
      <h3>4. Clusters</h3>
      <button @click="getClusters">GET /users/{{ userId }}/clusters/</button>
      <br /><br />
      <textarea v-model="clusterForm.kubeconfig" placeholder="kubeconfig yaml" rows="4" cols="60" />
      <br />
      <input v-model="clusterForm.name" placeholder="cluster name" />
      <button @click="createCluster">POST /users/{{ userId }}/clusters/</button>
    </section>

    <!-- Pod Logs WebSocket -->
    <section>
      <h3>5. Pod Logs (WebSocket)</h3>
      <input v-model="ws.clusterId" placeholder="cluster id" style="width: 80px" />
      <input v-model="ws.namespace" placeholder="namespace" />
      <input v-model="ws.podName" placeholder="pod name" />
      <button @click="connectWs" :disabled="wsConnected">Connect</button>
      <button @click="disconnectWs" :disabled="!wsConnected">Disconnect</button>
      <span v-if="wsConnected" style="color: green; margin-left: 8px">● Connected</span>
      <span v-else style="color: gray; margin-left: 8px">○ Disconnected</span>
      <br /><br />
      <pre
        style="
          background: #0d0d0d;
          color: #00ff41;
          padding: 16px;
          border-radius: 6px;
          height: 200px;
          overflow-y: auto;
        "
        ref="logBox"
        >{{ logs || '— waiting for logs —' }}</pre
      >
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
import { ref, nextTick } from 'vue'

const BASE = 'http://127.0.0.1:8000/api'
const WS_BASE = 'ws://127.0.0.1:8000'

const token = ref('')
const userId = ref('1')
const result = ref('— no request yet —')

const reg = ref({ username: '', email: '', password: '' })
const login = ref({ username: '', password: '' })
const clusterForm = ref({ name: '', kubeconfig: '' })

const ws = ref({ clusterId: '1', namespace: 'default', podName: '' })
const wsConnected = ref(false)
const logs = ref('')
const logBox = ref<HTMLPreElement | null>(null)
let socket: WebSocket | null = null

function authHeaders() {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token.value}`,
  }
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

async function register() {
  await req(`${BASE}/kcore/users/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(reg.value),
  })
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

async function getUsers() {
  await req(`${BASE}/kcore/users/`, { headers: authHeaders() })
}

async function getUserDetail() {
  await req(`${BASE}/kcore/users/${userId.value}/`, { headers: authHeaders() })
}

async function getClusters() {
  await req(`${BASE}/kcore/users/${userId.value}/clusters/`, { headers: authHeaders() })
}

async function createCluster() {
  await req(`${BASE}/kcore/users/${userId.value}/clusters/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(clusterForm.value),
  })
}

function connectWs() {
  const { clusterId, namespace, podName } = ws.value
  const url = `${WS_BASE}/ws/clusters/${clusterId}/pods/${namespace}/${podName}/logs/`
  logs.value = ''
  socket = new WebSocket(url)

  socket.onopen = () => {
    wsConnected.value = true
  }

  socket.onmessage = async (event) => {
    const { log } = JSON.parse(event.data)
    logs.value += log
    await nextTick()
    if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
  }

  socket.onclose = () => {
    wsConnected.value = false
  }

  socket.onerror = (e) => {
    logs.value += `\n[error] ${String(e)}`
    wsConnected.value = false
  }
}

function disconnectWs() {
  socket?.close()
  socket = null
}
</script>
