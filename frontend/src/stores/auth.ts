import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const BASE = 'http://127.0.0.1:8000/api'

export interface UserInfo {
  id: number
  username: string
  email: string
  is_staff: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem('token') ?? '')
  const user = ref<UserInfo | null>(JSON.parse(localStorage.getItem('user') ?? 'null'))

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => !!user.value?.is_staff)

  function authHeaders() {
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token.value}`,
    }
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
    localStorage.setItem('token', data.access)

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
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return { token, user, isLoggedIn, isAdmin, authHeaders, login, logout }
})
