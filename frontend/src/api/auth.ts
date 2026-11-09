import api from '@/api/client'
import type { LoginResponse, MeResponse } from '@/types/auth'

export async function login(payload: {
  username: string
  password: string
  company_slug?: string
}) {
  const { data } = await api.post<LoginResponse>('/auth/login/', payload)
  return data
}

export async function verifyMfa(payload: { mfa_pending_token?: string; token: string }) {
  const { data } = await api.post<LoginResponse>('/auth/mfa/verify/', payload)
  return data
}

export async function logout() {
  const refresh = localStorage.getItem('rm_refresh_token')
  try {
    await api.post('/auth/logout/', { refresh })
  } catch {
    /* ignore */
  }
}

export async function fetchMe() {
  const { data } = await api.get<MeResponse>('/me/')
  return data
}

export async function changePassword(payload: {
  new_password: string
  confirm_password: string
}) {
  const { data } = await api.post<LoginResponse>('/auth/change-password/', payload)
  return data
}

export async function fetchCompanyContext(slug: string) {
  const { data } = await api.get(`/companies/${slug}/`)
  return data
}

export async function fetchBilling() {
  const { data } = await api.get('/billing/')
  return data
}
