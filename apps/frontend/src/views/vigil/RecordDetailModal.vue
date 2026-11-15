<template>
  <Transition name="vg-modal">
    <div v-if="record" class="vg-root vg-overlay" @click.self="close">
      <div ref="dialog" class="vg-modal" role="dialog" aria-modal="true" :aria-label="`Record ${record.id}`" tabindex="-1">

        <header class="m-head">
          <div class="m-title">
            <span class="vg-badge" :class="record.is_attack ? 'attack' : 'normal'">
              {{ record.is_attack ? 'ATTACK' : 'NORMAL' }}
            </span>
            <span v-if="record.is_attack" class="vg-type">
              <span class="sw" :style="{ background: typeColor(record.attack_type) }" />
              {{ record.attack_type || 'anomaly' }}
            </span>
            <span class="m-id">#{{ record.id }}</span>
          </div>
          <div class="m-nav">
            <button v-if="hasNav" class="vg-btn icon" :disabled="!canPrev" title="Previous (←)" @click="$emit('prev')">
              <el-icon><ArrowLeft /></el-icon>
            </button>
            <button v-if="hasNav" class="vg-btn icon" :disabled="!canNext" title="Next (→)" @click="$emit('next')">
              <el-icon><ArrowRight /></el-icon>
            </button>
            <button class="vg-btn icon" title="Close (Esc)" @click="close"><el-icon><Close /></el-icon></button>
          </div>
        </header>

        <div class="m-body">
          <!-- Flow summary -->
          <div class="flow-line vg-mono">
            <span>{{ record.src_ip }}<span class="vg-muted">:{{ record.src_port }}</span></span>
            <span class="arrow">→</span>
            <span>{{ record.dst_ip }}<span class="vg-muted">:{{ record.dst_port }}</span></span>
            <span class="vg-badge proto">{{ record.protocol }}</span>
          </div>

          <div class="kv-grid">
            <div class="kv"><span class="k">Detected at</span><span class="v vg-mono">{{ fmtTime(record.created_at) }}</span></div>
            <div class="kv"><span class="k">Model</span><span class="v vg-mono accent">{{ record.model_name }}</span></div>
            <div class="kv">
              <span class="k">Confidence</span>
              <span class="v">
                <span class="vg-conf">
                  <span class="bar"><span class="fill" :class="record.is_attack ? 'attack' : 'normal'" :style="{ width: ((record.confidence ?? 0) * 100) + '%' }" /></span>
                  <span class="txt">{{ fmtPct(record.confidence, 1) }}</span>
                </span>
              </span>
            </div>
            <div class="kv">
              <span class="k">Ground truth</span>
              <span class="v">
                <template v-if="outcome">
                  <span class="vg-badge" :class="record.label === 1 ? 'attack' : 'normal'">{{ record.label === 1 ? 'ATTACK' : 'NORMAL' }}</span>
                  <span class="vg-badge" :class="`out-${outcome}`">{{ OUTCOME_TEXT[outcome] }}</span>
                </template>
                <span v-else class="vg-muted">No label (live traffic)</span>
              </span>
            </div>
            <div class="kv">
              <span class="k">Cilium action</span>
              <span class="v"><span class="vg-badge" :class="`act-${record.cilium_action || 'ignore'}`">{{ record.cilium_action || 'none' }}</span></span>
            </div>
            <div v-if="record.cilium_reason" class="kv"><span class="k">Cilium reason</span><span class="v">{{ record.cilium_reason }}</span></div>
          </div>

          <p v-if="record.explanation" class="explain">{{ record.explanation }}</p>

          <!-- ZSL -->
          <section v-if="zsl.length">
            <h3 class="sec">Attack-type similarity</h3>
            <div class="zsl">
              <div v-for="[label, sim] in zsl" :key="label" class="zsl-row" :class="{ top: label === record.attack_type }">
                <span class="zsl-l">{{ label }}</span>
                <span class="zsl-t"><span class="zsl-f" :style="{ width: Math.max(0, sim) * 100 + '%', background: typeColor(label) }" /></span>
                <span class="zsl-v vg-mono">{{ fmtPct(sim, 1) }}</span>
              </div>
            </div>
          </section>

          <!-- Features -->
          <section v-if="featureGroups.length">
            <h3 class="sec">Flow features <span class="vg-muted">({{ featureCount }})</span></h3>
            <div class="fgroups">
              <div v-for="g in featureGroups" :key="g.name" class="fgroup">
                <div class="fgroup-t">{{ g.name }}</div>
                <div v-for="[k, v] in g.items" :key="k" class="frow">
                  <span class="fk">{{ k }}</span>
                  <span class="fv vg-mono">{{ fmtFeature(v) }}</span>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script lang="ts" setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  type VigilRecord, fmtTime, fmtPct, fmtFeature, outcomeOf, OUTCOME_TEXT, typeColor,
} from './vigil'

const props = defineProps<{
  record: VigilRecord | null
  canPrev?: boolean
  canNext?: boolean
  hasNav?: boolean
}>()
const emit = defineEmits<{ close: []; prev: []; next: [] }>()

const dialog = ref<HTMLElement | null>(null)
const close = () => emit('close')

const outcome = computed(() => (props.record ? outcomeOf(props.record) : null))

const zsl = computed(() => {
  const raw = props.record?.raw_output
  if (!raw) return []
  return (Object.entries(raw).filter(([, v]) => typeof v === 'number') as [string, number][])
    .sort((a, b) => b[1] - a[1])
})

const META = new Set(['src_ip', 'dst_ip', 'src_port', 'dst_port', 'protocol', 'label'])
const GROUPS: { name: string; test: (k: string) => boolean }[] = [
  { name: 'Volume & direction', test: k => /packets|fwd_|bwd_|bidirectional/.test(k) },
  { name: 'Timing', test: k => /duration|iat_|per_second|aggregation/.test(k) },
  { name: 'TCP flags', test: k => /^(syn|ack|fin|rst|psh|urg)_/.test(k) },
  { name: 'Replies & verdict', test: k => /reply|forward|drop/.test(k) },
  { name: 'Protocol', test: k => k.startsWith('is_') },
]

const featureGroups = computed(() => {
  const fi = props.record?.flow_input
  if (!fi) return []
  const buckets = new Map<string, [string, unknown][]>()
  for (const [k, v] of Object.entries(fi)) {
    if (META.has(k)) continue
    const g = GROUPS.find(g => g.test(k))?.name ?? 'Other'
    if (!buckets.has(g)) buckets.set(g, [])
    buckets.get(g)!.push([k, v])
  }
  return [...GROUPS.map(g => g.name), 'Other']
    .filter(n => buckets.has(n))
    .map(n => ({ name: n, items: buckets.get(n)! }))
})
const featureCount = computed(() => featureGroups.value.reduce((s, g) => s + g.items.length, 0))

function onKey(e: KeyboardEvent) {
  if (!props.record) return
  if (e.key === 'Escape') close()
  else if (props.hasNav && e.key === 'ArrowLeft' && props.canPrev) emit('prev')
  else if (props.hasNav && e.key === 'ArrowRight' && props.canNext) emit('next')
}
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))

watch(() => props.record?.id, async id => {
  if (id != null) { await nextTick(); dialog.value?.focus() }
})
</script>

<style scoped>
.vg-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(2, 6, 15, .7) !important; backdrop-filter: blur(2px);
  display: flex; align-items: center; justify-content: center; padding: 24px;
}
.vg-modal {
  width: 100%; max-width: 760px; max-height: 88vh;
  display: flex; flex-direction: column; overflow: hidden;
  background: var(--vg-surface); border: 1px solid var(--vg-border-strong);
  border-radius: 14px; box-shadow: 0 24px 80px rgba(0, 0, 0, .55);
  outline: none;
}
.m-head {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 12px 16px 12px 20px; border-bottom: 1px solid var(--vg-border);
}
.m-title { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; min-width: 0; }
.m-id { color: var(--vg-text-3); font-size: 13px; font-variant-numeric: tabular-nums; }
.m-nav { display: flex; gap: 6px; }
.vg-btn.icon { width: 32px; padding: 0; justify-content: center; }

.m-body { overflow-y: auto; padding: 18px 20px 22px; display: flex; flex-direction: column; gap: 18px; }

.flow-line {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  font-size: 15px; color: var(--vg-text);
  padding: 12px 14px; background: var(--vg-bg); border: 1px solid var(--vg-border); border-radius: 10px;
}
.flow-line .arrow { color: var(--vg-text-3); }

.kv-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 24px; }
.kv { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.kv .k { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--vg-text-3); }
.kv .v { font-size: 13px; color: var(--vg-text); display: flex; align-items: center; gap: 6px; flex-wrap: wrap; word-break: break-all; }
.kv .v.accent { color: var(--vg-accent); }

.explain {
  margin: 0; padding: 10px 14px; font-size: 13px; line-height: 1.6; color: var(--vg-text-2);
  background: var(--vg-bg); border-left: 3px solid var(--vg-border-strong); border-radius: 0 8px 8px 0;
}

.sec { margin: 0 0 10px; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: var(--vg-text-2); }

.zsl { display: flex; flex-direction: column; gap: 6px; }
.zsl-row { display: grid; grid-template-columns: 170px 1fr 56px; align-items: center; gap: 10px; font-size: 12px; color: var(--vg-text-2); }
.zsl-row.top { color: var(--vg-text); font-weight: 600; }
.zsl-l { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.zsl-t { height: 6px; background: var(--vg-border); border-radius: 4px; overflow: hidden; }
.zsl-f { display: block; height: 100%; border-radius: 4px; }
.zsl-v { text-align: right; }

.fgroups { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 12px; }
.fgroup { background: var(--vg-bg); border: 1px solid var(--vg-border); border-radius: 10px; padding: 10px 12px; }
.fgroup-t { font-size: 11px; font-weight: 600; color: var(--vg-text-3); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; }
.frow { display: flex; justify-content: space-between; gap: 8px; padding: 3px 0; font-size: 12px; }
.fk { color: var(--vg-text-3); }
.fv { color: var(--vg-text); }

@media (max-width: 640px) {
  .vg-overlay { padding: 0; align-items: flex-end; }
  .vg-modal { max-height: 92vh; border-radius: 14px 14px 0 0; }
  .kv-grid { grid-template-columns: 1fr; }
  .zsl-row { grid-template-columns: 110px 1fr 48px; }
}

.vg-modal-enter-active, .vg-modal-leave-active { transition: opacity .18s ease; }
.vg-modal-enter-from, .vg-modal-leave-to { opacity: 0; }
.vg-modal-enter-active .vg-modal { transition: transform .22s cubic-bezier(.2, .9, .3, 1.2); }
.vg-modal-enter-from .vg-modal { transform: translateY(8px) scale(.98); }
</style>
