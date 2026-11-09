ls#!/bin/bash
# Script de setup inicial para VPS Hostinger
# Execute este script como root ou com sudo

set -e

echo "=========================================="
echo "🚀 Setup Inicial - VPS Hostinger"
echo "=========================================="

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verificar se está rodando como root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}❌ Por favor, execute este script com sudo${NC}"
    exit 1
fi

# 1. Atualizar sistema
echo -e "${GREEN}📦 Atualizando sistema...${NC}"
apt-get update
apt-get upgrade -y

# 2. Instalar dependências básicas
echo -e "${GREEN}📦 Instalando dependências...${NC}"
apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    postgresql \
    postgresql-contrib \
    nginx \
    git \
    curl \
    build-essential \
    libpq-dev \
    python3-dev \
    supervisor \
    certbot \
    python3-certbot-nginx \
    ufw

# 3. Configurar PostgreSQL
echo -e "${GREEN}🗄️ Configurando PostgreSQL...${NC}"
systemctl start postgresql
systemctl enable postgresql

# 4. Criar usuário e banco de dados (ajuste conforme necessário)
read -p "Digite o nome do banco de dados: " DB_NAME
read -p "Digite o usuário do banco de dados: " DB_USER
read -sp "Digite a senha do banco de dados: " DB_PASSWORD
echo

sudo -u postgres psql <<EOF
CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
ALTER USER ${DB_USER} CREATEDB;
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
\q
EOF

echo -e "${GREEN}✅ PostgreSQL configurado${NC}"

# 5. Configurar Firewall (UFW)
echo -e "${GREEN}🔥 Configurando firewall...${NC}"
ufw allow 'Nginx Full'
ufw allow OpenSSH
ufw --force enable
echo -e "${GREEN}✅ Firewall configurado${NC}"

# 6. Criar usuário para aplicação (se não existir)
read -p "Digite o nome do usuário para a aplicação (ex: appuser): " APP_USER
if ! id "$APP_USER" &>/dev/null; then
    useradd -m -s /bin/bash $APP_USER
    echo -e "${GREEN}✅ Usuário $APP_USER criado${NC}"
else
    echo -e "${YELLOW}⚠️ Usuário $APP_USER já existe${NC}"
fi

# 7. Criar estrutura de diretórios
echo -e "${GREEN}📁 Criando estrutura de diretórios...${NC}"
mkdir -p /var/www/saas-viabilidade
mkdir -p /var/www/saas-viabilidade/media
mkdir -p /var/www/saas-viabilidade/staticfiles
mkdir -p /var/log/gunicorn
chown -R $APP_USER:$APP_USER /var/www/saas-viabilidade
chown -R $APP_USER:$APP_USER /var/log/gunicorn
echo -e "${GREEN}✅ Diretórios criados${NC}"

# 8. Salvar informações em arquivo temporário
cat > /tmp/vps_setup_info.txt <<EOF
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
APP_USER=${APP_USER}
EOF

echo "=========================================="
echo -e "${GREEN}✅ Setup inicial concluído!${NC}"
echo "=========================================="
echo ""
echo "📝 Informações salvas em /tmp/vps_setup_info.txt"
echo ""
echo "Próximos passos:"
echo "1. Clone o repositório em /var/www/saas-viabilidade"
echo "2. Configure o arquivo .env com as informações do banco"
echo "3. Execute o script deploy_vps.sh"
echo ""
echo "Informações do banco:"
echo "  Nome: ${DB_NAME}"
echo "  Usuário: ${DB_USER}"
echo "  Senha: (configurada acima)"
echo ""

