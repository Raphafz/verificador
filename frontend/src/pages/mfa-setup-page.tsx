import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'
import * as mfaApi from '@/api/mfa'
import { AuthCard } from '@/components/auth/auth-card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/contexts/auth-context'
import { authStorage } from '@/lib/auth-storage'
import { isMfaRequired, postLoginPath } from '@/lib/auth-utils'

const schema = z.object({
  code: z.string().min(6, 'Informe o código de 6 dígitos'),
})

type FormData = z.infer<typeof schema>

export function MfaSetupPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const token = authStorage.getAccess()
  const [backupCodes, setBackupCodes] = useState<string[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: setup, isLoading, isError, error: setupError } = useQuery({
    queryKey: ['mfa-setup'],
    queryFn: mfaApi.startMfaSetup,
    retry: false,
    enabled: isMfaRequired(user),
  })

  useEffect(() => {
    if (user && !isMfaRequired(user)) {
      navigate(postLoginPath(user, token), { replace: true })
    }
  }, [user, token, navigate])

  useEffect(() => {
    if (!isError) return
    const status = (setupError as { response?: { status?: number; data?: { detail?: string } } })
      ?.response?.status
    const detail =
      (setupError as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? ''
    if (status === 400 || detail.toLowerCase().includes('não é obrigatório')) {
      navigate(postLoginPath(user, token), { replace: true })
    }
  }, [isError, setupError, user, token, navigate])

  const {
    register,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) })

  async function onSubmit(data: FormData) {
    setError(null)
    try {
      const result = await mfaApi.confirmMfaSetup(data.code)
      setBackupCodes(result.backup_codes)
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Código inválido.'
      setError(msg)
    }
  }

  if (backupCodes) {
    return (
      <AuthCard title="MFA ativado" subtitle="Guarde os códigos de backup em local seguro">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2 rounded-[12px] border border-border bg-muted p-4 font-mono text-sm">
            {backupCodes.map((code) => (
              <span key={code}>{code}</span>
            ))}
          </div>
          <Button className="w-full" onClick={() => navigate('/mfa', { replace: true })}>
            Confirmar com código do app
          </Button>
        </div>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Configurar MFA" subtitle="Escaneie o QR no autenticador e confirme com um código">
      {isLoading ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">Gerando QR…</p>
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => navigate(postLoginPath(user, token), { replace: true })}
          >
            Pular e continuar
          </Button>
        </div>
      ) : isError ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">MFA não está ativo neste ambiente.</p>
          <Button className="w-full" onClick={() => navigate(postLoginPath(user, token), { replace: true })}>
            Continuar
          </Button>
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          {setup?.qr_base64 ? (
            <img
              src={`data:image/png;base64,${setup.qr_base64}`}
              alt="QR Code MFA"
              className="mx-auto rounded-[12px] border border-border bg-white p-2"
              width={200}
              height={200}
            />
          ) : setup?.provisioning_uri ? (
            <p className="break-all text-center text-xs text-muted-foreground">
              {setup.provisioning_uri}
            </p>
          ) : null}
          <div>
            <Label htmlFor="code">Código TOTP</Label>
            <Input
              id="code"
              inputMode="numeric"
              placeholder="000000"
              className="text-center text-lg tracking-[0.3em]"
              {...register('code')}
            />
          </div>
          {error && (
            <p className="rounded-[12px] border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? 'Validando…' : 'Ativar MFA'}
          </Button>
        </form>
      )}
    </AuthCard>
  )
}
