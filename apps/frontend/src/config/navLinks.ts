import type { Component } from 'vue'
import { House, Monitor, DataAnalysis, QuestionFilled, Setting } from '@element-plus/icons-vue'

// 顶部导航和 footer 共用；public 的不需要登录，其余未登录时点击会先去登录页再回来
export interface NavLink { to: string; label: string; icon: Component; public?: boolean }

export const NAV_LINKS: NavLink[] = [
  { to: '/',       label: 'Home',           icon: House,          public: true },
  { to: '/kcore',  label: 'Kubernetes',     icon: Monitor },
  { to: '/autotf', label: 'Terraform Scan', icon: DataAnalysis },
  { to: '/vigil',  label: 'AI Vigil',       icon: DataAnalysis },
  { to: '/help',   label: 'Help',           icon: QuestionFilled, public: true },
]

export const ADMIN_LINK: NavLink = { to: '/admin', label: 'Admin', icon: Setting }
