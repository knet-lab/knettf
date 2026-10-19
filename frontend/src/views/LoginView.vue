<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <div class="login-title">
        <span>NetSentinel</span>
      </div>
      <el-form :model="form" @submit.prevent="handleLogin">
        <el-form-item>
          <el-input
            v-model="form.username"
            placeholder="Username"
            prefix-icon="User"
            size="large"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="Password"
            prefix-icon="Lock"
            show-password
            size="large"
          />
        </el-form-item>
        <el-form-item v-if="error">
          <el-alert :title="error" type="error" show-icon :closable="false" />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            native-type="submit"
            size="large"
            :loading="loading"
            style="width: 100%"
          >
            Sign In
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
.login-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: #f0f2f5;
}

.login-card {
  width: 400px;
}

.login-title {
  text-align: center;
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 32px;
  color: #303133;
}
</style>
