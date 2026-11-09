import { useQuery } from '@tanstack/react-query'
import * as adminApi from '@/api/admin'
import { SimpleTable } from '@/components/data/simple-table'
import { PageHeader } from '@/components/layout/page-header'
import { Badge } from '@/components/ui/badge'
import { SsrLink } from '@/components/ssr-link'

export function RmMapsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['maps'],
    queryFn: () => adminApi.fetchMaps(),
  })

  return (
    <div className="ds-fade-up space-y-6">
      <PageHeader badge="RM" title="Mapas CTO" description="Arquivos enviados por todas as empresas" />

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
            { key: 'company', header: 'Empresa', cell: (r) => r.company_name },
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
        href="/rm/mapas/"
        label="Upload e download"
        description="Envio de arquivos e exclusão no painel SSR."
      />
    </div>
  )
}
