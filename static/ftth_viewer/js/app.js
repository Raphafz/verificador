// Sistema de logging otimizado
(function(){
    const SILENCE_LOGS = true; // Reativado para debug do dark mode
    const LOG_LEVELS = {
        ERROR: 0,
        WARN: 1,
        INFO: 2,
        DEBUG: 3
    };
    
    let currentLogLevel = LOG_LEVELS.INFO;
    
    // Função para filtrar logs repetitivos
    const logFilter = (() => {
        const logCounts = new Map();
        const maxRepeats = 5; // Máximo de logs repetidos
        
        return (message, level) => {
            const key = `${level}:${message}`;
            const count = logCounts.get(key) || 0;
            
            if (count >= maxRepeats) {
                return false; // Não mostrar mais este log
            }
            
            logCounts.set(key, count + 1);
            return true;
        };
    })();
    
    if (SILENCE_LOGS) {
        console.log = function(){};
        console.info = function(){};
        console.debug = function(){};
        console.warn = function(){};
    } else {
        // Interceptar console.warn para filtrar logs repetitivos
        const originalWarn = console.warn;
        console.warn = function(...args) {
            const message = args.join(' ');
            if (logFilter(message, 'WARN')) {
                originalWarn.apply(console, args);
            }
        };
    }
    const originalError = console.error;
    console.error = function(){
        try {
            // Filtrar erros irrelevantes do DOM/Leaflet
            const errorString = Array.from(arguments).join(' ');
            const irrelevantErrors = [
                'addEventParent',
                'reading \'addEventParent\'',
                'Leaflet internal error',
                'ResizeObserver loop limit exceeded'
            ];
            
            // Filtrar erros 404 esperados (mapa ausente no servidor)
            // NÃO filtrar erros de "endereço não encontrado" da busca de endereço - esses devem ser mostrados ao usuário
            const expected404Patterns = [
                '404',
                'not found',
                'não encontrado',
                '/api/coordenadas',
            ];
            
            // Se o erro contém alguma das strings irrelevantes, não mostrar
            if (irrelevantErrors.some(pattern => errorString.includes(pattern))) {
                return;
            }
            
            // NÃO interceptar erros de "Endereço não encontrado" - esses devem ser tratados pela função de busca
            const isAddressNotFound = errorString.includes('Endereço não encontrado') || 
                                     (errorString.includes('/api/geocode') && errorString.includes('Endereço'));
            
            // Se for um 404 esperado relacionado a mapas (não endereço), logar como warning em vez de error
            if (!isAddressNotFound && expected404Patterns.some(pattern => errorString.includes(pattern)) && 
                !errorString.includes('SOLUÇÃO CRÍTICA')) {
                // Converter para warning — mapa pode não existir no disco
                console.warn('⚠️ [404 Esperado]', ...Array.from(arguments).map(a => {
                    if (a instanceof Error) return a.message || 'Recurso não encontrado';
                    if (typeof a === 'string') {
                        return a.replace(/(api[_-]?key|token|secret|senha)=([^&\s]+)/ig, '$1=***');
                    }
                    return a;
                }));
                return; // Não mostrar como erro crítico
            }
            
            const sanitized = Array.from(arguments).map(a => {
                if (a instanceof Error) return a.message || 'Erro';
                if (typeof a === 'string') {
                    return a.replace(/(api[_-]?key|token|secret|senha)=([^&\s]+)/ig, '$1=***');
                }
                return a;
            });
            originalError.apply(console, sanitized);
        } catch (e) {
            // Silenciar completamente erros no tratamento de erro
        }
    };
})();

// Base de API dinâmica: /<company_slug>/verificador/api ou fallback /verificador/api
const API_BASE = (() => {
    try {
        const parts = window.location.pathname.split('/').filter(Boolean);
        const first = parts[0] || '';

        let basePath;
        if (first === 'verificador') {
            basePath = '/verificador/api';
        } else if (first && first !== 'rm' && first !== 'admin') {
            basePath = `/${first}/verificador/api`;
        } else {
            basePath = '/verificador/api';
        }

        // Normaliza a URL garantindo barra inicial e removendo duplicações
        const normalizedPath = new URL(basePath, window.location.origin).pathname;
        return normalizedPath.endsWith('/') ? normalizedPath.slice(0, -1) : normalizedPath;
    } catch (_e) {
        return '/verificador/api';
    }
})();

const IS_ADMIN = Boolean(window.IS_ADMIN);
let currentCTODetails = null;
window.currentCTO = null;

const DEFAULT_CENTER = [-22.9068, -43.1729];
const DEFAULT_ZOOM = 12;
const activeMapLayers = new Map();
let lastLoadedLayerKey = null;

function getLayerKey(filename, mapId) {
    if (mapId) return `id:${mapId}`;
    if (filename) return `file:${filename}`;
    return `temp:${Date.now()}`;
}

function cssEscape(value) {
    if (window.CSS && typeof window.CSS.escape === 'function') {
        return window.CSS.escape(value);
    }
    return String(value).replace(/"/g, '\\"').replace(/'/g, "\\'");
}

function findCheckboxElement(key) {
    const selector = `.cto-checkbox-input[data-map-key="${cssEscape(key)}"]`;
    return document.querySelector(selector);
}

function setCheckboxStateForKey(key, checked) {
    const checkbox = findCheckboxElement(key);
    if (!checkbox) return;
    checkbox.checked = checked;
    const card = checkbox.closest('.cto-card');
    if (card) {
        card.classList.toggle('selected', checked);
    }
}

function resetMapView() {
    if (typeof map !== 'undefined' && map && typeof map.setView === 'function') {
        map.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
    }
}

function getCombinedBounds() {
    let combined = null;
    activeMapLayers.forEach(entry => {
        const { bounds } = entry || {};
        if (!bounds || typeof bounds.isValid !== 'function' || !bounds.isValid()) {
            return;
        }
        if (!combined) {
            combined = L.latLngBounds(bounds.getSouthWest(), bounds.getNorthEast());
        } else {
            combined.extend(bounds.getSouthWest());
            combined.extend(bounds.getNorthEast());
        }
    });
    return combined;
}

function focusMapOnCurrentLayers() {
    if (typeof map === 'undefined' || !map || typeof map.fitBounds !== 'function') {
        return;
    }
    const combinedBounds = getCombinedBounds();
    if (combinedBounds && combinedBounds.isValid && combinedBounds.isValid()) {
        map.fitBounds(combinedBounds.pad(0.1));
    } else {
        resetMapView();
    }
}

function removeMapLayerByKey(key, { updateCheckbox = true, suppressFit = false } = {}) {
    const entry = activeMapLayers.get(key);
    if (!entry) return;
    try {
        if (entry.layer && map && typeof map.hasLayer === 'function' && map.hasLayer(entry.layer)) {
            map.removeLayer(entry.layer);
        } else if (entry.layer && typeof entry.layer.remove === 'function') {
            entry.layer.remove();
        }
    } catch (error) {
        console.warn('Erro ao remover camada do mapa:', error);
    }
    activeMapLayers.delete(key);
    if (lastLoadedLayerKey === key) {
        const remainingKeys = Array.from(activeMapLayers.keys());
        lastLoadedLayerKey = remainingKeys.length ? remainingKeys[remainingKeys.length - 1] : null;
    }
    if (updateCheckbox) {
        setCheckboxStateForKey(key, false);
    }
    if (!suppressFit) {
        focusMapOnCurrentLayers();
    }
}

function clearAllMapLayers({ resetCheckboxes = true, suppressFit = false } = {}) {
    const keys = Array.from(activeMapLayers.keys());
    keys.forEach(key => {
        removeMapLayerByKey(key, { updateCheckbox: resetCheckboxes, suppressFit: true });
    });
    activeMapLayers.clear();
    lastLoadedLayerKey = null;
    if (!suppressFit) {
        focusMapOnCurrentLayers();
    }
}

function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// ===== DARK MODE FUNCTIONALITY =====
function applyFtthTheme(theme, { persist = true } = {}) {
    const normalized = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', normalized);
    if (document.body) {
        document.body.setAttribute('data-theme', normalized);
    }

    const metaTheme = document.querySelector('meta[name="theme-color"]');
    if (metaTheme) {
        metaTheme.content = normalized === 'dark' ? '#121212' : '#003366';
    }

    document.querySelectorAll('#theme-toggle-btn, #theme-toggle-btn-mobile').forEach((btn) => {
        const icon = btn.querySelector('i');
        if (normalized === 'dark') {
            if (icon) icon.className = 'fas fa-sun';
            btn.title = 'Alternar para tema claro';
        } else {
            if (icon) icon.className = 'fas fa-moon';
            btn.title = 'Alternar para tema escuro';
        }
    });

    if (persist) {
        try {
            localStorage.setItem('theme', normalized);
            localStorage.setItem('rm-theme', normalized);
        } catch (_e) {
            /* ignore */
        }
    }
}

function toggleFtthTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    applyFtthTheme(current === 'light' ? 'dark' : 'light');
}

function initializeThemeToggle() {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeThemeToggle, { once: true });
        return;
    }
    if (window.__ftthThemeInitialized) {
        return;
    }
    window.__ftthThemeInitialized = true;

    let savedTheme = 'light';
    try {
        savedTheme = localStorage.getItem('theme') || localStorage.getItem('rm-theme') || 'light';
    } catch (_e) {
        savedTheme = 'light';
    }
    applyFtthTheme(savedTheme, { persist: false });

    document.querySelectorAll('#theme-toggle-btn, #theme-toggle-btn-mobile').forEach((btn) => {
        if (btn.dataset.ftthThemeBound) {
            return;
        }
        btn.dataset.ftthThemeBound = '1';
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            toggleFtthTheme();
        });
    });
}

// Função global para testar o dark mode
window.testDarkMode = function() {
    toggleFtthTheme();
    return document.documentElement.getAttribute('data-theme') || 'light';
};

// Função de diagnóstico completo do dark mode
window.diagnoseDarkMode = function() {
    const originalLog = console.log;
    originalLog('🔍 === DIAGNÓSTICO COMPLETO DO DARK MODE ===');
    
    // 1. Verificar elementos HTML
    const themeBtn = document.getElementById('theme-toggle-btn');
    const themeIcon = themeBtn ? themeBtn.querySelector('i') : null;
    
    originalLog('1. Elementos HTML:');
    originalLog('   - Botão encontrado:', !!themeBtn);
    originalLog('   - Ícone encontrado:', !!themeIcon);
    
    if (themeBtn) {
        originalLog('   - Botão classes:', themeBtn.className);
        originalLog('   - Botão title:', themeBtn.title);
    }
    
    if (themeIcon) {
        originalLog('   - Ícone classes:', themeIcon.className);
    }
    
    // 2. Verificar atributos de tema
    const htmlTheme = document.documentElement.getAttribute('data-theme');
    const bodyTheme = document.body.getAttribute('data-theme');
    
    originalLog('2. Atributos de tema:');
    originalLog('   - HTML data-theme:', htmlTheme);
    originalLog('   - Body data-theme:', bodyTheme);
    
    // 3. Verificar localStorage
    const savedTheme = localStorage.getItem('theme');
    originalLog('3. LocalStorage:');
    originalLog('   - Tema salvo:', savedTheme);
    
    // 4. Verificar estilos CSS
    const computedStyle = window.getComputedStyle(document.body);
    originalLog('4. Estilos aplicados:');
    originalLog('   - Background:', computedStyle.backgroundColor);
    originalLog('   - Color:', computedStyle.color);
    
    // 5. Verificar variáveis CSS
    const rootStyle = window.getComputedStyle(document.documentElement);
    originalLog('5. Variáveis CSS:');
    originalLog('   - --bg-primary:', rootStyle.getPropertyValue('--bg-primary'));
    originalLog('   - --text-primary:', rootStyle.getPropertyValue('--text-primary'));
    originalLog('   - --dark-bg-primary:', rootStyle.getPropertyValue('--dark-bg-primary'));
    originalLog('   - --dark-text-primary:', rootStyle.getPropertyValue('--dark-text-primary'));
    
    // 6. Testar funcionalidade
    originalLog('6. Testando funcionalidade...');
    if (themeBtn) {
        originalLog('   - Simulando clique...');
        themeBtn.click();
        
        setTimeout(() => {
            const newTheme = document.documentElement.getAttribute('data-theme');
            originalLog('   - Tema após clique:', newTheme);
            originalLog('🔍 === FIM DO DIAGNÓSTICO ===');
        }, 100);
    } else {
        originalLog('   - Botão não encontrado, não é possível testar');
        originalLog('🔍 === FIM DO DIAGNÓSTICO ===');
    }
};

// Elementos da barra de pesquisa principal - serão inicializados quando o DOM estiver pronto
let searchInput, searchBtn, clearSearchBtn, searchResults;

// Variável para controlar debounce da busca
let searchTimeout;
// Variável para controlar o modo de clique/navegação
let isClickMode = false;

// Cache inteligente com múltiplas camadas
const smartCache = (() => {
    const stores = {
        search: new Map(),
        coordinates: new Map(),
        viability: new Map(),
        routes: new Map()
    };
    
    const meta = {
        search: new Map(),
        coordinates: new Map(),
        viability: new Map(),
        routes: new Map()
    };
    
    const TTL = {
        search: 10 * 60 * 1000,      // 10 minutos
        coordinates: 60 * 60 * 1000, // 1 hora
        viability: 30 * 60 * 1000,   // 30 minutos
        routes: 2 * 60 * 60 * 1000   // 2 horas
    };
    
    return {
        get(type, key) {
            const store = stores[type];
            const metaStore = meta[type];
            const ts = metaStore.get(key);
            
            if (!ts) return null;
            if (Date.now() - ts > TTL[type]) {
                store.delete(key);
                metaStore.delete(key);
                return null;
            }
            return store.get(key) || null;
        },
        
        set(type, key, value) {
            stores[type].set(key, Array.isArray(value) ? value.slice() : value);
            meta[type].set(key, Date.now());
        },
        
        cleanExpired() {
            const now = Date.now();
            Object.keys(stores).forEach(type => {
                const store = stores[type];
                const metaStore = meta[type];
                
                for (const [key, ts] of metaStore.entries()) {
                    if (now - ts > TTL[type]) {
                        store.delete(key);
                        metaStore.delete(key);
                    }
                }
            });
        },
        
        size(type) { 
            return type ? stores[type].size : Object.values(stores).reduce((sum, store) => sum + store.size, 0);
        },
        
        clear(type) {
            if (type) {
                stores[type].clear();
                meta[type].clear();
            } else {
                Object.values(stores).forEach(store => store.clear());
                Object.values(meta).forEach(metaStore => metaStore.clear());
            }
        },

        remove(type, key) {
            if (!stores[type]) return;
            stores[type].delete(key);
            meta[type].delete(key);
        }
    };
})();

// Cache simples para compatibilidade (deprecated)
const searchCache = smartCache;

// Sistema de monitoramento de performance
const performanceMonitor = (() => {
    const metrics = {
        loadTimes: [],
        cacheHits: 0,
        cacheMisses: 0,
        apiCalls: 0,
        errors: 0
    };
    
    return {
        startTimer(label) {
            return performance.now();
        },
        
        endTimer(startTime, label) {
            const duration = performance.now() - startTime;
            metrics.loadTimes.push({ label, duration, timestamp: Date.now() });
            
            // Manter apenas os últimos 100 tempos
            if (metrics.loadTimes.length > 100) {
                metrics.loadTimes = metrics.loadTimes.slice(-100);
            }
            
            return duration;
        },
        
        recordCacheHit() {
            metrics.cacheHits++;
        },
        
        recordCacheMiss() {
            metrics.cacheMisses++;
        },
        
        recordApiCall() {
            metrics.apiCalls++;
        },
        
        recordError() {
            metrics.errors++;
        },
        
        getStats() {
            const avgLoadTime = metrics.loadTimes.length > 0 
                ? metrics.loadTimes.reduce((sum, item) => sum + item.duration, 0) / metrics.loadTimes.length 
                : 0;
            
            const cacheHitRate = metrics.cacheHits + metrics.cacheMisses > 0 
                ? (metrics.cacheHits / (metrics.cacheHits + metrics.cacheMisses) * 100).toFixed(1)
                : 0;
            
            return {
                avgLoadTime: avgLoadTime.toFixed(2),
                cacheHitRate: `${cacheHitRate}%`,
                apiCalls: metrics.apiCalls,
                errors: metrics.errors,
                totalRequests: metrics.cacheHits + metrics.cacheMisses
            };
        },
        
        showIndicator() {
            const stats = this.getStats();
            const indicator = document.createElement('div');
            indicator.className = 'performance-indicator show';
            indicator.innerHTML = `
                <div>⚡ ${stats.avgLoadTime}ms</div>
                <div>📦 ${stats.cacheHitRate}</div>
                <div>🌐 ${stats.apiCalls}</div>
                <div>❌ ${stats.errors}</div>
            `;
            
            document.body.appendChild(indicator);
            
            setTimeout(() => {
                indicator.classList.remove('show');
                setTimeout(() => indicator.remove(), 300);
            }, 2000);
        }
    };
})();

function cleanExpiredCache() {
    try {
        searchCache.cleanExpired();
    } catch (e) {
        console.warn('cleanExpiredCache falhou:', e);
    }
}

// Inicialização do mapa Leaflet (Maricá e limites do Brasil)
const brazilBounds = L.latLngBounds(
    L.latLng(-34.0, -74.0),  // sudoeste aproximado
    L.latLng(5.5, -34.0)     // nordeste aproximado
);

// Detectar se é dispositivo mobile
const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || 
                 (window.innerWidth <= 768) ||
                 ('ontouchstart' in window);

// Configurações otimizadas para mobile
const mapOptions = {
    zoomControl: false,
    preferCanvas: true,
    maxBounds: brazilBounds,
    maxBoundsViscosity: 1.0,
    // Melhorias para mobile - GARANTIR TODOS OS GESTOS ESTÃO HABILITADOS
    dragging: true,
    touchZoom: true, // CRÍTICO: Habilitar zoom por toque (pinch)
    doubleClickZoom: true, // Habilitar double-tap zoom no mobile
    scrollWheelZoom: !isMobile, // Desabilitar zoom com scroll no mobile (usa pinch)
    boxZoom: false, // Desabilitar box zoom no mobile
    keyboard: false, // Desabilitar teclado no mobile
    // Configurações de performance para mobile
    fadeAnimation: !isMobile, // Desabilitar fade no mobile para melhor performance
    zoomAnimation: true,
    zoomAnimationThreshold: isMobile ? 3 : 4, // Threshold menor no mobile para melhor resposta
    // Melhorias de toque - AJUSTADAS PARA MELHOR RESPONSIVIDADE
    tap: true,
    tapTolerance: isMobile ? 30 : 15, // Tolerância MUITO maior para toque no mobile (evitar conflitos)
    // Configurações de arraste melhoradas para mobile
    inertia: true, // Habilitar inércia para arraste mais suave
    inertiaDeceleration: isMobile ? 2000 : 3000, // Desaceleração mais rápida no mobile
    inertiaMaxSpeed: isMobile ? 2000 : 1500, // Velocidade máxima maior no mobile para melhor resposta
    easeLinearity: isMobile ? 0.3 : 0.25, // Mais linear no mobile para movimento mais previsível
    worldCopyJump: false,
    // Melhorias de renderização (Leaflet usa preferCanvas para isso)
    // Configurações de zoom - AJUSTADAS PARA MOBILE
    minZoom: 5,
    maxZoom: 19,
    zoomSnap: isMobile ? 0 : 0.25, // Sem snap no mobile para zoom mais fluido
    zoomDelta: isMobile ? 1 : 1.5
};

const map = L.map('map', mapOptions);

// Garantir que todos os handlers de toque estejam habilitados após criação do mapa
if (isMobile) {
    // Forçar habilitar todos os handlers de toque no mobile
    map.touchZoom.enable();
    map.doubleClickZoom.enable();
    map.dragging.enable();
    
    // Melhorar detecção de gestos de pinch
    const mapElement = document.getElementById('map');
    if (mapElement) {
        // Remover qualquer bloqueio de gestos
        mapElement.style.touchAction = 'pan-x pan-y pinch-zoom double-tap-zoom';
        
        // Prevenir que eventos sejam bloqueados
        mapElement.addEventListener('touchstart', function(e) {
            // Permitir múltiplos toques para pinch zoom
            if (e.touches.length > 1) {
                e.preventDefault = () => {}; // Não prevenir para permitir pinch
            }
        }, { passive: true });
        
        mapElement.addEventListener('touchmove', function(e) {
            // Permitir movimento para arraste e zoom
            if (e.touches.length > 1) {
                e.preventDefault = () => {}; // Não prevenir para permitir pinch
            }
        }, { passive: true });
    }
}

L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
    minZoom: 5,
    noWrap: true,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'
}).addTo(map);

// Adicionar controle de zoom no canto inferior esquerdo
L.control.zoom({ position: 'bottomleft' }).addTo(map);

// Adicionar controle de direção norte (bússola)
const northControl = L.Control.extend({
    onAdd: function(map) {
        const container = L.DomUtil.create('div', 'leaflet-control leaflet-control-north');
        container.innerHTML = '<div class="north-arrow">N</div>';

        container.addEventListener('click', function() {
            map.setView(map.getCenter(), map.getZoom());
        });
        
        return container;
    }
});

new northControl({ position: 'bottomright' }).addTo(map);

// Vista inicial no Rio de Janeiro, RJ
resetMapView();

// Tornar acessível globalmente
window.map = map;

// Função para garantir que gestos estejam sempre habilitados no mobile
function ensureMobileGesturesEnabled() {
    if (isMobile && map) {
        // Forçar habilitar todos os handlers críticos
        try {
            map.touchZoom.enable();
            map.doubleClickZoom.enable();
            map.dragging.enable();
            
            const mapElement = document.getElementById('map');
            if (mapElement) {
                // Garantir que o CSS permita gestos
                mapElement.style.touchAction = 'pan-x pan-y pinch-zoom double-tap-zoom';
                
                // Remover qualquer bloqueio de eventos
                const leafletContainer = mapElement.querySelector('.leaflet-container');
                if (leafletContainer) {
                    leafletContainer.style.touchAction = 'pan-x pan-y pinch-zoom double-tap-zoom';
                }
            }
        } catch (e) {
            console.warn('Erro ao garantir gestos mobile:', e);
        }
    }
}

// Garantir gestos após carregamento completo
document.addEventListener('DOMContentLoaded', function() {
    if (isMobile) {
        // Aguardar um pouco para garantir que o mapa está totalmente inicializado
        setTimeout(ensureMobileGesturesEnabled, 500);
        
        // Re-verificar após eventos de toque (caso algo desabilite)
        document.addEventListener('touchend', function() {
            setTimeout(ensureMobileGesturesEnabled, 100);
        }, { passive: true });
    }
});

// Chamar quando o mapa estiver pronto
map.whenReady(function() {
    ensureMobileGesturesEnabled();
});

// Helpers: CEP validation, CEP search via ViaCEP, and notifications
function extractCEP(query) {
    const digits = (query || '').replace(/\D/g, '');
    return /^\d{8}$/.test(digits) ? digits : null;
}

function isValidCEP(query) {
    return extractCEP(query) !== null;
}

async function searchByCEP(query) {
    const cep = extractCEP(query);
    if (!cep) return [];

    try {
        const response = await fetch(`${API_BASE}/cep?cep=${cep}`);
        if (!response.ok) {
            return [];
        }
        const data = await response.json();
        if (!data || data.erro) {
            return [];
        }

        return [{
            display_name: data.display_name || `${cep}, Brasil`,
            type: 'CEP',
            importance: 1.0,
            address: data,
            cepNormalized: cep,
            searchCity: data.city,
            searchState: data.state,
        }];
    } catch (e) {
        console.warn('Erro ao consultar CEP:', e);
        return [];
    }
}

/** Mensagens curtas para o usuário final (viabilidade / mapas) */
const FTTH_USER_MESSAGES = {
    mapas_erro: 'Não foi possível carregar os mapas. Tente novamente.',
    mapas_vazio: 'Nenhum mapa disponível. Faça upload no painel.',
    viabilidade_erro: 'Não foi possível verificar a viabilidade. Tente de novo.',
    geocode_erro: 'Endereço não encontrado. Confira o texto e tente outra busca.',
    cto_salvo: 'CTO adicionado ao mapa.',
    cto_removido: 'CTO removido do mapa.',
    conexao_erro: 'Falha de conexão. Verifique a internet e tente novamente.',
};

function showNotification(message, type = 'info', duration = null) {
    try {
        const text = typeof message === 'string' ? message.trim() : String(message);
        if (typeof window.toastManager !== 'undefined' && text.length < 220) {
            const titles = { success: 'Pronto', error: 'Ops', warning: 'Atenção', info: null };
            const d = duration !== null ? duration : (type === 'error' ? 7000 : type === 'warning' ? 6000 : 5000);
            window.toastManager.show(text, type, titles[type] || null, d);
            return;
        }
        console.log(`[${type}] ${text}`);
        let container = document.getElementById('app-notifications');
        if (!container) {
            container = document.createElement('div');
            container.id = 'app-notifications';
            container.style.position = 'fixed';
            container.style.top = '80px';
            container.style.right = '20px';
            container.style.zIndex = '2000';
            container.style.display = 'flex';
            container.style.flexDirection = 'column';
            container.style.gap = '8px';
            container.style.maxWidth = '500px';
            document.body.appendChild(container);
        }
        const el = document.createElement('div');
        
        // Suportar mensagens multilinha
        const messageLines = message.split('\n');
        if (messageLines.length > 1) {
            // Criar estrutura com título e corpo
            const title = messageLines[0];
            const body = messageLines.slice(1).join('\n');
            
            el.innerHTML = `
                <div style="font-weight: 600; margin-bottom: 6px; font-size: 14px;">${title}</div>
                <div style="font-size: 13px; opacity: 0.95; line-height: 1.5; white-space: pre-wrap; max-height: 400px; overflow-y: auto;">${body}</div>
            `;
        } else {
            el.textContent = message;
        }
        
        el.style.padding = '12px 16px';
        el.style.borderRadius = '8px';
        el.style.boxShadow = '0 4px 12px rgba(0,0,0,0.2)';
        el.style.fontSize = '14px';
        el.style.color = '#fff';
        el.style.lineHeight = '1.4';
        el.style.wordWrap = 'break-word';
        el.style.maxWidth = '100%';
        
        // Cores baseadas no tipo
        if (type === 'success') {
            el.style.background = '#10B981'; // --rm-success
        } else if (type === 'error') {
            el.style.background = '#EF4444'; // --rm-error
        } else if (type === 'warning') {
            el.style.background = '#F59E0B'; // --rm-warning
        } else {
            el.style.background = '#00D2FF'; // acento RM
        }
        
        container.appendChild(el);
        
        // Duração baseada no tipo (warnings e errors ficam mais tempo) ou usar duração customizada
        const autoCloseDuration = duration !== null ? duration : (type === 'warning' || type === 'error' ? 10000 : 3000);
        
        // Para mensagens críticas, adicionar botão de fechar manual
        if (autoCloseDuration >= 15000) {
            const closeBtn = document.createElement('button');
            closeBtn.innerHTML = '×';
            closeBtn.style.position = 'absolute';
            closeBtn.style.top = '4px';
            closeBtn.style.right = '4px';
            closeBtn.style.background = 'transparent';
            closeBtn.style.border = 'none';
            closeBtn.style.color = '#fff';
            closeBtn.style.fontSize = '20px';
            closeBtn.style.cursor = 'pointer';
            closeBtn.style.padding = '0 8px';
            closeBtn.style.lineHeight = '1';
            closeBtn.onclick = () => {
                el.style.opacity = '0';
                el.style.transition = 'opacity 300ms ease';
                setTimeout(() => el.remove(), 300);
            };
            el.style.position = 'relative';
            el.appendChild(closeBtn);
        }
        
        setTimeout(() => {
            el.style.opacity = '0';
            el.style.transition = 'opacity 300ms ease';
            setTimeout(() => el.remove(), 300);
        }, autoCloseDuration);
    } catch (e) {
        console.log('Notification:', message);
    }
}

// Parse coordinates from query, supports "lat, lon" or "lat lon" e DMS
function parseCoordinatesFromQuery(query) {
    const q = (query || '').trim();
    if (!q) return null;

    // 1) Tenta DMS com letras de hemisfério (ex.: 22°57'57.5"S 42°57'10.2"W ou 22°54'59.5"S 42°48'35.2"W)
    // Melhorado para suportar diferentes formatos: graus antes ou depois, hemisfério antes ou depois das aspas
    const dmsTokens = [];
    
    // Regex melhorado que captura:
    // - Graus (obrigatório): \d+(?:\.\d+)?
    // - Minutos (opcional): \d{1,2}
    // - Segundos (opcional): \d+(?:\.\d+)?
    // - Hemisfério (obrigatório): N, S, E, W, O
    // Suporta formatos: "22°57'57.5"S", "S 22°57'57.5", "22° 57' 57.5\" S", etc.
    const dmsRegex = /(?:^|\s)([NnSsEeWwOo])?\s*(\d+(?:\.\d+)?)\s*[°º]\s*(\d{1,2})?\s*['′'′]?\s*(\d+(?:\.\d+)?)?\s*["″""]?\s*([NnSsEeWwOo])?/g;
    let m;
    while ((m = dmsRegex.exec(q)) !== null) {
        // Hemisfério pode estar antes ou depois
        let hemi = (m[1] || m[5] || '').toUpperCase();
        if (!hemi) continue; // Pula se não tiver hemisfério
        
        // Português: 'O' (Oeste) equivale a 'W'
        if (hemi === 'O') hemi = 'W';
        
        const deg = parseFloat(m[2]);
        const min = m[3] ? parseFloat(m[3]) : 0;
        const sec = m[4] ? parseFloat(m[4]) : 0;
        
        // Converter para decimal
        const dec = Math.abs(deg) + (min / 60) + (sec / 3600);
        const signed = (hemi === 'S' || hemi === 'W') ? -dec : dec;
        
        dmsTokens.push({ value: signed, hemi });
    }
    
    // Se encontrou pelo menos 2 tokens DMS
    if (dmsTokens.length >= 2) {
        // Prefere NS para latitude e EW para longitude
        const latToken = dmsTokens.find(t => t.hemi === 'N' || t.hemi === 'S') || dmsTokens[0];
        const lonToken = dmsTokens.find(t => t.hemi === 'E' || t.hemi === 'W') || dmsTokens[1];
        const lat = latToken?.value;
        const lon = lonToken?.value;
        if (isFinite(lat) && isFinite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
            return { lat, lon };
        }
    }
    
    // Tentativa alternativa: formato mais flexível para DMS
    // Exemplo: "22°57'57.5\"S 42°57'10.2\"W" ou "22°57'57.5\"S 42°57'10.2\"W"
    // Suporta aspas simples, duplas e diferentes tipos de aspas Unicode
    const dmsAltRegex = /(\d+(?:\.\d+)?)\s*[°º]\s*(\d{1,2})\s*['′'′]\s*(\d+(?:\.\d+)?)\s*["″""]?\s*([NnSsEeWwOo])\s+(\d+(?:\.\d+)?)\s*[°º]\s*(\d{1,2})\s*['′'′]\s*(\d+(?:\.\d+)?)\s*["″""]?\s*([NnSsEeWwOo])/i;
    const altMatch = q.match(dmsAltRegex);
    if (altMatch) {
        // Primeira coordenada (latitude)
        const latDeg = parseFloat(altMatch[1]);
        const latMin = parseFloat(altMatch[2]);
        const latSec = parseFloat(altMatch[3]);
        let latHemi = altMatch[4].toUpperCase();
        if (latHemi === 'O') latHemi = 'W';
        const latDec = Math.abs(latDeg) + (latMin / 60) + (latSec / 3600);
        const lat = (latHemi === 'S') ? -latDec : latDec;
        
        // Segunda coordenada (longitude)
        const lonDeg = parseFloat(altMatch[5]);
        const lonMin = parseFloat(altMatch[6]);
        const lonSec = parseFloat(altMatch[7]);
        let lonHemi = altMatch[8].toUpperCase();
        if (lonHemi === 'O') lonHemi = 'W';
        const lonDec = Math.abs(lonDeg) + (lonMin / 60) + (lonSec / 3600);
        const lon = (lonHemi === 'W') ? -lonDec : lonDec;
        
        if (isFinite(lat) && isFinite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
            return { lat, lon };
        }
    }
    
    // Tentativa final: formato específico com aspas duplas e hemisfério depois das aspas
    // Exemplo: "22°57'57.5\"S 42°57'10.2\"W" ou "22°57'57.5"S 42°57'10.2"W"
    // Regex mais simples e direto que captura o padrão exato
    const dmsQuotedRegex = /(\d+(?:\.\d+)?)\s*[°º]\s*(\d{1,2})\s*['′'′]\s*(\d+(?:\.\d+)?)\s*["″""]?\s*([NnSsEeWwOo])\s+(\d+(?:\.\d+)?)\s*[°º]\s*(\d{1,2})\s*['′'′]\s*(\d+(?:\.\d+)?)\s*["″""]?\s*([NnSsEeWwOo])/i;
    const quotedMatch = q.match(dmsQuotedRegex);
    if (quotedMatch) {
        // Primeira coordenada (latitude)
        const latDeg = parseFloat(quotedMatch[1]);
        const latMin = parseFloat(quotedMatch[2]);
        const latSec = parseFloat(quotedMatch[3]);
        let latHemi = quotedMatch[4].toUpperCase();
        if (latHemi === 'O') latHemi = 'W';
        const latDec = Math.abs(latDeg) + (latMin / 60) + (latSec / 3600);
        const lat = (latHemi === 'S') ? -latDec : latDec;
        
        // Segunda coordenada (longitude)
        const lonDeg = parseFloat(quotedMatch[5]);
        const lonMin = parseFloat(quotedMatch[6]);
        const lonSec = parseFloat(quotedMatch[7]);
        let lonHemi = quotedMatch[8].toUpperCase();
        if (lonHemi === 'O') lonHemi = 'W';
        const lonDec = Math.abs(lonDeg) + (lonMin / 60) + (lonSec / 3600);
        const lon = (lonHemi === 'W') ? -lonDec : lonDec;
        
        if (isFinite(lat) && isFinite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
            return { lat, lon };
        }
    }
    
    // Última tentativa: regex mais permissivo que tenta capturar qualquer formato DMS
    // Remove caracteres especiais e tenta encontrar padrões DMS
    const cleanQ = q.replace(/["″""]/g, '').trim();
    const dmsFlexibleRegex = /(\d+(?:\.\d+)?)\s*[°º]\s*(\d{1,2})\s*['′'′]\s*(\d+(?:\.\d+)?)\s*([NnSsEeWwOo])\s+(\d+(?:\.\d+)?)\s*[°º]\s*(\d{1,2})\s*['′'′]\s*(\d+(?:\.\d+)?)\s*([NnSsEeWwOo])/i;
    const flexibleMatch = cleanQ.match(dmsFlexibleRegex);
    if (flexibleMatch) {
        // Primeira coordenada (latitude)
        const latDeg = parseFloat(flexibleMatch[1]);
        const latMin = parseFloat(flexibleMatch[2]);
        const latSec = parseFloat(flexibleMatch[3]);
        let latHemi = flexibleMatch[4].toUpperCase();
        if (latHemi === 'O') latHemi = 'W';
        const latDec = Math.abs(latDeg) + (latMin / 60) + (latSec / 3600);
        const lat = (latHemi === 'S') ? -latDec : latDec;
        
        // Segunda coordenada (longitude)
        const lonDeg = parseFloat(flexibleMatch[5]);
        const lonMin = parseFloat(flexibleMatch[6]);
        const lonSec = parseFloat(flexibleMatch[7]);
        let lonHemi = flexibleMatch[8].toUpperCase();
        if (lonHemi === 'O') lonHemi = 'W';
        const lonDec = Math.abs(lonDeg) + (lonMin / 60) + (lonSec / 3600);
        const lon = (lonHemi === 'W') ? -lonDec : lonDec;
        
        if (isFinite(lat) && isFinite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
            return { lat, lon };
        }
    }

    // 2) Fallback: decimal "lat, lon" ou "lat lon"
    const normalized = q.replace(/[,;]/g, ' ').trim();
    const matches = normalized.match(/[-+]?\d*\.?\d+/g);
    if (!matches || matches.length < 2) return null;
    const lat = parseFloat(matches[0]);
    const lon = parseFloat(matches[1]);
    if (!isFinite(lat) || !isFinite(lon)) return null;
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;
    return { lat, lon };
}

// Função searchAddress removida - pertencia ao primeiro método de pesquisa

// Função displaySearchResults removida - pertencia ao primeiro método de pesquisa

// Funções de pesquisa removidas - pertenciam ao primeiro método de pesquisa

// Esconder dropdown quando clicar fora
document.addEventListener('click', (e) => {
    const searchContainer = document.querySelector('.top-search-container');
    if (searchResults && searchContainer && !searchContainer.contains(e.target)) {
        searchResults.classList.remove('show');
    }
});

// Função para resumir endereço
function resumirEndereco(endereco) {
    // Verificar se endereco é válido
    if (!endereco || typeof endereco !== 'string') {
        return endereco || '';
    }
    
    // Pegar apenas a primeira parte (rua/avenida) e cidade
    const partes = endereco.split(',');
    if (partes.length >= 2) {
        const rua = partes[0].trim();
        const cidade = partes[1].trim();
        return `${rua}, ${cidade}`;
    }
    return endereco.length > 50 ? endereco.substring(0, 50) + '...' : endereco;
}

// Função util para normalizar número do CTO (remove prefixos e mantém dígitos com . ou -)
function formatCtoNumber(name) {
    if (!name) return 'Desconhecido';
    const str = String(name).trim();
    // Captura sequências como 16, 16.01, 12-3, etc.
    const match = str.match(/\d+(?:[.\-]\d+)*/);
    if (match) return match[0];
    // Fallback: remove tudo que não for dígito, ponto ou hífen
    const cleaned = str.replace(/[^0-9.\-]/g, '').replace(/^[-.]+|[-.]+$/g, '').trim();
    return cleaned || str;
}

function escapeHtml(text) {
    if (text == null) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function formatDistance(meters) {
    const value = Number(meters);
    if (Number.isNaN(value)) return '—';
    if (value >= 1000) {
        return `${(value / 1000).toFixed(2).replace('.', ',')} km`;
    }
    return `${Math.round(value)} m`;
}

function getViabilityStatusMeta(status) {
    if (status === 'Viável') {
        return { className: 'viability-status--viable', icon: 'fa-check-circle' };
    }
    if (status === 'Viabilidade Limitada') {
        return { className: 'viability-status--limited', icon: 'fa-exclamation-circle' };
    }
    return { className: 'viability-status--unviable', icon: 'fa-times-circle' };
}

function truncateText(text, maxLen = 32) {
    if (text == null) return '';
    const str = String(text);
    return str.length > maxLen ? `${str.slice(0, maxLen - 1)}…` : str;
}

function buildViabilityMetric(icon, label, value, wide = false) {
    const safeValue = escapeHtml(value);
    return `
        <div class="viability-metric${wide ? ' viability-metric--wide' : ''}" title="${safeValue}">
            <span class="viability-metric-icon" aria-hidden="true"><i class="fas ${icon}"></i></span>
            <div class="viability-metric-body">
                <span class="viability-metric-label">${escapeHtml(label)}</span>
                <span class="viability-metric-value">${safeValue}</span>
            </div>
        </div>`;
}

function buildViabilityResultPopup(data, endereco) {
    const enderecoResumido = resumirEndereco(endereco);
    const status = data.viabilidade?.status || 'N/A';
    const meta = getViabilityStatusMeta(status);
    const distancia = formatDistance(data.distancia?.metros);
    const cto = formatCtoNumber(data.cto?.nome || 'N/A');
    const mapa = truncateText(data.cto?.arquivo || 'N/A', 28);
    const descricao = data.viabilidade?.descricao || '';

    return `
        <div class="viability-result-popup">
            <div class="viability-result-header">
                <div class="viability-result-status-icon ${meta.className}" aria-hidden="true">
                    <i class="fas ${meta.icon}"></i>
                </div>
                <div class="viability-result-heading">
                    <span class="viability-status-badge ${meta.className}">${escapeHtml(status)}</span>
                    ${descricao ? `<span class="viability-result-desc">${escapeHtml(descricao)}</span>` : ''}
                </div>
            </div>
            <div class="viability-result-metrics">
                ${buildViabilityMetric('fa-map-marker-alt', 'Endereço', enderecoResumido, true)}
                ${buildViabilityMetric('fa-route', 'Distância', distancia)}
                ${buildViabilityMetric('fa-network-wired', 'CTO', cto)}
                ${buildViabilityMetric('fa-layer-group', 'Mapa', mapa, true)}
            </div>
            <button type="button" data-ftth-action="close-viability" class="viability-close-btn viability-close-btn--compact">
                <i class="fas fa-times" aria-hidden="true"></i>
                <span>Fechar</span>
            </button>
        </div>`;
}

function buildCtoMarkerPopup({ nome, arquivo, lat, lng, showRemoveBtn = false }) {
    const latStr = Number(lat).toFixed(6);
    const lngStr = Number(lng).toFixed(6);
    const nomeDisplay = formatCtoNumber(nome || 'CTO');
    const mapaDisplay = truncateText(arquivo || 'N/A', 28);

    return `
        <div class="viability-result-popup viability-result-popup--cto">
            <div class="viability-result-header">
                <div class="viability-result-status-icon viability-status--viable" aria-hidden="true">
                    <i class="fas fa-map-pin"></i>
                </div>
                <div class="viability-result-heading">
                    <span class="viability-result-eyebrow">Ponto de rede</span>
                    <span class="viability-popup-title">${escapeHtml(nomeDisplay)}</span>
                </div>
            </div>
            <div class="viability-result-metrics">
                ${buildViabilityMetric('fa-layer-group', 'Mapa', mapaDisplay, true)}
                ${buildViabilityMetric('fa-crosshairs', 'Coordenadas', `${latStr}, ${lngStr}`, true)}
            </div>
            ${showRemoveBtn ? '<button type="button" class="viability-close-btn viability-close-btn--compact viability-close-btn--danger remove-cto-btn"><i class="fas fa-trash-alt" aria-hidden="true"></i><span>Remover CTO</span></button>' : ''}
        </div>`;
}

function buildCtoResultPopup(data, showRemoveBtn) {
    return buildCtoMarkerPopup({
        nome: data.cto?.nome || 'N/A',
        arquivo: data.cto?.arquivo || 'N/A',
        lat: data.cto?.lat || 0,
        lng: data.cto?.lon || 0,
        showRemoveBtn,
    });
}

// Funções da barra de pesquisa principal
function initializeMainSearch() {
    // Aguardar um pouco para garantir que o DOM esteja pronto
    setTimeout(() => {
        // Inicializar elementos do DOM
        searchInput = document.getElementById('search-input');
        searchBtn = document.getElementById('search-btn');
        clearSearchBtn = document.getElementById('clear-search'); // Opcional
        searchResults = document.getElementById('search-results');
        
        if (!searchInput || !searchBtn || !searchResults) {
            console.error('Elementos da barra de pesquisa não encontrados!');
            console.log('Elementos encontrados:', {
                searchInput: !!searchInput,
                searchBtn: !!searchBtn,
                clearSearchBtn: !!clearSearchBtn,
                searchResults: !!searchResults
            });
            return;
        }

    // Event listeners
    searchBtn.addEventListener('click', () => {
        performSearch().catch(error => {
            console.error('Erro na pesquisa:', error);
            showNotification('Erro ao realizar pesquisa', 'error');
        });
    });
    
    // Adicionar event listener apenas se o botão existir
    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', clearSearch);
    }
    
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            performSearch().catch(error => {
                console.error('Erro na pesquisa:', error);
                showNotification('Erro ao realizar pesquisa', 'error');
            });
        }
    });

    // Debounce para pesquisa e autocomplete - evitar muitas requisições
    let searchTimeout = null;
    let suggestionTimeout = null;
    
    searchInput.addEventListener('input', (e) => {
        // Limpar timeout anterior
        if (searchTimeout) {
            clearTimeout(searchTimeout);
        }
        if (suggestionTimeout) {
            clearTimeout(suggestionTimeout);
        }
        
        const query = e.target.value.trim();
        if (query.length === 0) {
            if (clearSearchBtn) {
                clearSearchBtn.style.display = 'none';
            }
            hideSearchResults();
        } else {
            if (clearSearchBtn) {
                clearSearchBtn.style.display = 'block';
            }
            
            // Mostrar sugestões enquanto digita (após 3 caracteres)
            if (query.length >= 3) {
                suggestionTimeout = setTimeout(() => {
                    fetchAddressSuggestions(query);
                }, 300); // Aguardar 300ms após parar de digitar
            } else {
                hideSearchResults();
            }
        }
    });

    // Fechar resultados ao clicar fora
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-container')) {
            hideSearchResults();
        }
    });
    
    console.log('✅ Barra de pesquisa inicializada com sucesso!');
    }, 100); // Aguardar 100ms para garantir que o DOM esteja pronto
}

async function performSearch(forcedQuery) {
    const inputEl = document.getElementById('search-input');
    const query = (typeof forcedQuery === 'string' ? forcedQuery : (inputEl?.value ?? searchInput?.value ?? '')).trim();
    if (!query) return;

    showSearchLoadingScreen(query);

    try {
        // Verificar se é coordenada
        const coords = parseCoordinatesFromQuery(query);
        if (coords) {
            await processSearchResultWithConfirmation(coords.lat, coords.lng, `Coordenadas: ${coords.lat}, ${coords.lng}`);
            hideSearchResults();
            return;
        }

        // Método unificado: buscar por CEP ou endereço
        await searchUnified(query);

    } catch (error) {
        console.error('Erro na pesquisa:', error);
        showNotification('Erro ao realizar pesquisa', 'error');
    } finally {
        hideViabilityLoading();
        hideSearchLoading();
    }
}

// Método unificado de pesquisa que funciona para CEP e endereços
async function searchUnified(query) {
    let searchQuery = query;
    let addressText = query;

    // Se for CEP, buscar informações do endereço primeiro
    if (isValidCEP(query)) {
        try {
            const cepResults = await searchByCEP(query);
            if (cepResults && cepResults.length > 0) {
                const cepData = cepResults[0];
                searchQuery = cepData.display_name;
                addressText = `${cepData.display_name} - CEP: ${query}`;
            }
        } catch (error) {
            console.warn('Erro ao buscar CEP, tentando busca direta:', error);
        }
    }

    // Buscar coordenadas usando API do backend (que faz proxy para Nominatim)
    try {
        const geocodeUrl = `${API_BASE}/geocode?${new URLSearchParams({ endereco: searchQuery })}`;
        const response = await fetch(geocodeUrl);
        
        // Verificar Content-Type para saber se a resposta é JSON
        const contentType = response.headers.get('content-type') || '';
        const isJson = contentType.includes('application/json');
        
        // Fazer parse do JSON apenas uma vez
        let result;
        if (isJson) {
            try {
                result = await response.json();
            } catch (e) {
                // Se não conseguir fazer parse, tratar como erro
                throw new Error(`Erro ao processar resposta do servidor: ${response.statusText}`);
            }
        } else {
            // Se não for JSON, tratar como erro
            throw new Error(`Resposta não é JSON. Status: ${response.status}`);
        }
        
        const isGeocodeMiss =
            response.status === 422 ||
            result.codigo === 'geocode_nao_encontrado' ||
            (result.erro && result.erro.includes('Endereço não encontrado'));

        if (isGeocodeMiss) {
            showNotification('📍 Endereço não encontrado. Tente usar um endereço mais completo ou específico.', 'warning', 5000);
            console.warn('⚠️ Endereço não encontrado:', query);
            hideSearchResults();
            return;
        }

        // Verificar se a resposta foi bem-sucedida
        if (!response.ok) {
            const errorMessage = result.erro || result.message || `Erro HTTP ${response.status}`;
            throw new Error(errorMessage);
        }

        // Verificar se há erro na resposta
        if (result.erro) {
            throw new Error(result.erro);
        }

        // Verificar se temos coordenadas válidas
        if (result.lat && result.lng) {
            await processSearchResultWithConfirmation(parseFloat(result.lat), parseFloat(result.lng), result.endereco_completo || addressText);
            hideSearchResults();
        } else {
            // Endereço não encontrado - mostrar mensagem ao usuário
            showNotification('📍 Endereço não encontrado. Tente usar um endereço mais completo ou específico.', 'warning', 5000);
            hideSearchResults();
        }
    } catch (error) {
        // Verificar se é erro de "endereço não encontrado"
        const isAddressNotFound = error.message && (
            error.message.includes('Endereço não encontrado') || 
            error.message.includes('geocode_nao_encontrado') ||
            (error.message.includes('404') && error.message.includes('Endereço')) ||
            (error.message.includes('422') && error.message.includes('Endereço'))
        );
        
        if (isAddressNotFound) {
            // Mostrar mensagem ao usuário quando endereço não for encontrado
            showNotification('📍 Endereço não encontrado. Tente usar um endereço mais completo ou específico.', 'warning', 5000);
            console.warn('⚠️ Endereço não encontrado:', query);
        } else {
            // Outros erros - logar e mostrar mensagem
            console.error('Erro na busca:', error);
            showNotification('Erro ao buscar localização: ' + (error.message || 'Erro desconhecido'), 'error');
        }
        hideSearchResults();
    }
}

// Função auxiliar para processar resultado da pesquisa com confirmação
async function processSearchResultWithConfirmation(lat, lng, addressText) {
    await markLocationWithConfirmation(lat, lng, addressText);
}

// Função para marcar localização e mostrar popup de confirmação
async function markLocationWithConfirmation(lat, lng, addressText, fromClickMode = false) {
    const sessionId = beginViabilityPopupSession();

    map.setView([lat, lng], 16);

    if (window.searchMarker && map.hasLayer(window.searchMarker)) {
        map.removeLayer(window.searchMarker);
    }

    const searchIcon = L.divIcon({
        className: 'search-marker',
        html: '<div class="search-marker-pin"><div class="search-marker-pulse"></div></div>',
        iconSize: [22, 22],
        iconAnchor: [11, 11]
    });

    window.searchMarker = L.marker([lat, lng], { icon: searchIcon }).addTo(map);

    const isMobileDevice =
        /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
        window.innerWidth <= 768 ||
        'ontouchstart' in window;

    const buttonMobileClass = isMobileDevice ? ' mobile-button' : '';

    const confirmPopup = `
        <div class="viability-popup viability-confirm-popup">
            <div class="viability-popup-header">
                <span class="viability-popup-header-icon" aria-hidden="true"><i class="fas fa-search-location"></i></span>
                <h4 class="viability-popup-title">Verificar viabilidade?</h4>
            </div>
            <p class="viability-popup-subtitle">Confirme para analisar CTOs próximos e calcular a rota.</p>
            <div class="popup-actions">
                <button type="button" class="confirm-verify-btn${buttonMobileClass}">
                    <i class="fas fa-check" aria-hidden="true"></i>
                    <span>Sim</span>
                </button>
                <button type="button" class="cancel-verify-btn${buttonMobileClass}">
                    <i class="fas fa-times" aria-hidden="true"></i>
                    <span>Não</span>
                </button>
            </div>
        </div>`;

    window.searchMarker
        .bindPopup(confirmPopup, getSearchMarkerPopupOptions())
        .openPopup();

    nudgeMapForPopupAnchor(window.searchMarker);
    ensureMarkerPopupVisible(window.searchMarker);

    registerViabilityPopupGuards(window.searchMarker);
    registerMapPopupClickGuard();

    window.searchMarker.on('popupopen', () => {
        const popupNode = getViabilityPopupContentNode(window.searchMarker);
        attachPopupListeners(popupNode, lat, lng, addressText, fromClickMode);
    });

    schedulePopupButtonBind(window.searchMarker, lat, lng, addressText, fromClickMode, sessionId);
}


async function displaySearchResults(results) {
    if (!searchResults) return;

    searchResults.innerHTML = '';
    
    results.forEach((result, index) => {
        const item = document.createElement('div');
        item.className = 'search-result-item';
        item.innerHTML = `
            <div class="search-result-title">${result.display_name && typeof result.display_name === 'string' ? result.display_name.split(',')[0] : 'Local'}</div>
            <div class="search-result-address">${result.display_name || 'Endereço não disponível'}</div>
        `;
        
        item.addEventListener('click', async () => {
            const lat = parseFloat(result.lat);
            const lng = parseFloat(result.lon);
            const addressText = result.display_name || 'Local selecionado';
            
            // Usar o mesmo método de marcação com confirmação que funciona no mapa
            await markLocationWithConfirmation(lat, lng, addressText);
            
            searchInput.value = result.display_name && typeof result.display_name === 'string' ? result.display_name.split(',')[0] : 'Local';
            hideSearchResults();
        });
        
        searchResults.appendChild(item);
    });
    
    searchResults.style.display = 'block';
}

function clearSearch() {
    searchInput.value = '';
    if (clearSearchBtn) {
        clearSearchBtn.style.display = 'none';
    }
    hideSearchResults();
    searchInput.focus();
}

function hideSearchResults() {
    if (searchResults) {
        searchResults.style.display = 'none';
        searchResults.innerHTML = '';
    }
}

function showSearchLoading() {
    if (searchResults) {
        searchResults.innerHTML = '<div class="search-result-item suggestion-loading"><i class="fas fa-spinner"></i> Pesquisando...</div>';
        searchResults.style.display = 'block';
    }
}

function showSearchLoadingScreen(query) {
    hideSearchResults();

    if (isValidCEP(query)) {
        const cep = extractCEP(query);
        const cepFmt = cep && cep.length === 8 ? `${cep.slice(0, 5)}-${cep.slice(5)}` : cep;
        showViabilityLoading(
            'Buscando CEP...',
            cepFmt ? `Consultando ${cepFmt} e localizando no mapa` : 'Consultando endereço e localizando no mapa',
            'cep'
        );
        return;
    }

    if (parseCoordinatesFromQuery(query)) {
        showViabilityLoading('Localizando coordenadas...', 'Posicionando no mapa', 'coords');
        return;
    }

    showViabilityLoading('Buscando endereço...', 'Geocodificando e localizando no mapa', 'address');
}

// Função para buscar sugestões de endereços enquanto o usuário digita
async function fetchAddressSuggestions(query) {
    if (!query || query.length < 3) {
        hideSearchResults();
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/geocode/suggestions?q=${encodeURIComponent(query)}`);
        
        if (!response.ok) {
            return; // Silenciosamente falha se não conseguir buscar sugestões
        }
        
        const data = await response.json();
        const suggestions = data.suggestions || [];
        
        if (suggestions.length > 0 && searchResults) {
            // Limpar resultados anteriores
            searchResults.innerHTML = '';
            
            // Criar itens de sugestão
            suggestions.forEach((suggestion, index) => {
                const item = document.createElement('div');
                item.className = 'search-result-item';
                
                // Extrair informações do endereço para exibir de forma mais limpa
                const displayName = suggestion.display_name || '';
                const addressParts = displayName.split(',');
                const primaryAddress = addressParts[0]?.trim() || displayName;
                const secondaryAddress = addressParts.slice(1, 3).join(',').trim() || '';
                
                item.innerHTML = `
                    <i class="fas fa-map-marker-alt"></i>
                    <div class="suggestion-text">
                        <div class="suggestion-name">${primaryAddress}</div>
                        ${secondaryAddress ? `<div class="suggestion-details">${secondaryAddress}</div>` : ''}
                    </div>
                `;
                
                // Adicionar evento de clique
                item.addEventListener('click', () => {
                    searchInput.value = displayName;
                    hideSearchResults();
                    // Executar a busca com o endereço selecionado
                    performSearch().catch(error => {
                        console.error('Erro na pesquisa:', error);
                        showNotification('Erro ao realizar pesquisa', 'error');
                    });
                });
                
                searchResults.appendChild(item);
            });
            
            searchResults.style.display = 'block';
        } else {
            hideSearchResults();
        }
    } catch (error) {
        // Silenciosamente falha se houver erro (não queremos mostrar erro para sugestões)
        console.debug('Erro ao buscar sugestões:', error);
        hideSearchResults();
    }
}

function hideSearchLoading() {
    // A função displaySearchResults ou hideSearchResults cuidará disso
}

// Funções para o loading screen da verificação de viabilidade (transições CSS)
const FTTH_LOADING_EXIT_MS = 460;
const FTTH_LOADING_ICONS = {
    cep: 'fa-map-pin',
    address: 'fa-search-location',
    coords: 'fa-crosshairs',
    viability: 'fa-network-wired',
    map: 'fa-map',
};

function formatMapDisplayName(filename) {
    if (!filename || typeof filename !== 'string') return 'mapa';
    return filename.replace(/\.[^.]+$/, '').replace(/_/g, ' ').trim() || 'mapa';
}

function showMapLoading(message = 'Carregando mapa', subtext = 'Processando coordenadas e desenhando na malha') {
    const loadingOverlay = document.getElementById('map-loading-overlay');
    const mapEl = document.getElementById('map');
    if (!loadingOverlay) return;

    setFtthLoadingMessage(loadingOverlay, message, subtext, 'map');

    loadingOverlay.classList.remove('is-closing');
    loadingOverlay.setAttribute('aria-hidden', 'false');
    loadingOverlay.setAttribute('aria-busy', 'true');
    mapEl?.classList.add('map-is-loading');

    requestAnimationFrame(() => {
        requestAnimationFrame(() => loadingOverlay.classList.add('is-open'));
    });
}

function hideMapLoading() {
    const loadingOverlay = document.getElementById('map-loading-overlay');
    const mapEl = document.getElementById('map');
    if (!loadingOverlay || !loadingOverlay.classList.contains('is-open')) {
        mapEl?.classList.remove('map-is-loading');
        return;
    }

    const finish = () => {
        loadingOverlay.classList.remove('is-closing', 'is-open');
        loadingOverlay.setAttribute('aria-hidden', 'true');
        loadingOverlay.setAttribute('aria-busy', 'false');
        mapEl?.classList.remove('map-is-loading');
    };

    loadingOverlay.classList.remove('is-open');
    loadingOverlay.classList.add('is-closing');

    const onEnd = (e) => {
        if (e.target !== loadingOverlay || e.propertyName !== 'opacity') return;
        loadingOverlay.removeEventListener('transitionend', onEnd);
        finish();
    };
    loadingOverlay.addEventListener('transitionend', onEnd);
    setTimeout(finish, FTTH_LOADING_EXIT_MS + 60);
}

function setFtthLoadingMessage(loadingOverlay, message, subtext, iconKey = 'viability') {
    const textEl = loadingOverlay.querySelector('.loading-text');
    const subtextEl = loadingOverlay.querySelector('.loading-subtext');
    const iconEl = loadingOverlay.querySelector('.loading-brand__icon');
    const content = loadingOverlay.querySelector('.loading-content');
    const iconClass = FTTH_LOADING_ICONS[iconKey] || FTTH_LOADING_ICONS.viability;

    if (textEl) {
        textEl.innerHTML =
            `${escapeHtml(message)}<span class="loading-dots" aria-hidden="true"><span></span><span></span><span></span></span>`;
    }
    if (subtextEl) {
        subtextEl.textContent = subtext;
        subtextEl.classList.remove('is-updating');
        void subtextEl.offsetWidth;
        subtextEl.classList.add('is-updating');
    }
    if (iconEl) {
        iconEl.className = `fas ${iconClass} loading-brand__icon`;
    }
    if (content) {
        content.classList.remove('is-message-updating');
        void content.offsetWidth;
        content.classList.add('is-message-updating');
    }
}

function showViabilityLoading(message = 'Verificando viabilidade...', subtext = 'Analisando CTOs próximos e calculando rotas', iconKey = 'viability') {
    const loadingOverlay = document.getElementById('loading-overlay');
    if (!loadingOverlay) return;

    setFtthLoadingMessage(loadingOverlay, message, subtext, iconKey);

    loadingOverlay.style.removeProperty('display');
    loadingOverlay.style.removeProperty('opacity');
    loadingOverlay.classList.remove('is-closing');
    loadingOverlay.setAttribute('aria-hidden', 'false');
    loadingOverlay.setAttribute('aria-busy', 'true');

    requestAnimationFrame(() => {
        requestAnimationFrame(() => loadingOverlay.classList.add('is-open'));
    });
}

function hideViabilityLoading() {
    const loadingOverlay = document.getElementById('loading-overlay');
    if (!loadingOverlay || !loadingOverlay.classList.contains('is-open')) return;

    const finish = () => {
        loadingOverlay.classList.remove('is-closing', 'is-open');
        loadingOverlay.setAttribute('aria-hidden', 'true');
        loadingOverlay.setAttribute('aria-busy', 'false');
    };

    loadingOverlay.classList.remove('is-open');
    loadingOverlay.classList.add('is-closing');

    const onEnd = (e) => {
        if (e.target !== loadingOverlay || e.propertyName !== 'opacity') return;
        loadingOverlay.removeEventListener('transitionend', onEnd);
        finish();
    };
    loadingOverlay.addEventListener('transitionend', onEnd);
    setTimeout(finish, FTTH_LOADING_EXIT_MS + 60);
}

/** Libera bloqueio do popup e fecha o marcador de busca (erro / cancelar). */
function fecharPopupErroViabilidade() {
    window.popupClosingLocked = false;

    if (window.searchMarker) {
        const marker = window.searchMarker;
        const popup = marker.getPopup && marker.getPopup();
        if (popup && popup.options) {
            popup.options.closeOnClick = true;
            popup.options.autoClose = true;
        }
        try {
            if (typeof marker.closePopup === 'function') {
                marker.closePopup();
            }
        } catch (err) {
            /* ignore */
        }
        try {
            if (typeof map !== 'undefined' && map.hasLayer(marker)) {
                map.removeLayer(marker);
            }
        } catch (err) {
            /* ignore */
        }
        window.searchMarker = null;
    }

    if (typeof map !== 'undefined') {
        try {
            map.closePopup();
        } catch (err) {
            /* ignore */
        }
    }

    hideViabilityLoading();
}

window.fecharPopupErroViabilidade = fecharPopupErroViabilidade;

/** Incrementa a cada nova busca/marcação — evita listeners de pesquisas anteriores. */
function beginViabilityPopupSession() {
    window._viabilityPopupSession = (window._viabilityPopupSession || 0) + 1;
    window.popupClosingLocked = false;
    if (window._popupConnectTimer) {
        clearTimeout(window._popupConnectTimer);
        window._popupConnectTimer = null;
    }
    return window._viabilityPopupSession;
}

/** Margem da área visível do mapa (top bar + bordas) para autopan do popup. */
const FTTH_MAP_VIEW_INSET = { top: 92, right: 24, bottom: 28, left: 24 };

function getSearchMarkerPopupOptions(extra = {}) {
    return {
        closeOnClick: false,
        autoClose: false,
        closeButton: true,
        autoPan: true,
        autoPanPaddingTopLeft: L.point(FTTH_MAP_VIEW_INSET.left, FTTH_MAP_VIEW_INSET.top),
        autoPanPaddingBottomRight: L.point(FTTH_MAP_VIEW_INSET.right, FTTH_MAP_VIEW_INSET.bottom),
        ...extra,
    };
}

function getFtthFitBoundsPadding(extraBottom = 100) {
    return {
        paddingTopLeft: L.point(FTTH_MAP_VIEW_INSET.left + 32, FTTH_MAP_VIEW_INSET.top + 32),
        paddingBottomRight: L.point(
            FTTH_MAP_VIEW_INSET.right + 32,
            FTTH_MAP_VIEW_INSET.bottom + extraBottom
        ),
    };
}

function afterMapAnimation(callback, timeoutMs = 480) {
    if (typeof map === 'undefined' || !callback) return;
    let settled = false;
    const finish = () => {
        if (settled) return;
        settled = true;
        map.off('moveend', finish);
        map.off('zoomend', finish);
        callback();
    };
    map.once('moveend', finish);
    map.once('zoomend', finish);
    setTimeout(finish, timeoutMs);
}

function ensureMarkerPopupVisible(marker) {
    if (!marker || typeof map === 'undefined') return;

    const run = () => {
        const popup = marker.getPopup && marker.getPopup();
        if (!popup) return;

        if (typeof popup._adjustPan === 'function') {
            popup._adjustPan();
        }

        const popupEl = popup.getElement && popup.getElement();
        const mapEl = map.getContainer && map.getContainer();
        if (!popupEl || !mapEl) return;

        const mapRect = mapEl.getBoundingClientRect();
        const popupRect = popupEl.getBoundingClientRect();
        let dx = 0;
        let dy = 0;

        if (popupRect.right > mapRect.right - FTTH_MAP_VIEW_INSET.right) {
            dx += popupRect.right - (mapRect.right - FTTH_MAP_VIEW_INSET.right);
        }
        if (popupRect.left < mapRect.left + FTTH_MAP_VIEW_INSET.left) {
            dx += popupRect.left - (mapRect.left + FTTH_MAP_VIEW_INSET.left);
        }
        if (popupRect.top < mapRect.top + FTTH_MAP_VIEW_INSET.top) {
            dy += popupRect.top - (mapRect.top + FTTH_MAP_VIEW_INSET.top);
        }
        if (popupRect.bottom > mapRect.bottom - FTTH_MAP_VIEW_INSET.bottom) {
            dy += popupRect.bottom - (mapRect.bottom - FTTH_MAP_VIEW_INSET.bottom);
        }

        if (dx || dy) {
            map.panBy(L.point(dx, dy), { animate: true, duration: 0.35 });
        }
    };

    requestAnimationFrame(() => requestAnimationFrame(run));
}

function nudgeMapForPopupAnchor(marker) {
    if (!marker || typeof map === 'undefined') return;
    const latlng = marker.getLatLng && marker.getLatLng();
    if (!latlng) return;

    const point = map.latLngToContainerPoint(latlng);
    const size = map.getSize();
    const targetX = size.x * 0.5;
    const targetY = size.y * 0.56;
    const dx = point.x - targetX;
    const dy = point.y - targetY;

    if (Math.abs(dx) > 10 || Math.abs(dy) > 10) {
        map.panBy(L.point(dx, dy), { animate: true, duration: 0.35 });
    }
}

function openSearchMarkerPopup(content) {
    if (!window.searchMarker || typeof window.searchMarker.setPopupContent !== 'function') return;

    window.searchMarker.setPopupContent(content);
    nudgeMapForPopupAnchor(window.searchMarker);
    if (typeof window.searchMarker.openPopup === 'function') {
        window.searchMarker.openPopup();
    }
    ensureMarkerPopupVisible(window.searchMarker);
    setTimeout(() => ensureMarkerPopupVisible(window.searchMarker), 120);
    setTimeout(() => ensureMarkerPopupVisible(window.searchMarker), 380);
}

function getViabilityPopupContentNode(marker) {
    if (!marker || typeof marker.getPopup !== 'function') return null;
    const root = marker.getPopup()?.getElement?.();
    if (!root) return null;
    return root.querySelector('.leaflet-popup-content') || root;
}

function isViabilityPopupActionTarget(target) {
    return !!(
        target &&
        target.closest &&
        (target.closest('.confirm-verify-btn') ||
            target.closest('.cancel-verify-btn') ||
            target.closest('.leaflet-popup-close-button') ||
            target.closest('.viability-close-btn'))
    );
}

/** Impede fechar o popup de confirmação enquanto a viabilidade roda. */
function lockViabilityPopupClosing() {
    const marker = window.searchMarker;
    if (!marker || typeof marker.getPopup !== 'function') return;

    try {
        const popup = marker.getPopup();
        if (popup && popup.options) {
            popup.options.closeOnClick = false;
            popup.options.autoClose = false;
        }

        if (typeof marker.closePopup === 'function' && !marker._viabilityCloseWrapped) {
            marker._viabilityCloseWrapped = true;
            const nativeMarkerClose = marker.closePopup;
            marker.closePopup = function () {
                if (window.popupClosingLocked) return this;
                return nativeMarkerClose.apply(this, arguments);
            };
        }

        if (typeof map !== 'undefined' && typeof map.closePopup === 'function' && !map._viabilityCloseWrapped) {
            map._viabilityCloseWrapped = true;
            const nativeMapClose = map.closePopup;
            map.closePopup = function () {
                if (
                    window.popupClosingLocked &&
                    window.searchMarker &&
                    typeof window.searchMarker.isPopupOpen === 'function' &&
                    window.searchMarker.isPopupOpen()
                ) {
                    return this;
                }
                return nativeMapClose.apply(this, arguments);
            };
        }
    } catch (err) {
        console.warn('Não foi possível bloquear fechamento do popup:', err);
    }
}

async function runViabilityConfirmation(lat, lng, addressText, fromClickMode) {
    window.popupClosingLocked = true;
    try {
        lockViabilityPopupClosing();
    } catch (err) {
        console.warn('Não foi possível bloquear fechamento do popup:', err);
    }

    if (fromClickMode && isClickMode) {
        window.shouldReturnToNavigationMode = true;
    }

    showViabilityLoading('Verificando viabilidade...', 'Buscando CTOs próximos e calculando rotas');

    if (window.searchMarker && typeof window.searchMarker.setPopupContent === 'function') {
        try {
            window.searchMarker.setPopupContent(
                '<div class="loading-popup"><i class="fas fa-spinner fa-spin"></i> Verificando viabilidade...</div>'
            );
        } catch (err) {
            console.warn('Não foi possível atualizar conteúdo do popup:', err);
        }
    }

    try {
        await verificarViabilidade(lat, lng, addressText);
        if (window.shouldReturnToNavigationMode && isClickMode) {
            setTimeout(() => {
                if (isClickMode) toggleCursorMode();
                window.shouldReturnToNavigationMode = false;
            }, 300);
        }
    } catch (error) {
        console.error('Erro na verificação de viabilidade:', error);
        showNotification('Erro ao verificar viabilidade', 'error');
        if (window.shouldReturnToNavigationMode && isClickMode) {
            setTimeout(() => {
                if (isClickMode) toggleCursorMode();
                window.shouldReturnToNavigationMode = false;
            }, 300);
        }
    } finally {
        setTimeout(() => {
            window.popupClosingLocked = false;
        }, 1000);
    }
}

function handleViabilityPopupCancel(fromClickMode) {
    fecharPopupErroViabilidade();
    if (fromClickMode && isClickMode) {
        setTimeout(() => {
            if (isClickMode) toggleCursorMode();
        }, 200);
    }
}

function attachPopupListeners(popupNode, lat, lng, addressText, fromClickMode = false) {
    if (!popupNode) return;

    const sessionId = window._viabilityPopupSession;
    popupNode.dataset.viabilityLat = String(lat);
    popupNode.dataset.viabilityLng = String(lng);
    popupNode.dataset.viabilityAddress = addressText || '';
    popupNode.dataset.viabilityFromClick = fromClickMode ? '1' : '0';
    popupNode.dataset.viabilitySession = String(sessionId);

    if (popupNode._viabilityClickHandler) {
        popupNode.removeEventListener('click', popupNode._viabilityClickHandler);
    }

    popupNode._viabilityClickHandler = async (e) => {
        if (String(window._viabilityPopupSession) !== popupNode.dataset.viabilitySession) return;

        const confirmBtn = e.target.closest('.confirm-verify-btn');
        const cancelBtn = e.target.closest('.cancel-verify-btn');
        if (!confirmBtn && !cancelBtn) return;

        e.preventDefault();
        e.stopPropagation();

        const pLat = parseFloat(popupNode.dataset.viabilityLat);
        const pLng = parseFloat(popupNode.dataset.viabilityLng);
        const pAddress = popupNode.dataset.viabilityAddress || '';
        const pFromClick = popupNode.dataset.viabilityFromClick === '1';

        if (cancelBtn) {
            handleViabilityPopupCancel(pFromClick);
            return;
        }

        try {
            await runViabilityConfirmation(pLat, pLng, pAddress, pFromClick);
        } catch (error) {
            console.error('Erro ao confirmar viabilidade:', error);
            window.popupClosingLocked = false;
            hideViabilityLoading();
            showNotification('Erro ao verificar viabilidade', 'error');
        }
    };

    popupNode.addEventListener('click', popupNode._viabilityClickHandler);
}

function schedulePopupButtonBind(marker, lat, lng, addressText, fromClickMode, sessionId) {
    const connect = () => {
        if (sessionId !== window._viabilityPopupSession) return;
        if (!marker || window.searchMarker !== marker) return;

        const popupNode = getViabilityPopupContentNode(marker);
        if (!popupNode) {
            window._popupConnectTimer = setTimeout(connect, 50);
            return;
        }

        attachPopupListeners(popupNode, lat, lng, addressText, fromClickMode);
    };

    window._popupConnectTimer = setTimeout(connect, 50);
}

function registerViabilityPopupGuards(marker) {
    if (!marker) return;

    marker.on('popupopen', () => {
        const popupElement = marker.getPopup()?.getElement?.();
        if (!popupElement) return;

        popupElement.addEventListener(
            'click',
            (e) => {
                if (isViabilityPopupActionTarget(e.target)) return;
                e.stopPropagation();
            },
            true
        );
    });

    marker.on('popupclose', (e) => {
        if (window.popupClosingLocked) {
            e.popup.openOn(marker);
            return false;
        }
    });
}

function registerMapPopupClickGuard() {
    if (map._viabilityMapClickGuardRegistered) return;
    map._viabilityMapClickGuardRegistered = true;

    map.on(
        'click',
        (e) => {
            if (!window.searchMarker || !window.searchMarker.isPopupOpen()) return;
            const popupElement = window.searchMarker.getPopup()?.getElement?.();
            const clickTarget = e.originalEvent?.target;
            if (popupElement && clickTarget && popupElement.contains(clickTarget)) {
                e.originalEvent?.stopPropagation();
                return false;
            }
        },
        true
    );
}

function showViabilityBusinessError(errorMessage, errorDetails, showUploadHint = false) {
    window.popupClosingLocked = false;
    showNotification(errorMessage, 'warning', 6000);

    if (window.searchMarker && typeof window.searchMarker.setPopupContent === 'function') {
        openSearchMarkerPopup(`
            <div class="viability-popup viability-error-popup">
                <div class="viability-popup-header">
                    <span class="viability-popup-header-icon viability-error-popup__icon" aria-hidden="true">
                        <i class="fas fa-exclamation-triangle"></i>
                    </span>
                    <h4 class="viability-popup-title">${escapeHtml(errorMessage)}</h4>
                </div>
                ${errorDetails ? `<p class="viability-popup-subtitle">${escapeHtml(errorDetails)}</p>` : ''}
                ${showUploadHint ? `
                    <div class="viability-error-popup__steps">
                        <strong>Como resolver:</strong>
                        <ol>
                            <li>Acesse o painel da empresa</li>
                            <li>Faça upload de mapas CTO (KML, KMZ, CSV, XLS, XLSX)</li>
                            <li>Ative o mapa na barra lateral e tente novamente</li>
                        </ol>
                    </div>
                ` : ''}
                <button type="button" class="viability-close-btn" data-ftth-action="close-viability-error">
                    <i class="fas fa-times" aria-hidden="true"></i>
                    <span>Fechar</span>
                </button>
            </div>
        `);
    }

    hideViabilityLoading();
}

// Função para verificar viabilidade
async function verificarViabilidade(lat, lon, endereco = '') {
    try {
        const mapCheckboxes = document.querySelectorAll('.cto-grid .cto-checkbox-input');
        if (mapCheckboxes.length === 0) {
            showViabilityBusinessError(
                'Nenhum mapa CTO cadastrado',
                'Faça upload de mapas no painel antes de verificar viabilidade.',
                true
            );
            return;
        }

        // Loading screen já deve estar visível (chamado antes), mas garantir que está
        showViabilityLoading('Verificando viabilidade...', 'Buscando CTOs próximos e calculando rotas');
        
        // Coletar IDs dos mapas ativos para incluir no cache
        const activeMapIds = [];
        activeMapLayers.forEach((entry, key) => {
            const mapId = entry?.meta?.mapId;
            if (mapId) {
                activeMapIds.push(mapId);
            }
        });
        
        // Criar hash dos mapas ativos (ordem importa, então ordenar)
        const mapIdsHash = activeMapIds.length > 0 
            ? activeMapIds.sort().join(',')
            : '';
        
        // Construir URL com parâmetros
        const params = new URLSearchParams({
            lat: lat.toString(),
            lon: lon.toString()
        });
        
        if (mapIdsHash) {
            params.append('map_ids', mapIdsHash);
        }

        if (window._viabilidadeForceRefresh) {
            params.append('refresh', '1');
            window._viabilidadeForceRefresh = false;
        }
        
        // Timeout para a verificação de viabilidade
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 segundos
        
        const response = await fetch(`${API_BASE}/verificar-viabilidade?${params.toString()}`, {
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        
        let data;
        try {
            data = await response.json();
        } catch (e) {
            // Se não conseguir parsear JSON, criar objeto de erro
            data = { erro: `Erro HTTP ${response.status}: ${response.statusText}` };
        }
        
        // Se a resposta não foi OK, tratar como erro
        if (!response.ok) {
            // Se já temos um objeto de erro do JSON, usar ele
            if (!data.erro) {
                data.erro = `Erro HTTP ${response.status}: ${response.statusText}`;
            }
            // Continuar para o tratamento de erro abaixo
        }

        if (data.erro) {
            const isExpectedBusinessError =
                response.status === 422 ||
                data.codigo === 'sem_cto' ||
                data.erro.includes('Nenhum CTO encontrado') ||
                data.erro.includes('Nenhum mapa');

            if (isExpectedBusinessError) {
                console.warn('Verificação indisponível:', data.erro);
            } else {
                console.error('Erro na verificação:', data.erro);
            }

            let errorMessage = data.erro;
            let errorDetails = '';
            let showUploadHint = false;

            if (data.erro.includes('Nenhum CTO encontrado') || data.erro.includes('Nenhum mapa')) {
                errorMessage = 'Nenhum mapa CTO carregado';
                errorDetails = 'Ative pelo menos um mapa na barra lateral ou faça upload de mapas CTO no painel.';
                showUploadHint = true;
            } else {
                errorDetails = data.erro;
            }

            showViabilityBusinessError(errorMessage, errorDetails, showUploadHint);
            return;
        }

        const ctoInfo = data.cto || {};
        currentCTODetails = {
            mapId: ctoInfo?.map_id ?? null,
            lat: ctoInfo?.lat ?? null,
            lon: ctoInfo?.lon ?? null,
            nome: ctoInfo?.nome ?? '',
            arquivo: ctoInfo?.arquivo ?? ''
        };
        window.currentCTO = currentCTODetails;

        // Notificar sucesso na verificação
        showNotification(`Viabilidade verificada: ${data.viabilidade.status}`, 'success');

        // Remover linha anterior se existir
        if (window.viabilityLine) {
            map.removeLayer(window.viabilityLine);
        }

        // Remover marcador do CTO anterior se existir
        if (window.ctoMarker) {
            map.removeLayer(window.ctoMarker);
        }

        // Remover camadas de CTOs existentes para destacar apenas o resultado atual
        clearAllMapLayers({ resetCheckboxes: true, suppressFit: true });

        // Não carregar todos os CTOs do arquivo durante a verificação.
        // Exibiremos apenas o CTO que atende (marcador destacado) e a rota.
        // Essa mudança evita poluir o mapa com pontos não relevantes.

        // Adicionar marcador destacado do CTO mais próximo
        const ctoIcon = L.divIcon({
            className: 'cto-marker',
            html: `
                <div class="cto-marker-icon">
                    <span class="cto-ring"></span>
                    <span class="cto-dot"></span>
                </div>
            `,
            iconSize: [28, 28],
            iconAnchor: [14, 14]
        });

        window.ctoMarker = L.marker([data.cto?.lat || 0, data.cto?.lon || 0], { 
            icon: ctoIcon 
        }).addTo(map);

        const ctoPopupContent = buildCtoResultPopup(data, IS_ADMIN && currentCTODetails?.mapId);
        window.ctoMarker.bindPopup(ctoPopupContent);

        if (IS_ADMIN && currentCTODetails?.mapId) {
            window.ctoMarker.on('popupopen', () => {
                const removeBtn = document.querySelector('.remove-cto-btn');
                if (removeBtn && !removeBtn.dataset.bound) {
                    removeBtn.dataset.bound = 'true';
                    removeBtn.addEventListener('click', (event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        removerCtoAtual();
                    });
                }
            });
        }

        // Desenhar linha seguindo a rota das ruas - Estilo Google Maps
        let routeCoordinates = [];
        
        if (data.rota?.geometria && Array.isArray(data.rota.geometria) && data.rota.geometria.length > 0) {
            // Converter coordenadas da rota de [lon, lat] para [lat, lon] para o Leaflet
            routeCoordinates = data.rota.geometria.map(coord => [coord[1], coord[0]]);
        } else {
            // Fallback para linha reta se não houver geometria da rota
            routeCoordinates = [
                [lat, lon],
                [data.cto?.lat || 0, data.cto?.lon || 0]
            ];
            console.log('⚠️ Usando linha reta - rota por ruas não disponível');
        }
        
        // Remover linha anterior se existir
        if (window.viabilityLine) {
            map.removeLayer(window.viabilityLine);
        }
        if (window.routeBorder) {
            map.removeLayer(window.routeBorder);
        }
        
        // Determinar cor da rota baseada na viabilidade
        const isViable = data.viabilidade.status === 'Viável';
        const routeColor = isViable ? '#1976D2' : '#D32F2F'; // Azul Google ou vermelho
        
        // Criar borda branca (efeito Google Maps)
        window.routeBorder = L.polyline(routeCoordinates, {
            color: '#FFFFFF',
            weight: 8,
            opacity: 0.9,
            smoothFactor: 3.0,
            lineCap: 'round',
            lineJoin: 'round'
        }).addTo(map);
        
        // Criar linha principal colorida
        window.viabilityLine = L.polyline(routeCoordinates, {
            color: routeColor,
            weight: 6,
            opacity: 1.0,
            smoothFactor: 3.0,
            lineCap: 'round',
            lineJoin: 'round'
        }).addTo(map);
        
        // Adicionar efeito de animação pulsante
        let pulseOpacity = 1.0;
        let increasing = false;
        
        const pulseAnimation = setInterval(() => {
            if (increasing) {
                pulseOpacity += 0.03;
                if (pulseOpacity >= 1.0) {
                    increasing = false;
                }
            } else {
                pulseOpacity -= 0.03;
                if (pulseOpacity <= 0.7) {
                    increasing = true;
                }
            }
            
            if (window.viabilityLine && map.hasLayer(window.viabilityLine)) {
                window.viabilityLine.setStyle({ opacity: pulseOpacity });
            } else {
                clearInterval(pulseAnimation);
            }
        }, 80);
        
        // Ajustar zoom para mostrar endereço, CTO e rota — antes de abrir o popup
        const group = new L.featureGroup([window.searchMarker, window.ctoMarker, window.viabilityLine]);
        const bounds = group.getBounds();
        const fitOpts = {
            maxZoom: 17,
            ...getFtthFitBoundsPadding(110),
        };

        afterMapAnimation(() => {
            openSearchMarkerPopup(buildViabilityResultPopup(data, endereco));
            hideViabilityLoading();
        });

        map.fitBounds(bounds.pad(0.28), fitOpts);
    } catch (error) {
        console.error('Erro ao verificar viabilidade:', error);
        window.popupClosingLocked = false;
        hideViabilityLoading(); // Esconder loading screen no erro
        
        let errorMessage = 'Erro ao verificar viabilidade';
        if (error.name === 'AbortError') {
            errorMessage = 'Verificação demorou mais que 60 segundos e foi cancelada. Tente novamente.';
            showNotification('Timeout na verificação - tente novamente', 'error');
        } else {
            showNotification('Erro de conexão na verificação', 'error');
        }
        
        if (window.searchMarker && typeof window.searchMarker.setPopupContent === 'function') {
            openSearchMarkerPopup(`
                <div class="viability-popup">
                    <p style="color: #e74c3c;">${errorMessage}</p>
                    <button type="button" class="cancel-verify-btn viability-close-btn" data-ftth-action="close-viability-error" style="margin-top: 10px; width: 100%; cursor: pointer;">Fechar</button>
                </div>
            `);
        }

        currentCTODetails = null;
        window.currentCTO = null;
    } finally {
        setTimeout(() => {
            window.popupClosingLocked = false;
        }, 300);
    }

}

async function removerCtoAtual(details = null) {
    if (!IS_ADMIN) {
        showNotification('Apenas administradores podem remover CTOs.', 'error');
        return;
    }

    const info = details || currentCTODetails;

    if (!info || !info.mapId) {
        showNotification('Nenhum CTO selecionado para remoção.', 'error');
        return;
    }

    try {
        const payload = {
            map_id: info.mapId,
            lat: info.lat,
            lon: info.lon,
            nome_cto: info.nome
        };

        const response = await fetch(`${API_BASE}/remover-cto`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.csrfToken || ''
            },
            body: JSON.stringify(payload)
        });

        let data = {};
        try {
            data = await response.json();
        } catch (_e) {
            // Ignora erro de parse, tratará abaixo
        }

        if (!response.ok || data?.erro) {
            const message = data?.erro || `HTTP ${response.status}: ${response.statusText}`;
            showNotification(`Erro ao remover CTO: ${message}`, 'error');
            return;
        }

        showNotification(
            (data?.mensagem || 'CTO removido com sucesso!') + ' Faça uma nova busca para atualizar a viabilidade.',
            'success'
        );
        window._viabilidadeForceRefresh = true;
        smartCache.clear('viability');
        await reloadActiveMapLayerAfterCtoChange(info.mapId);

        if (!details) {
            if (window.ctoMarker && map.hasLayer(window.ctoMarker)) {
                map.removeLayer(window.ctoMarker);
                window.ctoMarker = null;
            }
            if (window.routeBorder && map.hasLayer(window.routeBorder)) {
                map.removeLayer(window.routeBorder);
                window.routeBorder = null;
            }
            if (window.viabilityLine && map.hasLayer(window.viabilityLine)) {
                map.removeLayer(window.viabilityLine);
                window.viabilityLine = null;
            }
        } else if (details.marker) {
            try {
                const parentLayer = details.marker.__parentLayer;
                if (parentLayer && typeof parentLayer.removeLayer === 'function' && parentLayer.hasLayer && parentLayer.hasLayer(details.marker)) {
                    parentLayer.removeLayer(details.marker);
                } else if (map && typeof map.hasLayer === 'function' && map.hasLayer(details.marker)) {
                    map.removeLayer(details.marker);
                } else if (typeof details.marker.remove === 'function') {
                    details.marker.remove();
                }
            } catch (e) {
                console.warn('Não foi possível remover marcador do mapa:', e);
            }
        }

        if (window.searchMarker && typeof window.searchMarker.setPopupContent === 'function') {
            window.searchMarker.setPopupContent(`
                <div class="viability-popup">
                    <p>CTO removido com sucesso.</p>
                </div>
            `);
        }

        map.closePopup();

        if (!details || (currentCTODetails && currentCTODetails.mapId === info.mapId && currentCTODetails.lat === info.lat && currentCTODetails.lon === info.lon)) {
            currentCTODetails = null;
            window.currentCTO = null;
        }

        if (typeof loadCTOFiles === 'function') {
            try {
                await loadCTOFiles(true);
            } catch (error) {
                console.error('Erro ao atualizar lista de mapas após remover CTO:', error);
            }
        }
    } catch (error) {
        console.error('Erro ao remover CTO:', error);
        showNotification('Erro ao remover CTO', 'error');
    }
}

// Event listener global para botões CTO (usa event delegation)
function setupCTOButtonListeners() {
    const ctoGrid = document.querySelector('.cto-grid');
    if (!ctoGrid) return;
    
    ctoGrid.addEventListener('change', async (event) => {
        const checkbox = event.target.closest('.cto-checkbox-input');
        if (!checkbox) return;

        const card = checkbox.closest('.cto-card');
        const filename = checkbox.getAttribute('data-file') || '';
        const mapId = checkbox.getAttribute('data-map-id') || '';
        const mapKey = checkbox.getAttribute('data-map-key');

        if (!mapKey) {
            console.error('Chave do mapa não encontrada para o item selecionado.');
            return;
        }
        
        if (checkbox.checked) {
            card?.classList.add('loading');
            checkbox.disabled = true;

            // Fechar menu imediatamente e focar na loadscreen do mapa
            closeFtthSidebar();

            try {
                await loadKML(filename, mapId, { append: true });
                setCheckboxStateForKey(mapKey, true);
                lastLoadedLayerKey = mapKey;
            } catch (error) {
                // Tratar erros de forma mais específica
                const errorMessage = error.message || error.toString();
                const isNotFound = errorMessage.includes('não encontrado') || 
                                  errorMessage.includes('not found') || 
                                  error.status === 404;
                
                if (isNotFound) {
                    // Arquivo não encontrado - mostrar mensagem mais informativa
                    console.warn('⚠️ Mapa não encontrado:', filename || mapId);
                    console.info('💡 Envie o mapa novamente se o arquivo não estiver no servidor.');
                    
                    let notificationTitle = '⚠️ Mapa não encontrado';
                    let notificationMessage = `Mapa não encontrado: ${filename || mapId || 'arquivo'}`;
                    
                    if (error.solucao) {
                        let solucaoTexto = error.solucao;
                        if (solucaoTexto.length > 500) {
                            solucaoTexto = solucaoTexto.substring(0, 500) + '...';
                        }
                        notificationMessage += `\n\n${solucaoTexto}`;
                    } else {
                        notificationMessage += '\n\n💡 Faça upload do arquivo novamente pela interface web.';
                    }
                    
                    showNotification(notificationMessage, 'warning', 10000);
                } else {
                    // Outros erros - logar e mostrar mensagem de erro
                    console.error('Erro ao carregar mapa selecionado:', error);
                    
                    // Mostrar mensagem de erro mais detalhada se disponível
                    let notificationMessage = `Erro ao carregar mapa: ${filename}`;
                    if (error.solucao) {
                        notificationMessage += `\n\n${error.solucao}`;
                    } else if (errorMessage.length < 200) {
                        notificationMessage += `\n\n${errorMessage}`;
                    } else {
                        notificationMessage += `\n\n${errorMessage.substring(0, 200)}...`;
                    }
                    
                    showNotification(notificationMessage, 'error');
                }
                checkbox.checked = false;
                setCheckboxStateForKey(mapKey, false);
        } finally {
                checkbox.disabled = false;
                card?.classList.remove('loading');
            }
        } else {
            removeMapLayerByKey(mapKey, { updateCheckbox: false });
            card?.classList.remove('selected');
            lastLoadedLayerKey = activeMapLayers.size > 0 ? Array.from(activeMapLayers.keys()).pop() : null;
        }
    });
}

// Função legacy para compatibilidade (não faz nada, event delegation é usado)
function initializeCtoButtons() {
    // Função mantida para compatibilidade, mas não é mais necessária
    // porque usamos event delegation em setupCTOButtonListeners()
}

// Nova função: carregar KML/KMZ e exibir CTOs com lazy loading
async function loadKML(filename, mapId = null, options = {}) {
    const timer = performanceMonitor.startTimer('loadKML');
    console.log('📥 Carregando arquivo:', filename, mapId ? `(ID: ${mapId})` : '');
    if (!filename && !mapId) throw new Error('Nome de arquivo ou ID inválido');

    const mapLabel = formatMapDisplayName(filename);
    const showMapLoadUi = options.showMapLoading !== false;
    if (showMapLoadUi) {
        showMapLoading(
            `Carregando ${mapLabel}`,
            options.forceRefresh ? 'Atualizando coordenadas no servidor' : 'Processando coordenadas e desenhando na malha'
        );
    }

    // Verificar cache primeiro (usar ID ou filename como chave)
    const cacheKey = mapId ? `coords_id_${mapId}` : `coords_${filename}`;
    const cachedData = options.forceRefresh ? null : smartCache.get('coordinates', cacheKey);
    if (cachedData) {
        console.log('📦 Usando dados do cache para:', filename || mapId);
        performanceMonitor.recordCacheHit();
        performanceMonitor.endTimer(timer, 'loadKML-cached');
        try {
            return processKMLData(cachedData, filename, mapId, options);
        } finally {
            if (showMapLoadUi) hideMapLoading();
        }
    }

    performanceMonitor.recordCacheMiss();
    performanceMonitor.recordApiCall();

    // Declarar timeoutId fora do try para poder limpar no catch/finally
    let timeoutId = null;
    
    try {
        // Timeout controlado
        const controller = new AbortController();
        timeoutId = setTimeout(() => controller.abort(), 15000); // 15s

        // Construir URL com ID se disponível (prioridade) ou filename
        let url = `${API_BASE}/coordenadas?`;
        if (mapId) {
            url += `id=${encodeURIComponent(mapId)}`;
            if (filename) url += `&arquivo=${encodeURIComponent(filename)}`;
        } else {
            url += `arquivo=${encodeURIComponent(filename)}`;
        }
        if (options.forceRefresh) {
            url += '&refresh=true';
        }
        let data;
        const resp = await fetch(url, { signal: controller.signal });
        clearTimeout(timeoutId);
        
        // Verificar Content-Type primeiro
        const contentType = resp.headers.get('content-type') || '';
        const isJson = contentType.includes('application/json');
        
        // Verificar se a resposta foi bem-sucedida
        if (!resp.ok) {
            // Tentar obter mensagem de erro do JSON se possível
            let errorMessage = `Erro ${resp.status}: ${resp.statusText}`;
            let errorDetails = null;
            let errorSolucao = null;
            
            let errorData = null;
            if (isJson) {
                try {
                    errorData = await resp.json();
                    errorMessage = errorData.erro || errorData.message || errorMessage;
                    errorDetails = errorData.detalhes || null;
                    errorSolucao = errorData.solucao || null;
                    
                    // Se for "Arquivo não encontrado", criar mensagem mais informativa
                    if (errorMessage.includes('não encontrado') || errorMessage.includes('not found')) {
                        let fullMessage = errorMessage;
                        if (errorSolucao) {
                            fullMessage += `\n\n💡 Solução: ${errorSolucao}`;
                        }
                        if (errorDetails) {
                            fullMessage += `\n\nℹ️ Detalhes: ${errorDetails}`;
                        }
                        errorMessage = fullMessage;
                    }
                } catch (parseErr) {
                    // Se não conseguir fazer parse, usar mensagem padrão
                    console.warn('Não foi possível fazer parse da resposta de erro:', parseErr);
                }
            } else {
                // Se não for JSON, pode ser HTML (página de erro)
                try {
                    const text = await resp.text();
                    if (text.includes('<!doctype') || text.includes('<html')) {
                        errorMessage = `Erro do servidor (${resp.status}): O servidor retornou uma página de erro ao invés de dados JSON`;
                    }
                } catch (textErr) {
                    // Se não conseguir ler o texto, usar mensagem padrão
                    console.warn('Não foi possível ler a resposta de erro:', textErr);
                }
            }
            
            // Criar erro com informações adicionais
            const error = new Error(errorMessage);
            error.status = resp.status;
            error.details = errorDetails;
            error.solucao = errorSolucao;
            throw error;
        }
        
        // Verificar se a resposta é JSON
        if (!isJson) {
            const text = await resp.text();
            throw new Error(`Resposta não é JSON. Content-Type: ${contentType || 'não especificado'}`);
        }
        
        // Fazer parse do JSON
        data = await resp.json();
        
        // Verificar se há erro na resposta
        if (data && data.erro) {
            // Construir mensagem de erro mais informativa
            let errorMessage = data.erro;
            
            const isNotFound = data.erro.includes('não encontrado') || 
                              data.erro.includes('not found') || 
                              data.erro.includes('404');
            
            if (isNotFound) {
                console.warn('⚠️ Arquivo não encontrado:', filename || mapId, '-', data.erro);
                if (data.solucao) {
                    console.info('💡', data.solucao);
                }
            } else {
                // Outros erros - logar como erro crítico
                console.error('❌ Erro da API:', data.erro);
            }
            
            // Criar erro com todas as informações
            const error = new Error(errorMessage);
            error.status = 404; // Definir status para erro 404
            error.details = data.detalhes;
            error.solucao = data.solucao;
            throw error;
        }

        // Verificar se há dados válidos
        if (!Array.isArray(data) || data.length === 0) {
            console.warn('Nenhuma coordenada encontrada no arquivo:', filename);
            if (typeof showNotification === 'function') {
                showNotification(`Sem coordenadas em ${filename}`, 'error');
            }
            return;
        }

        // Salvar no cache apenas se for sucesso
        if (data && !data.erro) {
            smartCache.set('coordinates', cacheKey, data);
        }
        
        const duration = performanceMonitor.endTimer(timer, 'loadKML-api');
        console.log(`⚡ Arquivo carregado em ${duration.toFixed(2)}ms`);

        return processKMLData(data, filename, mapId, options);
    } catch (err) {
        // Limpar timeout se ainda estiver ativo
        if (timeoutId) {
            clearTimeout(timeoutId);
        }
        
        const isNotFound = err.status === 404 || 
                          (err.message && (err.message.includes('não encontrado') || 
                                          err.message.includes('not found') || 
                                          err.message.includes('404')));
        
        if (isNotFound) {
            console.warn('⚠️ Arquivo não encontrado:', filename || mapId, '-', err.message?.substring(0, 100) || 'Arquivo não disponível no servidor');
            if (err.solucao) {
                console.info('💡', err.solucao);
            }
        } else {
            // Outros erros - logar como erro crítico
            console.error('❌ Falha ao buscar coordenadas:', err);
        }
        
        // Não registrar como erro no monitor de performance se for 404 esperado
        if (!isNotFound) {
            performanceMonitor.recordError();
        }
        
        performanceMonitor.endTimer(timer, 'loadKML-error');
        throw err;
    } finally {
        if (showMapLoadUi) hideMapLoading();
    }
} // Fim da função loadKML

// Função separada para processar dados KML (reutilizável e otimizada)
function processKMLData(data, filename, mapId = null, options = {}) {
    const { append = false, skipFit = false } = options;

    if (!Array.isArray(data) || data.length === 0) {
        console.warn('Nenhuma coordenada encontrada no arquivo:', filename);
        if (typeof showNotification === 'function') {
            showNotification(`Sem coordenadas em ${filename}`, 'error');
        }
        return;
    }

    if (window.viabilityLine) {
        map.removeLayer(window.viabilityLine);
        window.viabilityLine = null;
    }
    if (window.routeBorder) {
        map.removeLayer(window.routeBorder);
        window.routeBorder = null;
    }
    if (window.ctoMarker) {
        map.removeLayer(window.ctoMarker);
        window.ctoMarker = null;
    }
    if (window.searchMarker) {
        map.removeLayer(window.searchMarker);
        window.searchMarker = null;
    }

    const layerKey = getLayerKey(filename, mapId);

    if (!append) {
        clearAllMapLayers({ resetCheckboxes: false, suppressFit: true });
    } else {
        removeMapLayerByKey(layerKey, { updateCheckbox: false, suppressFit: true });
    }

    const mapLayer = L.layerGroup();
    const mapBounds = L.latLngBounds();

    const blueIcon = L.divIcon({
        className: 'cto-marker-optimized',
        html: '<div style="background-color: #007bff; width: 8px; height: 8px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 5px rgba(0,123,255,0.8);"></div>',
        iconSize: [12, 12],
        iconAnchor: [6, 6]
    });

    const batchSize = 50;
    let processed = 0;
    
    function processBatch(startIndex) {
        const endIndex = Math.min(startIndex + batchSize, data.length);
        
        for (let i = startIndex; i < endIndex; i++) {
            const coord = data[i];
            try {
                if (coord.tipo === 'point' && (coord.lat !== undefined && coord.lng !== undefined)) {
                    let lat = typeof coord.lat === 'string' ? parseFloat(coord.lat.replace(',', '.')) : coord.lat;
                    let lng = typeof coord.lng === 'string' ? parseFloat(coord.lng.replace(',', '.')) : coord.lng;
                    
                    if (isNaN(lat) || isNaN(lng) || !isFinite(lat) || !isFinite(lng)) {
                        continue;
                    }
                    
                    if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
                        continue;
                    }

                    const markerMapId = coord.map_id || mapId || null;
                    const nomeOriginal = coord.nome || 'CTO';

                    mapBounds.extend([lat, lng]);

                    const marker = L.marker([lat, lng], { icon: blueIcon }).addTo(mapLayer);
                    marker.__layerKey = layerKey;
                    marker.__parentLayer = mapLayer;

                    const popupContent = buildCtoMarkerPopup({
                        nome: nomeOriginal,
                        arquivo: filename,
                        lat,
                        lng,
                        showRemoveBtn: !!(IS_ADMIN && markerMapId),
                    });

                    marker.bindPopup(popupContent);

                    marker.on('popupopen', (event) => {
                        const popupNode = event.popup.getElement();
                        if (!popupNode) return;

                        if (IS_ADMIN && markerMapId) {
                            const removeBtn = popupNode.querySelector('.remove-cto-btn');
                            if (removeBtn && !removeBtn.dataset.bound) {
                                removeBtn.dataset.bound = 'true';
                                removeBtn.addEventListener('click', (ev) => {
                                    ev.preventDefault();
                                    ev.stopPropagation();
                                    removerCtoAtual({
                                        mapId: markerMapId,
                                        lat,
                                        lon: lng,
                                        nome: nomeOriginal,
                                        marker
                                    });
                                });
                            }
                        }
                    });

                    processed++;
                }
            } catch (error) {
                if (error.message && !error.message.includes('Invalid LatLng')) {
                    console.warn(`Erro ao processar coordenada ${i}:`, error.message);
                }
            }
        }
        
        if (endIndex < data.length) {
            setTimeout(() => processBatch(endIndex), 5);
        } else {
            if (processed > 0) {
                mapLayer.addTo(map);
                activeMapLayers.set(layerKey, {
                    layer: mapLayer,
                    bounds: mapBounds.isValid() ? mapBounds : null,
                    meta: {
                        filename,
                        mapId,
                        count: processed
                    }
                });
                setCheckboxStateForKey(layerKey, true);
                lastLoadedLayerKey = layerKey;

                if (!skipFit) {
                    focusMapOnCurrentLayers();
            }
            
            console.log(`✅ ${processed} CTOs carregados do arquivo ${filename}`);
            
            if (typeof showNotification === 'function') {
                const base = filename.replace(/\.(kml|kmz|csv|xls|xlsx)$/i, '');
                showNotification(`${base} carregado! (${processed} pontos)`, 'success');
                }
            } else {
                console.warn(`Arquivo ${filename} não possui pontos válidos.`);
                removeMapLayerByKey(layerKey, { updateCheckbox: true, suppressFit: true });
                if (typeof showNotification === 'function') {
                    showNotification(`Mapa sem pontos válidos: ${filename}`, 'error');
                }
            }
        }
    }

    processBatch(0);
}

// Função para inicializar upload de arquivos (drag & drop + botão)
// COMENTADA - Elementos de upload não existem no HTML atual
/*
function initializeFileUpload() {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    const uploadBtn = document.getElementById('upload-btn');
    const progress = document.getElementById('upload-progress');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const uploadResults = document.getElementById('upload-results');

    if (!uploadArea || !fileInput || !uploadBtn) {
        console.warn('Área de upload não encontrada; inicialização ignorada.');
        return;
    }

    function resetProgress() {
        if (progress) progress.style.display = 'none';
        if (progressFill) progressFill.style.width = '0%';
        if (progressText) progressText.textContent = 'Enviando...';
    }

    function setProgress(percent, text) {
        if (progress && progressFill) {
            progress.style.display = 'block';
            progressFill.style.width = `${percent}%`;
        }
        if (progressText && text) progressText.textContent = text;
    }

    function showResult(message, type = 'success') {
        if (!uploadResults) return;
        const item = document.createElement('div');
        item.className = `upload-result ${type}`;
        item.textContent = message;
        uploadResults.prepend(item);
    }

    function uploadFile(file) {
        return new Promise((resolve, reject) => {
            const name = file?.name || 'arquivo';
            const ext = name.toLowerCase().split('.').pop();
            if (!['kml', 'kmz'].includes(ext)) {
                showResult(`Formato inválido: ${name}. Use .kml ou .kmz`, 'error');
                if (typeof showNotification === 'function') {
                    showNotification(`Formato inválido: ${name}`, 'error');
                }
                return reject(new Error('Formato inválido'));
            }

            const formData = new FormData();
            formData.append('file', file);

            setProgress(5, 'Preparando envio...');

            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/upload');

            xhr.upload.onprogress = function (e) {
                if (e.lengthComputable) {
                    const percent = Math.min(95, Math.round((e.loaded / e.total) * 95));
                    setProgress(percent, `Enviando (${percent}%)...`);
                } else {
                    setProgress(50, 'Enviando...');
                }
            };

            xhr.onreadystatechange = function () {
                if (xhr.readyState === 4) {
                    try {
                        const resp = JSON.parse(xhr.responseText || '{}');
                        if (xhr.status >= 200 && xhr.status < 300 && resp && resp.sucesso) {
                            setProgress(100, 'Concluído');
                            showResult(`✅ ${name} enviado (${resp.coordenadas_encontradas} coordenadas)`, 'success');
                            if (typeof showNotification === 'function') {
                                showNotification(`Arquivo ${name} enviado com sucesso!`, 'success');
                            }
                            resolve(resp);
                        } else {
                            const msg = (resp && resp.erro) ? resp.erro : `Falha ao enviar ${name}`;
                            showResult(`❌ ${msg}`, 'error');
                            if (typeof showNotification === 'function') {
                                showNotification(msg, 'error');
                            }
                            reject(new Error(msg));
                        }
                    } catch (err) {
                        showResult(`❌ Erro ao processar resposta para ${name}`, 'error');
                        reject(err);
                    } finally {
                        setTimeout(() => resetProgress(), 1200);
                    }
                }
            };

            xhr.onerror = function () {
                showResult(`❌ Erro de rede ao enviar ${name}`, 'error');
                if (typeof showNotification === 'function') {
                    showNotification(`Erro de rede ao enviar ${name}`, 'error');
                }
                reject(new Error('Network error'));
                setTimeout(() => resetProgress(), 1200);
            };

            xhr.send(formData);
        });
    }

    function handleFiles(files) {
        if (!files || files.length === 0) return;
        const list = Array.from(files);
        (async () => {
            for (const file of list) {
                try {
                    await uploadFile(file);
                } catch (err) {
                    console.error('Erro no upload:', err);
                }
            }
        })();
    }

    // Interações drag & drop
    ['dragenter', 'dragover'].forEach(evt => {
        uploadArea.addEventListener(evt, e => {
            e.preventDefault();
            e.stopPropagation();
            uploadArea.classList.add('dragover');
        });
    });
    ['dragleave', 'drop'].forEach(evt => {
        uploadArea.addEventListener(evt, e => {
            e.preventDefault();
            e.stopPropagation();
            uploadArea.classList.remove('dragover');
        });
    });
    uploadArea.addEventListener('drop', e => {
        handleFiles(e.dataTransfer.files);
    });

    // Clique para selecionar arquivos
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => handleFiles(fileInput.files));
}
*/

// Inicializar upload de arquivos
// initializeFileUpload(); // Movido para DOMContentLoaded
 
 // Inicializar botões dos CTOs
// initializeCtoButtons(); // Movido para DOMContentLoaded
 
 // Inicializar dashboard e carregar arquivos
 cleanExpiredCache();
 // loadKmlFiles(); // Comentado - não precisamos mais da lista dinâmica
 
 // Atualizar dashboard periodicamente (a cada 5 minutos)
 setInterval(() => {
     cleanExpiredCache();
 }, 5 * 60 * 1000);
 

 
// Inicializar barra de pesquisa principal
// initializeMainSearch(); // Removido - será chamado no DOMContentLoaded

// Inicializar menu hambúrguer e sidebar
// initializeMenuToggle(); // Movido para DOMContentLoaded

// Inicializar botão de alternância do cursor
// initializeCursorToggle(); // Movido para DOMContentLoaded

// ===== FUNCIONALIDADES MELHORADAS DA BARRA DE PESQUISA =====
 
 // Variáveis globais para a barra de pesquisa melhorada
 let searchHistory = [];
 let currentSuggestions = [];
 let selectedSuggestionIndex = -1;
 
 // Inicializar funcionalidades melhoradas da barra de pesquisa
function initializeEnhancedSearchBar() {
    // Carregar histórico do localStorage
    loadSearchHistory();

    const historyBtn = document.getElementById('history-btn');
    if (historyBtn && typeof SearchHistorySafe !== 'undefined' && SearchHistorySafe.isEnabled()) {
        historyBtn.hidden = false;
    }
     
     // Inicializar eventos
     initializeSearchEvents();
     initializeFilterEvents();
     initializeHistoryEvents();
     initializeKeyboardShortcuts();
     
     console.log('✅ Barra de pesquisa melhorada inicializada!');
 }
 
 function loadSearchHistory() {
     if (typeof SearchHistorySafe !== 'undefined' && SearchHistorySafe.isEnabled()) {
         try { sessionStorage.removeItem('search_history'); } catch (_) {}
         const items = SearchHistorySafe.load();
         searchHistory = SearchHistorySafe.toDisplayList(items).map((it) => ({
             query: it.query,
             timestamp: Date.now(),
             type: detectSearchType(it.query),
         }));
         return;
     }
     searchHistory = [];
 }

 function saveSearchHistory() {
     /* persistência feita em addToSearchHistory via SearchHistorySafe */
 }

 function addToSearchHistory(query) {
     if (!query || query.trim().length < 2) return;
     const cleanQuery = query.trim();
     if (typeof SearchHistorySafe !== 'undefined' && SearchHistorySafe.isEnabled()) {
         const items = SearchHistorySafe.add(cleanQuery);
         searchHistory = SearchHistorySafe.toDisplayList(items).map((it) => ({
             query: it.query,
             timestamp: Date.now(),
             type: detectSearchType(it.query),
         }));
         return;
     }
 }
 
 // Detectar tipo de pesquisa
 function detectSearchType(query) {
     const numberPattern = /^\d+$/;
     
     if (isValidCEP(query)) return 'cep';
     if (numberPattern.test(query)) return 'number';
     if (query.includes(',') || query.includes('-')) return 'address';
     return 'city';
 }
 
 // Inicializar eventos da pesquisa
 function initializeSearchEvents() {
     console.log('🔧 Inicializando eventos de pesquisa...');
     
     // Aguardar o DOM estar completamente carregado
     if (document.readyState === 'loading') {
         document.addEventListener('DOMContentLoaded', initializeSearchEvents);
         return;
     }
     
     const searchInput = document.getElementById('search-input');
    const clearBtn = document.querySelector('.clear-search-btn');
    
    if (!searchInput) {
        console.error('❌ Campo de pesquisa não encontrado!');
        return;
    }
     
     // Remover event listeners existentes para evitar duplicação
     const newSearchInput = searchInput.cloneNode(true);
     searchInput.parentNode.replaceChild(newSearchInput, searchInput);
     
     // Referenciar o novo elemento
     const freshSearchInput = document.getElementById('search-input');
     
     // Evento de input apenas para mostrar/ocultar botão de limpar
    freshSearchInput.addEventListener('input', function(e) {
        const query = e.target.value;
        console.log('⌨️ Input event disparado com query:', query);
        
        // Mostrar sugestões (inclui detecção de CEP)
        showSuggestions(query);
        
        // Limpar timeout anterior se existir
        if (searchTimeout) {
            clearTimeout(searchTimeout);
        }
        
        // Se a query estiver vazia, limpar resultados
        if (!query || query.trim().length === 0) {
            hideAllDropdowns();
            // Limpar resultados de pesquisa se existirem
            const resultsContainer = document.getElementById('search-results');
            if (resultsContainer) {
                resultsContainer.innerHTML = '';
                resultsContainer.style.display = 'none';
            }
            return;
        }
        
        // Não executar busca automática - aguardar Enter ou clique na lupa
    });
     
     // Event listener para focus (sem sugestões ou histórico)
     freshSearchInput.addEventListener('focus', function() {
     });
     
     // Event listener para blur
     freshSearchInput.addEventListener('blur', function() {
         // Delay para permitir cliques em sugestões
         setTimeout(() => {
             hideSuggestions();
         }, 200);
     });
     
     // Event listener para Enter no campo (usa keydown para maior compatibilidade)
    freshSearchInput.addEventListener('keydown', function(e) {
         if (e.key === 'Enter') {
             console.log('⌨️ Enter pressionado!');
             e.preventDefault();
             
             // Se o dropdown de sugestões está visível, deixa o handler global decidir
             const suggestionsDropdown = document.querySelector('.search-suggestions-dropdown');
             if (suggestionsDropdown && suggestionsDropdown.style.display !== 'none') {
                 return;
             }
             
             // Cancelar qualquer timeout pendente para pesquisa imediata
             if (searchTimeout) {
                 clearTimeout(searchTimeout);
                 searchTimeout = null;
             }
             
             const query = this.value.trim();
            if (query) {
                addToSearchHistory(query);
                performSearch(query).catch(error => {
                    console.error('Erro na pesquisa:', error);
                    showNotification('Erro ao realizar pesquisa', 'error');
                });
                hideAllDropdowns();
            }
         }
     });
     
     // Event listener para botão de limpar
     if (clearBtn) {
         clearBtn.addEventListener('click', function() {
             freshSearchInput.value = '';
             freshSearchInput.focus();
             hideAllDropdowns();
             // Limpar resultados de pesquisa
             const resultsContainer = document.getElementById('search-results');
             if (resultsContainer) {
                 resultsContainer.innerHTML = '';
                 resultsContainer.style.display = 'none';
             }
         });
     }
     
     // Reconectar botão da lupa após clonagem do input
     const searchBtn = document.getElementById('search-btn');
     if (searchBtn) {
         // Remover listeners antigos
         const newSearchBtn = searchBtn.cloneNode(true);
         searchBtn.parentNode.replaceChild(newSearchBtn, searchBtn);
         
         // Adicionar novo listener
        newSearchBtn.addEventListener('click', function() {
            const query = freshSearchInput.value.trim();
            if (query) {
                addToSearchHistory(query);
                performSearch(query).catch(error => {
                    console.error('Erro na pesquisa:', error);
                    showNotification('Erro ao realizar pesquisa', 'error');
                });
                hideAllDropdowns();
            }
        });
     }
 }
 
 // Inicializar eventos dos filtros
 function initializeFilterEvents() {
     const filterBtn = document.querySelector('.filter-btn');
     const filterDropdown = document.querySelector('.filter-dropdown');
     
     if (filterBtn && filterDropdown) {
         filterBtn.addEventListener('click', function(e) {
             e.stopPropagation();
             toggleDropdown(filterDropdown, filterBtn);
         });
         
         // Event listeners para opções de filtro
         const filterOptions = filterDropdown.querySelectorAll('.filter-option');
         filterOptions.forEach(option => {
             option.addEventListener('click', function() {
                 // Implementar lógica de filtro aqui
                 console.log('Filtro selecionado:', this.textContent);
                 hideAllDropdowns();
             });
         });
     }
 }
 
 // Inicializar eventos de histórico
 function initializeHistoryEvents() {
     const historyBtn = document.querySelector('.history-btn');
     const historyDropdown = document.querySelector('.history-dropdown');
     
     if (historyBtn && historyDropdown) {
         historyBtn.addEventListener('click', function(e) {
             e.stopPropagation();
             showSearchHistory();
         });
     }
 }
 
 // Inicializar atalhos de teclado
 function initializeKeyboardShortcuts() {
     document.addEventListener('keydown', function(e) {
         const searchInput = document.getElementById('search-input');
         const suggestionsDropdown = document.querySelector('.search-suggestions-dropdown');
         
         // Ctrl/Cmd + K para focar na pesquisa
         if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
             e.preventDefault();
             if (searchInput) {
                 searchInput.focus();
                 searchInput.select();
             }
         }
         
         // Escape para fechar dropdowns
         if (e.key === 'Escape') {
             hideAllDropdowns();
             if (searchInput) {
                 searchInput.blur();
             }
         }
         
         // Navegação por setas nas sugestões
         if (suggestionsDropdown && suggestionsDropdown.style.display !== 'none') {
             if (e.key === 'ArrowDown') {
                 e.preventDefault();
                 navigateSuggestions(1);
             } else if (e.key === 'ArrowUp') {
                 e.preventDefault();
                 navigateSuggestions(-1);
             } else if (e.key === 'Enter') {
                 e.preventDefault();
                 if (selectedSuggestionIndex >= 0) {
                     selectSuggestion(selectedSuggestionIndex);
                 } else {
                     // Se não há sugestão selecionada, executar pesquisa imediata
                     if (searchTimeout) {
                         clearTimeout(searchTimeout);
                         searchTimeout = null;
                     }
                     
                     const query = document.getElementById('search-input').value.trim();
                    if (query) {
                        addToSearchHistory(query);
                        performSearch(query).catch(error => {
                            console.error('Erro na pesquisa:', error);
                            showNotification('Erro ao realizar pesquisa', 'error');
                        });
                        hideAllDropdowns();
                    }
                 }
             }
         }
     });
 }
 
 // Função para mostrar sugestões
function showSuggestions(query) {
    if (!query || query.trim().length < 2) {
        hideSuggestions();
        return;
    }
    
    const suggestions = generateSuggestions(query);
    const dropdown = document.querySelector('.search-suggestions-dropdown');
    
    if (!dropdown || suggestions.length === 0) {
        hideSuggestions();
        return;
    }
    
    dropdown.innerHTML = suggestions.map((suggestion, index) => `
        <div class="suggestion-item" data-index="${index}" role="button" tabindex="0">
            <i class="suggestion-icon ${getSuggestionIcon(suggestion.type)}"></i>
            <span class="suggestion-text">${suggestion.text}</span>
            <span class="suggestion-type">${suggestion.type}</span>
        </div>
    `).join('');
    
    currentSuggestions = suggestions;
    selectedSuggestionIndex = -1;
    
    console.log('📋 Dropdown innerHTML após inserção:', dropdown.innerHTML);
    console.log('📋 Chamando showDropdown...');
    showDropdown(dropdown);
    console.log('📋 Dropdown style display após showDropdown:', dropdown.style.display);
}
 
 // Função para gerar sugestões
 function generateSuggestions(query) {
     const suggestions = [];
     const lowerQuery = query.toLowerCase();
     
     // Sugestões baseadas no histórico
     const historyMatches = searchHistory
         .filter(item => item.query.toLowerCase().includes(lowerQuery))
         .slice(0, 3)
         .map(item => ({
             text: item.query,
             type: item.type,
             source: 'history'
         }));
     
     suggestions.push(...historyMatches);
     
     // Sugestões automáticas baseadas no tipo
     if (/^\d/.test(query)) {
         if (query.length <= 8) {
             suggestions.push({
                 text: query + ' (CEP)',
                 type: 'cep',
                 source: 'auto'
             });
         }
     } else {
         suggestions.push({
             text: query,
             type: 'address',
             source: 'auto'
         });
     }
     
     return suggestions.slice(0, 5);
 }
 
 // Função para obter ícone da sugestão
 function getSuggestionIcon(type) {
     switch (type) {
         case 'cep': return 'fas fa-map-pin';
         case 'address': return 'fas fa-map-marker-alt';
         case 'number': return 'fas fa-hashtag';
         default: return 'fas fa-search';
     }
 }
 
 // Função para navegar pelas sugestões
 function navigateSuggestions(direction) {
     const suggestions = document.querySelectorAll('.suggestion-item');
     if (suggestions.length === 0) return;
     
     // Remove seleção anterior
     suggestions.forEach(item => item.classList.remove('selected'));
     
     // Calcula novo índice
     selectedSuggestionIndex += direction;
     
     if (selectedSuggestionIndex < 0) {
         selectedSuggestionIndex = suggestions.length - 1;
     } else if (selectedSuggestionIndex >= suggestions.length) {
         selectedSuggestionIndex = 0;
     }
     
     // Adiciona nova seleção
     suggestions[selectedSuggestionIndex].classList.add('selected');
 }
 
 // Função para selecionar sugestão
window.selectSuggestion = function(index) {
    if (index < 0 || index >= currentSuggestions.length) {
        return;
    }
    
    const suggestion = currentSuggestions[index];
    const searchInput = document.getElementById('search-input');
    
    if (searchInput) {
        const cleanText = suggestion.text.replace(' (CEP)', '');
        searchInput.value = cleanText;
        addToSearchHistory(cleanText);
        performSearch(cleanText).catch(error => {
            console.error('Erro na pesquisa:', error);
            showNotification('Erro ao realizar pesquisa', 'error');
        });
        hideAllDropdowns();
        searchInput.focus();
    }
}
 
 // Função para mostrar histórico de pesquisa
 function showSearchHistory() {
     const dropdown = document.querySelector('.history-dropdown');
     if (!dropdown) return;
     
     if (searchHistory.length === 0) {
         dropdown.innerHTML = '<div class="history-empty">Nenhum histórico de pesquisa</div>';
     } else {
         dropdown.innerHTML = `
             <div class="history-header">
                 <span>Pesquisas recentes</span>
                 <button type="button" class="clear-history-btn" data-ftth-action="clear-history">
                     <i class="fas fa-trash"></i>
                 </button>
             </div>
             ${searchHistory.slice(0, 10).map((item, index) => `
                 <div class="history-item" data-index="${index}" role="button" tabindex="0">
                     <i class="history-icon ${getSuggestionIcon(item.type)}"></i>
                     <span class="history-text">${item.query}</span>
                     <span class="history-time">${new Date(item.timestamp).toLocaleDateString()}</span>
                 </div>
             `).join('')}
         `;
         
         // Atualizar currentSuggestions para permitir seleção
         currentSuggestions = searchHistory.slice(0, 10).map(item => ({
             text: item.query,
             type: item.type,
             source: 'history'
         }));
     }
     
     showDropdown(dropdown);
 }
 
 // Função para limpar histórico
 function clearSearchHistory() {
     searchHistory = [];
     saveSearchHistory();
     showSearchHistory();
     showNotification('Histórico de pesquisa limpo', 'success');
 }
 
 // Função para mostrar dropdown
function showDropdown(dropdown) {
    hideAllDropdowns();
    dropdown.style.display = 'block';
}
 
 // Função para esconder sugestões
 function hideSuggestions() {
     const dropdown = document.querySelector('.search-suggestions-dropdown');
     if (dropdown) {
         dropdown.style.display = 'none';
     }
 }
 
 // Função para alternar dropdown
 function toggleDropdown(dropdown, button) {
     if (dropdown.style.display === 'block') {
         dropdown.style.display = 'none';
         button.classList.remove('active');
     } else {
         hideAllDropdowns();
         dropdown.style.display = 'block';
         button.classList.add('active');
     }
 }
 
 // Função para esconder todos os dropdowns
 function hideAllDropdowns() {
     const dropdowns = document.querySelectorAll('.search-suggestions-dropdown, .filter-dropdown, .history-dropdown');
     const buttons = document.querySelectorAll('.filter-btn, .history-btn');
     
     dropdowns.forEach(dropdown => {
         dropdown.style.display = 'none';
     });
     
     buttons.forEach(button => {
         button.classList.remove('active');
     });
     
     selectedSuggestionIndex = -1;
     
     // Limpar seleções
     const selectedItems = document.querySelectorAll('.suggestion-item.selected, .history-item.selected');
     selectedItems.forEach(item => {
         item.classList.remove('selected');
     });
 }
 
 // Event listener global para fechar dropdowns
 document.addEventListener('click', function(e) {
     const searchContainer = e.target.closest('.search-container');
     if (!searchContainer) {
         hideAllDropdowns();
     }
 });
 
 // Inicializar funcionalidades melhoradas da barra de pesquisa
 initializeEnhancedSearchBar();





// Fecha sidebar + overlay (qualquer viewport) — usado ao selecionar mapa, etc.
function closeFtthSidebar() {
    const sidebar = document.getElementById('sidebar');
    const menuToggle = document.getElementById('menu-toggle');
    const overlay = document.getElementById('overlay');

    sidebar?.classList.remove('active');
    menuToggle?.classList.remove('active');
    overlay?.classList.remove('active');
    document.body.classList.remove('no-scroll');

    requestAnimationFrame(() => {
        if (window.map && typeof window.map.invalidateSize === 'function') {
            window.map.invalidateSize({ animate: false });
        }
    });
}

// Inicializa o menu hambúrguer e controla a sidebar
function initializeMenuToggle() {
    console.log('🍔 Inicializando menu...');
    const sidebar = document.getElementById('sidebar');
    const menuToggle = document.getElementById('menu-toggle');
    const closeMenu = document.getElementById('close-menu');
    const overlay = document.getElementById('overlay');

    if (!sidebar || !menuToggle) {
        console.error('❌ Elementos de menu não encontrados.');
        return;
    }

    function openSidebar() {
        sidebar.classList.add('active');
        menuToggle.classList.add('active');
        if (overlay) overlay.classList.add('active');
        document.body.classList.add('no-scroll');
        if (typeof hideAllDropdowns === 'function') hideAllDropdowns();
    }

    function closeSidebar() {
        closeFtthSidebar();
    }

    // Abrir/fechar ao clicar no botão hambúrguer
    menuToggle.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (sidebar.classList.contains('active')) {
            closeSidebar();
        } else {
            openSidebar();
        }
    });

    // Fechar ao clicar no botão de fechar dentro da sidebar
    if (closeMenu) {
        closeMenu.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            closeSidebar();
        });
    }

    // Fechar ao clicar no overlay
    if (overlay) {
        overlay.addEventListener('click', (e) => {
            e.preventDefault();
            closeSidebar();
        });
    }

    // Fechar ao clicar fora da sidebar
    document.addEventListener('click', (e) => {
        const clickedInsideSidebar = e.target.closest('#sidebar');
        const clickedMenuToggle = e.target.closest('#menu-toggle');
        if (!clickedInsideSidebar && !clickedMenuToggle && sidebar.classList.contains('active')) {
            closeSidebar();
        }
    });

    // Fechar com ESC
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeSidebar();
        }
    });
}

// Função para inicializar o botão de alternância do cursor
function initializeCursorToggle() {
    console.log('🔄 Inicializando alternância do cursor...');
    
    // Aguardar o DOM estar completamente carregado
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeCursorToggle);
        return;
    }
    
    const cursorToggleBtn = document.getElementById('cursor-toggle-btn');
    const map = window.map;
    
    if (!cursorToggleBtn) {
        console.error('❌ Botão de alternância do cursor não encontrado!');
        return;
    }
    
    if (!map) {
        console.error('❌ Mapa não encontrado!');
        return;
    }
    
    // Verificar se o evento já foi adicionado
    if (cursorToggleBtn.hasAttribute('data-initialized')) {
        console.log('⚠️ Botão já inicializado, pulando...');
        return;
    }
    
    // Adicionar evento de clique no botão
    cursorToggleBtn.addEventListener('click', function() {
        console.log('🔄 Alternando modo do cursor...');
        toggleCursorMode();
    });
    
    // Marcar como inicializado
    cursorToggleBtn.setAttribute('data-initialized', 'true');
    
    console.log('✅ Alternância do cursor inicializada com sucesso!');
}

// Função para alternar entre modo navegação e modo clique
function toggleCursorMode() {
    const cursorToggleBtn = document.getElementById('cursor-toggle-btn');
    const iconElement = cursorToggleBtn.querySelector('i');
    const textElement = cursorToggleBtn.querySelector('.cursor-mode-text');
    
    isClickMode = !isClickMode;
    
    if (isClickMode) {
        // Ativar modo clique
        console.log('✅ Modo clique ativado');
        cursorToggleBtn.classList.add('click-mode');
        iconElement.className = 'fas fa-crosshairs';
        textElement.textContent = 'Marcar';
        cursorToggleBtn.title = 'Modo marcação ativo - Clique no mapa para marcar';
        
        // Alterar cursor do mapa
        document.getElementById('map').style.cursor = 'crosshair';
        
        // Desabilitar arrastar e zoom do mapa
        map.dragging.disable();
        map.scrollWheelZoom.disable();
        map.doubleClickZoom.disable();
        map.touchZoom.disable();
        map.boxZoom.disable();
        map.keyboard.disable();
        
        // Adicionar evento de clique no mapa
        // Prevenir que cliques dentro do popup fechem o popup
        map.on('click', function(e) {
            // Se houver popup aberto, verificar se o clique foi dentro dele
            if (window.searchMarker && window.searchMarker.isPopupOpen()) {
                const popupElement = window.searchMarker.getPopup().getElement();
                if (popupElement) {
                    const clickTarget = e.originalEvent?.target;
                    if (clickTarget && popupElement.contains(clickTarget)) {
                        // Clique foi dentro do popup, não processar
                        return;
                    }
                }
            }
            // Se não foi dentro do popup, processar normalmente
            onMapClick(e);
        });
        
        showNotification('Modo marcação ativado', 'info');
    } else {
        // Ativar modo navegação
        console.log('🧭 Modo navegação ativado');
        cursorToggleBtn.classList.remove('click-mode');
        iconElement.className = 'fas fa-hand-pointer';
        textElement.textContent = 'Navegar';
        cursorToggleBtn.title = 'Alternar para modo de marcação';
        
        // Restaurar cursor do mapa
        document.getElementById('map').style.cursor = '';
        
        // Reabilitar arrastar e zoom do mapa - GARANTIR TUDO ESTÁ HABILITADO NO MOBILE
        map.dragging.enable();
        map.scrollWheelZoom.enable();
        map.doubleClickZoom.enable();
        map.touchZoom.enable(); // CRÍTICO: Zoom por pinch no mobile
        map.boxZoom.enable();
        map.keyboard.enable();
        
        // No mobile, garantir que todos os gestos estejam habilitados
        if (isMobile) {
            // Forçar habilitar todos os handlers críticos para mobile
            map.touchZoom.enable();
            map.doubleClickZoom.enable();
            map.dragging.enable();
            
            // Garantir que o elemento do mapa permita gestos
            const mapElement = document.getElementById('map');
            if (mapElement) {
                mapElement.style.touchAction = 'pan-x pan-y pinch-zoom double-tap-zoom';
            }
        }
        
        // Remover evento de clique no mapa
        map.off('click', onMapClick);
        
        // Remover notificação desnecessária
    }
}

// Debounce para evitar múltiplos cliques
let lastClickTime = 0;
const CLICK_DEBOUNCE_MS = 500; // 500ms entre cliques

// Função para lidar com cliques no mapa quando em modo marcação
async function onMapClick(e) {
    if (!isClickMode) return;
    
    // Debounce: ignorar cliques muito rápidos
    const now = Date.now();
    if (now - lastClickTime < CLICK_DEBOUNCE_MS) {
        return;
    }
    lastClickTime = now;
    
    const lat = e.latlng.lat;
    const lng = e.latlng.lng;
    
    // Mostrar loading screen IMEDIATAMENTE para feedback visual rápido
    showViabilityLoading('Processando local...', 'Obtendo informações do endereço', 'address');
    
    // Mostrar marcador IMEDIATAMENTE para feedback visual rápido
    map.setView([lat, lng], 16);
    
    // Remover marcador anterior se existir
    if (window.searchMarker && map.hasLayer(window.searchMarker)) {
        map.removeLayer(window.searchMarker);
    }
    
    // Criar ícone do marcador de pesquisa
    const searchIcon = L.divIcon({
        className: 'search-marker',
        html: '<div class="search-marker-pin"><div class="search-marker-pulse"></div></div>',
        iconSize: [22, 22],
        iconAnchor: [11, 11]
    });
    
    // Adicionar marcador IMEDIATAMENTE
    window.searchMarker = L.marker([lat, lng], { icon: searchIcon }).addTo(map);
    
    // Tentar obter endereço via geocodificação reversa (com timeout curto)
    let addressText = `Coordenadas: ${lat.toFixed(6)}, ${lng.toFixed(6)}`;
    
    // Fazer geocodificação em paralelo (não bloquear)
    const geoController = new AbortController();
    const geoTimeout = setTimeout(() => geoController.abort(), 2000); // Timeout de 2 segundos
    
    const geoPromise = fetch(
        `${API_BASE}/geocode?${new URLSearchParams({ lat: String(lat), lon: String(lng) })}`,
        { signal: geoController.signal }
    ).then(response => {
        clearTimeout(geoTimeout);
        if (response.ok) {
            return response.json();
        }
        if (response.status === 422) {
            return null;
        }
        return null;
    }).then(geoData => {
        if (geoData && geoData.endereco_completo) {
            addressText = geoData.endereco_completo;
            // Atualizar popup se já estiver aberto
            if (window.searchMarker && window.searchMarker.isPopupOpen()) {
                window.searchMarker.setPopupContent(createLocationPopupContent(lat, lng, addressText, true));
            }
        }
    }).catch(error => {
        // Ignorar erro silenciosamente
        console.warn('Geocodificação em background falhou:', error);
    });
    
    // Aguardar geocodificação (mas não bloquear muito)
    await Promise.race([
        geoPromise,
        new Promise(resolve => setTimeout(resolve, 2000)) // Máximo 2 segundos
    ]);
    
    // Esconder loading screen temporariamente (será mostrado novamente quando confirmar)
    hideViabilityLoading();

    const sessionId = beginViabilityPopupSession();

    const popupContent = createLocationPopupContent(lat, lng, addressText, true);
    window.searchMarker
        .bindPopup(popupContent, getSearchMarkerPopupOptions())
        .openPopup();

    nudgeMapForPopupAnchor(window.searchMarker);
    ensureMarkerPopupVisible(window.searchMarker);

    registerViabilityPopupGuards(window.searchMarker);
    registerMapPopupClickGuard();

    window.searchMarker.on('popupopen', () => {
        const popupNode = getViabilityPopupContentNode(window.searchMarker);
        attachPopupListeners(popupNode, lat, lng, addressText, true);
    });

    schedulePopupButtonBind(window.searchMarker, lat, lng, addressText, true, sessionId);
}

// Função helper para criar conteúdo do popup
function createLocationPopupContent(lat, lng, addressText, fromClickMode) {
    // Detectar mobile para ajustar estilos
    const isMobileDevice = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || 
                          (window.innerWidth <= 768) ||
                          ('ontouchstart' in window);
    
    const buttonMobileClass = isMobileDevice ? ' mobile-button' : '';
    
    return `
        <div class="location-popup">
            <div class="viability-popup-header">
                <span class="viability-popup-header-icon" aria-hidden="true"><i class="fas fa-map-marker-alt"></i></span>
                <h4 class="location-popup-title">Local selecionado</h4>
            </div>
            <p class="location-popup-address">${escapeHtml(addressText)}</p>
            <div class="location-popup-actions">
                <button type="button" class="confirm-verify-btn${buttonMobileClass}">
                    <i class="fas fa-check" aria-hidden="true"></i>
                    <span>Verificar viabilidade</span>
                </button>
                <button type="button" class="cancel-verify-btn${buttonMobileClass}">
                    <i class="fas fa-times" aria-hidden="true"></i>
                    <span>Cancelar</span>
                </button>
            </div>
        </div>
    `;
}



// Disponibilizar ação global para fechar a verificação e resetar o mapa
window.fecharVerificacao = function() {
    try {
        window.popupClosingLocked = false;
        fecharPopupErroViabilidade();
        // Remover linha de viabilidade e borda de rota
        if (window.viabilityLine && map.hasLayer(window.viabilityLine)) {
            map.removeLayer(window.viabilityLine);
            window.viabilityLine = null;
        }
        if (window.routeBorder && map.hasLayer(window.routeBorder)) {
            map.removeLayer(window.routeBorder);
            window.routeBorder = null;
        }
        // Remover marcador do CTO
        if (window.ctoMarker && map.hasLayer(window.ctoMarker)) {
            map.removeLayer(window.ctoMarker);
            window.ctoMarker = null;
        }
        // Remover camadas de CTO carregadas via checkboxes
        clearAllMapLayers({ resetCheckboxes: true, suppressFit: true });
        // Remover marcador de busca
        if (window.searchMarker && map.hasLayer(window.searchMarker)) {
            map.removeLayer(window.searchMarker);
            window.searchMarker = null;
        }
        // Limpar UI de busca
        if (typeof searchResults !== 'undefined' && searchResults) {
            searchResults.classList.remove('show');
            searchResults.innerHTML = '';
        }
        if (typeof addressSearch !== 'undefined' && addressSearch) {
            addressSearch.value = '';
        }
        // Resetar mapa para a visão inicial (Rio de Janeiro)
        resetMapView();
    currentCTODetails = null;
    window.currentCTO = null;
        // Remover notificação desnecessária
    } catch (err) {
        console.error('Erro ao fechar verificação:', err);
    }
};

// Função global para marcar e verificar (usado em popups inline)
window.marcarEVerificar = async function(lat, lng, endereco = '') {
    await markLocationWithConfirmation(lat, lng, endereco || `Coordenadas: ${lat}, ${lng}`);
};

// Função para apenas marcar o local sem verificar viabilidade
window.apenasMarcar = function(lat, lng) {
    // Fechar popup atual
    map.closePopup();
    
    // Remover marcador se existir
    if (window.searchMarker && map.hasLayer(window.searchMarker)) {
        map.removeLayer(window.searchMarker);
        window.searchMarker = null;
    }
    
    // Remover linha de viabilidade se existir
    if (window.viabilityLine && map.hasLayer(window.viabilityLine)) {
        map.removeLayer(window.viabilityLine);
        window.viabilityLine = null;
    }
    
    // Remover marcador CTO se existir
    if (window.ctoMarker && map.hasLayer(window.ctoMarker)) {
        map.removeLayer(window.ctoMarker);
        window.ctoMarker = null;
    }
    
    // Remover notificação desnecessária
};


// Função para carregar arquivos dinamicamente da API
async function loadCTOFiles(forceRefresh = false) {
    const refreshBtn = document.getElementById('refresh-maps-btn');
    const ctoGridEarly = document.querySelector('.cto-grid');
    if (ctoGridEarly && window.SkeletonUI) {
        window.SkeletonUI.renderCTOGrid(ctoGridEarly, 4);
    }
    
    try {
        // Mostrar indicador de loading no botão
        if (refreshBtn) {
            refreshBtn.classList.add('loading');
            refreshBtn.disabled = true;
        }
        
        // Adicionar parâmetro refresh para bypass do cache se necessário
        const url = forceRefresh ? `${API_BASE}/arquivos?refresh=true` : `${API_BASE}/arquivos`;
        const response = await fetch(url, {
            headers: { 'X-Skip-Global-Loading': '1' },
        });
        
        if (!response.ok) {
            console.error('Erro ao carregar arquivos:', response.status, response.statusText);
            showNotification(FTTH_USER_MESSAGES.mapas_erro, 'error');
            if (refreshBtn) {
                refreshBtn.classList.remove('loading');
                refreshBtn.disabled = false;
            }
            return;
        }
        
        const data = await response.json();
        
        const ctoGrid = document.querySelector('.cto-grid');
        if (!ctoGrid) return;
        if (window.SkeletonUI) window.SkeletonUI.clearBusy(ctoGrid);
        
        // Limpar todos os botões dinâmicos
        ctoGrid.innerHTML = '';
        
        // Função helper para criar botão de CTO
        function createCTOButton(arquivo) {
            const nomeDisplay = arquivo.nome.replace(/\.[^.]+$/, ''); // Remove extensão
            const mapKey = getLayerKey(arquivo.nome, arquivo.id);
            
            const card = document.createElement('label');
            card.className = 'cto-card';
            card.setAttribute('data-map-key', mapKey);

            card.innerHTML = `
                <input 
                    type="checkbox" 
                    class="cto-checkbox-input" 
                    data-file="${arquivo.nome}" 
                    data-type="${arquivo.tipo || ''}"
                    data-map-key="${mapKey}"
                    ${arquivo.id ? `data-map-id="${arquivo.id}"` : ''}
                />
                <div class="cto-icon">
                    <i class="fas fa-map"></i>
                </div>
                <div class="cto-info">
                    <span class="cto-name">${nomeDisplay}</span>
                </div>
            `;
            
            const checkbox = card.querySelector('.cto-checkbox-input');
            if (activeMapLayers.has(mapKey)) {
                checkbox.checked = true;
                card.classList.add('selected');
            }
            
            return card;
        }
        
        // Verificar se está agrupado por empresa
        if (data.agrupado && data.empresas) {
            // Renderizar agrupado por empresa
            Object.keys(data.empresas).sort().forEach(empresaNome => {
                const arquivos = data.empresas[empresaNome];
                
                // Criar seção de empresa
                const empresaSection = document.createElement('div');
                empresaSection.className = 'cto-empresa-section';
                
                const empresaHeader = document.createElement('div');
                empresaHeader.className = 'cto-empresa-header';
                empresaHeader.innerHTML = `
                    <i class="fas fa-building"></i>
                    <span class="cto-empresa-nome">${empresaNome}</span>
                    <span class="cto-empresa-count">(${arquivos.length})</span>
                `;
                empresaSection.appendChild(empresaHeader);
                
                const empresaGrid = document.createElement('div');
                empresaGrid.className = 'cto-empresa-grid';
                
                arquivos.forEach(arquivo => {
                    const button = createCTOButton(arquivo);
                    empresaGrid.appendChild(button);
                });
                
                empresaSection.appendChild(empresaGrid);
                ctoGrid.appendChild(empresaSection);
            });
            
            const totalArquivos = Object.values(data.empresas).reduce((sum, arr) => sum + arr.length, 0);
            console.log(`✅ ${totalArquivos} arquivos de ${Object.keys(data.empresas).length} empresas carregados`);
        } else {
            // Formato simples (array de arquivos)
            const arquivos = Array.isArray(data) ? data : [];
            
            arquivos.forEach(arquivo => {
                const button = createCTOButton(arquivo);
                ctoGrid.appendChild(button);
            });
            
            console.log(`✅ ${arquivos.length} arquivos carregados dinamicamente`);
        }
        
        // Se não encontrou nenhum arquivo, mostrar mensagem
        if ((data.agrupado && Object.keys(data.empresas).length === 0) || 
            (!data.agrupado && (!Array.isArray(data) || data.length === 0))) {
            smartCache.clear('coordinates');
            const ctoGrid = document.querySelector('.cto-grid');
            if (ctoGrid && ctoGrid.children.length === 0) {
                ctoGrid.innerHTML = `
                    <div class="ds-empty-state">
                        <div class="ds-empty-state__icon"><i class="fas fa-map"></i></div>
                        <p class="ds-empty-state__title">Nenhum mapa disponível</p>
                        <p class="ds-empty-state__text">Faça upload de um mapa CTO no painel para começar.</p>
                    </div>
                `;
                showNotification(FTTH_USER_MESSAGES.mapas_vazio, 'info', 4000);
            }
        }
        
        // Remover loading do botão
        if (refreshBtn) {
            refreshBtn.classList.remove('loading');
            refreshBtn.disabled = false;
        }
    } catch (error) {
        console.error('Erro ao carregar arquivos:', error);
        const ctoGrid = document.querySelector('.cto-grid');
        if (ctoGrid) {
            if (window.SkeletonUI) window.SkeletonUI.clearBusy(ctoGrid);
            ctoGrid.innerHTML = `
                <div class="ds-empty-state">
                    <div class="ds-empty-state__icon" style="color: var(--ds-danger);"><i class="fas fa-exclamation-triangle"></i></div>
                    <p class="ds-empty-state__title">Erro ao carregar mapas</p>
                    <p class="ds-empty-state__text">${FTTH_USER_MESSAGES.mapas_erro}</p>
                    <button type="button" class="btn btn-sm btn-primary" data-ftth-action="retry-load-maps" style="margin-top: 0.75rem;">
                        <i class="fas fa-redo"></i> Tentar novamente
                    </button>
                </div>
            `;
        }
        showNotification(FTTH_USER_MESSAGES.mapas_erro, 'error');
        
        // Remover loading do botão em caso de erro
        if (refreshBtn) {
            refreshBtn.classList.remove('loading');
            refreshBtn.disabled = false;
        }
    }
}

// Tornar função global para poder ser chamada de botões
window.loadCTOFiles = loadCTOFiles;
window.FTTH_USER_MESSAGES = FTTH_USER_MESSAGES;
window.showNotification = showNotification;

// ===== INICIALIZAÇÃO DO SISTEMA =====
// ===== MOBILE SIDEBAR BUTTONS CONNECTION =====
function initializeMobileSidebarButtons() {
    // Conectar botão mobile do cursor toggle
    const cursorToggleBtnMobile = document.getElementById('cursor-toggle-btn-mobile');
    if (cursorToggleBtnMobile) {
        cursorToggleBtnMobile.addEventListener('click', function() {
            const originalBtn = document.getElementById('cursor-toggle-btn');
            if (originalBtn) {
                originalBtn.click();
            } else {
                toggleCursorMode();
            }
        });
    }
    
    /* tema: inicializado em initializeThemeToggle() */
    
    // Conectar botão mobile do add CTO toggle
    const addCTOToggleBtnMobile = document.getElementById('add-cto-toggle-btn-mobile');
    if (addCTOToggleBtnMobile) {
        addCTOToggleBtnMobile.addEventListener('click', function() {
            const originalBtn = document.getElementById('add-cto-toggle-btn');
            if (originalBtn) {
                originalBtn.click();
            } else {
                toggleAddCTOMode();
            }
        });
    }
}

/**
 * Ações dinâmicas sem onclick (compatível com CSP strict)
 */
function initializeFtthDelegatedActions() {
    document.addEventListener('click', function (e) {
        const refreshBtn = e.target.closest('#refresh-maps-btn');
        if (refreshBtn) {
            e.preventDefault();
            if (typeof loadCTOFiles === 'function') {
                loadCTOFiles(true);
            }
            return;
        }

        const actionEl = e.target.closest('[data-ftth-action]');
        if (actionEl) {
            const action = actionEl.getAttribute('data-ftth-action');
            if (action === 'close-viability') {
                e.preventDefault();
                if (typeof window.fecharVerificacao === 'function') {
                    window.fecharVerificacao();
                }
                return;
            }
            if (action === 'close-viability-error') {
                e.preventDefault();
                if (typeof fecharPopupErroViabilidade === 'function') {
                    fecharPopupErroViabilidade();
                }
                return;
            }
            if (action === 'clear-history') {
                e.preventDefault();
                if (typeof clearSearchHistory === 'function') {
                    clearSearchHistory();
                }
                return;
            }
            if (action === 'retry-load-maps') {
                e.preventDefault();
                if (typeof loadCTOFiles === 'function') {
                    loadCTOFiles(true);
                }
                return;
            }
        }

        const suggestionItem = e.target.closest('.suggestion-item[data-index]');
        if (suggestionItem) {
            const idx = parseInt(suggestionItem.getAttribute('data-index'), 10);
            if (!Number.isNaN(idx) && typeof window.selectSuggestion === 'function') {
                window.selectSuggestion(idx);
            }
            return;
        }

        const historyItem = e.target.closest('.history-item[data-index]');
        if (historyItem) {
            const idx = parseInt(historyItem.getAttribute('data-index'), 10);
            if (!Number.isNaN(idx) && typeof window.selectSuggestion === 'function') {
                window.selectSuggestion(idx);
            }
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        const item = e.target.closest('.suggestion-item[data-index], .history-item[data-index]');
        if (!item) return;
        e.preventDefault();
        const idx = parseInt(item.getAttribute('data-index'), 10);
        if (!Number.isNaN(idx) && typeof window.selectSuggestion === 'function') {
            window.selectSuggestion(idx);
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    initializeFtthDelegatedActions();
    // Inicializar botões mobile do side menu
    initializeMobileSidebarButtons();
    console.log('🚀 Iniciando sistema...');
    
    // Inicializar modo escuro PRIMEIRO
    console.log('🌙 Inicializando tema primeiro...');
    initializeThemeToggle();
    
    // Aguardar um pouco antes de inicializar outras funcionalidades
    setTimeout(() => {
        console.log('🔧 Inicializando outras funcionalidades...');
        initializeMainSearch();
        setupCTOButtonListeners(); // Usar event delegation (funciona para todos os botões)
        loadCTOFiles(); // Carregar arquivos dinamicamente e adicionar novos botões
        initializeCursorToggle();
        initializeMenuToggle();
        initializeAddCTO(); // Inicializar funcionalidade de adicionar CTO (apenas para admins)
        
        console.log('✅ Sistema inicializado com sucesso!');
        console.log('💡 Dica: Use Ctrl+Shift+P para ver estatísticas de performance');
        
        // Atalho de teclado para mostrar estatísticas de performance (Ctrl+Shift+P)
        document.addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.shiftKey && e.key === 'P') {
                e.preventDefault();
                performanceMonitor.showIndicator();
            }
        });
    }, 100);
});

/* tema inicializado uma vez em DOMContentLoaded */

// ===== FUNCIONALIDADE ADICIONAR CTO (APENAS PARA ADMINS) =====
let isAddCTOMode = false;
let addCTOMarker = null;
let addCTOClickHandler = null;

function initializeAddCTO() {
    const addCTOBtn = document.getElementById('add-cto-toggle-btn');
    const addCTOPopup = document.getElementById('add-cto-popup');
    
    if (!addCTOBtn || !addCTOPopup) {
        // Funcionalidade não disponível (usuário não é admin)
        return;
    }
    
    const map = window.map;
    if (!map) {
        console.error('❌ Mapa não encontrado para adicionar CTO!');
        return;
    }
    
    // Carregar lista de mapas no select
    loadMapsForAddCTO();

    // Garantir popup fechado ao carregar (CSS .add-cto-popup usa display:none por padrão)
    closeAddCTOPopup();
    
    // Toggle do botão
    addCTOBtn.addEventListener('click', function() {
        toggleAddCTOMode();
    });
    
    // Fechar popup
    const closeBtn = document.getElementById('close-add-cto-popup');
    const cancelBtn = document.getElementById('cancel-add-cto');
    
    if (closeBtn) {
        closeBtn.addEventListener('click', closeAddCTOPopup);
    }
    
    if (cancelBtn) {
        cancelBtn.addEventListener('click', closeAddCTOPopup);
    }
    
    // Fechar ao clicar fora
    addCTOPopup.addEventListener('click', function(e) {
        if (e.target === addCTOPopup) {
            closeAddCTOPopup();
        }
    });
    
    // Submit do formulário
    const form = document.getElementById('add-cto-form');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            saveCTO();
        });
    }
}

function toggleAddCTOMode() {
    const addCTOBtn = document.getElementById('add-cto-toggle-btn');
    const map = window.map;
    
    if (!addCTOBtn || !map) return;
    
    isAddCTOMode = !isAddCTOMode;
    
    if (isAddCTOMode) {
        // Ativar modo adicionar CTO
        addCTOBtn.classList.add('active');
        addCTOBtn.querySelector('.add-cto-mode-text').textContent = 'Cancelar';
        document.getElementById('map').style.cursor = 'crosshair';
        
        // Desabilitar navegação do mapa
        map.dragging.disable();
        map.scrollWheelZoom.disable();
        map.doubleClickZoom.disable();
        map.touchZoom.disable();
        map.boxZoom.disable();
        map.keyboard.disable();
        
        // Adicionar handler de clique
        addCTOClickHandler = function(e) {
            const { lat, lng } = e.latlng;
            openAddCTOPopup(lat, lng);
        };
        map.on('click', addCTOClickHandler);
        
        showNotification('Modo adicionar CTO ativado - Clique no mapa para adicionar', 'info');
    } else {
        // Desativar modo
        addCTOBtn.classList.remove('active');
        addCTOBtn.querySelector('.add-cto-mode-text').textContent = 'Adicionar CTO';
        document.getElementById('map').style.cursor = '';
        
        // Reabilitar navegação
        map.dragging.enable();
        map.scrollWheelZoom.enable();
        map.doubleClickZoom.enable();
        map.touchZoom.enable(); // CRÍTICO: Zoom por pinch no mobile
        map.boxZoom.enable();
        
        // No mobile, garantir que todos os gestos estejam habilitados
        if (isMobile) {
            map.touchZoom.enable();
            map.doubleClickZoom.enable();
            map.dragging.enable();
            
            const mapElement = document.getElementById('map');
            if (mapElement) {
                mapElement.style.touchAction = 'pan-x pan-y pinch-zoom double-tap-zoom';
            }
        }
        map.keyboard.enable();
        
        // Remover handler
        if (addCTOClickHandler) {
            map.off('click', addCTOClickHandler);
            addCTOClickHandler = null;
        }
        
        // Remover marcador temporário
        if (addCTOMarker) {
            map.removeLayer(addCTOMarker);
            addCTOMarker = null;
        }
        
        closeAddCTOPopup();
    }
}

function openAddCTOPopup(lat, lng) {
    const popup = document.getElementById('add-cto-popup');
    const latDisplay = document.getElementById('cto-lat-display');
    const lonDisplay = document.getElementById('cto-lon-display');
    const map = window.map;
    
    if (!popup || !latDisplay || !lonDisplay || !map) return;
    
    // Atualizar coordenadas
    latDisplay.textContent = lat.toFixed(6);
    lonDisplay.textContent = lng.toFixed(6);
    
    // Armazenar coordenadas no formulário
    popup.dataset.lat = lat;
    popup.dataset.lng = lng;
    
    // Adicionar marcador temporário
    if (addCTOMarker) {
        map.removeLayer(addCTOMarker);
    }
    
    addCTOMarker = L.marker([lat, lng], {
        icon: L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        })
    }).addTo(map);
    
    // Mostrar popup
    popup.classList.add('is-open');
    popup.setAttribute('aria-hidden', 'false');
}

function closeAddCTOPopup() {
    const popup = document.getElementById('add-cto-popup');
    const map = window.map;
    
    if (popup) {
        popup.classList.remove('is-open');
        popup.setAttribute('aria-hidden', 'true');
    }
    
    // Remover marcador temporário
    if (addCTOMarker && map) {
        map.removeLayer(addCTOMarker);
        addCTOMarker = null;
    }
    
    // Limpar formulário
    const form = document.getElementById('add-cto-form');
    if (form) {
        form.reset();
    }
    
    // Não desativar o modo automaticamente - o usuário pode querer adicionar mais CTOs
}

async function loadMapsForAddCTO() {
    const select = document.getElementById('cto-map');
    if (!select) return;
    
    try {
        const response = await fetch(`${API_BASE}/arquivos?refresh=true`);
        if (!response.ok) throw new Error('Erro ao carregar mapas');
        
        const arquivos = await response.json();
        
        // Limpar opções
        select.innerHTML = '<option value="">Selecione um mapa...</option>';
        
        // Adicionar mapas
        arquivos.forEach(arquivo => {
            const option = document.createElement('option');
            option.value = arquivo.id || '';
            option.textContent = `${arquivo.nome} (${arquivo.tipo.toUpperCase()})`;
            select.appendChild(option);
        });
        
        if (arquivos.length === 0) {
            select.innerHTML = '<option value="">Nenhum mapa disponível</option>';
        }
    } catch (error) {
        console.error('Erro ao carregar mapas:', error);
        select.innerHTML = '<option value="">Erro ao carregar mapas</option>';
    }
}

// Função auxiliar para obter CSRF token
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

async function reloadActiveMapLayerAfterCtoChange(mapId) {
    if (!mapId) return;
    for (const [layerKey, entry] of activeMapLayers.entries()) {
        if (String(entry?.meta?.mapId) !== String(mapId)) continue;
        const filename = entry?.meta?.filename;
        if (!filename) continue;
        smartCache.remove('coordinates', `coords_id_${mapId}`);
        removeMapLayerByKey(layerKey, { updateCheckbox: false, suppressFit: true });
        try {
            await loadKML(filename, mapId, { append: true, forceRefresh: true });
        } catch (err) {
            console.warn('Não foi possível recarregar camada do mapa após adicionar CTO:', err);
        }
        break;
    }
}

async function saveCTO() {
    const popup = document.getElementById('add-cto-popup');
    const form = document.getElementById('add-cto-form');
    const saveBtn = document.getElementById('save-cto');
    
    if (!popup || !form || !saveBtn) return;
    
    const nomeCTO = document.getElementById('cto-name').value.trim();
    const mapId = document.getElementById('cto-map').value;
    const lat = parseFloat(popup.dataset.lat);
    const lon = parseFloat(popup.dataset.lng);
    
    // Validação
    if (!nomeCTO) {
        showNotification('Por favor, informe o nome do CTO', 'error');
        return;
    }
    
    if (!mapId) {
        showNotification('Por favor, selecione um mapa', 'error');
        return;
    }
    
    if (isNaN(lat) || isNaN(lon)) {
        showNotification('Coordenadas inválidas', 'error');
        return;
    }
    
    // Desabilitar botão
    saveBtn.disabled = true;
    saveBtn.textContent = 'Salvando...';
    
    // Obter CSRF token (tentar do window primeiro, depois do cookie)
    const csrftoken = window.csrfToken || getCookie('csrftoken');
    
    try {
        const response = await fetch(`${API_BASE}/adicionar-cto`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken || '',
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                nome_cto: nomeCTO,
                lat: lat,
                lon: lon,
                map_id: parseInt(mapId)
            })
        });
        
        // Verificar se a resposta é JSON antes de tentar parsear
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.error('Resposta não é JSON:', text.substring(0, 200));
            throw new Error(`Erro do servidor (${response.status}): ${text.substring(0, 100)}`);
        }
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.erro || 'Erro ao salvar CTO');
        }
        
        // Sucesso
        showNotification(
            (data.mensagem || 'CTO adicionado com sucesso!') + ' Faça uma nova busca para atualizar a viabilidade.',
            'success'
        );
        window._viabilidadeForceRefresh = true;
        smartCache.clear('viability');
        
        // Fechar popup e desativar modo
        closeAddCTOPopup();
        if (isAddCTOMode) {
            toggleAddCTOMode();
        }
        
        const savedMapId = parseInt(mapId, 10);
        await reloadActiveMapLayerAfterCtoChange(savedMapId);

        setTimeout(() => {
            loadCTOFiles(true);
        }, 500);
        
    } catch (error) {
        console.error('Erro ao salvar CTO:', error);
        showNotification(error.message || 'Erro ao salvar CTO', 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Salvar CTO';
    }
}
