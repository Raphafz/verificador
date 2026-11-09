import { cn } from '@/lib/utils'

export function Badge({
  children,
  variant = 'default',
  className,
}: {
  children: React.ReactNode
  variant?: 'default' | 'success' | 'warning' | 'muted'
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold',
        variant === 'default' && 'bg-primary/10 text-primary',
        variant === 'success' && 'bg-success/15 text-success',
        variant === 'warning' && 'bg-amber-500/15 text-amber-700 dark:text-amber-300',
        variant === 'muted' && 'bg-muted text-muted-foreground',
        className,
      )}
    >
      {children}
    </span>
  )
}
