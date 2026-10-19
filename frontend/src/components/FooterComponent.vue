<template>
  <footer class="app-footer">
    <span class="brand">NetSentinel</span>
    <nav>
      <RouterLink to="/">Home</RouterLink>
      <RouterLink to="/help">Manual</RouterLink>
    </nav>
    <span class="note">© {{ year }} · Home and Manual are public</span>
  </footer>
</template>

<script setup lang="ts">
const year = new Date().getFullYear()
</script>

<style scoped>
.app-footer {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 16px;
  height: 32px;
  padding: 0 16px;
  font-size: 12px;
  color: #909399;
  background: #fafafa;
  border-top: 1px solid #e4e7ed;
}
.brand { font-weight: 600; color: #606266; }
nav { display: flex; gap: 12px; }
nav a { color: #409eff; text-decoration: none; }
nav a:hover { text-decoration: underline; }
nav a.router-link-exact-active { color: #303133; font-weight: 600; }
.note { margin-left: auto; }
@media (max-width: 600px) { .note { display: none; } }
</style>
