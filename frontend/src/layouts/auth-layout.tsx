import { Moon, Sun } from 'lucide-react'
import { Outlet } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useTheme } from '@/contexts/theme-context'

export function AuthLayout() {
  const { theme, toggleTheme } = useTheme()
  const year = new Date().getFullYear()

  return (
    <div className="ds-mesh-bg flex min-h-screen min-h-dvh flex-col">
      <div className="absolute right-4 top-4 z-10">
        <Button variant="outline" size="icon" onClick={toggleTheme} aria-label="Alternar tema">
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </div>

      <div className="flex flex-1 items-center justify-center px-4 py-8">
        <Outlet />
      </div>

      <footer className="py-6 text-center text-xs text-muted-foreground">
        &copy; {year} RM Systems
      </footer>
    </div>
  )
}
