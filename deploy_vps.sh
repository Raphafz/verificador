#!/bin/bash
# Script de deploy para VPS Hostinger
# Execute este script como o usuário da aplicação (não root)

set -e

echo "=========================================="
echo "🚀 Deploy - VPS Hostinger"
echo "=========================================="

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Diretório da aplicação
APP_DIR="/var/www/saas-viabilidade"
cd "$APP_DIR"

# Verificar se o arquivo .env existe
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️ Arquivo .env não encontrado!${NC}"
    echo "Executando setup de variáveis de ambiente..."
    if [ -f "setup-env.sh" ]; then
        bash setup-env.sh
    else
        echo -e "${RED}❌ Arquivo setup-env.sh não encontrado!${NC}"
        echo "Por favor, crie o arquivo .env manualmente baseado no .env.example.vps"
        exit 1
    fi
    
    # Verificar novamente se foi criado
    if [ ! -f ".env" ]; then
        echo -e "${RED}❌ Falha ao criar arquivo .env!${NC}"
        exit 1
    fi
fi

# Carregar variáveis de ambiente do .env (apenas as que não começam com #)
# Usar source ao invés de export para manter compatibilidade
set -a
source .env 2>/dev/null || export $(grep -v '^#' .env | grep -v '^$' | xargs)
set +a

# 1. Ativar ambiente virtual
echo -e "${GREEN}🐍 Ativando ambiente virtual...${NC}"
if [ ! -d "venv" ]; then
    python3.11 -m venv venv
fi
source venv/bin/activate

# 2. Atualizar pip
echo -e "${GREEN}📦 Atualizando pip...${NC}"
pip install --upgrade pip

# 3. Instalar/atualizar dependências
echo -e "${GREEN}📦 Instalando dependências...${NC}"
pip install -r requirements.txt

# 4. Executar migrações
echo -e "${GREEN}🗄️ Executando migrações...${NC}"
python manage.py migrate --noinput

# 5. Coletar arquivos estáticos
echo -e "${GREEN}📦 Coletando arquivos estáticos...${NC}"
python manage.py collectstatic --noinput --clear

# 6. Criar diretório de mídia se não existir
echo -e "${GREEN}📁 Verificando diretório de mídia...${NC}"
mkdir -p media
mkdir -p Mapas/kml Mapas/kmz Mapas/csv Mapas/xls Mapas/xlsx

# 7. Reiniciar serviços
echo -e "${GREEN}🔄 Reiniciando serviços...${NC}"
sudo systemctl restart gunicorn
sudo systemctl restart nginx

echo "=========================================="
echo -e "${GREEN}✅ Deploy concluído!${NC}"
echo "=========================================="

