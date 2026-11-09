import { Navigate, Outlet, useParams } from 'react-router-dom'
import { useAuth } from '@/contexts/auth-context'
import { authStorage } from '@/lib/auth-storage'
import { companySlugFromUser, isMfaRequired, loginPathForUser, postLoginPath } from '@/lib/auth-utils'

function AuthLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center text-muted-foreground">
      Carregando…
    </div>
  )
}

export function TokenRoute() {
  const token = authStorage.getAccess()
  if (!token) return <Navigate to="/rm/login" replace />
  return <Outlet />
}

export function ProtectedRoute() {
  const { user, isBootstrapping, mfaVerified } = useAuth()
  const token = authStorage.getAccess()

  if (!token) return <Navigate to="/rm/login" replace />
  if (isBootstrapping) return <AuthLoading />
  if (!user) return <Navigate to={loginPathForUser(null, token)} replace />
  if (!mfaVerified) return <Navigate to="/mfa" replace />
  return <Outlet />
}

export function MfaGuard() {
  const pending = authStorage.getMfaPending()
  const token = authStorage.getAccess()
  if (!pending && !token) return <Navigate to="/rm/login" replace />
  return <Outlet />
}

export function MfaSetupGuard() {
  const token = authStorage.getAccess()
  const { user, isBootstrapping } = useAuth()
  if (!token) return <Navigate to="/rm/login" replace />
  if (isBootstrapping) return <AuthLoading />
  if (user && !isMfaRequired(user)) {
    return <Navigate to={postLoginPath(user, token)} replace />
  }
  return <Outlet />
}

export function TenantRoute() {
  const { slug } = useParams<{ slug: string }>()
  const { user, isBootstrapping } = useAuth()
  const token = authStorage.getAccess()

  if (isBootstrapping) return <AuthLoading />
  if (!slug) return <Navigate to="/" replace />
  if (user?.role === 'RM') return <Outlet />

  const companySlug = companySlugFromUser(user, token)
  if (companySlug === slug) return <Outlet />

  return <Navigate to={loginPathForUser(user, token)} replace />
}

export function RmRoute() {
  const { user, isBootstrapping } = useAuth()
  if (isBootstrapping) return <AuthLoading />
  if (user?.role !== 'RM') return <Navigate to="/" replace />
  return <Outlet />
}

export function GuestRoute() {
  const { user, isBootstrapping } = useAuth()
  const token = authStorage.getAccess()

  if (isBootstrapping) return <AuthLoading />

  if (token && user) {
    if (user.role === 'RM') return <Navigate to="/rm/dashboard" replace />
    const slug = companySlugFromUser(user, token)
    if (slug) return <Navigate to={`/${slug}/hub`} replace />
  }

  return <Outlet />
}
