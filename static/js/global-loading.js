/**
 * Sistema Global de Loading Screen — RM Systems
 * Transições enter/leave completas + interceptação HTTP
 */

class GlobalLoadingScreen {
    constructor() {
        this.loadingOverlay = null;
        this.activeRequests = new Map();
        this.showDelayMs = 900;
        this.maxRequestMs = 20000;
        this.minVisibleMs = 120;
        this.navLoadingEnabled = false;
        this.exitDurationMs = 420;
        this.pendingShowTimer = null;
        this._shownAt = 0;
        this._hideTimer = null;
        this._exitFallbackTimer = null;
        this.currentMessage = 'Carregando...';
        this._navTimeout = null;
        this._pendingNavId = null;
        this.init();
    }

    init() {
        if (this.isPageDisabled()) {
            return;
        }
        this.createLoadingOverlay();
        this.interceptFetch();
        this.interceptXMLHttpRequest();
        this.handlePageNavigation();
        this.startStaleWatcher();
        this.bindEscapeDismiss();
        window.addEventListener('pageshow', () => this.forceHide());
        this.forceHide();
    }

    isPageDisabled() {
        if (window.__DISABLE_GLOBAL_LOADING__) return true;
        const body = document.body;
        if (body?.dataset?.noGlobalLoading === '1') return true;
        if (body?.classList?.contains('ftth-viewer-page')) return true;
        if (body?.classList?.contains('upload-page')) return true;
        if (body?.classList?.contains('company-tickets-page')) return true;
        if (body?.classList?.contains('olt-console-page')) return true;
        const path = window.location?.pathname || '';
        if (/\/olt\/?/i.test(path)) return true;
        if (/\/upload\/?$/i.test(path)) return true;
        if (/\/alertas\//i.test(path)) return true;
        if (/\/olt\/.*\/ao-vivo\/?/i.test(path)) return true;
        if (/\/tickets\//i.test(path)) return true;
        return false;
    }

    startStaleWatcher() {
        setInterval(() => this.pruneStaleRequests(), 2000);
    }

    pruneStaleRequests() {
        const now = Date.now();
        for (const [id, data] of this.activeRequests.entries()) {
            if (data.manual) continue;
            if (now - (data.timestamp || 0) > this.maxRequestMs) {
                this.removeRequest(id);
            }
        }
        if (this.activeRequests.size === 0) {
            this.forceHide();
        }
    }

    bindEscapeDismiss() {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.loadingOverlay?.classList.contains('gl-open')) {
                this.forceHide();
            }
        });
    }

    createLoadingOverlay() {
        if (document.getElementById('global-loading-overlay')) {
            this.loadingOverlay = document.getElementById('global-loading-overlay');
            return;
        }

        const overlay = document.createElement('div');
        overlay.id = 'global-loading-overlay';
        overlay.className = 'global-loading-overlay';
        overlay.setAttribute('aria-hidden', 'true');
        overlay.style.cssText =
            'position:fixed;inset:0;z-index:999999;display:flex;align-items:center;' +
            'justify-content:center;visibility:hidden;opacity:0;pointer-events:none;';
        overlay.innerHTML = `
            <div class="global-loading-content" role="status" aria-live="polite" aria-busy="false">
                <div class="global-loading-brand" aria-hidden="true">
                    <div class="global-loading-spinner"></div>
                    <div class="global-loading-rings">
                        <span class="global-loading-ring global-loading-ring--outer"></span>
                        <span class="global-loading-ring global-loading-ring--inner"></span>
                    </div>
                    <div class="global-loading-core">
                        <i class="fas fa-network-wired fa-spin" aria-hidden="true"></i>
                    </div>
                </div>
                <div class="global-loading-text">Carregando<span class="global-loading-dots" aria-hidden="true"><span></span><span></span><span></span></span></div>
                <p class="global-loading-sub">Aguarde um momento</p>
                <div class="global-loading-progress" aria-hidden="true">
                    <div class="global-loading-progress-bar"></div>
                </div>
                <button type="button" class="global-loading-dismiss" aria-label="Fechar indicador de carregamento">Fechar (ESC)</button>
            </div>
        `;
        document.body.appendChild(overlay);
        this.loadingOverlay = overlay;
        const dismissBtn = overlay.querySelector('.global-loading-dismiss');
        if (dismissBtn) {
            dismissBtn.addEventListener('click', () => this.forceHide());
        }
    }

    injectStyles() {
        /* noop — CSS em static/css/global-loading.css */
    }

    _setBusy(busy) {
        const panel = this.loadingOverlay?.querySelector('.global-loading-content');
        if (panel) panel.setAttribute('aria-busy', busy ? 'true' : 'false');
    }

    _clearExitTimers() {
        if (this._hideTimer) {
            clearTimeout(this._hideTimer);
            this._hideTimer = null;
        }
        if (this._exitFallbackTimer) {
            clearTimeout(this._exitFallbackTimer);
            this._exitFallbackTimer = null;
        }
    }

    _playEnter() {
        if (!this.loadingOverlay) return;
        this._clearExitTimers();
        this.loadingOverlay.classList.remove('gl-leaving');
        this.loadingOverlay.setAttribute('aria-hidden', 'false');
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                this.loadingOverlay.classList.add('gl-open');
                this._setBusy(true);
                this._shownAt = Date.now();
            });
        });
    }

    _playExit(callback) {
        if (!this.loadingOverlay) {
            if (callback) callback();
            return;
        }
        if (!this.loadingOverlay.classList.contains('gl-open') && !this.loadingOverlay.classList.contains('gl-leaving')) {
            if (callback) callback();
            return;
        }

        this._clearExitTimers();
        this.loadingOverlay.classList.remove('gl-open');
        this.loadingOverlay.classList.add('gl-leaving');
        this._setBusy(false);

        const finish = () => {
            this.loadingOverlay.classList.remove('gl-leaving');
            this.loadingOverlay.setAttribute('aria-hidden', 'true');
            if (callback) callback();
        };

        const onTransitionEnd = (e) => {
            if (e.target !== this.loadingOverlay || e.propertyName !== 'opacity') return;
            this.loadingOverlay.removeEventListener('transitionend', onTransitionEnd);
            if (this._exitFallbackTimer) {
                clearTimeout(this._exitFallbackTimer);
                this._exitFallbackTimer = null;
            }
            finish();
        };

        this.loadingOverlay.addEventListener('transitionend', onTransitionEnd);
        this._exitFallbackTimer = setTimeout(() => {
            this.loadingOverlay.removeEventListener('transitionend', onTransitionEnd);
            finish();
        }, this.exitDurationMs + 80);
    }

    show(message = null) {
        if (!this.loadingOverlay || this.isPageDisabled()) return;

        if (message) {
            this.currentMessage = message;
            const textElement = this.loadingOverlay.querySelector('.global-loading-text');
            if (textElement) {
                const base = message.replace(/\.\.\.$/, '').trim();
                textElement.innerHTML =
                    `${base}<span class="global-loading-dots" aria-hidden="true"><span></span><span></span><span></span></span>`;
            }
        }

        if (this.loadingOverlay.classList.contains('gl-open')) return;
        this._playEnter();
    }

    scheduleShow() {
        if (this.isPageDisabled()) return;
        if (this.pendingShowTimer) return;
        this.pendingShowTimer = setTimeout(() => {
            this.pendingShowTimer = null;
            if (this.isPageDisabled() || this.activeRequests.size === 0) return;
            const first = Array.from(this.activeRequests.values())[0];
            this.show(first?.message || this.currentMessage);
        }, this.showDelayMs);
    }

    cancelScheduledShow() {
        if (this.pendingShowTimer) {
            clearTimeout(this.pendingShowTimer);
            this.pendingShowTimer = null;
        }
    }

    hide() {
        if (!this.loadingOverlay) return;
        this.cancelScheduledShow();
        if (this.activeRequests.size > 0) return;

        const elapsed = Date.now() - (this._shownAt || 0);
        const wait = Math.max(0, this.minVisibleMs - elapsed);

        if (this._hideTimer) clearTimeout(this._hideTimer);
        this._hideTimer = setTimeout(() => {
            this._hideTimer = null;
            if (this.activeRequests.size === 0) {
                this._playExit();
            }
        }, wait);
    }

    shouldIgnoreRequest(urlString, options = {}) {
        if (this.isPageDisabled()) return true;

        const method = String(options.method || 'GET').toUpperCase();
        if (
            (method === 'GET' || method === 'HEAD' || method === 'OPTIONS') &&
            !/\/api\//i.test(urlString) &&
            !/\.json(\?|$)/i.test(urlString)
        ) {
            return true;
        }

        const headers = options.headers;
        if (headers) {
            if (headers instanceof Headers && headers.get('X-Skip-Global-Loading') === '1') {
                return true;
            }
            if (typeof headers === 'object' && headers['X-Skip-Global-Loading'] === '1') {
                return true;
            }
        }

        const ignorePatterns = [
            /\.(css|js|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot|webp|mp4|mp3)$/i,
            /\/static\//,
            /\/media\//,
            /\/api\/health/,
            /\/api\/status/,
            /\/favicon\.ico/,
            /\/manifest\.json/,
            /\/sw\.js/,
            /\/service-worker\.js/,
            /\/whatsapp\/status\/?/i,
            /\/whatsapp\/qr/i,
            /\/alertas\//i,
            /\/worker-status\/?/i,
            /\/olt\/.*\/status\/?/i,
            /\/jobs\/\d+\/status\/?/i,
            /\/verificador\/api\//i,
            /verificar-viabilidade/i,
            /\/api\/geocode/i,
            /\/api\/coordenadas/i,
            /\/api\/arquivos/i,
            /whatsapp\/conectar/i,
            /whatsapp\/desconectar/i,
            /\/upload\/arquivo\/?/i,
            /\/upload\/?$/i,
            /\/mensagens\/?/i,
            /\/tickets\/\d+\/mensagens/i,
            /get_new_messages/i,
        ];

        return ignorePatterns.some((pattern) => pattern.test(urlString));
    }

    addRequest(requestId, metadata = {}) {
        if (this.isPageDisabled() && !metadata.manual) return;
        this.activeRequests.set(requestId, {
            url: metadata.url || '',
            message: metadata.message || this.getContextualMessage(metadata.url || ''),
            timestamp: Date.now(),
            ...metadata,
        });

        if (metadata.manual) {
            const requestData = this.activeRequests.get(requestId);
            this.show(requestData?.message);
        } else {
            this.scheduleShow();
        }
    }

    removeRequest(requestId) {
        this.activeRequests.delete(requestId);
        if (this.activeRequests.size === 0) {
            this.hide();
            return;
        }
        const nextRequest = Array.from(this.activeRequests.values())[0];
        if (nextRequest?.message && this.loadingOverlay?.classList.contains('gl-open')) {
            this.show(nextRequest.message);
        }
    }

    getContextualMessage(url) {
        if (!url) return 'Carregando...';

        const urlLower = url.toLowerCase();

        if (urlLower.includes('verificar-viabilidade') || urlLower.includes('viabilidade')) {
            return 'Verificando viabilidade...';
        }
        if (urlLower.includes('geocode')) {
            return 'Buscando endereço...';
        }
        if (urlLower.includes('coordenadas') || urlLower.includes('arquivos') || urlLower.includes('cto')) {
            return 'Carregando mapas...';
        }
        if (urlLower.includes('upload') || urlLower.includes('enviar')) {
            return 'Enviando arquivo...';
        }
        if (urlLower.includes('search') || urlLower.includes('buscar') || urlLower.includes('pesquisar')) {
            return 'Pesquisando...';
        }
        if (urlLower.includes('login') || urlLower.includes('auth')) {
            return 'Entrando...';
        }
        if (urlLower.includes('save') || urlLower.includes('update') || urlLower.includes('salvar') || urlLower.includes('atualizar')) {
            return 'Salvando...';
        }
        if (urlLower.includes('delete') || urlLower.includes('remove') || urlLower.includes('deletar') || urlLower.includes('remover')) {
            return 'Removendo...';
        }
        if (urlLower.includes('/api/')) {
            return 'Processando...';
        }
        return 'Carregando...';
    }

    interceptFetch() {
        const originalFetch = window.fetch;
        const self = this;

        window.fetch = async function (...args) {
            const url = args[0];
            const options = args[1] || {};

            let urlString = '';
            if (typeof url === 'string') {
                urlString = url;
            } else if (url instanceof Request) {
                urlString = url.url;
            } else if (url instanceof URL) {
                urlString = url.toString();
            }

            if (self.shouldIgnoreRequest(urlString, options)) {
                return originalFetch.apply(this, args);
            }

            const requestId = `fetch_${Date.now()}_${Math.random()}`;
            const message = self.getContextualMessage(urlString);
            self.addRequest(requestId, { url: urlString, message });

            try {
                const response = await originalFetch.apply(this, args);
                self.removeRequest(requestId);
                return response;
            } catch (error) {
                self.removeRequest(requestId);
                throw error;
            }
        };
    }

    interceptXMLHttpRequest() {
        const self = this;
        const originalOpen = XMLHttpRequest.prototype.open;
        const originalSend = XMLHttpRequest.prototype.send;

        XMLHttpRequest.prototype.open = function (method, url, ...rest) {
            this._url = url;
            this._method = method;
            return originalOpen.apply(this, [method, url, ...rest]);
        };

        XMLHttpRequest.prototype.send = function (...args) {
            const url = this._url;

            if (self.shouldIgnoreRequest(url || '', {})) {
                return originalSend.apply(this, args);
            }

            const requestId = `xhr_${Date.now()}_${Math.random()}`;
            const message = self.getContextualMessage(url);
            self.addRequest(requestId, { url, message });

            const originalOnReadyStateChange = this.onreadystatechange;
            this.onreadystatechange = function () {
                if (originalOnReadyStateChange) {
                    originalOnReadyStateChange.apply(this, arguments);
                }
                if (this.readyState === 4) {
                    self.removeRequest(requestId);
                }
            };

            this.addEventListener('loadend', () => self.removeRequest(requestId));
            this.addEventListener('error', () => self.removeRequest(requestId));

            return originalSend.apply(this, args);
        };
    }

    handlePageNavigation() {
        if (!this.navLoadingEnabled) {
            window.addEventListener('load', () => this.forceHide());
            return;
        }

        document.addEventListener('click', (e) => {
            if (this.isPageDisabled()) return;

            const link = e.target.closest('a');
            if (!link) return;

            const href = link.getAttribute('href');
            if (!href) return;

            if (
                href.startsWith('#') ||
                href.startsWith('javascript:') ||
                link.hasAttribute('download') ||
                link.target === '_blank' ||
                link.hasAttribute('data-no-loading')
            ) {
                return;
            }

            if (this._pendingNavId) {
                this.removeRequest(this._pendingNavId);
            }
            this._pendingNavId = `nav_${Date.now()}_${Math.random()}`;
            this.addRequest(this._pendingNavId, {
                url: href,
                message: 'Carregando página...',
            });

            clearTimeout(this._navTimeout);
            this._navTimeout = setTimeout(() => {
                if (this._pendingNavId) {
                    this.removeRequest(this._pendingNavId);
                    this._pendingNavId = null;
                }
            }, 12000);
        });

        window.addEventListener('load', () => {
            if (this._pendingNavId) {
                this.removeRequest(this._pendingNavId);
                this._pendingNavId = null;
            }
            this.forceHide();
        });
    }

    forceShow(message = 'Carregando...') {
        const requestId = `manual_${Date.now()}_${Math.random()}`;
        this.addRequest(requestId, { message, manual: true });
        return requestId;
    }

    forceHideManual(requestId) {
        if (requestId) {
            this.removeRequest(requestId);
        } else {
            for (const [id, data] of this.activeRequests.entries()) {
                if (data.manual) {
                    this.removeRequest(id);
                }
            }
        }
    }

    forceHide() {
        this.cancelScheduledShow();
        this.activeRequests.clear();
        this._pendingNavId = null;
        clearTimeout(this._navTimeout);
        if (this._hideTimer) {
            clearTimeout(this._hideTimer);
            this._hideTimer = null;
        }
        this._playExit();
    }
}

if (typeof window !== 'undefined') {
    const _glPath = window.location?.pathname || '';
    if (
        /\/alertas\//i.test(_glPath) ||
        /\/olt\/.*\/ao-vivo\/?/i.test(_glPath) ||
        /\/tickets\//i.test(_glPath)
    ) {
        window.__DISABLE_GLOBAL_LOADING__ = true;
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.globalLoadingScreen = new GlobalLoadingScreen();
    });
} else {
    window.globalLoadingScreen = new GlobalLoadingScreen();
}

window.GlobalLoadingScreen = GlobalLoadingScreen;
