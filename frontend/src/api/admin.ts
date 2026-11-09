import api from '@/api/client'
import type { AppUser, Company, MapFile } from '@/types/admin'

export async function fetchCompanies() {
  const { data } = await api.get<Company[]>('/companies/')
  return data
}

export async function fetchCompany(id: number) {
  const { data } = await api.get<Company>(`/companies/${id}/`)
  return data
}

export async function fetchCompanyStats(id: number) {
  const { data } = await api.get(`/companies/${id}/stats/`)
  return data
}

export async function fetchUsers(params?: { company?: number }) {
  const { data } = await api.get<AppUser[]>('/users/', { params })
  return data
}

export async function fetchUserStats() {
  const { data } = await api.get<{
    total: number
    active: number
    inactive: number
    recent_registrations: number
  }>('/users/stats/')
  return data
}

export async function fetchMaps(params?: { company?: number }) {
  const { data } = await api.get<MapFile[]>('/maps/', { params })
  return data
}

export async function fetchMapStats() {
  const { data } = await api.get<{
    total: number
    this_month: number
    this_week: number
  }>('/maps/stats/')
  return data
}

export async function fetchRecentMaps() {
  const { data } = await api.get<MapFile[]>('/maps/recent/')
  return data
}
