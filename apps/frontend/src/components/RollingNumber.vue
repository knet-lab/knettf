<template>
  <span class="rn-wrap">
    <span v-if="chars === null" class="rn-dash">—</span>
    <template v-else>
      <template v-for="item in chars" :key="item.key">
        <span v-if="item.ch === '.' || item.ch === '-'" class="rn-dot">{{ item.ch }}</span>
        <span v-else class="rn-slot">
          <span class="rn-strip" :style="{ transform: `translateY(-${parseInt(item.ch) * 10}%)` }">
            <span v-for="d in 10" :key="d" class="rn-cell">{{ d - 1 }}</span>
          </span>
        </span>
      </template>
      <span v-if="suffix" class="rn-suffix">{{ suffix }}</span>
    </template>
  </span>
</template>

<script lang="ts" setup>
import { computed } from 'vue'

const props = defineProps<{
  value: number | null | undefined
  decimals?: number
  suffix?: string
}>()

const chars = computed(() => {
  if (props.value == null) return null
  const s = props.decimals != null
    ? props.value.toFixed(props.decimals)
    : String(Math.round(props.value))
  // key digits right-to-left so units slot keeps its key when digit count grows
  const arr = s.split('')
  const len = arr.length
  return arr.map((ch, i) => ({ ch, key: ch === '.' || ch === '-' ? `${ch}-${i}` : String(len - 1 - i) }))
})
</script>

<style scoped>
.rn-wrap {
  display: inline-flex;
  align-items: flex-end;
  line-height: 1;
}

.rn-slot {
  display: inline-block;
  height: 1em;
  overflow: hidden;
  vertical-align: top;
}

.rn-strip {
  display: flex;
  flex-direction: column;
  transition: transform 0.55s cubic-bezier(0.23, 1, 0.32, 1);
  will-change: transform;
}

.rn-cell {
  height: 1em;
  line-height: 1em;
  display: block;
  text-align: center;
}

.rn-dot {
  display: inline-block;
  line-height: 1em;
  margin: 0 0.04em;
  vertical-align: top;
}

.rn-suffix {
  font-size: 0.65em;
  margin-left: 0.1em;
  align-self: flex-end;
  margin-bottom: 0.05em;
  opacity: 0.75;
}

.rn-dash { line-height: 1em; }
</style>
