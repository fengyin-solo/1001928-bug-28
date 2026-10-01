import { defineStore } from 'pinia'

const ROLE_STORAGE_KEY = 'pitch.operatorRole'
export type OperatorRole = 'admin' | 'readonly'

function loadRole(): OperatorRole {
  return localStorage.getItem(ROLE_STORAGE_KEY) === 'readonly' ? 'readonly' : 'admin'
}

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: '值班管理员',
    shiftLabel: '白班 08:00-20:00',
    scope: '风电场机组运维平台',
    role: loadRole(),
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
    readonly: (state) => state.role === 'readonly',
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
