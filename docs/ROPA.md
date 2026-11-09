# ROPA — Registro de Operações de Tratamento

**Controlador:** RM Systems  
**Sistema:** Saas Verificador de Viabilidade (multi-tenant B2B)  
**Versão do documento:** 2026-05-21  
**Responsável:** Encarregado de Dados — privacidade@rmsys.app

> Preencha e revise com jurídico. Este modelo reflete o que o código trata hoje.

---

## 1. Tratamentos realizados

| # | Operação | Dados | Titulares | Base legal | Finalidade | Retenção |
|---|----------|-------|-----------|------------|------------|----------|
| 1 | Cadastro de usuário | Nome, e-mail, telefone, login | Colaboradores das empresas clientes | Execução de contrato | Acesso ao SaaS | Conta ativa + 5 anos após inatividade* |
| 2 | Cadastro de empresa | CNPJ, razão social, e-mail, telefone, endereço | Pessoa jurídica cliente | Execução de contrato | Multi-tenant | Vigência contratual |
| 3 | Consentimento | IP, user-agent, data/hora, versão do documento | Usuários | Consentimento (art. 7º, I) | Termos, privacidade, cookies | 5 anos |
| 4 | Verificador FTTH | Coordenadas, endereços (geocoding), mapas CTO | Clientes finais indiretos / operação ISP | Legítimo interesse / contrato com ISP | Viabilidade de rede | Cache 90 dias (`purge_old_caches`) |
| 5 | Tickets de suporte | Mensagens, metadados | Usuários | Contrato | Suporte | 2 anos após fechamento* |
| 6 | Alertas Telegram→WhatsApp | Telefones, mensagens de alerta | Configurado pelo cliente ISP | Contrato com ISP (operador) | Monitoramento | Configuração do cliente |
| 7 | OLT/VPN | Credenciais de rede | Infraestrutura do cliente | Contrato | Operação técnica | Criptografado em repouso; exclusão com empresa |
| 8 | Logs de segurança | IP, username (sem senha) | Usuários | Legítimo interesse / segurança | Auditoria, anti-fraude | 90 dias–1 ano* |

\* Prazos sugeridos — ajustar na política interna.

---

## 2. Suboperadores (ver também SUBOPERADORES-LGPD.md)

| Suboperador | Serviço | Localização | DPA |
|-------------|---------|-------------|-----|
| Hospedagem / PostgreSQL | Banco de dados | [preencher] | [ ] |
| OpenStreetMap Nominatim | Geocoding | UE / internacional | [ ] |
| OSRM / OpenRouteService | Rotas | [preencher] | [ ] |
| Sentry (opcional) | Erros | EUA | [ ] DPA + PII off |
| Provedor SMTP | E-mail transacional | [preencher] | [ ] |

---

## 3. Medidas de segurança (implementadas no código)

- Autenticação Django, Argon2, sessão 1h, cookies HttpOnly/Secure  
- Criptografia Fernet: OLT, VPN, token Telegram  
- Middleware multi-tenant, CSRF, CSP, rate limiting (produção)  
- Portal do titular: `/meus-dados/`, exportação JSON, desativação de conta  
- API interna alert-bridge: token em header + allowlist IP  

---

## 4. Fluxo de direitos do titular

1. Portal: `/meus-dados/`  
2. Exportação: `/meus-dados/exportar/`  
3. Exclusão: desativação imediata + fila `DataSubjectRequest`  
4. Processamento DPO: `python manage.py process_data_subject_requests`  
5. Canal DPO: `/encarregado-dados/`  

---

## 5. Incidentes

| Etapa | Ação |
|-------|------|
| Detecção | Monitoramento logs, Sentry, cliente |
| Contenção | Revogar tokens, rotacionar `SECRET_KEY` / `FIELD_ENCRYPTION_KEY` se vazamento |
| Notificação | ANPD + titulares conforme art. 48 (prazo 72h úteis avaliar) |
| Registro | Ticket interno + anexo a este ROPA |

---

## 6. Revisão

| Data | Responsável | Alteração |
|------|-------------|-----------|
| 2026-05-21 | TI | Versão inicial alinhada ao código |
