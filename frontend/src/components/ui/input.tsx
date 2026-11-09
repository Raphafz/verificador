import * as React from 'react'
import { cn } from '@/lib/utils'

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'flex h-10 w-full rounded-[12px] border border-border bg-background px-3.5 py-2 text-[0.9375rem] text-foreground placeholder:text-muted-foreground transition-colors focus-visible:border-accent focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-accent/15 dark:bg-muted',
        className,
      )}
      {...props}
    />
  )
}
