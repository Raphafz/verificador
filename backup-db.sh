#!/bin/bash
# Script de backup do banco de dados para VPS
# Use com crontab para backups automáticos
# P3: criptografia GPG opcional — defina BACKUP_GPG_PASSPHRASE_FILE no .env

set -e

# Configurações
BACKUP_DIR="/var/backups/saas-viabilidade"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

# Carregar DATABASE_URL do .env
ENV_FILE="${ENV_FILE:-/var/www/saas-viabilidade/.env}"
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Arquivo .env não encontrado: $ENV_FILE"
    exit 1
fi

export $(grep -v '^#' "$ENV_FILE" | grep -E '^(DATABASE_URL|BACKUP_GPG_PASSPHRASE_FILE)=' | xargs)

if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL não configurada no .env"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

BACKUP_FILE="$BACKUP_DIR/backup_$DATE.sql.gz"
echo "📦 Iniciando backup do banco de dados..."
echo "   Arquivo: $BACKUP_FILE"

if pg_dump "$DATABASE_URL" | gzip > "$BACKUP_FILE"; then
    echo "✅ Backup criado: $BACKUP_FILE"
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "   Tamanho: $SIZE"

    # Criptografia GPG (P3)
    if [ -n "$BACKUP_GPG_PASSPHRASE_FILE" ] && [ -f "$BACKUP_GPG_PASSPHRASE_FILE" ]; then
        if command -v gpg >/dev/null 2>&1; then
            GPG_OUT="${BACKUP_FILE}.gpg"
            gpg --batch --yes --passphrase-file "$BACKUP_GPG_PASSPHRASE_FILE" \
                -c -o "$GPG_OUT" "$BACKUP_FILE"
            rm -f "$BACKUP_FILE"
            BACKUP_FILE="$GPG_OUT"
            echo "🔐 Backup criptografado: $BACKUP_FILE"
        else
            echo "⚠️ gpg não instalado — backup permanece apenas compactado"
        fi
    fi

    echo "🗑️ Removendo backups antigos (> $RETENTION_DAYS dias)..."
    find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR" -name "backup_*.sql.gz.gpg" -mtime +$RETENTION_DAYS -delete

    echo ""
    echo "📋 Backups recentes:"
    ls -lh "$BACKUP_DIR"/backup_* 2>/dev/null | tail -5 || echo "   Nenhum backup encontrado"
    exit 0
else
    echo "❌ Erro ao criar backup!"
    exit 1
fi
