import api from '@/api/client'

export interface MfaSetupStart {
  provisioning_uri: string
  qr_base64: string
  needs_confirmation: boolean
}

export interface MfaSetupConfirm {
  done: boolean
  backup_codes: string[]
  message: string
}

export async function startMfaSetup() {
  const { data } = await api.post<MfaSetupStart>('/auth/mfa/setup/', {})
  return data
}

export async function confirmMfaSetup(code: string) {
  const { data } = await api.post<MfaSetupConfirm>('/auth/mfa/setup/', { code })
  return data
}
