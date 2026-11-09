import { ArrowRight } from 'lucide-react'
import { MODULE_META } from '@/lib/module-meta'
import { isSsrModuleUrl } from '@/lib/ssr-routes'
import { cn } from '@/lib/utils'

interface ModuleCardProps {
  code: string
  label: string
  description?: string
  url?: string
  index?: number
}

export function ModuleCard({ code, label, description, url, index = 0 }: ModuleCardProps) {
  const meta = MODULE_META[code]
  const Icon = meta?.icon
  const color = meta?.color ?? '#003366'
  const desc = description || meta?.description || ''

  const content = (
    <>
      <div
        className="mb-4 flex h-[58px] w-[58px] items-center justify-center rounded-2xl text-white shadow-md"
        style={{ background: color }}
      >
        {Icon && <Icon className="h-6 w-6" />}
      </div>
      <h3 className="mb-2 text-lg font-bold text-foreground">{label}</h3>
      <p className="m-0 text-sm leading-relaxed text-muted-foreground">{desc}</p>
      <span className="absolute bottom-5 right-5 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-primary">
        <ArrowRight className="h-4 w-4" />
      </span>
    </>
  )

  const className = cn(
    'group relative block h-full overflow-hidden rounded-[20px] border border-border bg-card p-7 shadow-sm transition-all hover:-translate-y-1.5 hover:border-accent/40 hover:shadow-lg ds-fade-up',
  )

  if (url) {
    const ssr = isSsrModuleUrl(url)
    return (
      <a
        href={url}
        className={className}
        style={{ animationDelay: `${index * 60}ms` }}
        {...(ssr ? { 'data-ssr': 'true' } : {})}
      >
        <span className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-brand-deep to-brand-cyan opacity-0 transition-opacity group-hover:opacity-100" />
        {content}
      </a>
    )
  }

  return (
    <div className={className} style={{ animationDelay: `${index * 60}ms` }}>
      {content}
    </div>
  )
}
