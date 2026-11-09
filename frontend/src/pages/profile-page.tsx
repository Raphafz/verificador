import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Shield, Smartphone } from 'lucide-react'
import { PageHeader } from '@/components/layout/page-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import * as sessionsApi from '@/api/sessions'
import { useAuth } from '@/contexts/auth-context'
import { toast } from 'sonner'

export function ProfilePage() {
  const { user } = useAuth()
  const qc = useQueryClient()

  const { data: sessions, isLoading: loadingSessions } = useQuery({
    queryKey: ['sessions'],
    queryFn: sessionsApi.fetchSessions,
  })

  const { data: devices, isLoading: loadingDevices } = useQuery({
    queryKey: ['trusted-devices'],
    queryFn: sessionsApi.fetchTrustedDevices,
  })

  const revokeSession = useMutation({
    mutationFn: ({ id, type }: { id: number; type: 'django_session' | 'jwt_refresh' }) =>
      sessionsApi.revokeSession(id, type),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sessions'] })
      toast.success('Sessão encerrada.')
    },
    onError: () => toast.error('Não foi possível encerrar a sessão.'),
  })

  const revokeDevice = useMutation({
    mutationFn: (id: number) => sessionsApi.revokeTrustedDevice(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trusted-devices'] })
      toast.success('Dispositivo removido.')
    },
  })

  return (
    <div className="ds-fade-up space-y-8">
      <PageHeader
        badge="Conta"
        title="Perfil e segurança"
        description={`${user?.full_name || user?.username} · ${user?.email}`}
      />

      <section className="rounded-[16px] border border-border bg-card p-6 shadow-sm">
        <div className="mb-4 flex items-center gap-2">
          <Shield className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-bold">Sessões ativas</h2>
        </div>
        {loadingSessions ? (
          <p className="text-sm text-muted-foreground">Carregando…</p>
        ) : (
          <ul className="space-y-3">
            {(sessions?.jwt_refresh_tokens ?? [])
              .filter((t) => !t.blacklisted)
              .map((t) => (
                <li
                  key={t.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-[12px] border border-border px-4 py-3 text-sm"
                >
                  <div>
                    <Badge variant="muted">JWT refresh</Badge>
                    <p className="mt-1 text-muted-foreground">
                      Criado em {t.created_at ? new Date(t.created_at).toLocaleString('pt-BR') : '—'}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={revokeSession.isPending}
                    onClick={() => revokeSession.mutate({ id: t.id, type: 'jwt_refresh' })}
                  >
                    Revogar
                  </Button>
                </li>
              ))}
            {(sessions?.django_sessions ?? []).map((s) => (
              <li
                key={s.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-[12px] border border-border px-4 py-3 text-sm"
              >
                <div>
                  <Badge variant={s.is_current ? 'success' : 'muted'}>
                    {s.is_current ? 'Sessão atual' : 'Django'}
                  </Badge>
                  <p className="mt-1 text-muted-foreground">
                    {s.ip_address || 'IP desconhecido'} ·{' '}
                    {s.last_seen_at ? new Date(s.last_seen_at).toLocaleString('pt-BR') : '—'}
                  </p>
                </div>
                {!s.is_current && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={revokeSession.isPending}
                    onClick={() => revokeSession.mutate({ id: s.id, type: 'django_session' })}
                  >
                    Revogar
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-[16px] border border-border bg-card p-6 shadow-sm">
        <div className="mb-4 flex items-center gap-2">
          <Smartphone className="h-5 w-5 text-accent" />
          <h2 className="text-lg font-bold">Dispositivos confiáveis (MFA)</h2>
        </div>
        {loadingDevices ? (
          <p className="text-sm text-muted-foreground">Carregando…</p>
        ) : (devices?.devices ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhum dispositivo confiável registrado.</p>
        ) : (
          <ul className="space-y-3">
            {(devices?.devices ?? []).map((d) => (
              <li
                key={d.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-[12px] border border-border px-4 py-3 text-sm"
              >
                <div>
                  <p className="font-semibold">{d.label || 'Dispositivo'}</p>
                  <p className="text-muted-foreground">
                    {d.ip_address} · expira {new Date(d.expires_at).toLocaleDateString('pt-BR')}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={revokeDevice.isPending}
                  onClick={() => revokeDevice.mutate(d.id)}
                >
                  Remover
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
