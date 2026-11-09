export interface Company {
  id: number
  name: string
  slug: string
  email: string
  phone: string
  address: string
  cnpj_masked: string
  created_at: string
  user_count: number
  map_count: number
}

export interface AppUser {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  full_name: string
  phone: string
  role: string
  is_active: boolean
  company: number | null
  company_name?: string
  date_joined: string
  last_login: string | null
}

export interface MapFile {
  id: number
  original_filename: string
  description: string
  file_type: string
  file_size: number
  file_size_mb: number
  uploaded_at: string
  company: number
  company_name: string
  uploaded_by: number | null
  uploaded_by_name: string
  processing_status: string
  is_processed: boolean
}

export interface StatsSummary {
  companies?: number
  users?: { total: number; active: number; inactive: number }
  maps?: { total: number; this_month: number; this_week: number }
}

export interface TrustedDevice {
  id: number
  label: string
  ip_address: string
  created_at: string
  last_used_at: string
  expires_at: string
}

export interface SessionRecord {
  id: number
  type: 'django_session' | 'jwt_refresh'
  ip_address?: string
  user_agent?: string
  is_current?: boolean
  last_seen_at?: string
  expires_at?: string
  created_at?: string
  blacklisted?: boolean
}
