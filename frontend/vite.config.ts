import path from 'node:path'
import { fileURLToPath } from 'node:url'
import type { ProxyOptions } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { djangoStaticDevPlugin } from './vite-django-static'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '..')
const DJANGO_TARGET = process.env.VITE_DJANGO_PROXY ?? 'http://127.0.0.1:8000'

function djangoProxy(): ProxyOptions {
  return {
    target: DJANGO_TARGET,
    changeOrigin: true,
    configure: (proxy) => {
      proxy.on('proxyReq', (proxyReq, req) => {
        const host = req.headers.host
        if (!host) return
        proxyReq.setHeader('X-Forwarded-Host', host)
        const proto =
          req.headers['x-forwarded-proto'] === 'https' ||
          (req.socket as { encrypted?: boolean }).encrypted
            ? 'https'
            : 'http'
        proxyReq.setHeader('X-Forwarded-Proto', proto)
      })
    },
  }
}

export default defineConfig({
  plugins: [djangoStaticDevPlugin(REPO_ROOT), react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: true,
    port: 5173,
    allowedHosts: [
      '.ngrok-free.app',
      '.ngrok.io',
      '.ngrok.app',
      '.trycloudflare.com',
      '.loca.lt',
      'localhost',
    ],
    proxy: {
      '/api': djangoProxy(),
      '/media': djangoProxy(),
      // /static servido pelo plugin django-static-dev (disco local)
      '^/[^/]+/olt': djangoProxy(),
      '^/[^/]+/verificador': djangoProxy(),
      '^/[^/]+/alertas': djangoProxy(),
      '^/[^/]+/upload': djangoProxy(),
      '^/[^/]+/tickets': djangoProxy(),
      '^/[^/]+/painel/(?:usuarios|mapas|relatorios)': djangoProxy(),
      '^/rm/(?:admin|tickets)': djangoProxy(),
    },
  },
})
