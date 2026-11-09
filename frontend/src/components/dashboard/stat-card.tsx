import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface StatCardProps {
  label: string
  value: string | number
  icon: LucideIcon
  tone?: 'users' | 'maps' | 'active' | 'default'
}

const tones: Record<string, string> = {
  users: 'from-blue-600/15 to-blue-600/5 text-blue-600',
  maps: 'from-emerald-600/15 to-emerald-600/5 text-emerald-600',
  active: 'from-amber-600/15 to-amber-600/5 text-amber-600',
  default: 'from-brand-deep/15 to-brand-cyan/5 text-primary',
}

export function StatCard({ label, value, icon: Icon, tone = 'default' }: StatCardProps) {
  return (
    <article className="flex items-center gap-4 rounded-[16px] border border-border bg-card p-5 shadow-sm">
      <div
        className={cn(
          'flex h-12 w-12 items-center justify-center rounded-[12px] bg-gradient-to-br',
          tones[tone],
        )}
      >
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-2xl font-extrabold tracking-tight text-foreground">{value}</p>
        <p className="text-sm text-muted-foreground">{label}</p>
      </div>
    </article>
  )
}
