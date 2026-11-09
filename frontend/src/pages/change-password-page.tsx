import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'
import * as authApi from '@/api/auth'
import { AuthCard } from '@/components/auth/auth-card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/contexts/auth-context'

const schema = z
  .object({
    new_password: z.string().min(8, 'Mínimo 8 caracteres'),
    confirm_password: z.string(),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: 'As senhas não coincidem',
    path: ['confirm_password'],
  })

type FormData = z.infer<typeof schema>

export function ChangePasswordPage() {
  const navigate = useNavigate()
  const { applyLoginResult } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) })

  async function onSubmit(data: FormData) {
    setError(null)
    try {
      const result = await authApi.changePassword(data)
      const redirect = await applyLoginResult(result)
      if (redirect) navigate(redirect, { replace: true })
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Não foi possível alterar a senha.'
      setError(msg)
    }
  }

  return (
    <AuthCard title="Defina sua nova senha" subtitle="Troca obrigatória no primeiro acesso">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
        <div>
          <Label htmlFor="new_password">Nova senha</Label>
          <Input id="new_password" type="password" {...register('new_password')} />
          {errors.new_password && (
            <p className="mt-2 text-sm text-destructive">{errors.new_password.message}</p>
          )}
        </div>
        <div>
          <Label htmlFor="confirm_password">Confirmar senha</Label>
          <Input id="confirm_password" type="password" {...register('confirm_password')} />
          {errors.confirm_password && (
            <p className="mt-2 text-sm text-destructive">{errors.confirm_password.message}</p>
          )}
        </div>
        {error && (
          <p className="rounded-[12px] border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? 'Salvando…' : 'Salvar e continuar'}
        </Button>
      </form>
    </AuthCard>
  )
}
