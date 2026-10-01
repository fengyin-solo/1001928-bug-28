import { defineStore } from 'pinia'

export type OperatorRole = 'readwrite' | 'readonly'

const ROLE_STORAGE_KEY = 'pitch.operatorRole'

/** 不依赖 pinia 实例读取当前角色，供请求封装等模块直接使用。 */
export function readOperatorRole(): OperatorRole {
  return localStorage.getItem(ROLE_STORAGE_KEY) === 'readonly' ? 'readonly' : 'readwrite'
}

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: '值班管理员',
    shiftLabel: '白班 08:00-20:00',
    scope: '风电场机组运维平台',
    role: readOperatorRole() as OperatorRole,
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
    isReadonly: (state) => state.role === 'readonly',
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setRole(role: OperatorRole) {
      this.role = role
      localStorage.setItem(ROLE_STORAGE_KEY, role)
    },
  },
})
