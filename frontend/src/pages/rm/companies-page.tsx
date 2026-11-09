import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import * as adminApi from '@/api/admin'
import { SimpleTable } from '@/components/data/simple-table'
import { PageHeader } from '@/components/layout/page-header'
import { SsrLink } from '@/components/ssr-link'

export function RmCompaniesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['companies'],
    queryFn: adminApi.fetchCompanies,
  })

  return (
    <div className="ds-fade-up space-y-6">
      <PageHeader
        badge="RM"
        title="Empresas"
        description="Tenants cadastrados na plataforma"
      />

      {isLoading ? (
        <div className="h-48 animate-pulse rounded-[16px] bg-muted" />
      ) : (
        <SimpleTable
          rows={data ?? []}
          keyFn={(r) => r.id}
          columns={[
            {
              key: 'name',
              header: 'Empresa',
              cell: (r) => (
                <div>
                  <p className="font-semibold">{r.name}</p>
                  <p className="text-xs text-muted-foreground">{r.slug}</p>
                </div>
              ),
            },
            { key: 'users', header: 'Usuários', cell: (r) => r.user_count },
            { key: 'maps', header: 'Mapas', cell: (r) => r.map_count },
            {
              key: 'actions',
              header: 'Ações',
              cell: (r) => (
                <Link
                  to={`/${r.slug}/hub`}
                  className="text-sm font-semibold text-accent hover:underline"
                >
                  Hub
                </Link>
              ),
            },
          ]}
        />
      )}

      <SsrLink
        href="/rm/empresas/"
        label="Gestão avançada"
        description="Criar, editar e excluir empresas permanece no painel SSR."
      />
    </div>
  )
}
