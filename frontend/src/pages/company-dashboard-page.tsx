import { useQuery } from '@tanstack/react-query'
import { Calendar, CheckCircle, Map, Users, UserCheck } from 'lucide-react'
import { useParams } from 'react-router-dom'
import * as authApi from '@/api/auth'
import { StatCard } from '@/components/dashboard/stat-card'
import { useAuth } from '@/contexts/auth-context'

export function CompanyDashboardPage() {
  const { slug } = useParams<{ slug: string }>()
  const { user } = useAuth()
  const { data } = useQuery({
    queryKey: ['company', slug],
    queryFn: () => authApi.fetchCompanyContext(slug!),
    enabled: Boolean(slug),
  })

  const quotas = (data?.quotas ?? {}) as Record<string, number>

  return (
    <div className="ds-fade-up space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-6">
        <div>
          <span className="mb-2 inline-block rounded-full bg-primary/10 px-2.5 py-0.5 text-[0.7rem] font-bold uppercase tracking-wider text-primary">
            Painel da empresa
          </span>
          <h1 className="text-3xl font-extrabold tracking-tight">{data?.name || slug}</h1>
          <p className="mt-2 max-w-lg text-muted-foreground">
            Resumo de usuários, mapas CTO e atalhos do dia a dia.
          </p>
        </div>
        <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm font-semibold text-muted-foreground">
          <Calendar className="h-4 w-4" />
          {new Date().toLocaleDateString('pt-BR')}
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Usuários" value={quotas.users_count ?? '—'} icon={Users} tone="users" />
        <StatCard label="Mapas CTO" value={quotas.maps_count ?? '—'} icon={Map} tone="maps" />
        <StatCard label="Usuários ativos" value={quotas.active_users ?? '—'} icon={UserCheck} tone="active" />
        <StatCard label="Mapas processados" value={quotas.maps_processed ?? '—'} icon={CheckCircle} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="rounded-[16px] border border-border bg-card p-6 shadow-sm">
          <h2 className="text-lg font-bold">Atalhos</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            <a
              href={`/${slug}/usuarios`}
              className="rounded-[12px] border border-border px-4 py-2 text-sm font-semibold hover:bg-muted"
            >
              Usuários
            </a>
            <a
              href={`/${slug}/mapas`}
              className="rounded-[12px] border border-border px-4 py-2 text-sm font-semibold hover:bg-muted"
            >
              Mapas
            </a>
            <a
              href={`/${slug}/billing`}
              className="rounded-[12px] border border-accent/30 bg-accent/5 px-4 py-2 text-sm font-semibold text-accent"
            >
              Billing
            </a>
          </div>
        </section>
        <section className="rounded-[16px] border border-border bg-card p-6 shadow-sm">
          <h2 className="text-lg font-bold">Verificador FTTH</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Olá, {user?.full_name}. O mapa completo continua no painel SSR até a Fase 3:
          </p>
          <a
            href={`/${slug}/verificador/`}
            className="mt-4 inline-flex items-center gap-2 rounded-[12px] border border-accent/30 bg-accent/5 px-4 py-2 text-sm font-semibold text-accent hover:bg-accent/10"
          >
            Abrir verificador
          </a>
        </section>
      </div>
    </div>
  )
}
