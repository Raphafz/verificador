import { useParams } from 'react-router-dom'
import { LoginForm } from '@/pages/login-form'

export function CompanyLoginPage() {
  const { slug } = useParams<{ slug: string }>()

  return (
    <LoginForm
      title="Entrar"
      subtitle={slug ? `Acesso à empresa ${slug}` : 'Acesso ao painel da empresa'}
      companySlug={slug}
      backLink={{ to: '/', label: 'Voltar à landing' }}
    />
  )
}
