import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const BASE = import.meta.env.VITE_API_BASE

export interface UserInfo {
  id: number
  username: string
  email: string
  is_staff: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem('token') ?? '')
  const refreshToken = ref<string>(localStorage.getItem('refreshToken') ?? '')
  const user = ref<UserInfo | null>(JSON.parse(localStorage.getItem('user') ?? 'null'))

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => !!user.value?.is_staff)

  function authHeaders() {
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token.value}`,
    }
  }

  // 防止并发请求同时触发多次刷新
  let refreshPromise: Promise<boolean> | null = null

  async function tryRefresh(): Promise<boolean> {
    if (!refreshToken.value) return false
    if (refreshPromise) return refreshPromise

    refreshPromise = (async () => {
      try {
        const res = await fetch(`${BASE}/auth/token/refresh/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh: refreshToken.value }),
        })
        if (!res.ok) return false

        const data = await res.json()
        token.value = data.access
        localStorage.setItem('token', data.access)
        return true
      } catch {
        return false
      } finally {
        refreshPromise = null
      }
    })()

    return refreshPromise
  }

  // 统一请求入口，自动处理 token 过期
  async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
    const isFormData = init.body instanceof FormData
    const makeHeaders = () => ({
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(init.headers as Record<string, string>),
      Authorization: `Bearer ${token.value}`,
    })

    let res = await fetch(input, { ...init, headers: makeHeaders() })

    if (res.status === 401) {
      const ok = await tryRefresh()
      if (ok) {
        res = await fetch(input, { ...init, headers: makeHeaders() })
      } else {
        logout()
        window.location.href = '/login'
      }
    }

    return res
  }

  async function login(username: string, password: string): Promise<string | null> {
    const res = await fetch(`${BASE}/auth/token/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) return 'Invalid username or password'

    const data = await res.json()
    token.value = data.access
    refreshToken.value = data.refresh
    localStorage.setItem('token', data.access)
    localStorage.setItem('refreshToken', data.refresh)

    // fetch user info
    const meRes = await fetch(`${BASE}/kcore/users/me/`, {
      headers: authHeaders(),
    })

    if (meRes.ok) {
      const me = await meRes.json()
      user.value = me.data
      localStorage.setItem('user', JSON.stringify(me.data))
    }

    return null
  }

  function logout() {
    token.value = ''
    refreshToken.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
    localStorage.removeItem('user')
  }

  return { token, user, isLoggedIn, isAdmin, authHeaders, apiFetch, login, logout }
})
