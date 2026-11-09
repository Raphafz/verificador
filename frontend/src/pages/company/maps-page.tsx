import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import * as adminApi from '@/api/admin'
import * as authApi from '@/api/auth'
import { SimpleTable } from '@/components/data/simple-table'
import { PageHeader } from '@/components/layout/page-header'
import { Badge } from '@/components/ui/badge'
import { SsrLink } from '@/components/ssr-link'

export function CompanyMapsPage() {
  const { slug } = useParams<{ slug: string }>()
  const { data: ctx } = useQuery({
    queryKey: ['company', slug],
    queryFn: () => authApi.fetchCompanyContext(slug!),
    enabled: Boolean(slug),
  })

  const { data, isLoading } = useQuery({
    queryKey: ['maps', slug],
    queryFn: () => adminApi.fetchMaps(),
    enabled: Boolean(slug),
  })

  return (
    <div className="ds-fade-up space-y-6">
      <PageHeader
        badge="Empresa"
        title="Mapas CTO"
        description={`Arquivos de ${ctx?.name || slug}`}
      />

      {isLoading ? (
        <div className="h-48 animate-pulse rounded-[16px] bg-muted" />
      ) : (
        <SimpleTable
          rows={data ?? []}
          keyFn={(r) => r.id}
          columns={[
            {
              key: 'file',
              header: 'Arquivo',
              cell: (r) => (
                <div>
                  <p className="font-semibold">{r.original_filename || r.description}</p>
                  <p className="text-xs text-muted-foreground">{r.file_type}</p>
                </div>
              ),
            },
            {
              key: 'size',
              header: 'Tamanho',
              cell: (r) => `${r.file_size_mb} MB`,
            },
            {
              key: 'status',
              header: 'Status',
              cell: (r) => (
                <Badge variant={r.is_processed ? 'success' : 'warning'}>
                  {r.processing_status || (r.is_processed ? 'Processado' : 'Pendente')}
                </Badge>
              ),
            },
            {
              key: 'date',
              header: 'Enviado',
              cell: (r) => new Date(r.uploaded_at).toLocaleDateString('pt-BR'),
            },
          ]}
        />
      )}

      <SsrLink
        href={`/${slug}/mapas/`}
        label="Upload de mapas"
        description="Envio e processamento de arquivos CTO no painel SSR."
      />
    </div>
  )
}
