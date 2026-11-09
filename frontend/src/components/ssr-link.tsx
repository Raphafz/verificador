import { ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface SsrLinkProps {
  href: string
  label: string
  description?: string
}

export function SsrLink({ href, label, description }: SsrLinkProps) {
  return (
    <section className="rounded-[16px] border border-dashed border-border bg-card/60 p-5">
      <p className="text-sm font-semibold">{label}</p>
      {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      <a href={href} className="mt-4 inline-flex">
        <Button variant="outline" type="button" className="gap-2">
          Abrir no painel SSR
          <ExternalLink className="h-4 w-4" />
        </Button>
      </a>
    </section>
  )
}
