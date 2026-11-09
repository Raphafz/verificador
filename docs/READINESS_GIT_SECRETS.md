# READINESS — Git Secrets (Auditoria Histórica)

> **Modo:** READ ONLY — nenhum histórico alterado  
> **Data:** 25/05/2026  
> **Remote:** `origin` → `https://github.com/castrox-dev/Saas-Verificador-de-Viabilidade.git`

---

## 1. Resumo executivo

| Achado | Classificação |
|--------|---------------|
| `.env` commitado no histórico Git | **CONFIRMADO** |
| `.env` presente em `origin/main` atual | **NÃO ENCONTRADO** (removido) |
| Segredos ainda recuperáveis via histórico | **CONFIRMADO** |
| `.env` local no workspace | **NÃO ENCONTRADO** |
| `.env` tracked atualmente | **NÃO ENCONTRADO** |
| Stashes com segredos | **NÃO ENCONTRADO** |

**Veredicto:** vazamento histórico **confirmado e crítico**. Remoção no commit `70e71e4` **não apaga** segredos do GitHub — qualquer clone com histórico completo ou `git show <commit>:.env` ainda expõe credenciais.

---

## 2. Evidências — `.env` no Git

### Commits que tocaram `.env` (11 total)

| Commit | Data | Mensagem |
|--------|------|----------|
| `dc29e12` | 2025-10-23 | atualizações (**primeiro .env**) |
| `21addbf` | 2025-10-24 | Toma quietinho |
| `2ad988b` | 2025-05-20 | PORRAAAAAAAAAA |
| `248e5c7` | 2025-05-21 | atualicaçaos |
| `09a1ac4` | 2025-05-21 | k |
| `1886dbc` | 2025-05-23 | att |
| `6e79f32` | 2025-05-23 | att |
| `46c60d0` | 2025-05-24 | Add Resend email backend |
| `deef3cd` | 2025-05-24 | aaaaaaaaaaa |
| `21c5918` | 2025-05-25 | Add token-based session security |
| `70e71e4` | 2025-05-26 | Validações de segurança (**DELETE .env**) |

### Branches contendo histórico vazado

```
main
remotes/origin/main
remotes/origin/CastroX
remotes/origin/fix-push-temp
```

**Todos contêm `dc29e12`** — vazamento presente em todas as branches remotas mapeadas.

### Estado atual `origin/main`

```
git show origin/main:.env → fatal: path '.env' does not exist
```

✅ Tip do branch main está limpo. ❌ Histórico remoto **não** está limpo.

---

## 3. Tipos de segredos encontrados no histórico

Inspeção via `git log -S` e `git show 70e71e4` (diff de remoção — **valores redigidos neste relatório**):

| Tipo | Classificação | Commits relevantes |
|------|---------------|-------------------|
| `SECRET_KEY=` Django | **CONFIRMADO** | `dc29e12` … `21c5918` |
| `FIELD_ENCRYPTION_KEY=` | **CONFIRMADO** | `deef3cd`, `6e79f32`, `70e71e4` (delete diff) |
| `DATABASE_URL=` (Neon PostgreSQL + senha) | **CONFIRMADO** | `2ad988b`, `deef3cd`, `70e71e4` |
| `RESEND_API_KEY=re_***` | **CONFIRMADO** | `46c60d0`, `70e71e4` |
| `ALERT_BRIDGE_API_TOKEN` | **CONFIRMADO** | `deef3cd`, `6e79f32`, `1886dbc` |
| `REDIS_URL` | **CONFIRMADO** | múltiplos |
| E-mail/senhas em comentários `.env.example` | **SUSPEITO** | `senha123` placeholder |

### Padrões buscados — resultados

| Padrão | Resultado |
|--------|-----------|
| `.env` file history | **CONFIRMADO** (11 commits) |
| `SECRET_KEY=` | **CONFIRMADO** |
| `FIELD_ENCRYPTION_KEY=` | **CONFIRMADO** |
| `RESEND_API_KEY=` | **CONFIRMADO** |
| `postgresql://` / `npg_` (Neon) | **CONFIRMADO** |
| `ASAAS` | **CONFIRMADO** (presente em .env histórico) |
| `ALERT_BRIDGE` | **CONFIRMADO** |
| Telegram bot token hardcoded | **NÃO ENCONTRADO** no .env (tokens no DB) |
| VPN credentials hardcoded | **NÃO ENCONTRADO** no Git (estão no DB encrypted) |
| `git stash list` | **NÃO ENCONTRADO** |

---

## 4. Primeiro vs último `.env` commitado

### `dc29e12` (2025-10-23) — primeiro commit

Conteúdo inicial **menos crítico:**
- `SECRET_KEY=dev-secret-key-change-me`
- `DEBUG=True`
- Sem DATABASE_URL Neon aparente no trecho inicial

### `2ad988b` / `deef3cd` — escalada

- Adição de `DATABASE_URL` Neon production-like
- Chaves Resend, FIELD_ENCRYPTION_KEY, bridge tokens

### `70e71e4` — remoção

- Deleta `.env` do tracking
- Atualiza `.gitignore`
- **Não** reescreve histórico (`git filter-repo` / BFG **não** aplicado)

---

## 5. `.env.example` — risco de cópia

**Arquivo:** `.env.example`

| Item | Classificação |
|------|---------------|
| Placeholder `senha123` em DATABASE_URL comentado | **SUSPEITO** — risco operacional |
| Placeholders genéricos bridge/token | OK (documentação) |
| Commit `70e71e4` melhorou example | Evidência positiva |

---

## 6. Proteções atuais no repo

| Controle | Arquivo | Status |
|----------|---------|--------|
| `.gitignore` ignora `.env` | `.gitignore` | ✅ |
| `scripts/security-check.sh` falha se `.env` tracked | CI security workflow | ✅ |
| `.env` não em `git ls-files` | verificado | ✅ |
| Histórico limpo | — | ❌ |

---

## 7. Impacto

1. **SECRET_KEY** vazada → forjar sessões Django históricas (até rotação)
2. **DATABASE_URL Neon** → acesso direto ao banco se credenciais não rotacionadas
3. **FIELD_ENCRYPTION_KEY** → descriptografar CNPJ, Telegram, OLT no DB
4. **RESEND_API_KEY** → envio de e-mail em nome da conta
5. **ALERT_BRIDGE_API_TOKEN** → fetch configs + tokens Telegram via API interna

---

## 8. Classificação por item

| Item | Status |
|------|--------|
| `.env` no Git remoto (histórico) | **CONFIRMADO** |
| `.env` no tip main remoto | **NÃO ENCONTRADO** |
| SECRET_KEY vazada | **CONFIRMADO** |
| DATABASE_URL vazada | **CONFIRMADO** |
| FIELD_ENCRYPTION_KEY vazada | **CONFIRMADO** |
| RESEND_API_KEY vazada | **CONFIRMADO** |
| ASAAS keys vazadas | **CONFIRMADO** |
| Bridge token vazado | **CONFIRMADO** |
| Telegram token no Git | **NÃO ENCONTRADO** (DB only) |
| OLT/VPN no Git | **NÃO ENCONTRADO** (DB only) |
| Stash com secrets | **NÃO ENCONTRADO** |

---

## 9. Ações recomendadas (NÃO executadas nesta auditoria)

1. **Rotacionar imediatamente:** SECRET_KEY, DATABASE_URL (senha Neon), FIELD_ENCRYPTION_KEY, RESEND, bridge tokens, ASAAS
2. **Considerar** `git filter-repo`/BFG + force push (coordenação equipe) OU tratar repo como comprometido
3. **Auditar Neon** — logs de acesso, IPs desconhecidos
4. **Revogar** API keys Resend/Asaas no painel
5. **Re-salvar** campos criptografados após nova FIELD_ENCRYPTION_KEY
6. **Nunca** commitar `.env` novamente — usar `.env.local` gitignored

---

## 10. Evidência de comandos (read-only)

```powershell
git rev-list --all --count -- ".env"     # → 11
git show origin/main:.env                 # → fatal (não existe no tip)
git log --all --format="%h %ai %s" -- ".env"
git branch -a --contains dc29e12          # → main + remotes
git stash list                            # → vazio
```

---

**⚠️ ALERTA:** Este relatório confirma vazamento real. Segredos aparecem no diff de `70e71e4` — não reproduzidos aqui por segurança. Operador deve assumir **comprometimento total** até rotação completa.

*Histórico Git não foi alterado.*
