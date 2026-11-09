import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import * as authApi from '@/api/auth'
import { AuthCard } from '@/components/auth/auth-card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/contexts/auth-context'
import { authStorage } from '@/lib/auth-storage'

const schema = z.object({
  token: z.string().min(6, 'Informe o código de 6 dígitos').max(8),
})

type FormData = z.infer<typeof schema>

export function MfaPage() {
  const navigate = useNavigate()
  const { applyLoginResult, logout } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const hasToken = Boolean(authStorage.getAccess())
  const {
    register,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) })

  async function onSubmit(data: FormData) {
    const pending = authStorage.getMfaPending()
    const token = authStorage.getAccess()
    if (!pending && !token) {
      navigate('/rm/login')
      return
    }
    setError(null)
    try {
      const result = await authApi.verifyMfa({
        mfa_pending_token: pending ?? undefined,
        token: data.token,
      })
      const redirect = await applyLoginResult(result)
      if (redirect) navigate(redirect, { replace: true })
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Código inválido.'
      setError(msg)
    }
  }

  async function handleRestartLogin() {
    await logout()
    navigate('/rm/login', { replace: true })
  }

  return (
    <AuthCard
      title="Verificação em dois fatores"
      subtitle="Código de 6 dígitos do app autenticador (Google Authenticator, Microsoft Authenticator, etc.)"
    >
      <p className="mb-4 rounded-[12px] border border-border bg-muted/50 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
        Só existe esse código se você já escaneou o QR na configuração de MFA. Se nunca fez isso, use{' '}
        <Link to="/mfa/setup" className="font-semibold text-accent hover:underline">
          configurar MFA
        </Link>{' '}
        ou{' '}
        <button type="button" onClick={handleRestartLogin} className="font-semibold text-accent hover:underline">
          voltar ao login
        </button>{' '}
        para limpar a sessão.
      </p>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
        <div>
          <Label htmlFor="token">Código TOTP</Label>
          <Input
            id="token"
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="000000"
            className="text-center text-lg tracking-[0.3em]"
            {...register('token')}
          />
        </div>
        {error && (
          <p className="rounded-[12px] border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={isSubmitting || !hasToken}>
          {isSubmitting ? 'Validando…' : 'Confirmar'}
        </Button>
        {!hasToken && (
          <p className="text-center text-sm text-muted-foreground">
            <Link to="/rm/login" className="font-semibold text-accent hover:underline">
              Faça login novamente
            </Link>
          </p>
        )}
      </form>
    </AuthCard>
  )
}
