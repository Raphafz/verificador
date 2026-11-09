# Escopo de suporte OLT — plano XL e módulo OLT/ONU

Documento comercial/técnico para alinhar expectativa com clientes **XL — Rede** e evitar escopo de NOC gerenciado.

## O que está incluído

| Item | Detalhe |
|------|---------|
| Cadastro de OLTs | Huawei / ZTE — SSH ou Telnet, credenciais criptografadas |
| VPN por empresa | OpenVPN / L2TP-IPsec; teste de conectividade na UI |
| Jobs ONU | Listagem offline por porta GPON; exclusão em lote por SN |
| Fila automática | Quando slot VPN/container ocupado, job entra na fila |
| Modo container | Multi-VPN na mesma VPS (produção recomendada) |
| Logs | Log técnico por job + arquivo operacional no servidor |
| Limites | Conforme plano (`max_olts`, `max_olt_jobs_month`) |

## O que NÃO está incluído (fora do SaaS)

- Monitoramento 24×7 da OLT ou da rede do cliente
- Correção de configuração na OLT (VLAN, profile, service-port)
- Suporte à infraestrutura do cliente (energia, fibra, splitters)
- Garantia de disponibilidade da VPN do cliente
- Desenvolvimento de comandos CLI customizados por firmware
- SLA de minutos para incidentes de rede

## Responsabilidades

| Parte | Responsabilidade |
|-------|------------------|
| Cliente | Credenciais corretas, VPN estável, janela de manutenção |
| RM Systems | Software, deploy documentado, bugs da plataforma |
| Hospedagem | VPS conforme `docs/deploy/OLT_WORKER.md` |

## Plano XL — expectativa

- Limites ampliados (OLTs e jobs/mês); não é NOC dedicado.
- Suporte comercial em horário acordado; incidentes críticos de **plataforma** prioritizados.
- Customizações de CLI ou integrações extras: orçamento à parte.

## Referências técnicas

- Deploy worker: [OLT_WORKER.md](../deploy/OLT_WORKER.md)
- Quotas: `core/plans.py`, `core/quotas.py`
