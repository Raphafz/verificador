import api from '@/api/client'
import type { LoginResponse } from '@/types/auth'

export async function requestPasswordReset(payload: { email: string; company_slug?: string }) {
  const { data } = await api.post<{ detail: string }>('/auth/password-reset/', payload)
  return data
}

export async function confirmPasswordReset(payload: {
  uid: string
  token: string
  new_password: string
  company_slug?: string
}) {
  const { data } = await api.post<{ detail: string }>('/auth/password-reset/confirm/', payload)
  return data
}

export async function activateAccount(payload: {
  token: string
  password: string
  password_confirm: string
}) {
  const { data } = await api.post<LoginResponse>('/auth/activate/', payload)
  return data
}
