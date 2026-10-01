<template>
  <section class="page" data-module="pitch">
    <header class="page-head">
      <div>
        <h2>变桨系统管理</h2>
        <p class="page-desc">维护变桨系统，围绕系统编号、所属机组、变桨方式、桨距角范围做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" :disabled="session.isReadonly" @click="openCreate">登记变桨系统</button>
        <button class="btn" type="button" @click="exportRows">导出变桨系统清单</button>
      </div>
    </header>

    <p v-if="session.isReadonly" class="readonly-tip">当前为只读账号，仅可查询与导出，登记与状态流转已禁用。</p>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in textFilters" :key="field.key" class="filter-item">
        <span>{{ field.label }}</span>
        <input v-model="filters[field.key]" :placeholder="`按${field.label}检索`" />
      </label>
      <label class="filter-item">
        <span>变桨状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              :disabled="session.isReadonly || submittingId === row.id"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">没有命中筛选条件的变桨系统，请调整查询条件</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条变桨系统记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/pitch'
const FILTER_STORAGE_KEY = 'pitch.filters'
const columns = ["系统编号", "所属机组", "变桨方式", "桨距角范围", "蓄电池电压", "上次调试日", "调试人员", "变桨状态"]
const actions = ["提交调试", "登记角度偏差", "锁定变桨"]
const statuses = ["待调试", "调试正常", "角度偏差", "已锁定"]
const stats = [{"label": "待调试变桨", "value": 0}, {"label": "角度偏差台数", "value": 0}, {"label": "本月调试数", "value": 0}]

// 文本检索字段与后端参数一一对应，避免按中文列名拼参数导致筛选被静默忽略。
const textFilters = [
  { key: 'keyword', label: '系统编号' },
  { key: 'mode', label: '变桨方式' },
  { key: 'angle', label: '桨距角范围' },
] as const

type FilterKey = 'keyword' | 'mode' | 'angle' | 'status'

function loadFilters(): Record<FilterKey, string> {
  const fallback: Record<FilterKey, string> = { keyword: '', mode: '', angle: '', status: '' }
  try {
    const saved = JSON.parse(localStorage.getItem(FILTER_STORAGE_KEY) ?? '{}') as Partial<Record<FilterKey, string>>
    return { ...fallback, ...saved }
  } catch {
    return fallback
  }
}

const session = useSessionStore()
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const submittingId = ref<number | null>(null)
const filters = reactive<Record<FilterKey, string>>(loadFilters())

// 筛选条件实时持久化，重开页面后输入与下拉选择保持原样。
watch(filters, (value) => {
  localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(value))
}, { deep: true })

function resetFilters() {
  filters.keyword = ''
  filters.mode = ''
  filters.angle = ''
  filters.status = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = session.isReadonly
    ? '只读账号不能登记变桨系统'
    : '变桨系统登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  if (session.isReadonly || submittingId.value !== null) {
    return
  }
  errorMessage.value = ''
  submittingId.value = Number(row.id)
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = (await response.json().catch(() => null)) as { message?: string } | null
    if (!response.ok) {
      throw new Error(payload?.message ?? '变桨系统动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '变桨系统操作失败'
  } finally {
    submittingId.value = null
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  for (const field of textFilters) {
    const value = filters[field.key].trim()
    if (value) {
      params.set(field.key, value)
    }
  }
  if (filters.status) {
    params.set('status', filters.status)
  }
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error('变桨系统列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '变桨系统列表读取失败'
  }
}

onMounted(reload)
</script>
