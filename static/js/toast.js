/**
 * Sistema de Notificações Toast Profissional
 * Autor: RM Systems
 */

class ToastManager {
    constructor() {
        this.container = null;
        this.toasts = [];
        this.init();
    }

    init() {
        // Criar container se não existir
        if (!document.querySelector('.toast-container')) {
            this.container = document.createElement('div');
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        } else {
            this.container = document.querySelector('.toast-container');
        }
    }

    show(message, type = 'info', title = null, duration = 5000) {
        const toast = this.createToast(message, type, title, duration);
        this.container.appendChild(toast);
        this.toasts.push(toast);

        // Animar entrada
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);

        // Auto remover
        if (duration > 0) {
            this.startProgress(toast, duration);
            setTimeout(() => {
                this.remove(toast);
            }, duration);
        }

        return toast;
    }

    createToast(message, type, title, duration) {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = {
            success: '<i class="fas fa-check-circle"></i>',
            error: '<i class="fas fa-times-circle"></i>',
            warning: '<i class="fas fa-exclamation-triangle"></i>',
            info: '<i class="fas fa-info-circle"></i>'
        };

        const titles = {
            success: title || 'Pronto',
            error: title || 'Ops',
            warning: title || 'Atenção',
            info: title || null
        };

        const titleHtml = titles[type]
            ? `<div class="toast-title">${titles[type]}</div>`
            : '';
        toast.innerHTML = `
            <div class="toast-icon">${icons[type] || icons.info}</div>
            <div class="toast-content">
                ${titleHtml}
                <div class="toast-message">${message}</div>
            </div>
            <button type="button" class="toast-close" aria-label="Fechar">×</button>
            ${duration > 0 ? '<div class="toast-progress"></div>' : ''}
        `;

        const closeBtn = toast.querySelector('.toast-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.remove(toast));
        }

        return toast;
    }

    startProgress(toast, duration) {
        const progress = toast.querySelector('.toast-progress');
        if (progress) {
            progress.style.width = '100%';
            setTimeout(() => {
                progress.style.width = '0%';
                progress.style.transition = `width ${duration}ms linear`;
            }, 50);
        }
    }

    remove(toast) {
        if (toast && toast.parentElement) {
            toast.classList.remove('show');
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.parentElement.removeChild(toast);
                }
                this.toasts = this.toasts.filter(t => t !== toast);
            }, 300);
        }
    }

    success(message, title = null, duration = 5000) {
        return this.show(message, 'success', title, duration);
    }

    error(message, title = null, duration = 7000) {
        return this.show(message, 'error', title, duration);
    }

    warning(message, title = null, duration = 6000) {
        return this.show(message, 'warning', title, duration);
    }

    info(message, title = null, duration = 5000) {
        return this.show(message, 'info', title, duration);
    }

    clear() {
        this.toasts.forEach(toast => this.remove(toast));
    }
}

// Instância global
const toastManager = new ToastManager();

// Expor toastManager globalmente para permitir remoção manual de toasts
window.toastManager = toastManager;

// Funções de conveniência globais
window.showToast = (message, type, title, duration) => toastManager.show(message, type, title, duration);
window.showSuccess = (message, title, duration) => toastManager.success(message, title, duration);
window.showError = (message, title, duration) => toastManager.error(message, title, duration);
window.showWarning = (message, title, duration) => toastManager.warning(message, title, duration);
window.showInfo = (message, title, duration) => toastManager.info(message, title, duration);

// Converter mensagens Django em toasts (único ponto — evita duplicata com ux-forms.js)
function initDjangoMessageToasts() {
    const container = document.querySelector('.messages');
    if (!container || container.dataset.toastConverted === '1') {
        return;
    }
    container.dataset.toastConverted = '1';
    const items = container.querySelectorAll('.message, li');
    items.forEach(message => {
        const text = message.textContent.trim();
        if (!text) return;
        const classList = message.classList;
        let type = 'info';
        if (classList.contains('success')) type = 'success';
        else if (classList.contains('error')) type = 'error';
        else if (classList.contains('warning')) type = 'warning';
        toastManager.show(text, type);
    });
    container.classList.add('ds-messages-hidden');
}

document.addEventListener('DOMContentLoaded', initDjangoMessageToasts);

// Exportar para uso em módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ToastManager;
}