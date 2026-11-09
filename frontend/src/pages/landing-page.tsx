import { Bell, MapPin, Server, Shield, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

const plans = [
  {
    name: 'Starter',
    price: 'Sob consulta',
    features: ['Verificador FTTH', 'Até 5 usuários', 'Suporte por e-mail'],
    highlighted: false,
  },
  {
    name: 'Business',
    price: 'Sob consulta',
    features: ['Alertas WhatsApp', 'OLT / ONU', 'Suporte prioritário'],
    highlighted: true,
  },
  {
    name: 'Enterprise',
    price: 'Sob consulta',
    features: ['SLA dedicado', 'Multi-unidade', 'Onboarding assistido'],
    highlighted: false,
  },
]

const features = [
  { icon: MapPin, title: 'Viabilidade FTTH', desc: 'Mapas CTO, geocoding e análise de viabilidade em tempo real.' },
  { icon: Bell, title: 'Alertas inteligentes', desc: 'Telegram → WhatsApp com monitoramento de rede.' },
  { icon: Server, title: 'OLT / ONU', desc: 'Operações GPON: listar offline e remover ONTs.' },
  { icon: Shield, title: 'Multi-tenant seguro', desc: 'Isolamento por empresa, MFA e auditoria enterprise.' },
]

export function LandingPage() {
  return (
    <>
      <section className="relative overflow-hidden px-4 pb-20 pt-16 lg:px-6 lg:pt-24">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_-20%,rgba(0,210,255,0.18),transparent_60%)]" />
        <div className="relative mx-auto max-w-4xl text-center">
          <span className="mb-4 inline-block rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-accent">
            Plataforma ISP unificada
          </span>
          <h1 className="text-4xl font-extrabold tracking-tight text-foreground md:text-5xl lg:text-6xl">
            Viabilidade, alertas e OLT
            <span className="block bg-gradient-to-r from-brand-deep to-brand-cyan bg-clip-text text-transparent dark:from-brand-cyan dark:to-white">
              em um só painel
            </span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
            RM Systems centraliza a operação do provedor: verifique viabilidade FTTH, monitore alertas
            e gerencie OLTs com isolamento multi-tenant e segurança enterprise.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <a href="mailto:vendas@rmsys.app?subject=Demonstração%20RM%20Systems">
              <Button size="lg">Falar com vendas</Button>
            </a>
            <Link to="/rm/login">
              <Button variant="outline" size="lg">
                Acessar plataforma
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-4 px-4 pb-16 md:grid-cols-2 lg:grid-cols-4 lg:px-6">
        {features.map((f) => (
          <article
            key={f.title}
            className="rounded-[20px] border border-border bg-card/80 p-6 shadow-sm backdrop-blur transition-transform hover:-translate-y-1"
          >
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-[12px] ds-gradient-brand text-white">
              <f.icon className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-foreground">{f.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.desc}</p>
          </article>
        ))}
      </section>

      <section className="border-t border-border bg-card/50 px-4 py-16 lg:px-6">
        <div className="mx-auto max-w-6xl">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-extrabold tracking-tight">Planos</h2>
            <p className="mt-2 text-muted-foreground">
              Ativação via link comercial — self-signup em breve
            </p>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            {plans.map((plan) => (
              <article
                key={plan.name}
                className={`relative rounded-[20px] border p-7 shadow-sm transition-all hover:-translate-y-1 hover:shadow-md ${
                  plan.highlighted
                    ? 'border-accent/40 bg-card shadow-[var(--shadow-glow)]'
                    : 'border-border bg-card'
                }`}
              >
                {plan.highlighted && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full ds-gradient-brand px-3 py-0.5 text-xs font-bold text-white">
                    Popular
                  </span>
                )}
                <h3 className="text-xl font-bold">{plan.name}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{plan.price}</p>
                <ul className="mt-6 space-y-3 text-sm text-muted-foreground">
                  {plan.features.map((feat) => (
                    <li key={feat} className="flex items-center gap-2">
                      <Zap className="h-3.5 w-3.5 shrink-0 text-accent" />
                      {feat}
                    </li>
                  ))}
                </ul>
                <a
                  href="mailto:vendas@rmsys.app?subject=Plano%20RM%20Systems"
                  className="mt-8 block"
                >
                  <Button variant={plan.highlighted ? 'default' : 'outline'} className="w-full">
                    Falar com vendas
                  </Button>
                </a>
              </article>
            ))}
          </div>
        </div>
      </section>

      <footer className="border-t border-border px-4 py-8 text-center text-sm text-muted-foreground">
        &copy; {new Date().getFullYear()} RM Systems · Plataforma SaaS para provedores ISP
      </footer>
    </>
  )
}
