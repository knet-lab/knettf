<template>
  <RouterLink to="/" class="brand" :class="{ light }">
    <svg viewBox="0 0 32 32" :width="size" :height="size" aria-hidden="true">
      <defs>
        <linearGradient id="ns-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#60a5fa" />
          <stop offset="1" stop-color="#8b5cf6" />
        </linearGradient>
      </defs>
      <path d="M16 2 4 7v8c0 7.2 5 12.9 12 15 7-2.1 12-7.8 12-15V7L16 2Z" fill="url(#ns-g)" />
      <path d="M10 16.5h3l2-4 3 8 2-4h2" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
    <span>NetSentinel</span>
  </RouterLink>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number; light?: boolean }>(), { size: 26, light: false })
</script>

<style scoped>
.brand { display: inline-flex; align-items: center; gap: 10px; text-decoration: none; color: #f1f5f9; font-weight: 800; font-size: 16.5px; letter-spacing: -0.01em; }
.brand.light { color: #0f172a; }
</style>
