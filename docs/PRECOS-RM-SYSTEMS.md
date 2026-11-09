# RM Systems — Tabela de preços (ISP / FTTH)

Precificação por **empresa (CNPJ)** em **BRL/mês**. Valores sugeridos para venda; negociáveis em contrato anual ou volume.

**Contato:** comercial@rmsys.com.br · suporte@rmsys.com.br

---

## Como o preço é formado

```
Mensalidade = Plano base (ou módulos à la carte)
            + Excedentes do mês anterior (se houver)
            + Setup (pagamento único, na entrada)
```

| Métrica | O que conta |
|---------|-------------|
| **Usuários** | Logins ativos na empresa |
| **Mapas CTO** | Arquivos ativos no verificador |
| **Consultas de viabilidade** | Verificações no mapa / mês |
| **Chips WhatsApp** | Linhas conectadas (alertas) |
| **Números de alerta** | Telefones que recebem encaminhamento |
| **Mensagens de alerta** | Telegram → WhatsApp / mês |
| **OLTs** | Equipamentos cadastrados |
| **Jobs ONU** | Listagens e exclusões / mês |

---

## Planos fechados (recomendado)

| Limite / mês | **P** Essencial | **M** Comercial | **G** Operação | **XL** Rede |
|:-------------|----------------:|----------------:|---------------:|------------:|
| **Usuários** | 3 | 8 | 15 | 40 |
| **Mapas CTO** | 15 | 40 | 80 | 200 |
| **Consultas viabilidade** | 500 | 2.000 | 8.000 | 25.000 |
| **Verificador FTTH** | Sim | Sim | Sim | Sim |
| **Chips WhatsApp** | — | — | 2 | 6 |
| **Números alerta** | — | — | 8 | 25 |
| **Mensagens alerta** | — | — | 3.000 | 15.000 |
| **Módulo Alertas** | — | — | Sim | Sim |
| **OLTs** | — | — | — | 5 |
| **Jobs ONU** | — | — | — | 120 |
| **Módulo OLT/ONU** | — | — | — | Sim |
| **Tickets suporte** | Sim | Sim | Sim | Sim + prioridade |
| **Valor mensal** | **R$ 297** | **R$ 497** | **R$ 797** | **R$ 1.497** |

### Perfil de cada plano

| Plano | Indicado para |
|-------|----------------|
| **P — Essencial** | ISP pequeno, 1–3 vendedores, poucos mapas, só viabilidade |
| **M — Comercial** | Equipe comercial maior, várias regiões, sem NOC automatizado |
| **G — Operação** | Comercial + NOC: alertas Telegram → WhatsApp |
| **XL — Rede** | Operação completa + engenharia (OLT/ONU, vários chips) |

---

## Só Verificador FTTH (à la carte)

| Faixa | Usuários | Mapas CTO | Consultas/mês | Mensal |
|:-----:|----------|-----------|---------------|--------|
| **V1** | até 5 | até 20 | 1.000 | **R$ 249** |
| **V2** | até 12 | até 60 | 5.000 | **R$ 449** |
| **V3** | até 30 | até 150 | 20.000 | **R$ 749** |
| **V4** | sob consulta | sob consulta | sob consulta | sob consulta |

---

## Só Alertas (Telegram → WhatsApp)

| Faixa | Chips | Números destino | Mensagens/mês | Mensal |
|:-----:|-------|----------------|---------------|--------|
| **A1** | 1 | até 5 | 1.500 | **R$ 179** |
| **A2** | 2 | até 12 | 5.000 | **R$ 329** |
| **A3** | 5 | até 30 | 20.000 | **R$ 549** |
| **A4** | 10 | até 60 | 50.000 | **R$ 899** |

---

## Só OLT / ONU

| Faixa | OLTs | Jobs ONU/mês | Mensal |
|:-----:|------|--------------|--------|
| **O1** | 1 | 40 | **R$ 199** |
| **O2** | 3 | 120 | **R$ 399** |
| **O3** | 8 | 400 | **R$ 699** |
| **O4** | 20 | 1.200 | **R$ 1.199** |

---

## Add-ons (acima do incluso no plano)

| Recurso | Pacote extra / mês |
|---------|-------------------:|
| +1 usuário | R$ 29 |
| +10 mapas CTO | R$ 35 |
| +1.000 consultas viabilidade | R$ 25 |
| +1 chip WhatsApp | R$ 69 |
| +5 números destino | R$ 39 |
| +1.000 mensagens alerta | R$ 45 |
| +1 OLT | R$ 89 |
| +50 jobs ONU | R$ 49 |

---

## Excedentes (mês seguinte, sem upgrade)

| Recurso | Excedente |
|---------|----------:|
| Usuário | R$ 35 / usuário |
| Mapas CTO (cada 10) | R$ 45 |
| Consultas (cada 1.000) | R$ 32 |
| Chip WhatsApp | R$ 79 / chip |
| Números destino (cada 5) | R$ 49 |
| Mensagens alerta (cada 1.000) | R$ 55 |
| OLT | R$ 99 / OLT |
| Jobs ONU (cada 50) | R$ 59 |

> Se o excedente for recorrente e passar de **~80%** do próximo plano, ofereça **upgrade**.

---

## Setup (pagamento único)

| Serviço | Valor |
|---------|------:|
| Onboarding remoto 1h (incluso P e M) | R$ 0 |
| Onboarding + mapas + 1 chip (plano G) | **R$ 690** |
| Onboarding completo (P ou M avulso) | **R$ 1.290** |
| Onboarding completo (plano XL) | R$ 0 |
| Treinamento extra 2h (até 15 pessoas) | **R$ 690** |

---

## Descontos

| Modalidade | Desconto |
|------------|----------:|
| Pagamento **anual** antecipado | **12%** |
| Pagamento **semestral** | **6%** |
| 2ª empresa (mesmo grupo) | **10%** na 2ª |
| Trial verificador 14 dias | 1 usuário, 3 mapas, 200 consultas |

**Fidelidade sugerida:** 3 meses nos planos **G** e **XL**.

---

## Matriz rápida: qual plano indicar?

| Tamanho | Usuários | Mapas | Chips | OLT | Plano |
|---------|----------|-------|-------|-----|-------|
| Micro | 3 | 15 | 0 | 0 | **P** |
| Pequeno | 8 | 40 | 0 | 0 | **M** |
| Médio + NOC | 15 | 80 | 2 | 0 | **G** |
| Médio + engenharia | 25 | 120 | 3 | 3 | **XL** ou G + O2 |
| Grande | 40+ | 200+ | 6+ | 5+ | **XL** + excedente |

---

## Exemplo de proposta

**Cenário:** 10 usuários, 55 mapas, 1 chip, 6 números, ~4.000 msgs/mês, 2 OLT, ~60 jobs.

| Item | Valor |
|------|------:|
| Plano G Operação | R$ 797 |
| +1.000 mensagens | R$ 45 |
| Módulo OLT faixa O2 | R$ 399 |
| **Total mensal** | **R$ 1.241** |
| Setup (entrada) | R$ 690 |

---

## Resumo por faixa de preço

| Produto | Entrada | Padrão | Topo |
|---------|--------:|-------:|-----:|
| Só verificador | R$ 249–297 | R$ 449–497 | R$ 749+ |
| Verificador + alertas | — | R$ 797 | R$ 1.100+ |
| Plataforma completa (XL) | — | — | **R$ 1.497** |

---

*Versão comercial — maio/2026. Referência técnica: `core/plans.py`.*
