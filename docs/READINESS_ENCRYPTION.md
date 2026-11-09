# READINESS — Criptografia Fernet (Auditoria)

> **Modo:** READ ONLY — nenhum dado regravado  
> **Data:** 25/05/2026

---

## 1. Resumo executivo

| Verificação | Resultado |
|-------------|-----------|
| Implementação Fernet | ✅ Documentada em `core/field_encryption.py` |
| Modelos com EncryptedField | ✅ 6 campos mapeados |
| Inspeção live DB produção | ⚠️ **BLOQUEADA** — `.env` ausente no workspace |
| Fallback inseguro SECRET_KEY | ⚠️ Existe (opt-in, perigoso se ativado) |
| Comportamento falha decrypt | Retorna `""` + log (silencioso para UI) |

**Classificação global:** ⚠️ **LEGADO QUEBRADO PROVÁVEL** (evidência operacional anterior) — requer validação com `.env` real do operador.

---

## 2. Campos criptografados (mapa completo)

| Modelo | Campo | App | Migration encrypt |
|--------|-------|-----|-------------------|
| `Company` | `cnpj` | core | `0018`, `0020` |
| `AlertBridgeConfig` | `telegram_bot_token` | alerts | `0008` |
| `OltEquipment` | `password` | olt_ops | `0005` |
| `OltEquipment` | `enable_password` | olt_ops | `0006` |
| `CompanyVpnConfig` | `ipsec_psk` | olt_ops | `0005` |
| `CompanyVpnConfig` | `vpn_password` | olt_ops | `0005` |
| `CompanyVpnConfig` | `ovpn_content` | olt_ops | texto (não EncryptedCharField — verificar modelo) |

**Implementação campo:** `core/encrypted_fields.py` → `EncryptedCharField` — encrypt on save, decrypt on read.

---

## 3. Lógica de chave (`core/field_encryption.py`)

### Encrypt (sempre)
- Exige `FIELD_ENCRYPTION_KEY` válida via `get_fernet()`
- **Sem fallback** silencioso em encrypt

### Decrypt (ordem)
1. `FIELD_ENCRYPTION_KEY` do env (com normalização padding `=`)
2. Se `ALLOW_FIELD_ENCRYPTION_SECRET_FALLBACK` + DEBUG + não produção → deriva de `SECRET_KEY`

### Falha decrypt
```python
# decrypt_value → retorna "" após log error
logger.error("Falha ao descriptografar campo (chave trocada ou dado legado)...")
return ""
```

**Risco UX:** painel mostra campo vazio — operador pode achar "bug" ou salvar valor errado.

---

## 4. CHECK 3 — Inspeção live (status)

### Ambiente auditoria

| Item | Valor |
|------|-------|
| `.env` no workspace | ❌ Ausente |
| `.env.local` | ❌ Ausente |
| Conexão Neon produção | ❌ **Não utilizada** (política: não usar credenciais do Git) |

### Evidência operacional prévia (logs/conversa)

| Sintoma | Classificação |
|---------|---------------|
| `Falha ao descriptografar campo` ao carregar bridge | **LEGADO QUEBRADO** |
| `FIELD_ENCRYPTION_KEY` com 43 chars (sem `=`) | **CHAVE INVÁLIDA** (corrigível com padding) |
| CNPJ empresa id=1 ilegível | **LEGADO QUEBRADO** |
| Bridge token OK após correção chave | **OK** parcial |

### Script de auditoria (para operador executar localmente)

```python
# READ ONLY — não salva nada
# python manage.py shell
from core.models import Company
from alerts.models import AlertBridgeConfig
from olt_ops.models import OltEquipment, CompanyVpnConfig

def audit_field(label, value):
    from core.field_encryption import is_encrypted, decrypt_value
    if not value:
        return "VAZIO"
    if not is_encrypted(str(value)):
        return "PLAINTEXT_LEGADO"
    dec = decrypt_value(str(value))
    return "OK" if dec else "DECRYPT_FALHOU"

for c in Company.objects.all():
    print(c.id, c.slug, "cnpj:", audit_field("cnpj", c.cnpj))

for cfg in AlertBridgeConfig.objects.all():
    print(cfg.company.slug, "telegram:", audit_field("tg", cfg.telegram_bot_token))

for olt in OltEquipment.objects.all():
    print(olt.id, "password:", audit_field("pwd", olt.password))
```

**Esta auditoria automatizada NÃO foi executada contra Neon** nesta etapa.

---

## 5. Compatibilidade da chave atual

| Cenário | Classificação |
|---------|---------------|
| Chave Fernet 44 chars válida | **OK** |
| Chave 43 chars (falta `=`) | **CHAVE INVÁLIDA** — `normalize_fernet_key()` tenta corrigir |
| Chave rotacionada sem re-save | **LEGADO QUEBRADO** |
| Dados migrados com chave A, env com chave B | **LEGADO QUEBRADO** |
| `ALLOW_FIELD_ENCRYPTION_SECRET_FALLBACK=true` em prod | **CRÍTICO** — não usar |

---

## 6. Impacto por integração

| Integração | Se decrypt falha |
|------------|------------------|
| Telegram bridge | Worker sem token → alertas param |
| OLT SSH | Job falha — credencial vazia |
| VPN | `VpnConnectionError` |
| CNPJ empresa | Exibição vazia; validação pode falhar |
| Billing | ❌ Não usa Fernet |

---

## 7. Migrations de criptografia — risco

| Migration | Risco |
|-----------|-------|
| `core.0018` RunPython encrypt CNPJ | Se key errada no migrate → lixo permanente |
| `alerts.0008` encrypt telegram | Idem |
| `olt_ops.0005` encrypt OLT/VPN | Idem |

**Recomendação:** backup DB antes de qualquer migrate encrypt em ambiente novo.

---

## 8. Classificação por registro (template)

*(Preencher após operador rodar script local)*

| Entidade | ID/Slug | Campo | Status |
|----------|---------|-------|--------|
| Company | id=1 | cnpj | **LEGADO QUEBRADO** (evidência operacional) |
| AlertBridgeConfig | * | telegram_bot_token | **OK** (pós-correção chave — evidência logs) |
| OltEquipment | * | password | **NÃO VALIDADO** |
| CompanyVpnConfig | * | vpn_password | **NÃO VALIDADO** |

---

## 9. Fallback inseguro

**Arquivo:** `core/field_encryption.py` L66–89

Ativo apenas se:
- `ALLOW_FIELD_ENCRYPTION_SECRET_FALLBACK=true` **E**
- `DEBUG=True` **E**
- `IS_PRODUCTION=False`

**Classificação em produção normal:** **NÃO ENCONTRADO** (desde que env correto).

---

## 10. Recomendações (NÃO executadas)

1. Operador roda script audit acima com `.env` local
2. Listar todos `DECRYPT_FALHOU` → re-salvar no painel (única correção sem perda)
3. Confirmar `FIELD_ENCRYPTION_KEY` com `python manage.py setup_p1_security --check`
4. **Não** ativar fallback SECRET_KEY em produção
5. Após rotação Git leak → **obrigatório** nova key + re-save all encrypted fields

---

## 11. Veredicto

| Classificação | Escopo |
|---------------|--------|
| **CHAVE INVÁLIDA** | Corrigida localmente (padding) — revalidar |
| **LEGADO QUEBRADO** | CNPJ id=1 confirmado por sintoma |
| **DADOS CORROMPIDOS** | **NÃO ENCONTRADO** (distinto de chave errada) |
| **OK** | Bridge token pós-fix (evidência logs runserver) |

**Blocker operacional:** campos encrypted ilegíveis impedem OLT/alertas até re-save manual.

---

*Nenhum registro foi regravado nesta auditoria.*
