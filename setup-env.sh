#!/bin/bash
# Script para configurar variáveis de ambiente na VPS
# Este script ajuda a criar o arquivo .env a partir do .env.example.vps

set -e

APP_DIR="/var/www/saas-viabilidade"
ENV_FILE="$APP_DIR/.env"
ENV_EXAMPLE="$APP_DIR/.env.example.vps"

echo "=========================================="
echo "🔧 Configuração de Variáveis de Ambiente"
echo "=========================================="
echo ""

# Verificar se está no diretório correto
if [ ! -d "$APP_DIR" ]; then
    echo "❌ Diretório da aplicação não encontrado: $APP_DIR"
    exit 1
fi

cd "$APP_DIR"

# Verificar se .env já existe
if [ -f "$ENV_FILE" ]; then
    echo "⚠️ Arquivo .env já existe!"
    read -p "Deseja sobrescrever? (s/N): " OVERWRITE
    if [[ ! "$OVERWRITE" =~ ^[Ss]$ ]]; then
        echo "✅ Mantendo arquivo .env existente"
        exit 0
    fi
    # Fazer backup do .env existente
    cp "$ENV_FILE" "$ENV_FILE.backup.$(date +%Y%m%d_%H%M%S)"
    echo "📦 Backup do .env criado"
fi

# Verificar se .env.example.vps existe
if [ ! -f "$ENV_EXAMPLE" ]; then
    echo "❌ Arquivo .env.example.vps não encontrado!"
    echo "Criando arquivo básico..."
    cat > "$ENV_EXAMPLE" <<'EOF'
# Configurações para VPS Hostinger
SECRET_KEY=
DEBUG=False
IS_LOCAL_DEV=False

ALLOWED_HOSTS=
CSRF_TRUSTED_ORIGINS=

DATABASE_URL=
DB_CONN_MAX_AGE=600

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=
SERVER_EMAIL=

OPENROUTESERVICE_API_KEY=
ROUTING_TIMEOUT=15
VIABILIDADE_VIABLE=300
VIABILIDADE_LIMITADA=800
VIABILIDADE_INVIAVEL=800
EOF
fi

# Copiar exemplo
cp "$ENV_EXAMPLE" "$ENV_FILE"
echo "✅ Arquivo .env criado a partir do exemplo"
echo ""

# Gerar SECRET_KEY se não existir
if ! grep -q "^SECRET_KEY=.*[^=]$" "$ENV_FILE" || grep -q "^SECRET_KEY=$" "$ENV_FILE"; then
    echo "🔑 Gerando SECRET_KEY..."
    SECRET_KEY=$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
    if [ -z "$SECRET_KEY" ]; then
        # Fallback caso Python não esteja disponível
        SECRET_KEY=$(openssl rand -base64 50 | tr -d "=+/" | cut -c1-50)
    fi
    sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" "$ENV_FILE"
    echo "✅ SECRET_KEY gerada e configurada"
fi

# Configurar permissões
chmod 600 "$ENV_FILE"
chown appuser:appuser "$ENV_FILE" 2>/dev/null || chown $USER:$USER "$ENV_FILE" 2>/dev/null
echo "✅ Permissões configuradas"
echo ""

echo "=========================================="
echo "📝 Próximos passos:"
echo "=========================================="
echo ""
echo "1. Edite o arquivo .env com suas configurações:"
echo "   nano $ENV_FILE"
echo ""
echo "2. Configure pelo menos estas variáveis:"
echo "   - SECRET_KEY (já gerada)"
echo "   - ALLOWED_HOSTS (ex: seu-dominio.com,www.seu-dominio.com)"
echo "   - CSRF_TRUSTED_ORIGINS (ex: https://seu-dominio.com,https://www.seu-dominio.com)"
echo "   - DATABASE_URL (ex: postgresql://user:pass@localhost:5432/dbname)"
echo "   - Configurações de EMAIL"
echo ""
echo "3. Após configurar, reinicie o Gunicorn:"
echo "   sudo systemctl restart gunicorn"
echo ""
echo "=========================================="

