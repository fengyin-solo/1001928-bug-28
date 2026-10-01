/** 统一请求封装：拼后端地址、抛网络错误、给页脚留一句可读的说明。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

const ROLE_STORAGE_KEY = 'pitch.operatorRole'

function currentRole(): string {
  return localStorage.getItem(ROLE_STORAGE_KEY) === 'readonly' ? 'readonly' : 'admin'
}

/** 写操作带上当前值班角色，后端据此放行或拦截只读账号。 */
function withRoleHeader(init?: RequestInit): RequestInit {
  const headers = new Headers(init?.headers)
  if (!headers.has('X-Operator-Role')) {
    headers.set('X-Operator-Role', currentRole())
  }
  return { ...init, headers }
}

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const method = (init?.method ?? 'GET').toUpperCase()
  const finalInit = method === 'GET' || method === 'HEAD' ? init : withRoleHeader(init)
  return fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...finalInit,
  }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}
