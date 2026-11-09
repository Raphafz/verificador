# BIMI — logo no perfil do remetente (Gmail)

Guia para exibir o ícone RM ao lado de `noreply@rmsys.com.br` na caixa de entrada.

## Pré-requisitos

1. Domínio **rmsys.com.br** verificado no [Resend](https://resend.com/domains) (SPF + DKIM ativos).
2. Site em **HTTPS** (ex.: `https://rmsys.com.br`).
3. Logo BIMI publicado em:
   ```
   https://rmsys.com.br/.well-known/bimi/logo.svg
   ```
   (rota já configurada neste projeto)

## Passo 1 — Regenerar o logo (obrigatório se o validador acusar "Image Format Incorrect")

O BIMI **não aceita** SVG com `<image href="data:...">` (PNG embutido). O arquivo deve ser **vetor puro** (`baseProfile="tiny-ps"`, só `<path>` / `<rect>`).

```bash
pip install opencv-python-headless   # só para gerar o SVG (dev/CI)
python scripts/generate_bimi_logo.py
```

Depois publique o novo `static/well-known/bimi/logo.svg` (deploy ou upload na Hostinger).

## Passo 2 — DNS na Hostinger (ou seu provedor)

Substitua `rmsys.com.br` se usar outro domínio de envio.

### SPF (se ainda não tiver via Resend)

O Resend fornece o registro SPF ao verificar o domínio. Mantenha **apenas um** TXT em `@` com SPF.

### DKIM

Copie do painel Resend (geralmente `resend._domainkey`).

### DMARC (obrigatório para BIMI)

| Tipo | Nome / Host | Valor |
|------|-------------|--------|
| TXT | `_dmarc` | `v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@rmsys.com.br; fo=1; adkim=s; aspf=s` |

Depois de 2–4 semanas estáveis, pode endurecer para `p=reject`.

### BIMI

| Tipo | Nome / Host | Valor |
|------|-------------|--------|
| TXT | `default._bimi` | `v=BIMI1; l=https://rmsys.com.br/.well-known/bimi/logo.svg;` |

> **VMC (certificado)** — opcional. Gmail pode exibir o logo **sem** VMC se DMARC estiver correto; o certificado VMC (~US$ 1.500/ano) aumenta compatibilidade em outros clientes.

## Passo 3 — Conferir

1. Abra no navegador: `https://rmsys.com.br/.well-known/bimi/logo.svg` — deve mostrar o ícone RM quadrado.
2. Use [BIMI Group Inspector](https://bimigroup.org/bimi-generator/) ou [MXToolbox BIMI](https://mxtoolbox.com/bimi.aspx) para validar DNS.
3. Envie e-mail de teste:
   ```bash
   python manage.py test_resend_email --password-reset --company fibramar --to SEU@gmail.com --email fibramar@email.com
   ```
4. O Gmail pode levar **até 48–72 h** após DNS propagar para mostrar o logo no perfil.

## Registros completos (copiar/colar)

```
# DMARC
_dmarc.rmsys.com.br.  IN  TXT  "v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@rmsys.com.br; fo=1; adkim=s; aspf=s"

# BIMI
default._bimi.rmsys.com.br.  IN  TXT  "v=BIMI1; l=https://rmsys.com.br/.well-known/bimi/logo.svg;"
```

## Troubleshooting

| Problema | Solução |
|----------|---------|
| **BIMI Image Format Incorrect** | Rode `python scripts/generate_bimi_logo.py` e republique o SVG vetorial |
| Logo não aparece no Gmail | Confirme DMARC `p=quarantine` ou `reject`; aguarde propagação DNS |
| URL do logo retorna timeout / ERR_CONNECTION_TIMED_OUT | O domínio não aponta para servidor web — veja seção abaixo |
| Silhueta genérica continua | BIMI ≠ imagem no corpo do e-mail; só afeta o avatar do remetente |
| Logo sumiu no mobile | Normal até BIMI propagar; corpo do e-mail usa só o letreiro |

## Domínio não abre (timeout) — o que fazer

O e-mail usa `@rmsys.com.br`, mas o **site** desse domínio precisa responder em HTTPS para o BIMI funcionar.

### Opção A — VPS com o SaaS (recomendado)

Na **Hostinger → DNS** do domínio `rmsys.com.br`:

| Tipo | Nome | Valor |
|------|------|--------|
| A | `@` | IP da sua VPS |
| A | `www` | IP da sua VPS |

No servidor, após deploy:

```bash
python manage.py collectstatic --noinput
sudo certbot --nginx -d rmsys.com.br -d www.rmsys.com.br
```

Teste: `https://rmsys.com.br/.well-known/bimi/logo.svg`

### Opção B — Só o logo (sem app completo)

Se ainda não fez deploy do Django, na Hostinger **Hospedagem de sites**:

1. Crie a pasta `public_html/.well-known/bimi/`
2. Envie o arquivo `static/well-known/bimi/logo.svg` do projeto
3. Ative SSL gratuito no domínio
4. Teste a URL no navegador

### Opção C — DNS em parking

Se os nameservers forem `dns-parking.com`, troque para os da Hostinger ou aponte registros A para o servidor correto. Enquanto o domínio estiver em parking, **nenhuma URL** `https://rmsys.com.br/...` vai funcionar.
