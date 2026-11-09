import fs from 'node:fs'
import path from 'node:path'
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Plugin } from 'vite'

const MIME: Record<string, string> = {
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.webp': 'image/webp',
  '.map': 'application/json',
}

function contentType(filePath: string): string {
  return MIME[path.extname(filePath).toLowerCase()] ?? 'application/octet-stream'
}

/** Em dev, serve /static/ do disco (evita 502 no proxy para Django). */
export function djangoStaticDevPlugin(repoRoot: string): Plugin {
  const roots = [
    path.join(repoRoot, 'static'),
    path.join(repoRoot, 'staticfiles'),
  ]

  return {
    name: 'django-static-dev',
    configureServer(server) {
      server.middlewares.use((req: IncomingMessage, res: ServerResponse, next: () => void) => {
        const raw = req.url?.split('?')[0] ?? ''
        if (!raw.startsWith('/static/')) {
          next()
          return
        }

        const rel = decodeURIComponent(raw.slice('/static/'.length))
        if (!rel || rel.includes('..')) {
          next()
          return
        }

        for (const root of roots) {
          const filePath = path.normalize(path.join(root, rel))
          if (!filePath.startsWith(path.normalize(root + path.sep))) continue
          try {
            const stat = fs.statSync(filePath)
            if (!stat.isFile()) continue
            res.statusCode = 200
            res.setHeader('Content-Type', contentType(filePath))
            res.setHeader('Cache-Control', 'no-cache')
            fs.createReadStream(filePath).pipe(res)
            return
          } catch {
            /* tenta próximo root */
          }
        }

        next()
      })
    },
  }
}
