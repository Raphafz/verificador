import { Moon, Sun } from 'lucide-react'
import { Link, Outlet } from 'react-router-dom'
import { Logo } from '@/components/brand/logo'
import { Button } from '@/components/ui/button'
import { useTheme } from '@/contexts/theme-context'

export function MarketingLayout() {
  const { theme, toggleTheme } = useTheme()

  return (
    <div className="ds-mesh-bg min-h-screen">
      <header className="ds-glass sticky top-0 z-50 border-b border-border">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 lg:px-6">
          <Logo to="/" height={32} />
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="Alternar tema">
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Link to="/rm/login">
              <Button variant="default">Entrar</Button>
            </Link>
          </div>
        </div>
      </header>
      <Outlet />
    </div>
  )
}
