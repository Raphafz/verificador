import { LoginForm } from '@/pages/login-form'

export function RmLoginPage() {
  return (
    <LoginForm
      title="Entrar"
      subtitle="Acesso seguro à plataforma operacional"
      backLink={{ to: '/', label: 'Voltar à landing' }}
    />
  )
}
