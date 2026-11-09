import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import * as authApi from '@/api/auth'
import { authStorage } from '@/lib/auth-storage'
import { isMfaVerifiedForUser, postLoginPath, slugFromToken } from '@/lib/auth-utils'
import type { LoginResponse, MeResponse } from '@/types/auth'

interface AuthContextValue {
  user: MeResponse | null
  isBootstrapping: boolean
  isAuthenticated: boolean
  mfaVerified: boolean
  applyLoginResult: (result: LoginResponse) => Promise<string | null>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

function buildMeFromLogin(result: LoginResponse): MeResponse | null {
  if (!result.user) return null
  const { company: companyId, ...rest } = result.user
  const slug = slugFromToken(result.access)
  const company =
    slug && companyId
      ? {
          id: typeof companyId === 'number' ? companyId : Number(companyId),
          name: result.user.company_name ?? slug,
          slug,
        }
      : undefined
  return {
    ...rest,
    company,
    mfa_required: result.mfa_required,
    mfa_verified: result.mfa_required === false ? true : (result.mfa_verified ?? true),
  }
}

function postLoginRedirect(user: MeResponse | undefined, access?: string): string | null {
  if (!user) return '/'
  return postLoginPath(user, access)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [sessionToken, setSessionToken] = useState<string | null>(() => authStorage.getAccess())

  const {
    data: user,
    isLoading,
    isFetching,
  } = useQuery({
    queryKey: ['me'],
    queryFn: authApi.fetchMe,
    enabled: Boolean(sessionToken),
    retry: false,
  })

  const isBootstrapping = Boolean(sessionToken) && !user && (isLoading || isFetching)

  const applyLoginResult = useCallback(
    async (result: LoginResponse) => {
      const needsMfa = Boolean(result.needs_mfa)
      if (needsMfa && result.mfa_pending_token) {
        authStorage.setMfaPending(result.mfa_pending_token)
        if (result.access && result.refresh) {
          authStorage.setTokens(result.access, result.refresh)
          setSessionToken(result.access)
        }
        return '/mfa'
      }

      if (result.must_change_password) {
        if (result.access && result.refresh) {
          authStorage.setTokens(result.access, result.refresh)
          setSessionToken(result.access)
        }
        return '/change-password'
      }

      if (result.needs_mfa_setup && result.mfa_required !== false) {
        if (result.access && result.refresh) {
          authStorage.setTokens(result.access, result.refresh)
          setSessionToken(result.access)
        }
        return '/mfa/setup'
      }

      if (result.access && result.refresh) {
        authStorage.setTokens(result.access, result.refresh)
        setSessionToken(result.access)

        if (result.user) {
          const me = buildMeFromLogin(result)
          if (me) queryClient.setQueryData<MeResponse>(['me'], me)
        }

        try {
          await queryClient.fetchQuery({ queryKey: ['me'], queryFn: authApi.fetchMe })
        } catch {
          /* segue com dados do login */
        }

        const me = queryClient.getQueryData<MeResponse>(['me'])
        return postLoginRedirect(me ?? (result.user as MeResponse | undefined), result.access)
      }

      return null
    },
    [queryClient],
  )

  const logout = useCallback(async () => {
    await authApi.logout()
    authStorage.clear()
    setSessionToken(null)
    queryClient.clear()
  }, [queryClient])

  const refreshUser = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['me'] })
  }, [queryClient])

  const value = useMemo<AuthContextValue>(
    () => ({
      user: user ?? null,
      isBootstrapping,
      isAuthenticated: Boolean(user),
      mfaVerified: isMfaVerifiedForUser(user),
      applyLoginResult,
      logout,
      refreshUser,
    }),
    [user, isBootstrapping, applyLoginResult, logout, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
