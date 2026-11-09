import { useQuery } from '@tanstack/react-query'
import * as adminApi from '@/api/admin'
import { SimpleTable } from '@/components/data/simple-table'
import { PageHeader } from '@/components/layout/page-header'
import { Badge } from '@/components/ui/badge'
import { SsrLink } from '@/components/ssr-link'

export function RmUsersPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => adminApi.fetchUsers(),
  })

  return (
    <div className="ds-fade-up space-y-6">
      <PageHeader badge="RM" title="Usuários" description="Visão global de contas na plataforma" />

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
            { key: 'company', header: 'Empresa', cell: (r) => r.company_name || '—' },
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
        href="/rm/usuarios/"
        label="CRUD completo"
        description="Criar usuários, enviar ativação e e-mails no painel SSR."
      />
    </div>
  )
}
