# RM Systems — Plataforma unificada

O SaaS reúne três módulos no mesmo tenant (empresa/CNPJ), com login único e isolamento multi-tenant.

| Módulo | Código | Função principal |
|--------|--------|------------------|
| **Verificador FTTH** | `verificador` | Mapas CTO, viabilidade, relatórios |
| **Alertas** | `alertas` | Bridge Telegram → WhatsApp (`services/alert_bridge/`) |
| **OLT / ONU** | `olt` | Cadastro de OLTs, jobs CLI (`olt_ops/`, `services/olt_worker/`) |

## Onde está no código

| Área | Caminho |
|------|---------|
| Planos e limites | `core/plans.py` |
| Empresa e módulos habilitados | `core/models.py` (`Company`) |
| URLs por tenant | `core/urls_company.py`, `ftth_viewer/`, `olt_ops/` |
| Onboarding | `python manage.py onboarding_checklist` |

## Documentação relacionada

- Técnica completa: [DOCUMENTACAO-TECNICA.md](DOCUMENTACAO-TECNICA.md)
- Preços: [PRECOS-RM-SYSTEMS.md](PRECOS-RM-SYSTEMS.md) · [precos-rm-systems.html](precos-rm-systems.html)
- Deploy: [deploy/DEPLOY.md](deploy/DEPLOY.md)
- LGPD: [ROPA.md](ROPA.md), [SUBOPERADORES-LGPD.md](SUBOPERADORES-LGPD.md)
- Índice geral: [README.md](README.md)

## Histórico

Os módulos **Alertas** e **OLT** substituem projetos desktop legados (`MENSAGENS/`, `Venda/`). Scripts antigos de referência estão em `archive/legacy-desktop-tools/` (lógica portada para `olt_ops/`).
