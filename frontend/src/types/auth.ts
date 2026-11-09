export interface AuthUser {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  full_name: string
  role: string
  company: number | null
  company_name?: string
  must_change_password?: boolean
  mfa_verified?: boolean
  mfa_required?: boolean
}

export interface CompanyBrief {
  id: number
  name: string
  slug: string
}

export interface CompanyContext {
  id: number
  name: string
  slug: string
  modules?: Array<{ code: string; label: string; url?: string }>
  quotas?: Record<string, unknown>
}

export interface LoginResponse {
  access?: string
  refresh?: string
  user?: AuthUser
  needs_mfa?: boolean
  needs_mfa_setup?: boolean
  mfa_required?: boolean
  mfa_pending_token?: string
  mfa_verified?: boolean
  must_change_password?: boolean
  detail?: string
}

export interface MeResponse extends Omit<AuthUser, 'company'> {
  modules?: Array<{ code: string; label: string; url?: string }>
  company?: CompanyBrief
}
