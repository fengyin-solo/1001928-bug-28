<template>
  <section class="page" data-module="pitch">
    <header class="page-head">
      <div>
        <h2>变桨系统管理</h2>
        <p class="page-desc">维护变桨系统，围绕系统编号、所属机组、变桨方式、桨距角范围做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" :disabled="session.readonly" @click="openCreate">登记变桨系统</button>
        <button class="btn" type="button" @click="exportRows">导出变桨系统清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>系统编号 / 桨距角读数</span>
        <input v-model="filters.keyword" placeholder="如 PITC-0001 或 91.5°" />
      </label>
      <label class="filter-item">
        <span>变桨方式</span>
        <select v-model="filters.mode">
          <option value="">全部方式</option>
          <option v-for="mode in modes" :key="mode" :value="mode">{{ mode }}</option>
        </select>
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
          <td v-for="column in columns" :key="column">{{ displayCell(row, column) }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              :disabled="session.readonly"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">没有命中的变桨系统，请调整变桨方式或变桨状态</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条变桨系统记录（同系统编号已去重）</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="creating" class="modal-mask" @click.self="closeCreate">
      <form class="modal-card" @submit.prevent="submitCreate">
        <h3>登记变桨系统</h3>
        <div class="form-item">
          <label>系统编号 *</label>
          <input v-model="form.系统编号" placeholder="如 PITC-0005" />
        </div>
        <div class="form-item">
          <label>所属机组 *</label>
          <input v-model="form.所属机组" placeholder="如 WT-05" />
        </div>
        <div class="form-item">
          <label>变桨方式 *</label>
          <input v-model="form.变桨方式" placeholder="电动变桨 / 液压变桨" />
        </div>
        <div class="form-item">
          <label>桨距角范围</label>
          <input v-model="form.桨距角范围" placeholder="如 0°~90°" />
        </div>
        <p v-if="formError" class="error-text">{{ formError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeCreate">取消</button>
          <button class="btn primary" type="submit" :disabled="submitting">
            {{ submitting ? '提交中…' : '提交登记' }}
          </button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | null>
type Filters = { keyword: string; mode: string; status: string }

const ENDPOINT = '/api/pitch'
const FILTER_STORAGE_KEY = 'pitch.filters'
const columns = ["系统编号", "所属机组", "变桨方式", "桨距角范围", "蓄电池电压", "上次调试日", "调试人员", "变桨状态"]
const actions = ["提交调试", "登记角度偏差", "锁定变桨"]
const statuses = ["待调试", "调试正常", "角度偏差", "已锁定"]
const modes = ["电动变桨", "液压变桨"]
const stats = [{"label": "待调试变桨", "value": 0}, {"label": "角度偏差台数", "value": 0}, {"label": "本月调试数", "value": 0}]

const session = useSessionStore()
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const creating = ref(false)
const submitting = ref(false)
const formError = ref('')
const form = reactive({ 系统编号: '', 所属机组: '', 变桨方式: '', 桨距角范围: '' })

function loadFilters(): Filters {
  const fallback: Filters = { keyword: '', mode: '', status: '' }
  try {
    const saved = JSON.parse(localStorage.getItem(FILTER_STORAGE_KEY) ?? '{}') as Partial<Filters>
    return { ...fallback, ...saved }
  } catch {
    return fallback
  }
}

const filters = reactive<Filters>(loadFilters())

watch(
  filters,
  (value) => {
    localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(value))
  },
  { deep: true },
)

function resetFilters() {
  filters.keyword = ''
  filters.mode = ''
  filters.status = ''
  void reload()
}

function displayCell(row: Row, column: string): string | number | null {
  if (column === '变桨状态') {
    return row['变桨状态'] ?? row.status ?? '—'
  }
  return row[column] ?? '—'
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  if (session.readonly) {
    errorMessage.value = '只读账号不能登记变桨系统'
    return
  }
  formError.value = ''
  creating.value = true
}

function closeCreate() {
  creating.value = false
}

async function submitCreate() {
  if (submitting.value) return
  formError.value = ''
  submitting.value = true
  try {
    const values: Record<string, string> = {
      系统编号: form.系统编号.trim(),
      所属机组: form.所属机组.trim(),
      变桨方式: form.变桨方式.trim(),
      桨距角范围: form.桨距角范围.trim(),
    }
    const response = await request(ENDPOINT, { method: 'POST', body: JSON.stringify({ values }) })
    const payload = await response.json().catch(() => ({}))
    if (response.status === 403) {
      throw new Error(payload.detail ?? '只读账号不能登记变桨系统')
    }
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message ?? '变桨系统登记失败')
    }
    form.系统编号 = ''
    form.所属机组 = ''
    form.变桨方式 = ''
    form.桨距角范围 = ''
    creating.value = false
    await reload()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '变桨系统登记失败'
  } finally {
    submitting.value = false
  }
}

async function runAction(action: string, row: Row) {
  if (session.readonly) {
    errorMessage.value = '只读账号不能执行变桨动作'
    return
  }
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => ({}))
    if (response.status === 403) {
      throw new Error(payload.detail ?? '只读账号不能执行变桨动作')
    }
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message ?? '变桨系统动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '变桨系统操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (filters.keyword.trim()) params.set('keyword', filters.keyword.trim())
  if (filters.mode) params.set('mode', filters.mode)
  if (filters.status) params.set('status', filters.status)
  const suffix = params.toString()
  try {
    const response = await request(`${ENDPOINT}${suffix ? `?${suffix}` : ''}`)
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
