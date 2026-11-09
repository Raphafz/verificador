import { useQuery } from '@tanstack/react-query'
import { CreditCard } from 'lucide-react'
import * as authApi from '@/api/auth'
import { Button } from '@/components/ui/button'

export function BillingStubPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['billing'],
    queryFn: authApi.fetchBilling,
  })

  if (isLoading) {
    return <div className="h-48 animate-pulse rounded-[20px] bg-muted" />
  }

  return (
    <div className="ds-fade-up space-y-6">
      <header className="border-b border-border pb-6">
        <span className="mb-2 inline-block rounded-full bg-primary/10 px-2.5 py-0.5 text-[0.7rem] font-bold uppercase tracking-wider text-primary">
          Billing
        </span>
        <h1 className="text-3xl font-extrabold tracking-tight">Plano e cobrança</h1>
        <p className="mt-2 text-muted-foreground">Stub v1 — leitura via API + webhook Asaas no backend</p>
      </header>

      <article className="max-w-xl rounded-[20px] border border-border bg-card p-7 shadow-sm">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-[12px] ds-gradient-brand text-white">
          <CreditCard className="h-5 w-5" />
        </div>
        <p className="text-sm text-muted-foreground">{data?.message}</p>
        <dl className="mt-6 space-y-3 text-sm">
          <div className="flex justify-between border-b border-border py-2">
            <dt className="text-muted-foreground">Plano</dt>
            <dd className="font-semibold">{data?.plan ?? '—'}</dd>
          </div>
          <div className="flex justify-between border-b border-border py-2">
            <dt className="text-muted-foreground">Status</dt>
            <dd className="font-semibold">{data?.status ?? '—'}</dd>
          </div>
          <div className="flex justify-between py-2">
            <dt className="text-muted-foreground">Checkout online</dt>
            <dd className="font-semibold">{data?.checkout_available ? 'Disponível' : 'Em breve'}</dd>
          </div>
        </dl>
        <a href="mailto:vendas@rmsys.app?subject=Upgrade%20de%20plano" className="mt-6 block">
          <Button className="w-full">{data?.cta ?? 'Falar com vendas'}</Button>
        </a>
      </article>
    </div>
  )
}
