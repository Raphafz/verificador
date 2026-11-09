import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate, useParams } from 'react-router-dom'
import { z } from 'zod'
import * as accountApi from '@/api/account'
import { AuthCard } from '@/components/auth/auth-card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/contexts/auth-context'

const schema = z
  .object({
    password: z.string().min(8, 'Mínimo 8 caracteres'),
    password_confirm: z.string(),
  })
  .refine((d) => d.password === d.password_confirm, {
    message: 'As senhas não coincidem',
    path: ['password_confirm'],
  })

type FormData = z.infer<typeof schema>

export function ActivatePage() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const { applyLoginResult } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { isSubmitting, errors },
  } = useForm<FormData>({ resolver: zodResolver(schema) })

  async function onSubmit(data: FormData) {
    if (!token) {
      setError('Link de ativação inválido.')
      return
    }
    setError(null)
    try {
      const result = await accountApi.activateAccount({
        token,
        password: data.password,
        password_confirm: data.password_confirm,
      })
      const redirect = await applyLoginResult(result)
      if (redirect) navigate(redirect, { replace: true })
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Não foi possível ativar a conta.'
      setError(msg)
    }
  }

  return (
    <AuthCard title="Ativar conta" subtitle="Defina sua senha para começar a usar a plataforma">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
        <div>
          <Label htmlFor="password">Senha</Label>
          <Input id="password" type="password" autoComplete="new-password" {...register('password')} />
          {errors.password && (
            <p className="mt-1 text-sm text-destructive">{errors.password.message}</p>
          )}
        </div>
        <div>
          <Label htmlFor="password_confirm">Confirmar senha</Label>
          <Input
            id="password_confirm"
            type="password"
            autoComplete="new-password"
            {...register('password_confirm')}
          />
          {errors.password_confirm && (
            <p className="mt-1 text-sm text-destructive">{errors.password_confirm.message}</p>
          )}
        </div>
        {error && (
          <p className="rounded-[12px] border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? 'Ativando…' : 'Ativar conta'}
        </Button>
      </form>
    </AuthCard>
  )
}
