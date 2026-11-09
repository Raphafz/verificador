import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { authStorage } from '@/lib/auth-storage'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

let refreshPromise: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const refresh = authStorage.getRefresh()
  if (!refresh) return null
  try {
    const { data } = await axios.post('/api/v1/auth/refresh/', { refresh })
    const access = data.access as string
    authStorage.setTokens(access, data.refresh ?? refresh)
    return access
  } catch {
    authStorage.clear()
    return null
  }
}

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = authStorage.getAccess()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true
      refreshPromise ??= refreshAccessToken()
      const access = await refreshPromise
      refreshPromise = null
      if (access) {
        original.headers.Authorization = `Bearer ${access}`
        return api(original)
      }
    }
    return Promise.reject(error)
  },
)

export default api
