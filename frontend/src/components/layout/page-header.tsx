import type { ReactNode } from 'react'

interface PageHeaderProps {
  badge?: string
  title: string
  description?: string
  actions?: ReactNode
}

export function PageHeader({ badge, title, description, actions }: PageHeaderProps) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-border pb-6">
      <div>
        {badge && (
          <span className="mb-2 inline-block rounded-full bg-primary/10 px-2.5 py-0.5 text-[0.7rem] font-bold uppercase tracking-wider text-primary">
            {badge}
          </span>
        )}
        <h1 className="text-3xl font-extrabold tracking-tight">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-muted-foreground">{description}</p>}
      </div>
      {actions}
    </header>
  )
}
