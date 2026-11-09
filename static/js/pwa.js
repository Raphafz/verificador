// Script para registrar e gerenciar o Service Worker PWA
// Desabilitar em produção se houver problemas
const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

if ('serviceWorker' in navigator && isDevelopment) {
  window.addEventListener('load', () => {
    // Registrar service worker no escopo raiz para ter acesso a todo o site
    // O header Service-Worker-Allowed: / deve estar configurado no servidor
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .then((registration) => {
        // Suprimir logs em produção
        const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        if (isDevelopment) {
          console.log('Service Worker registrado com sucesso:', registration.scope);
        }

        // Verificar atualizações periodicamente
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing;
          
          newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              // Novo service worker disponível
              // Opcional: mostrar notificação para o usuário atualizar
            }
          });
        });
      })
      .catch((error) => {
        // Suprimir erro do Service Worker em produção - não fazer nada
      });

    // Ouvir mensagens do service worker (sem log em produção)
    navigator.serviceWorker.addEventListener('message', (event) => {
      // Mensagens do service worker são tratadas silenciosamente
    });

    // Pedir permissão para notificações (opcional)
    if ('Notification' in window && Notification.permission === 'default') {
      // Não pedir automaticamente - apenas quando necessário
      // Notification.requestPermission();
    }
  });

  // Atualizar service worker quando a página ganhar foco
  window.addEventListener('focus', () => {
    if (navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({
        type: 'SKIP_WAITING'
      });
    }
  });
}

// Detectar se está instalado como PWA
window.addEventListener('beforeinstallprompt', (e) => {
  // Prevenir a prompt padrão
  e.preventDefault();
  
  // Guardar o evento para mostrar depois
  window.deferredPrompt = e;
  
  // Opcional: mostrar botão de instalação personalizado
});

// Detectar se foi instalado
window.addEventListener('appinstalled', () => {
  // Limpar o prompt adiado
  window.deferredPrompt = null;
});

// Função auxiliar para mostrar prompt de instalação (opcional)
function installPWA() {
  if (window.deferredPrompt) {
    window.deferredPrompt.prompt();
    
    window.deferredPrompt.userChoice.then((choiceResult) => {
      window.deferredPrompt = null;
    });
  }
}

// Expor função globalmente (opcional)
window.installPWA = installPWA;

