import { Lock } from 'lucide-react'
import type { ReactNode } from 'react'
import { Logo } from '@/components/brand/logo'
import { cn } from '@/lib/utils'

interface AuthCardProps {
  title: string
  subtitle: string
  children: ReactNode
  footer?: ReactNode
  className?: string
}

export function AuthCard({ title, subtitle, children, footer, className }: AuthCardProps) {
  return (
    <div
      className={cn(
        'ds-fade-up w-full max-w-[420px] rounded-[20px] border border-border bg-card p-8 shadow-lg',
        className,
      )}
    >
      <div className="mb-6 text-center">
        <Logo className="mx-auto mb-4" height={36} />
        <h1 className="text-[1.375rem] font-extrabold tracking-tight text-foreground">{title}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>
      </div>

      {children}

      <p className="mt-4 flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
        <Lock className="h-3.5 w-3.5 text-success" aria-hidden />
        Conexão criptografada · MFA disponível
      </p>

      {footer}
    </div>
  )
}
