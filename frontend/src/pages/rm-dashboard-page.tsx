import { useQuery } from '@tanstack/react-query'
import { Building2, Calendar, Map, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import * as adminApi from '@/api/admin'
import { StatCard } from '@/components/dashboard/stat-card'
import { SimpleTable } from '@/components/data/simple-table'
import { useAuth } from '@/contexts/auth-context'

export function RmDashboardPage() {
  const { user } = useAuth()

  const { data: companies } = useQuery({
    queryKey: ['companies'],
    queryFn: adminApi.fetchCompanies,
  })
  const { data: userStats } = useQuery({
    queryKey: ['users-stats'],
    queryFn: adminApi.fetchUserStats,
  })
  const { data: mapStats } = useQuery({
    queryKey: ['maps-stats'],
    queryFn: adminApi.fetchMapStats,
  })
  const { data: recentMaps } = useQuery({
    queryKey: ['maps-recent'],
    queryFn: adminApi.fetchRecentMaps,
  })

  return (
    <div className="ds-fade-up space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-6">
        <div>
          <span className="mb-2 inline-block rounded-full bg-primary/10 px-2.5 py-0.5 text-[0.7rem] font-bold uppercase tracking-wider text-primary">
            Operador RM
          </span>
          <h1 className="text-3xl font-extrabold tracking-tight">Dashboard</h1>
          <p className="mt-2 text-muted-foreground">
            Bem-vindo, {user?.full_name || user?.username}. Gestão multi-tenant da plataforma.
          </p>
        </div>
        <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm font-semibold text-muted-foreground">
          <Calendar className="h-4 w-4" />
          {new Date().toLocaleDateString('pt-BR')}
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <StatCard label="Empresas" value={companies?.length ?? '—'} icon={Building2} />
        <StatCard label="Usuários" value={userStats?.total ?? '—'} icon={Users} tone="users" />
        <StatCard label="Mapas" value={mapStats?.total ?? '—'} icon={Map} tone="maps" />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="rounded-[16px] border border-border bg-card p-6 shadow-sm">
          <h2 className="text-lg font-bold">Atalhos</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              to="/rm/empresas"
              className="rounded-[12px] border border-border px-4 py-2 text-sm font-semibold hover:bg-muted"
            >
              Empresas
            </Link>
            <Link
              to="/rm/usuarios"
              className="rounded-[12px] border border-border px-4 py-2 text-sm font-semibold hover:bg-muted"
            >
              Usuários
            </Link>
            <Link
              to="/rm/mapas"
              className="rounded-[12px] border border-border px-4 py-2 text-sm font-semibold hover:bg-muted"
            >
              Mapas
            </Link>
            <Link
              to="/rm/billing"
              className="rounded-[12px] border border-accent/30 bg-accent/5 px-4 py-2 text-sm font-semibold text-accent"
            >
              Billing
            </Link>
          </div>
        </section>
        <section className="rounded-[16px] border border-border bg-card p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-bold">Mapas recentes</h2>
          <SimpleTable
            rows={(recentMaps ?? []).slice(0, 5)}
            keyFn={(r) => r.id}
            emptyMessage="Nenhum mapa enviado ainda."
            columns={[
              { key: 'name', header: 'Arquivo', cell: (r) => r.original_filename || r.description },
              { key: 'company', header: 'Empresa', cell: (r) => r.company_name },
            ]}
          />
        </section>
      </div>
    </div>
  )
}
