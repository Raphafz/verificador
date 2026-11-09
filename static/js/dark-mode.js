/**
 * Sistema de Dark Mode para RM Systems SaaS
 * Gerencia a alternância entre modo claro e escuro
 */

class DarkModeManager {
    constructor() {
        this.themeKey = 'rm-theme';
        this.currentTheme = this.getStoredTheme();
        
        this.init();
    }
    
    init() {
        // Verificar se o tema já foi aplicado no <head>
        const html = document.documentElement;
        const currentDataTheme = html.getAttribute('data-theme');
        if (currentDataTheme && currentDataTheme !== this.currentTheme) {
            // Sincronizar com o tema já aplicado
            this.currentTheme = currentDataTheme;
            this.setStoredTheme(currentDataTheme);
        } else {
            this.applyTheme(this.currentTheme);
        }
        if (document.body && !document.body.getAttribute('data-theme')) {
            document.body.setAttribute('data-theme', this.currentTheme);
        }
        this.createThemeToggle();
        this.setupSystemThemeListener();
    }
    
    getStoredTheme() {
        try {
            const savedTheme = localStorage.getItem(this.themeKey);
            if (savedTheme) {
                return savedTheme;
            }
            // Se não houver tema salvo, detectar preferência do sistema
            return this.getSystemTheme();
        } catch (e) {
            return this.getSystemTheme();
        }
    }
    
    getSystemTheme() {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
        return 'light';
    }
    
    setStoredTheme(theme) {
        try {
            localStorage.setItem(this.themeKey, theme);
        } catch (e) {
            console.warn('Não foi possível salvar o tema:', e);
        }
    }
    
    applyTheme(theme) {
        const html = document.documentElement;

        // Transição suave entre temas
        html.classList.add('rm-theme-transition');
        setTimeout(() => html.classList.remove('rm-theme-transition'), 400);
        
        // Remove classes anteriores
        html.classList.remove('light-theme', 'dark-theme');
        
        // Aplica o tema atual
        if (theme === 'dark') {
            html.setAttribute('data-theme', 'dark');
            html.classList.add('dark-theme');
        } else {
            html.setAttribute('data-theme', 'light');
            html.classList.add('light-theme');
        }

        if (document.body) {
            document.body.setAttribute('data-theme', theme);
        }
        
        this.currentTheme = theme;
        this.setStoredTheme(theme);
        
        // Atualiza meta theme-color
        this.updateMetaThemeColor(theme);
        
        // Dispara evento customizado
        this.dispatchThemeChangeEvent(theme);
    }
    
    toggleTheme() {
        const newTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        this.applyTheme(newTheme);
        return newTheme;
    }
    
    updateMetaThemeColor(theme) {
        const metaThemeColor = document.querySelector('meta[name="theme-color"]');
        if (metaThemeColor) {
            metaThemeColor.content = theme === 'dark' ? '#070d18' : '#003366';
        }
    }
    
    dispatchThemeChangeEvent(theme) {
        const event = new CustomEvent('themeChanged', {
            detail: { theme: theme }
        });
        document.dispatchEvent(event);
    }
    
    createThemeToggle() {
        // Verifica se já existe o toggle
        if (document.getElementById('theme-toggle')) {
            return;
        }
        
        // Cria o botão de toggle
        const toggle = document.createElement('button');
        toggle.id = 'theme-toggle';
        toggle.className = 'theme-toggle topbar-theme-btn';
        toggle.type = 'button';
        toggle.setAttribute('aria-label', 'Alternar tema');
        toggle.setAttribute('title', 'Alternar entre modo claro e escuro');
        
        // Ícone do toggle
        const icon = document.createElement('i');
        icon.className = this.currentTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        toggle.appendChild(icon);
        
        // Adiciona evento de clique
        toggle.addEventListener('click', () => {
            const newTheme = this.toggleTheme();
            const icon = toggle.querySelector('i');
            icon.className = newTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
            
            // Animação do ícone
            icon.style.transform = 'rotate(360deg)';
            setTimeout(() => {
                icon.style.transform = 'rotate(0deg)';
            }, 300);
        });
        
        // Insere o toggle no DOM (barra superior, não flutuante)
        this.insertToggleInDOM(toggle);
    }
    
    insertToggleInDOM(toggle) {
        const topbarNav = document.querySelector('.topbar nav, .topbar__nav');
        if (topbarNav) {
            const anchor = topbarNav.querySelector('.topbar-user-menu') ||
                topbarNav.querySelector('a[href*="logout"]') ||
                topbarNav.lastElementChild;
            if (anchor) {
                topbarNav.insertBefore(toggle, anchor);
            } else {
                topbarNav.appendChild(toggle);
            }
            return;
        }

        toggle.classList.remove('topbar-theme-btn');
        toggle.classList.add('theme-toggle-fab');
        document.body.appendChild(toggle);
    }
    
    setupSystemThemeListener() {
        // Escuta mudanças no tema do sistema
        if (window.matchMedia) {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            
            const handleSystemThemeChange = (e) => {
                // Só aplica se o usuário não tiver escolhido um tema manualmente
                // Verifica se o tema atual é diferente do tema do sistema
                const savedTheme = localStorage.getItem(this.themeKey);
                const systemTheme = e.matches ? 'dark' : 'light';
                
                // Se não houver preferência salva OU se o tema salvo for 'auto' (futuro)
                // então seguir o tema do sistema
                if (!savedTheme || savedTheme === 'auto') {
                    this.applyTheme(systemTheme);
                    // Se estava vazio, salvar a preferência do sistema
                    if (!savedTheme) {
                        this.setStoredTheme(systemTheme);
                    }
                }
            };
            
            mediaQuery.addEventListener('change', handleSystemThemeChange);
        }
    }
    
    // Métodos públicos
    getCurrentTheme() {
        return this.currentTheme;
    }
    
    setTheme(theme) {
        if (['light', 'dark'].includes(theme)) {
            this.applyTheme(theme);
            const toggle = document.getElementById('theme-toggle');
            if (toggle) {
                const icon = toggle.querySelector('i');
                icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
            }
        }
    }
    
    isDarkMode() {
        return this.currentTheme === 'dark';
    }
    
    isLightMode() {
        return this.currentTheme === 'light';
    }
}

// Inicializa o gerenciador de tema quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    window.darkModeManager = new DarkModeManager();
});

// Exporta para uso global
window.DarkModeManager = DarkModeManager;
