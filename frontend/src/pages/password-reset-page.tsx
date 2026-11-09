import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useParams } from 'react-router-dom'
import { z } from 'zod'
import * as accountApi from '@/api/account'
import { AuthCard } from '@/components/auth/auth-card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from 'sonner'

const schema = z.object({
  email: z.string().email('Informe um e-mail válido'),
})

type FormData = z.infer<typeof schema>

export function PasswordResetPage() {
  const { slug } = useParams<{ slug?: string }>()
  const [done, setDone] = useState(false)
  const {
    register,
    handleSubmit,
    formState: { isSubmitting, errors },
  } = useForm<FormData>({ resolver: zodResolver(schema) })

  async function onSubmit(data: FormData) {
    try {
      const res = await accountApi.requestPasswordReset({
        email: data.email,
        company_slug: slug,
      })
      setDone(true)
      toast.success(res.detail)
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Não foi possível enviar o e-mail.'
      toast.error(msg)
    }
  }

  const loginPath = slug ? `/${slug}/login` : '/rm/login'

  return (
    <AuthCard
      title="Esqueci a senha"
      subtitle="Enviaremos um link de redefinição se o e-mail estiver cadastrado"
      footer={
        <p className="mt-4 text-center text-sm text-muted-foreground">
          <Link to={loginPath} className="font-semibold text-accent hover:underline">
            Voltar ao login
          </Link>
        </p>
      }
    >
      {done ? (
        <p className="rounded-[12px] border border-success/25 bg-success/10 px-4 py-3 text-sm text-foreground">
          Se o e-mail estiver cadastrado, você receberá um link para redefinir a senha.
        </p>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          <div>
            <Label htmlFor="email">E-mail</Label>
            <Input id="email" type="email" autoComplete="email" {...register('email')} />
            {errors.email && (
              <p className="mt-1 text-sm text-destructive">{errors.email.message}</p>
            )}
          </div>
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? 'Enviando…' : 'Enviar link'}
          </Button>
        </form>
      )}
    </AuthCard>
  )
}
