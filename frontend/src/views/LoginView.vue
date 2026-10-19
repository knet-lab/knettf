<template>
  <div class="login-wrap">
    <section class="login-side">
      <BrandMark :size="34" />
      <div class="side-copy">
        <h1>Secure your clusters,<br>catch attacks in real time.</h1>
        <p>Kubernetes management, Terraform security scanning and AI-based traffic detection in one place.</p>
        <ul>
          <li><el-icon><Cpu /></el-icon>Manage Kubernetes clusters</li>
          <li><el-icon><Document /></el-icon>Scan Terraform for misconfigurations</li>
          <li><el-icon><Aim /></el-icon>Live AI intrusion detection</li>
        </ul>
      </div>
      <RouterLink to="/help" class="side-help"><el-icon><Reading /></el-icon>New here? Read the manual</RouterLink>
    </section>

    <section class="login-main">
      <div class="login-card">
        <BrandMark class="mobile-brand" light />
        <h2>Sign in</h2>
        <p class="sub">Use the account your administrator created for you.</p>
        <el-form :model="form" label-position="top" @submit.prevent="handleLogin">
          <el-form-item label="Username">
            <el-input v-model="form.username" placeholder="Username" prefix-icon="User" size="large" autocomplete="username" />
          </el-form-item>
          <el-form-item label="Password">
            <el-input v-model="form.password" type="password" placeholder="Password" prefix-icon="Lock" show-password size="large" autocomplete="current-password" />
          </el-form-item>
          <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="err" />
          <el-button type="primary" native-type="submit" size="large" :loading="loading" class="submit">Sign In</el-button>
        </el-form>
        <RouterLink to="/" class="back"><el-icon><ArrowLeft /></el-icon>Back to home</RouterLink>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import BrandMark from '@/components/BrandMark.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const form = ref({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  loading.value = true
  error.value = ''
  const err = await auth.login(form.value.username, form.value.password)
  loading.value = false
  if (err) {
    error.value = err
    return
  }
  const redirect = route.query.redirect
  if (typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')) {
    router.push(redirect)
  } else if (auth.isAdmin) {
    router.push('/admin/dashboard')
  } else {
    router.push('/kcore')
  }
}
</script>

<style scoped>
.login-wrap { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); min-height: 100%; background: #f1f5f9; }

.login-side {
  position: relative; overflow: hidden; display: flex; flex-direction: column; justify-content: space-between;
  padding: 40px clamp(32px, 5vw, 80px); background: var(--ns-hero); color: #e2e8f0;
}
.login-side::after {
  content: ''; position: absolute; inset: 0; pointer-events: none;
  background-image: linear-gradient(rgba(255,255,255,.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px);
  background-size: 48px 48px; mask-image: radial-gradient(ellipse at 30% 50%, #000 20%, transparent 75%);
}
.login-side > * { position: relative; z-index: 1; }
.side-copy h1 { font-size: clamp(28px, 3.2vw, 46px); font-weight: 800; line-height: 1.15; letter-spacing: -0.02em; color: #fff; margin-bottom: 16px; }
.side-copy p { font-size: 16px; color: #94a3b8; max-width: 46ch; line-height: 1.7; }
.side-copy ul { list-style: none; padding: 0; margin-top: 28px; display: grid; gap: 14px; }
.side-copy li { display: flex; align-items: center; gap: 12px; font-size: 15px; color: #cbd5e1; }
.side-copy li .el-icon { width: 34px; height: 34px; border-radius: 10px; background: rgba(96,165,250,.14); color: #93c5fd; font-size: 17px; }
.side-help { display: inline-flex; align-items: center; gap: 8px; color: #94a3b8; text-decoration: none; font-size: 14px; }
.side-help:hover { color: #fff; }

.login-main { display: flex; align-items: center; justify-content: center; padding: 40px 24px; }
.login-card { width: min(420px, 100%); background: #fff; border: 1px solid #e2e8f0; border-radius: 18px; padding: 40px 36px; box-shadow: 0 20px 48px rgba(15,23,42,.08); }
.login-card h2 { font-size: 26px; font-weight: 800; color: #0f172a; letter-spacing: -0.01em; }
.sub { color: #64748b; font-size: 14px; margin: 6px 0 26px; }
.err { margin-bottom: 16px; }
.submit { width: 100%; height: 46px; font-size: 15.5px; border-radius: 10px; }
.back { display: inline-flex; align-items: center; gap: 6px; margin-top: 22px; font-size: 13.5px; color: #64748b; text-decoration: none; }
.back:hover { color: #2563eb; }
.mobile-brand { display: none !important; margin-bottom: 20px; }

@media (max-width: 860px) {
  .login-wrap { grid-template-columns: 1fr; }
  .login-side { display: none; }
  .mobile-brand { display: inline-flex !important; }
  .login-card { padding: 32px 22px; }
}
</style>
