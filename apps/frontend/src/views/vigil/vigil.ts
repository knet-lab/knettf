// Vigil 两个页面（总览 / 日志）共用的类型、格式化和请求工具。
// 只封装前端展示逻辑，接口与参数保持后端 vigil/views.py 现状。

import { useAuthStore } from '@/stores/auth'

export interface VigilRecord {
  id: number
  created_at: string
  src_ip: string
  dst_ip: string
  src_port: number
  dst_port: number
  protocol: string
  model_name: string
  is_attack: boolean
  confidence: number | null
  attack_type: string | null
  explanation: string
  cilium_action: string | null
  cilium_reason: string
  /** 数据集真实标签：0 = 正常，1 = 攻击，null = 无标签（线上流量） */
  label: 0 | 1 | null
  flow_input?: Record<string, unknown>
  raw_output?: Record<string, number>
}

export interface VigilStats {
  total?: number
  attacks?: number
  normal?: number
  attack_rate?: number
  by_attack_type?: { attack_type: string | null; count: number }[]
  by_model?: { model_name: string; count: number }[]
}

export function useVigilApi() {
  const auth = useAuthStore()
  return async function apiGet<T = unknown>(path: string, timeoutMs = 10000): Promise<T> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const res = await auth.apiFetch(path, { signal: controller.signal })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      return (json.data ?? json) as T
    } finally {
      clearTimeout(timer)
    }
  }
}

// ── 格式化 ────────────────────────────────────────────────────────────────────
const pad = (n: number) => String(n).padStart(2, '0')

export function fmtTime(iso: string | null | undefined, withDate = true): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const t = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  return withDate ? `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${t}` : t
}

/** 今天的记录只显示时间，其余显示日期 + 时间 */
export function fmtTimeSmart(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  return fmtTime(iso, !sameDay)
}

export function fmtAgo(ts: number | null, now: number): string {
  if (!ts) return '—'
  const s = Math.max(0, Math.round((now - ts) / 1000))
  if (s < 5) return 'just now'
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  return fmtTime(new Date(ts).toISOString())
}

export function fmtPct(v: number | null | undefined, digits = 0): string {
  return v == null || Number.isNaN(v) ? '—' : `${(v * 100).toFixed(digits)}%`
}

// 时间类特征（flow_duration、iat_*）单位是微秒，换算成易读的时长
export function fmtMicros(us: number): string {
  if (us === 0) return '0'
  if (us < 1000) return `${Number(us.toPrecision(3))} µs`
  if (us < 1e6) return `${Number((us / 1000).toPrecision(3))} ms`
  if (us < 60e6) return `${Number((us / 1e6).toPrecision(3))} s`
  return `${Math.floor(us / 60e6)} min ${Math.round((us % 60e6) / 1e6)} s`
}

export function fmtFeature(v: unknown, key = ''): string {
  if (typeof v === 'number' && /^(flow_duration|iat_)/.test(key)) return fmtMicros(v)
  if (typeof v !== 'number') return String(v ?? '—')
  if (Number.isInteger(v)) return v.toLocaleString()
  return Math.abs(v) >= 1000 ? v.toFixed(1) : Number(v.toPrecision(4)).toString()
}

// ── 判定对比（有真实标签时）─────────────────────────────────────────────────────
export type Outcome = 'TP' | 'TN' | 'FP' | 'FN' | null

export function outcomeOf(r: Pick<VigilRecord, 'is_attack' | 'label'>): Outcome {
  if (r.label !== 0 && r.label !== 1) return null
  if (r.label === 1) return r.is_attack ? 'TP' : 'FN'
  return r.is_attack ? 'FP' : 'TN'
}

export const OUTCOME_TEXT: Record<Exclude<Outcome, null>, string> = {
  TP: 'Caught',
  TN: 'Correct',
  FP: 'False alarm',
  FN: 'Missed',
}

// ── 攻击类型颜色：按名字稳定取色，避免写死不存在的类型 ───────────────────────────
const TYPE_PALETTE = ['#f87171', '#fb923c', '#fbbf24', '#a78bfa', '#f472b6', '#38bdf8', '#34d399', '#e879f9', '#facc15']

export function typeColor(name: string | null | undefined): string {
  const s = name || 'anomaly'
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return TYPE_PALETTE[h % TYPE_PALETTE.length]!
}

/** 页面可见时才轮询；返回 stop 函数 */
export function startVisiblePolling(fn: () => void, intervalMs: number): () => void {
  let timer: ReturnType<typeof setInterval> | null = null
  const start = () => { if (!timer) timer = setInterval(fn, intervalMs) }
  const stop = () => { if (timer) { clearInterval(timer); timer = null } }
  const onVis = () => {
    if (document.hidden) stop()
    else { fn(); start() }
  }
  document.addEventListener('visibilitychange', onVis)
  if (!document.hidden) start()
  return () => { stop(); document.removeEventListener('visibilitychange', onVis) }
}
