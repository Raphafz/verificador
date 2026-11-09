# Deploy na VPS Hostinger

Hospedagem prevista: **VPS Linux** com Nginx, Gunicorn e PostgreSQL.

## Arquivos de deploy

| Arquivo | Uso |
|---------|-----|
| `setup_vps.sh` | Instala dependências do sistema (primeira vez) |
| `setup-env.sh` | Cria `.env` na VPS |
| `deploy_vps.sh` | Atualiza código, migrações, estáticos, reinicia Gunicorn |
| `nginx.conf` | Site Nginx (ajuste `server_name` e caminhos) |
| `gunicorn.service` | Serviço systemd |
| `gunicorn_config.py` | Workers e timeout |
| `backup-db.sh` | Backup PostgreSQL |

## Variáveis no `.env` (produção)

```env
VPS_ENVIRONMENT=true
DEBUG=False
SECRET_KEY=sua-chave-forte
ALLOWED_HOSTS=rmsys.app,www.rmsys.app
CSRF_TRUSTED_ORIGINS=https://rmsys.app,https://www.rmsys.app
SITE_DOMAIN=rmsys.app
DATABASE_URL=postgresql://usuario:senha@localhost:5432/saas_viabilidade
VPS_MEDIA_ROOT=/var/www/saas-viabilidade/media
```

## Primeiro deploy

```bash
ssh usuario@seu-servidor
cd /var/www
git clone <repo> saas-viabilidade
cd saas-viabilidade
sudo ./setup_vps.sh          # uma vez
bash setup-env.sh && nano .env
sudo cp nginx.conf /etc/nginx/sites-available/saas-viabilidade
sudo ln -s /etc/nginx/sites-available/saas-viabilidade /etc/nginx/sites-enabled/
sudo cp gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable gunicorn
./deploy_vps.sh
sudo certbot --nginx -d rmsys.app -d www.rmsys.app
```

## Atualizar após mudanças no código

```bash
cd /var/www/saas-viabilidade
git pull
./deploy_vps.sh
```

## Arquivos estáticos (404 de CSS/JS)

```bash
source venv/bin/activate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
```

WhiteNoise está no `settings.py`; o Nginx também pode servir `/static/` de `staticfiles/`.

## Mídia (mapas CTO)

Mapas ficam em `VPS_MEDIA_ROOT`. **Não** sirva `/media/` como `alias` público no Nginx — isso expõe mapas CTO sem login.

O `nginx.conf` deste repositório faz **proxy** de `/media/` para o Gunicorn; o Django aplica autenticação e isolamento por empresa (`core/media_protected.py`).

Confirme após deploy:

```bash
curl -I https://seu-dominio/media/cto_maps/1/exemplo.kml
# Deve retornar 302/403 (não 200 público)
python manage.py check_security --deploy
```

## Settings Django

Use **apenas** `saas_viabilidade.settings` (via `manage.py`, `wsgi.py`, Gunicorn). O arquivo `settings_production.py` é **legado** — não use em produção.

## OLT multi-tenant (VPN)

Com mais de um ISP na mesma VPS, use worker em container:

```env
OLT_EXECUTION_MODE=container
```

Ver `docs/deploy/OLT_WORKER.md`.

## CSRF 403

Defina `CSRF_TRUSTED_ORIGINS` com `https://` no domínio real. O Django também gera origens a partir de `ALLOWED_HOSTS`.

## Checklist

- [ ] PostgreSQL rodando e `DATABASE_URL` correta
- [ ] `DEBUG=False` e `SECRET_KEY` forte
- [ ] `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` com seu domínio
- [ ] `collectstatic` executado
- [ ] Gunicorn e Nginx ativos
- [ ] SSL (Let's Encrypt)
- [ ] Pasta `media` com permissão para o usuário do Gunicorn
