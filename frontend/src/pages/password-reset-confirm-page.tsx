import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { z } from 'zod'
import * as accountApi from '@/api/account'
import { AuthCard } from '@/components/auth/auth-card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from 'sonner'

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

export function PasswordResetConfirmPage() {
  const navigate = useNavigate()
  const { slug } = useParams<{ slug?: string }>()
  const [params] = useSearchParams()
  const uid = params.get('uid') ?? params.get('uidb64') ?? ''
  const token = params.get('token') ?? ''
  const [error, setError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { isSubmitting, errors },
  } = useForm<FormData>({ resolver: zodResolver(schema) })

  async function onSubmit(data: FormData) {
    if (!uid || !token) {
      setError('Link inválido ou incompleto.')
      return
    }
    setError(null)
    try {
      const res = await accountApi.confirmPasswordReset({
        uid,
        token,
        new_password: data.new_password,
        company_slug: slug,
      })
      toast.success(res.detail)
      navigate(slug ? `/${slug}/login` : '/rm/login', { replace: true })
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Não foi possível redefinir a senha.'
      setError(msg)
    }
  }

  const loginPath = slug ? `/${slug}/login` : '/rm/login'

  return (
    <AuthCard
      title="Nova senha"
      subtitle="Defina uma senha forte para sua conta"
      footer={
        <p className="mt-4 text-center text-sm text-muted-foreground">
          <Link to={loginPath} className="font-semibold text-accent hover:underline">
            Ir para o login
          </Link>
        </p>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
        <div>
          <Label htmlFor="new_password">Nova senha</Label>
          <Input id="new_password" type="password" autoComplete="new-password" {...register('new_password')} />
          {errors.new_password && (
            <p className="mt-1 text-sm text-destructive">{errors.new_password.message}</p>
          )}
        </div>
        <div>
          <Label htmlFor="confirm_password">Confirmar senha</Label>
          <Input
            id="confirm_password"
            type="password"
            autoComplete="new-password"
            {...register('confirm_password')}
          />
          {errors.confirm_password && (
            <p className="mt-1 text-sm text-destructive">{errors.confirm_password.message}</p>
          )}
        </div>
        {error && (
          <p className="rounded-[12px] border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? 'Salvando…' : 'Redefinir senha'}
        </Button>
      </form>
    </AuthCard>
  )
}
