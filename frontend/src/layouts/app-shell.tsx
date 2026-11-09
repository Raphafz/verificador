import {

  Building2,

  CreditCard,

  LayoutDashboard,

  LogOut,

  Map,

  Menu,

  Moon,

  Sun,

  UserCircle,

  Users,

  X,

} from 'lucide-react'

import { useState } from 'react'

import { Link, Outlet, useLocation, useNavigate, useParams } from 'react-router-dom'

import { Logo } from '@/components/brand/logo'

import { Button } from '@/components/ui/button'

import { useAuth } from '@/contexts/auth-context'

import { useTheme } from '@/contexts/theme-context'

import { cn } from '@/lib/utils'



interface NavItem {

  label: string

  to: string

  icon: typeof LayoutDashboard

}



export function AppShell({ mode }: { mode: 'rm' | 'company' }) {

  const [open, setOpen] = useState(false)

  const [collapsed, setCollapsed] = useState(false)

  const { user, logout } = useAuth()

  const { theme, toggleTheme } = useTheme()

  const navigate = useNavigate()

  const location = useLocation()

  const { slug } = useParams<{ slug: string }>()



  const companyName =

    (user as { company?: { name: string; slug: string } } | undefined)?.company?.name ?? slug



  const nav: NavItem[] =

    mode === 'rm'

      ? [

          { label: 'Dashboard', to: '/rm/dashboard', icon: LayoutDashboard },

          { label: 'Empresas', to: '/rm/empresas', icon: Building2 },

          { label: 'Usuários', to: '/rm/usuarios', icon: Users },

          { label: 'Mapas', to: '/rm/mapas', icon: Map },

          { label: 'Billing', to: '/rm/billing', icon: CreditCard },

          { label: 'Perfil', to: '/rm/perfil', icon: UserCircle },

        ]

      : [

          { label: 'Hub', to: `/${slug}/hub`, icon: LayoutDashboard },

          { label: 'Painel', to: `/${slug}/dashboard`, icon: Building2 },

          { label: 'Usuários', to: `/${slug}/usuarios`, icon: Users },

          { label: 'Mapas', to: `/${slug}/mapas`, icon: Map },

          { label: 'Billing', to: `/${slug}/billing`, icon: CreditCard },

          { label: 'Perfil', to: `/${slug}/perfil`, icon: UserCircle },

        ]



  async function handleLogout() {

    await logout()

    navigate(mode === 'rm' ? '/rm/login' : `/${slug}/login`)

  }



  return (

    <div className="ds-mesh-bg min-h-screen">

      <header className="ds-glass fixed inset-x-0 top-0 z-[1100] flex h-16 items-center gap-4 border-b border-border px-4 lg:px-6">

        <Button

          variant="outline"

          size="icon"

          className="lg:hidden"

          onClick={() => setOpen((v) => !v)}

          aria-label="Menu"

        >

          {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}

        </Button>



        <Button

          variant="ghost"

          size="icon"

          className="hidden lg:inline-flex"

          onClick={() => setCollapsed((v) => !v)}

          aria-label="Recolher menu"

        >

          <Menu className="h-4 w-4" />

        </Button>



        <Logo

          to={mode === 'rm' ? '/rm/dashboard' : `/${slug}/hub`}

          height={30}

        />



        <div className="hidden flex-1 items-center justify-center gap-3 md:flex">

          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs font-semibold text-muted-foreground">

            <span className="h-2 w-2 rounded-full bg-success ds-pulse-dot" />

            Operacional

          </span>

          {mode === 'company' && companyName && (

            <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs font-semibold text-muted-foreground">

              <Building2 className="h-3.5 w-3.5" />

              {companyName}

            </span>

          )}

        </div>



        <div className="ml-auto flex items-center gap-2">

          <span className="hidden max-w-[140px] truncate text-sm font-medium text-muted-foreground sm:inline">

            {user?.full_name || user?.username}

          </span>

          <Button variant="outline" size="icon" onClick={toggleTheme} aria-label="Alternar tema">

            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}

          </Button>

          <Button variant="outline" size="icon" onClick={handleLogout} aria-label="Sair">

            <LogOut className="h-4 w-4" />

          </Button>

        </div>

      </header>



      <div className="flex pt-16">

        <aside

          className={cn(

            'fixed bottom-0 left-0 top-16 z-[1050] flex flex-col border-r border-border bg-card/95 transition-all lg:static',

            collapsed ? 'w-[68px]' : 'w-[260px]',

            open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',

          )}

        >

          <div className="border-b border-border px-4 py-3">

            {!collapsed && (

              <span className="text-[0.6875rem] font-bold uppercase tracking-widest text-muted-foreground">

                Navegação

              </span>

            )}

          </div>

          <nav className="flex-1 space-y-1 p-2">

            {nav.map((item) => {

              const active = location.pathname === item.to

              const Icon = item.icon

              return (

                <Link

                  key={item.to}

                  to={item.to}

                  onClick={() => setOpen(false)}

                  className={cn(

                    'relative flex items-center gap-3 rounded-[12px] border px-3 py-2.5 text-sm font-semibold transition-colors',

                    active

                      ? 'border-accent/35 bg-primary/10 text-foreground shadow-[var(--shadow-glow)]'

                      : 'border-transparent text-muted-foreground hover:border-border hover:bg-muted hover:text-foreground',

                  )}

                >

                  {active && (

                    <span className="absolute left-0 top-1/2 h-[60%] w-[3px] -translate-y-1/2 rounded-full bg-accent" />

                  )}

                  <Icon className="h-4 w-4 shrink-0 opacity-85" />

                  {!collapsed && <span>{item.label}</span>}

                </Link>

              )

            })}

          </nav>

          {!collapsed && (

            <p className="border-t border-border p-4 text-xs leading-relaxed text-muted-foreground">

              FTTH, Alertas e OLT abrem no painel SSR até a Fase 3–4.

            </p>

          )}

        </aside>



        {open && (

          <button

            type="button"

            className="fixed inset-0 top-16 z-[1040] bg-black/40 lg:hidden"

            onClick={() => setOpen(false)}

            aria-label="Fechar menu"

          />

        )}



        <main className="min-h-[calc(100vh-4rem)] flex-1 p-4 lg:p-6">

          <div className="mx-auto max-w-[1320px]">

            <Outlet />

          </div>

        </main>

      </div>

    </div>

  )

}

