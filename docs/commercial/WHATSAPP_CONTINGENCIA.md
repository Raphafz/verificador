# Contingência WhatsApp — Alertas RM Systems

Documento comercial e técnico para vendas e suporte (plano **G** e **XL**).

---

## 1. Risco

O módulo **Alertas** encaminha mensagens do **Telegram** para **WhatsApp** usando sessões pareadas (tecnologia não oficial, sujeita aos **Termos de Serviço da Meta**).

| Risco | Impacto para o ISP |
|-------|-------------------|
| Bloqueio de número/chip | Equipe de campo deixa de receber alertas no WhatsApp |
| Instabilidade do worker | Atraso ou falha no encaminhamento |
| Mudança de API Meta | Pode exigir migração para WhatsApp Business API (custo maior) |

---

## 2. O que está incluso no contrato (padrão)

- Configuração inicial de até **N chips** conforme plano ([PRECOS-RM-SYSTEMS.md](../PRECOS-RM-SYSTEMS.md))
- Worker de bridge na infraestrutura RM (VPS)
- Suporte para **reconectar QR** e trocar chip no painel (admin da empresa)
- Monitoramento de erro no campo `last_error` da configuração de alertas

**Não está incluso (salvo contrato XL+):**

- NOC 24×7 garantindo entrega de cada alerta
- Recuperação de número banido pela Meta
- Integração oficial **WhatsApp Business API** (cobrança à parte)

---

## 3. Plano B — operação degradada

Se o WhatsApp ficar indisponível:

1. **Manter Telegram** como canal primário (grupo NOC já configurado).
2. Desativar bridge no painel (`Bridge ativo` = off) para evitar fila de erros.
3. Notificar equipe para acompanhar o **grupo Telegram** até reconexão.
4. RM Systems pode provisionar **chip reserva** (plano G: até 2 chips; excedente conforme tabela).

Opcional futuro: canal **e-mail** ou **webhook** para ITSM (roadmap P3).

---

## 4. Plano C — canal oficial (enterprise)

Para ISPs que exigem contrato sem risco ToS:

- **WhatsApp Business API** (Cloud API ou BSP)
- Custo de mensagem + setup superior ao bridge atual
- Roadmap: item **P2-E08** em [MELHORIAS_A_FAZER.md](../internal/MELHORIAS_A_FAZER.md)

---

## 5. Boas práticas do cliente

- Usar números **dedicados** ao NOC (não número pessoal do diretor).
- Respeitar limites de **mensagens/mês** do plano (quotas no painel).
- Não disparar campanhas de marketing pelo mesmo chip dos alertas.
- Manter **antiban** ativo nas configurações de alertas.

---

## 6. SLA sugerido (texto para proposta)

| Item | Compromisso |
|------|-------------|
| Disponibilidade do painel SaaS | Conforme SLA geral da plataforma |
| Entrega WhatsApp | **Melhor esforço** — depende de Meta e do chip do cliente |
| Tempo para orientar reconexão QR | 1 dia útil (horário comercial) |
| Migração para API oficial | Sob projeto e orçamento separados |

---

*Versão 1.0 — maio/2026. Revisar com jurídico antes de anexar a contratos.*
