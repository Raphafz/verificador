import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'

interface LogoProps {
  className?: string
  to?: string
  height?: number
}

export function Logo({ className, to, height = 36 }: LogoProps) {
  const img = (
    <img
      src="/img/letreiro-rm.png"
      alt="RM Systems"
      height={height}
      className={cn('w-auto object-contain', className)}
      style={{ height }}
    />
  )

  if (to) {
    return (
      <Link to={to} className="inline-flex shrink-0 transition-opacity hover:opacity-90">
        {img}
      </Link>
    )
  }

  return img
}
