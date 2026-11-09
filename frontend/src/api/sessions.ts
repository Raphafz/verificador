import api from '@/api/client'
import type { SessionRecord, TrustedDevice } from '@/types/admin'

export async function fetchSessions() {
  const { data } = await api.get<{
    django_sessions: SessionRecord[]
    jwt_refresh_tokens: SessionRecord[]
  }>('/auth/sessions/')
  return data
}

export async function revokeSession(sessionId: number, type: 'django_session' | 'jwt_refresh') {
  const { data } = await api.delete('/auth/sessions/', {
    data: { session_id: sessionId, type },
  })
  return data
}

export async function fetchTrustedDevices() {
  const { data } = await api.get<{ devices: TrustedDevice[] }>('/auth/trusted-devices/')
  return data
}

export async function revokeTrustedDevice(deviceId: number | 'all') {
  const { data } = await api.delete('/auth/trusted-devices/', {
    data: { device_id: deviceId },
  })
  return data
}
