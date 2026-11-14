import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useAuthStore } from './auth'

const BASE = import.meta.env.VITE_API_BASE

type K8sRow = Record<string, unknown> & { metadata?: { name?: string } }

export const useKcoreStore = defineStore('kcore', () => {
  const auth = useAuthStore()

  const namespacesByCluster = ref<Record<number, string[]>>({})
  const loadingNamespaces = ref(false)

  // 防止同一 cluster 并发重复请求
  const inflightFetches = new Map<number, Promise<void>>()

  function getNamespaces(clusterId: number): string[] {
    return namespacesByCluster.value[clusterId] ?? []
  }

  async function fetchNamespaces(clusterId: number): Promise<void> {
    if (inflightFetches.has(clusterId)) {
      return inflightFetches.get(clusterId)
    }

    const promise = (async () => {
      loadingNamespaces.value = true
      try {
        const res = await auth.apiFetch(
          `${BASE}/kcore/clusters/${clusterId}/resources/namespaces/`,
        )
        const json = await res.json()
        const names: string[] = (json.data?.resources ?? [])
          .map((r: K8sRow) => r.metadata?.name)
          .filter((n: unknown): n is string => !!n)
        // 用 spread 创建新对象保证 Vue 响应式触发
        namespacesByCluster.value = { ...namespacesByCluster.value, [clusterId]: names }
      } catch {
        // 失败不覆盖已有缓存
      } finally {
        loadingNamespaces.value = false
        inflightFetches.delete(clusterId)
      }
    })()

    inflightFetches.set(clusterId, promise)
    return promise
  }

  function clearCluster(clusterId: number) {
    const next = { ...namespacesByCluster.value }
    delete next[clusterId]
    namespacesByCluster.value = next
  }

  return { loadingNamespaces, getNamespaces, fetchNamespaces, clearCluster }
})
