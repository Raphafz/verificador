import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Toaster } from 'sonner'
import {
  GuestRoute,
  MfaGuard,
  MfaSetupGuard,
  ProtectedRoute,
  RmRoute,
  TenantRoute,
  TokenRoute,
} from '@/components/guards'
import { AuthProvider } from '@/contexts/auth-context'
import { ThemeProvider } from '@/contexts/theme-context'
import { AppShell } from '@/layouts/app-shell'
import { AuthLayout } from '@/layouts/auth-layout'
import { MarketingLayout } from '@/layouts/marketing-layout'
import { ActivatePage } from '@/pages/activate-page'
import { BillingStubPage } from '@/pages/billing-stub-page'
import { ChangePasswordPage } from '@/pages/change-password-page'
import { CompanyMapsPage } from '@/pages/company/maps-page'
import { CompanyUsersPage } from '@/pages/company/users-page'
import { CompanyDashboardPage } from '@/pages/company-dashboard-page'
import { CompanyHubPage } from '@/pages/company-hub-page'
import { CompanyLoginPage } from '@/pages/company-login-page'
import { LandingPage } from '@/pages/landing-page'
import { MfaSetupPage } from '@/pages/mfa-setup-page'
import { MfaPage } from '@/pages/mfa-page'
import { PasswordResetConfirmPage } from '@/pages/password-reset-confirm-page'
import { PasswordResetPage } from '@/pages/password-reset-page'
import { ProfilePage } from '@/pages/profile-page'
import { RmCompaniesPage } from '@/pages/rm/companies-page'
import { RmMapsPage } from '@/pages/rm/maps-page'
import { RmUsersPage } from '@/pages/rm/users-page'
import { RmDashboardPage } from '@/pages/rm-dashboard-page'
import { RmLoginPage } from '@/pages/rm-login-page'
import { SsrRedirectPage } from '@/pages/ssr-redirect-page'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
})

function AnimatedRoutes() {
  const location = useLocation()

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      >
        <Routes location={location}>
          <Route element={<MarketingLayout />}>
            <Route path="/" element={<LandingPage />} />
          </Route>

          <Route
            path="/consent-required"
            element={<SsrRedirectPage path="/consent-required/" />}
          />

          <Route element={<GuestRoute />}>
            <Route element={<AuthLayout />}>
              <Route path="/rm/login" element={<RmLoginPage />} />
              <Route path="/:slug/login" element={<CompanyLoginPage />} />
              <Route path="/rm/password-reset" element={<PasswordResetPage />} />
              <Route path="/:slug/password-reset" element={<PasswordResetPage />} />
              <Route path="/rm/password-reset/confirm" element={<PasswordResetConfirmPage />} />
              <Route path="/:slug/password-reset/confirm" element={<PasswordResetConfirmPage />} />
              <Route path="/ativar-conta/:token" element={<ActivatePage />} />
            </Route>
          </Route>

          <Route element={<MfaGuard />}>
            <Route element={<AuthLayout />}>
              <Route path="/mfa" element={<MfaPage />} />
            </Route>
          </Route>

          <Route element={<MfaSetupGuard />}>
            <Route element={<AuthLayout />}>
              <Route path="/mfa/setup" element={<MfaSetupPage />} />
            </Route>
          </Route>

          <Route element={<TokenRoute />}>
            <Route element={<AuthLayout />}>
              <Route path="/change-password" element={<ChangePasswordPage />} />
            </Route>
          </Route>

          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell mode="rm" />}>
              <Route element={<RmRoute />}>
                <Route path="/rm/dashboard" element={<RmDashboardPage />} />
                <Route path="/rm/empresas" element={<RmCompaniesPage />} />
                <Route path="/rm/usuarios" element={<RmUsersPage />} />
                <Route path="/rm/mapas" element={<RmMapsPage />} />
                <Route path="/rm/billing" element={<BillingStubPage />} />
                <Route path="/rm/perfil" element={<ProfilePage />} />
              </Route>
            </Route>

            <Route element={<TenantRoute />}>
              <Route element={<AppShell mode="company" />}>
                <Route path="/:slug/hub" element={<CompanyHubPage />} />
                <Route path="/:slug/dashboard" element={<CompanyDashboardPage />} />
                <Route path="/:slug/usuarios" element={<CompanyUsersPage />} />
                <Route path="/:slug/mapas" element={<CompanyMapsPage />} />
                <Route path="/:slug/billing" element={<BillingStubPage />} />
                <Route path="/:slug/perfil" element={<ProfilePage />} />
              </Route>
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <BrowserRouter>
            <AnimatedRoutes />
            <Toaster richColors position="top-right" closeButton />
          </BrowserRouter>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}
