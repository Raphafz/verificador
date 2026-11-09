# Relatório CASCAVEL — RM Systems (staging local)

| Campo | Valor |
|--------|--------|
| **Data** | 2026-05-25 |
| **Alvo** | `http://127.0.0.1:8000` (`127.0.0.1:8000`) |
| **Ferramenta** | CASCAVEL v3.0.1 — perfil `web`, `--plugins-only` (55 plugins) |
| **Duração** | ~594 s |
| **JSON bruto** | `reports/cascavel/cascavel-export-20260525-084733/cascavel_20260525_085729.json` |
| **Log** | `reports/cascavel/scan-20260525-084733.log` |

## Resumo executivo

O scan reportou **229 findings** (91 críticos, 97 altos). Após triagem manual contra o código e respostas HTTP reais, a maior parte dos itens **críticos/altos são falsos positivos** típicos de:

- ambiente **HTTP local** (sem TLS/HSTS);
- fuzzing genérico (SSRF/SQLi/SSTI/RCE) sem confirmação de exploit;
- interpretação de **302 (redirect para login)** como “acesso admin sem autenticação”.

**Itens que merecem ação real** concentram-se em endurecimento de **CSP**, ocultação do header **Server**, política de **CDN/allowlist**, e validação em **produção HTTPS** (`CSP_STRICT`, HSTS, CORP/COEP já previstos no middleware quando `request.is_secure()`).

---

## Legenda de prioridade

| Prioridade | Significado |
|------------|-------------|
| **P0** | Corrigir antes de produção |
| **P1** | Corrigir no próximo ciclo de hardening |
| **P2** | Melhoria / aceitar risco documentado |
| **—** | Falso positivo ou só relevante em dev local |

---

## 1. Falsos positivos (não exigem correção de código)

### 1.1 SSL / HSTS (`ssl_check`)

| Severidade CASCAVEL | INFO |
| **Motivo** | Scan em `http://127.0.0.1:8000`; falha `SSL: WRONG_VERSION_NUMBER` é esperada. |
| **Ação** | **—** Em produção, terminar TLS no nginx/ALB e manter `SECURE_SSL_REDIRECT`, `SECURE_HSTS_*` em `saas_viabilidade/settings.py`. |

### 1.2 SQLi (`sqli_scanner` — 4× CRÍTICO)

| Detecção | `erro_detectado: pdo` em parâmetros `id`, `search`, `col`, `field` |
| **Motivo** | A “amostra” é HTML da página inicial (`<!DOCTYPE html>`), não erro de banco. O matcher confundiu substring `pdo` no HTML. |
| **Ação** | **—** Manter ORM Django, prepared statements e revisão de queries raw. Opcional: rodar testes `core/tests_*_security.py`. |

### 1.3 SSRF (`ssrf_scanner` — 62× CRÍTICO/ALTO)

| Detecção | Payloads em params genéricos (`url`, `link`, `src`, …) → metadata AWS / serviços internos |
| **Motivo** | Fuzzer envia payloads; não há evidência de endpoint da aplicação que **busque URL arbitrária** e retorne metadata. |
| **Ação** | **—** Auditar manualmente views que aceitam URL (webhooks, import, proxy). Se existirem, validar allowlist + bloqueio de IPs privados/metadata. |

### 1.4 SSTI / RCE / Blind RCE / XSS blind

| Plugins | `ssti_scanner`, `rce_scanner`, `blind_rce`, `xss_scanner`, `waf_bypass` |
| **Motivo** | Injeção de payloads OOB/refletidos **sem callback confirmado** nem execução comprovada. |
| **Ação** | **—** Garantir escape em templates Django (`{{ }}` auto-escape), nunca `mark_safe` em input de usuário, validar uploads. |

### 1.5 IDOR admin (`idor_scanner` — 2× CRÍTICO)

| Endpoints | `/admin/dashboard`, `/admin/users` |
| **Verificação** | `curl` retorna **302** (redirect para login), não 200 com dados. |
| **Ação** | **—** CASCAVEL não diferenciou redirect de acesso. Manter `@login_required` / middleware de tenant. |

### 1.6 Rate limit em login/registro (`password_policy`)

| Detecção | `/login` sem rate limit; dezenas de paths `/register`, `/api/v1/register`, etc. |
| **Motivo** | Muitos paths **não existem** (404/redirect); login **já tem** `@login_rate_limit` em `core/views.py` (`core/rate_limiting.py`: 20 tentativas / 15 min). DRF usa `core/throttling.py` nas APIs. |
| **Ação** | **P2** Validar se o limiter de login dispara em teste de força bruta; reforçar com nginx `limit_req` em produção. |

### 1.7 Admin exposto (`admin_finder`)

| Achado | `/admin/login` responde 302 com headers de segurança |
| **Motivo** | Django Admin é intencional; já há `X-Frame-Options: DENY`, CSP, MFA (django-otp) no projeto. |
| **Ação** | **P2** Em produção: restringir `/admin/` por IP/VPN, URL não padrão, MFA obrigatório. |

---

## 2. Achados reais ou parcialmente reais

> **Atualização 2026-05-25 (hardening v2):** CSP estrito por padrão, CRLF bloqueado, rate limit em login, PUT/DELETE só em `/api/`, header `Server` removido via WSGI, nonces em 32+ templates, SRI nos CDNs. Reinicie o `runserver` antes de validar.

### 2.1 CSP — `unsafe-inline` (ALTO) — **P0 em produção**

| Fonte | `security_headers`, `csp_bypass` |
| **Evidência** | Header real: `script-src ... 'unsafe-inline' ...` e `style-src-attr 'unsafe-inline'`. |
| **Causa** | Em `core/security_headers.py`, com `DEBUG=True` ou sem `CSP_STRICT`, a política relaxa para desenvolvimento (linhas 34–47). |
| **Correção** | 1. Em **produção**: `DEBUG=False`, `CSP_STRICT=True` (já suportado em `settings.py`). Isso ativa `strict-dynamic` + nonce e remove `unsafe-inline` em `script-src`. 2. Migrar scripts inline para arquivos estáticos ou tags com `nonce="{{ request.csp_nonce }}"`. 3. Reduzir `style-src-attr 'unsafe-inline'` usando classes CSS em vez de `style=""` inline. |
| **Verificação** | `python manage.py check_security` / testes `core/tests_phase4_security.py` (CSP strict). |

### 2.2 CSP — `img-src ... https:` (CRÍTICO no scanner) — **P1**

| Fonte | `CSP_WILDCARD` / `security_headers` |
| **Evidência** | `img-src 'self' data: blob: ... https:` — qualquer host HTTPS pode carregar imagens. |
| **Correção** | Substituir `https:` por hosts explícitos (CDN, tiles OSM, domínio da empresa). Exemplo em `build_content_security_policy()`: listar apenas `https://tile.openstreetmap.org` etc., sem curinga global. |
| **Risco** | Exfiltração via `<img src=https://evil.com/...>` se houver XSS. |

### 2.3 CSP — CDNs e JSONP (`csp_bypass` — vários CRÍTICOS) — **P1**

| Fonte | `cdn.jsdelivr.net`, `cdnjs.cloudflare.com`, `unpkg.com`, `*.googleapis.com` |
| **Motivo** | CDNs amplos permitem cenários de bypass de CSP se houver XSS (vetores JSONP legados). |
| **Correção** | 1. Usar **SRI** (`integrity=`) em `<script src>` de CDN. 2. Reduzir CDNs ao mínimo; preferir assets em `static/`. 3. Em produção com `strict-dynamic`, scripts com nonce não dependem de allowlist larga. 4. Documentar exceção em política de segurança. |

### 2.4 CSP — `data:` / `blob:` (MÉDIO) — **P2**

| Fonte | `font-src`, `img-src`, `worker-src` |
| **Correção** | Manter apenas se necessário (ícones, workers, mapas). Restringir `data:` a diretivas específicas se possível. |

### 2.5 Header `Server` exposto (BAIXO) — **P1**

| Valor | `WSGIServer/0.2 CPython/3.14.4` |
| **Correção** | Em produção, servir via **gunicorn/uvicorn + nginx** e usar `server_tokens off;` (nginx) ou `uvicorn --no-server-header`. Não expor versão Python no edge. |
| **Código** | Opcional: middleware que remove/sobrescreve `Server` em respostas Django. |

### 2.6 Headers CORP / COEP / DNS-Prefetch (BAIXO/INFO) — **P2 / só HTTPS**

| Achados | `MISSING_CROSS_ORIGIN_*`, `MISSING_X_DNS_PREFETCH_CONTROL` |
| **Estado** | `core/security_headers.py` já define **COOP/CORP/COEP** quando `request.is_secure()` (linhas 111–115). Em HTTP local não aparecem. |
| **Correção** | **P2** Adicionar `X-DNS-Prefetch-Control: off` em todas as respostas. Testar COEP em staging HTTPS (pode quebrar CDNs/embeds). |

### 2.7 Métodos HTTP perigosos (`http_methods` — ALTO) — **P2**

| Paths | `/`, `/api/`, `/admin/`, `/upload/` aceitam PUT, DELETE, TRACE, CONNECT |
| **Motivo** | `runserver` do Django é permissivo; em produção o proxy costuma bloquear TRACE. |
| **Correção** | No nginx: `limit_except GET POST HEAD { deny all; }` e bloquear TRACE. Opcional: middleware Django rejeitando métodos não usados nas rotas. |

### 2.8 Clickjacking — conflito XFO vs CSP (BAIXO) — **—**

| Achado | `XFO_CSP_CONFLICT` — XFO=DENY mas CSP “mais permissivo” |
| **Estado** | `frame-ancestors 'none'` na CSP alinha com anti-clickjacking; falso alarme de “conflito”. |
| **Ação** | Nenhuma obrigatória. |

### 2.9 CORS (`cors_checker`)

| Resultado | “CORS configurado corretamente” |
| **Ação** | Manter revisão em APIs novas (`CORS_ALLOWED_ORIGINS` em produção). |

---

## 3. Matriz consolidada (ação recomendada)

| # | Tema | Severidade scan | Prioridade real | Ação resumida |
|---|------|-----------------|-----------------|---------------|
| 1 | TLS/HSTS | INFO | — | HTTPS em produção |
| 2 | SQLi/SSRF/SSTI/RCE | CRÍTICO | — | Triagem; sem exploit confirmado |
| 3 | IDOR admin | CRÍTICO | — | 302 login; OK |
| 4 | CSP unsafe-inline | ALTO | **P0** | `CSP_STRICT=True` + nonces em prod |
| 5 | CSP img `https:` | CRÍTICO* | **P1** | Allowlist explícita |
| 6 | CSP CDNs | CRÍTICO* | **P1** | SRI + menos CDNs + strict-dynamic |
| 7 | Server header | BAIXO | **P1** | nginx / proxy |
| 8 | Rate limit login | ALTO | **P2** | Já existe; testar + nginx |
| 9 | HTTP TRACE/PUT | ALTO | **P2** | Bloquear no proxy |
| 10 | CORP/COEP/DNS | BAIXO | **P2** | HTTPS + header DNS |

\* Severidade do scanner; risco efetivo depende de XSS prévio.

---

## 4. Checklist de implementação (produção)

```bash
# .env produção (exemplo)
DEBUG=False
CSP_STRICT=True
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

1. **Deploy HTTPS** com HSTS (`SECURE_HSTS_SECONDS` já configurado quando `IS_PRODUCTION`).
2. **Ativar CSP estrita** — conferir header sem `'unsafe-inline'` em `script-src`.
3. **Restringir `img-src`** — remover curinga `https:`.
4. **nginx** — `server_tokens off`, `limit_req` no login, bloquear TRACE.
5. **Admin** — MFA obrigatório, restrição de rede.
6. **Re-scan** após deploy staging HTTPS:
   ```powershell
   $env:BASE_URL = "https://staging.seudominio.com"
   .\scripts\run-cascavel-staging.ps1
   ```

---

## 5. Referências no repositório

| Arquivo | Conteúdo |
|---------|----------|
| `core/security_headers.py` | CSP, XFO, Permissions-Policy, HSTS/COEP em HTTPS |
| `saas_viabilidade/settings.py` | `CSP_STRICT`, cookies, HSTS, `SECURE_*` |
| `core/rate_limiting.py` | `login_rate_limit` |
| `core/throttling.py` | Throttle DRF |
| `scripts/run-cascavel-staging.ps1` | Orquestração do scan |
| `docs/security/targets-rmsys.txt` | URLs sugeridas (scan por host; paths exigem ferramenta com crawl) |

---

## 6. Nota sobre o script PowerShell

O scan **gerou o JSON com sucesso**; o exit code `1` ocorreu porque o menu pós-scan recebeu `0` com BOM (`﻿0`) no pipe. Correção sugerida no script: usar `cmd /c echo 0` ou arquivo ASCII sem BOM. O relatório JSON **não foi afetado**.

---

---

## 7. Re-scan pós-hardening (2026-05-25)

### Comparativo de scans

| Métrica | Inicial (`085729`) | Hardening 1 (`092646`) | **Hardening v2 (`095628`)** |
|---------|-------------------|------------------------|----------------------------|
| Total findings | 229 | 223 | **201** |
| CRÍTICO | 91 | 87 | **79** |
| ALTO | 97 | 97 | **73** |
| MÉDIO | 28 | 28 | **22** |
| BAIXO | 7 | 6 | 20 |
| INFO | 6 | 5 | 7 |

**Δ total (inicial → v2):** **−28 findings** (−12 críticos, −24 altos).

**Plugins com melhora real:**

| Plugin | Inicial | v2 |
|--------|---------|-----|
| `security_headers` | 8 | **2** |
| `csp_bypass` | 60 | **45** |
| `sqli_scanner` | 4 | **2** |
| `crlf_scanner` | 1 (CRÍTICO) | **0** (limpo) |

**JSON v2:** `reports/cascavel/cascavel-export-20260525-094318/cascavel_20260525_095628.json`

**CSP no servidor (validado):** `script-src` com `strict-dynamic` + nonce, **sem** `unsafe-inline`.

**Plugin `security_headers` (scan 1):** 8 → **6** achados.

| Finding | Antes | Depois |
|---------|-------|--------|
| `MISSING_X_DNS_PREFETCH_CONTROL` | Sim | **Corrigido** |
| `MISSING_CROSS_ORIGIN_RESOURCE_POLICY` | Sim | **Corrigido** (CORP em HTTP) |
| `MISSING_CROSS_ORIGIN_EMBEDDER_POLICY` | Sim | Ainda (só com HTTPS pleno) |
| `DISCLOSURE_SERVER` | Sim | Ainda no `runserver` (gunicorn/nginx em prod) |
| `CSP_WILDCARD` (curinga `https:`) | Sim | **Corrigido** no header; scanner ainda marca `*.tile.openstreetmap.org` e CDNs |
| `CSP_UNSAFE_INLINE` | Sim | Ainda em **dev** (`DEBUG=True`); produção: `CSP_STRICT=true` |

**SRI:** tags CDN centralizadas em `templates/includes/cdn_*.html` (34 templates).

**JSON pós-correção:** `reports/cascavel/cascavel-export-20260525-091656/cascavel_20260525_092646.json`

Para validar após reiniciar o servidor:

```powershell
py manage.py runserver
.\scripts\run-cascavel-staging.ps1
```

### Expectativa realista do scanner

Mesmo com o código corrigido, o CASCAVEL **continuará reportando** dezenas de itens em `127.0.0.1:8000` porque:

- **SSRF/SSTI/RCE/blind_rce** (100+): fuzzing genérico sem exploit confirmado no Django.
- **csp_bypass**: alertas teóricos sobre CDNs allowlisted (mitigados com SRI + `strict-dynamic`).
- **password_policy**: paths `/register` inexistentes; login tem rate limit (`AuthRateLimitMiddleware` + `login_limiter`).
- **ssl_check**: HTTP local sem TLS.
- **admin_finder**: `/admin/login` é funcionalidade esperada.

Isso **não significa** vulnerabilidades abertas — triagem manual continua obrigatória.

---

## 9. Perfil `rmsys` + assets locais (2026-05-25)

| Métrica | Scan web (55 plugins) | **Scan `rmsys` (17 plugins)** |
|---------|----------------------|-------------------------------|
| Total | 201 | **67** |
| CRÍTICO | 79 | **15** |
| Duração | ~586 s | **~112 s** |

**Mudanças:**
- Perfil `tools/Cascavel/profiles/rmsys.yaml` (padrão em `run-cascavel-staging.ps1`)
- Bootstrap, Chart.js, Leaflet em `static/vendor/` (`scripts/download-vendor-static.ps1`)
- CSP: `script-src` só `'self'` + nonce + `strict-dynamic` (sem jsDelivr/unpkg)
- Menu CASCAVEL: `echo 0|` via `cmd` (exit 0)

**JSON:** `reports/cascavel/cascavel-export-20260525-101425/cascavel_20260525_101620.json`

Scan completo (fuzzing): `$env:PROFILE='web'; .\scripts\run-cascavel-staging.ps1`

---

## 8. Correções implementadas (código)

| Item | Arquivo / ação |
|------|----------------|
| CSP `strict-dynamic` + nonce (sem `unsafe-inline` em scripts) | `core/security_headers.py`, `CSP_STRICT=true` padrão |
| `img-src` sem `https:` curinga | Allowlist OSM + CDNs explícitos |
| COEP + CORP + DNS-Prefetch | `SecurityHeadersMiddleware` |
| CRLF em URL | `core/middleware_crlf.py` |
| TRACE/CONNECT + PUT/DELETE fora de `/api/` | `core/middleware_http_methods.py` |
| Rate limit login (sempre) | `core/middleware_auth_rate_limit.py` |
| Anti-bypass `X-Forwarded-For` | `core/rate_limiting.py`, `TRUST_X_FORWARDED_FOR=false` |
| Remover `Server` | `saas_viabilidade/wsgi_security.py` + middleware |
| SRI + nonce CDN | `templates/includes/cdn_*.html` |
| Nonce em scripts inline | `scripts/add_csp_nonce_to_templates.py` (32 arquivos) |

---

*Relatório gerado após triagem manual do JSON CASCAVEL e validação HTTP com `curl` contra `127.0.0.1:8000`.*
