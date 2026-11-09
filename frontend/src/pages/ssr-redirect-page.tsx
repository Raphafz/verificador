import { useEffect } from 'react'
import { useParams } from 'react-router-dom'

/** Redireciona fluxos ainda não migrados para o SSR Django. */
export function SsrRedirectPage({ path }: { path: string }) {
  const params = useParams()
  useEffect(() => {
    let target = path
    Object.entries(params).forEach(([key, value]) => {
      if (value) target = target.replace(`:${key}`, value)
    })
    window.location.replace(target)
  }, [path, params])

  return (
    <div className="flex min-h-screen items-center justify-center text-muted-foreground">
      Redirecionando…
    </div>
  )
}
