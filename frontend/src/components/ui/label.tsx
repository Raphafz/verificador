import * as React from 'react'
import { cn } from '@/lib/utils'

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn('mb-2 block text-[0.8125rem] font-semibold text-muted-foreground', className)}
      {...props}
    />
  )
}
