import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import * as adminApi from '@/api/admin'
import * as authApi from '@/api/auth'
import { SimpleTable } from '@/components/data/simple-table'
import { PageHeader } from '@/components/layout/page-header'
import { Badge } from '@/components/ui/badge'
import { SsrLink } from '@/components/ssr-link'

export function CompanyUsersPage() {
  const { slug } = useParams<{ slug: string }>()
  const { data: ctx } = useQuery({
    queryKey: ['company', slug],
    queryFn: () => authApi.fetchCompanyContext(slug!),
    enabled: Boolean(slug),
  })

  const { data, isLoading } = useQuery({
    queryKey: ['users', slug],
    queryFn: () => adminApi.fetchUsers(),
    enabled: Boolean(slug),
  })

  return (
    <div className="ds-fade-up space-y-6">
      <PageHeader
        badge="Empresa"
        title="Usuários"
        description={`Equipe de ${ctx?.name || slug}`}
      />

      {isLoading ? (
        <div className="h-48 animate-pulse rounded-[16px] bg-muted" />
      ) : (
        <SimpleTable
          rows={data ?? []}
          keyFn={(r) => r.id}
          columns={[
            {
              key: 'user',
              header: 'Usuário',
              cell: (r) => (
                <div>
                  <p className="font-semibold">{r.full_name || r.username}</p>
                  <p className="text-xs text-muted-foreground">{r.email}</p>
                </div>
              ),
            },
            {
              key: 'role',
              header: 'Função',
              cell: (r) => <Badge variant="muted">{r.role}</Badge>,
            },
            {
              key: 'status',
              header: 'Status',
              cell: (r) => (
                <Badge variant={r.is_active ? 'success' : 'warning'}>
                  {r.is_active ? 'Ativo' : 'Inativo'}
                </Badge>
              ),
            },
          ]}
        />
      )}

      <SsrLink
        href={`/${slug}/usuarios/`}
        label="Gerenciar usuários"
        description="Criar e editar usuários da empresa no painel SSR."
      />
    </div>
  )
}
