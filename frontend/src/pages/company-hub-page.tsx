import { useQuery } from '@tanstack/react-query'
import { Users } from 'lucide-react'
import { useParams } from 'react-router-dom'
import * as authApi from '@/api/auth'
import { ModuleCard } from '@/components/hub/module-card'

export function CompanyHubPage() {
  const { slug } = useParams<{ slug: string }>()
  const { data, isLoading } = useQuery({
    queryKey: ['company', slug],
    queryFn: () => authApi.fetchCompanyContext(slug!),
    enabled: Boolean(slug),
  })

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-32 animate-pulse rounded-[20px] bg-muted" />
        <div className="grid gap-4 md:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-48 animate-pulse rounded-[20px] bg-muted" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="ds-fade-up">
      <header className="mb-10 border-b border-border pb-6">
        <span className="mb-3 inline-block rounded-full bg-accent/10 px-2.5 py-0.5 text-[0.7rem] font-bold uppercase tracking-wider text-accent">
          Plataforma ISP
        </span>
        <h1 className="text-3xl font-extrabold tracking-tight md:text-4xl">{data?.name || slug}</h1>
        <p className="mt-2 text-lg text-muted-foreground">
          Escolha um módulo — viabilidade, OLT ou alertas WhatsApp
        </p>
        {data?.quotas && (
          <p className="mt-4 inline-flex items-center gap-2 rounded-full border border-accent/25 bg-accent/5 px-4 py-1.5 text-xs font-semibold text-muted-foreground">
            <Users className="h-3.5 w-3.5" />
            Plano {data.plan_code || '—'}
          </p>
        )}
      </header>

      {(data?.modules ?? []).length > 0 ? (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {(data?.modules ?? []).map(
            (mod: { code: string; label: string; description?: string; url?: string }, i: number) => (
              <ModuleCard
                key={mod.code}
                code={mod.code}
                label={mod.label}
                description={mod.description}
                url={mod.url}
                index={i}
              />
            ),
          )}
        </div>
      ) : (
        <div className="rounded-[16px] border border-amber-500/30 bg-amber-500/10 px-5 py-4 text-sm text-amber-700 dark:text-amber-300">
          Nenhum módulo habilitado para esta empresa. Contate o administrador RM Systems.
        </div>
      )}
    </div>
  )
}
