# Etapa 5 — Infra e CI/CD

**Status:** concluida (hardening de pipeline de seguranca).

## Objetivo

Tornar o pipeline de seguranca bloqueante, evitando falso verde em vulnerabilidades de dependencia, SAST e checks de deploy.

## Vulnerabilidades tratadas

| ID | Severidade | Problema | Correcao |
|----|------------|----------|----------|
| E5-1 | HIGH | `check_security --strict` com `|| true` no CI | Step agora bloqueia falha |
| E5-2 | HIGH | `pip-audit` com `|| true` | Step agora bloqueia vulnerabilidades |
| E5-3 | HIGH | `bandit` com `|| true` | Step agora bloqueia findings relevantes |

## Arquivos alterados

- `.github/workflows/security.yml`

## O que muda na pratica

- Pull requests com achados de seguranca passam a falhar no workflow `Security CI`.
- O step `Secret patterns scan` continua bloqueante como ja era antes.
- Nao houve alteracao de regra de negocio da aplicacao.

## Validacao local

- `git ls-files --error-unmatch .env` -> confirmou que `.env` nao esta versionado.
- Em ambiente Windows sem Bash, `scripts/security-check.sh` pode nao executar localmente; no GitHub Actions (ubuntu) ele roda normalmente.

## Proximo passo recomendado

- Opcional: adicionar shell alternativo PowerShell para varredura local em Windows, mantendo `security-check.sh` para CI Linux.
