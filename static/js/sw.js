// Service Worker para PWA - RM Systems
const CACHE_NAME = 'rm-systems-v1.0.0';
const urlsToCache = [
  '/',
  '/rm/login/',
];

// Instalar Service Worker
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Service Worker: Cache aberto');
        return cache.addAll(urlsToCache.map(url => {
          try {
            return new Request(url, { credentials: 'same-origin' });
          } catch (e) {
            return url;
          }
        }));
      })
      .catch((error) => {
        console.log('Service Worker: Erro ao adicionar ao cache', error);
      })
  );
  self.skipWaiting();
});

// Ativar Service Worker
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('Service Worker: Removendo cache antigo', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  return self.clients.claim();
});

// Interceptar requisições e servir do cache (Network First)
self.addEventListener('fetch', (event) => {
  // Ignorar requisições não-GET
  if (event.request.method !== 'GET') {
    return;
  }

  // Ignorar requisições de origem externa (não tentar fetch via SW para evitar CSP)
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) {
    fetch(event.request);
    return;
  }

  // Ignorar requisições para APIs (sempre buscar online - sem cache)
  if (url.pathname.includes('/api/') || 
      url.pathname.includes('/verificador/api/') ||
      url.pathname.includes('/admin/') ||
      url.pathname.includes('/media/')) {
    // Network only - não cachear APIs
    event.respondWith(fetch(event.request));
    return;
  }

  // Network First strategy - tentar rede primeiro, cache como fallback
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Verificar se a resposta é válida
        if (!response || response.status !== 200 || response.type !== 'basic') {
          return response;
        }

        // Clonar a resposta para cachear
        const responseToCache = response.clone();

        // Cachear apenas arquivos estáticos e páginas principais
        if (url.pathname.includes('/static/') || 
            event.request.destination === 'document' ||
            event.request.destination === 'style' ||
            event.request.destination === 'script' ||
            event.request.destination === 'image' ||
            event.request.destination === 'font') {
          caches.open(CACHE_NAME)
            .then((cache) => {
              cache.put(event.request, responseToCache);
            });
        }

        return response;
      })
      .catch(() => {
        // Se a rede falhar, tentar cache da mesma URL
        return caches.match(event.request);
      })
  );
});

// Mensagens do cliente
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

