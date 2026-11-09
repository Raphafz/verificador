import { zodResolver } from '@hookform/resolvers/zod'
import { Eye, EyeOff } from 'lucide-react'
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

const schema = z.object({
  username: z.string().min(1, 'Informe o usuário'),
  password: z.string().min(1, 'Informe a senha'),
  remember: z.boolean().optional(),
})

type FormData = z.infer<typeof schema>

interface LoginFormProps {
  title: string
  subtitle: string
  companySlug?: string
  backLink?: { to: string; label: string }
}

export function LoginForm({ title, subtitle, companySlug, backLink }: LoginFormProps) {
  const navigate = useNavigate()
  const { applyLoginResult } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [showPassword, setShowPassword] = useState(false)
  const {
    register,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema), defaultValues: { remember: false } })

  async function onSubmit(data: FormData) {
    setError(null)
    try {
      const result = await authApi.login({
        username: data.username,
        password: data.password,
        company_slug: companySlug,
      })
      const redirect = await applyLoginResult(result)
      if (redirect) navigate(redirect, { replace: true })
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Não foi possível entrar. Tente novamente.'
      setError(msg)
    }
  }

  return (
    <AuthCard
      title={title}
      subtitle={subtitle}
      footer={
        backLink ? (
          <p className="mt-4 text-center text-sm text-muted-foreground">
            <Link to={backLink.to} className="font-semibold text-accent hover:underline">
              {backLink.label}
            </Link>
          </p>
        ) : undefined
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
        <div>
          <Label htmlFor="username">E-mail ou usuário</Label>
          <Input
            id="username"
            placeholder="email@exemplo.com"
            autoComplete="username"
            {...register('username')}
          />
        </div>
        <div>
          <Label htmlFor="password">Senha</Label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? 'text' : 'password'}
              className="pr-11"
              autoComplete="current-password"
              {...register('password')}
            />
            <button
              type="button"
              className="absolute right-1 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-[10px] text-muted-foreground hover:bg-muted hover:text-foreground"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>
        <div className="flex items-center justify-between gap-2 text-sm">
          <label className="flex cursor-pointer items-center gap-2 text-muted-foreground">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-border accent-primary"
              {...register('remember')}
            />
            Lembrar login
          </label>
          <Link
            to={companySlug ? `/${companySlug}/password-reset` : '/rm/password-reset'}
            className="font-semibold text-accent hover:underline"
          >
            Esqueci a senha
          </Link>
        </div>
        {error && (
          <p className="rounded-[12px] border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? 'Entrando…' : 'Entrar'}
        </Button>
      </form>
    </AuthCard>
  )
}
