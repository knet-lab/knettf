<script setup lang="ts">
import { ref } from 'vue'

const manuals = [
  { key: 'user', label: 'User Manual', src: '/manual_en.html' },
  { key: 'guide', label: '使用管理手册', src: '/guide/index.html' },
  { key: 'ops', label: '运维对照手册', src: '/ops/index.html' },
]
const current = ref(manuals[0]!)
</script>

<template>
  <div class="help-wrapper">
    <div class="help-tabs">
      <button
        v-for="m in manuals"
        :key="m.key"
        :class="['help-tab', { active: current.key === m.key }]"
        @click="current = m"
      >
        {{ m.label }}
      </button>
    </div>
    <iframe :src="current.src" class="help-frame" :title="current.label" />
  </div>
</template>

<style scoped>
.help-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.help-tabs {
  display: flex;
  gap: 4px;
  padding: 8px 12px 0;
  background: #1d2535;
}

.help-tab {
  padding: 8px 16px;
  font-size: 13px;
  color: #a0aec0;
  background: transparent;
  border: none;
  border-radius: 6px 6px 0 0;
  cursor: pointer;
}

.help-tab:hover {
  color: #e2e8f0;
}

.help-tab.active {
  background: #f0f4f8;
  color: #1d2535;
  font-weight: 600;
}

.help-frame {
  flex: 1;
  width: 100%;
  border: none;
}
</style>
