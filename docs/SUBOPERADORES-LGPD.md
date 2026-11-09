# Suboperadores e transferência internacional

**Versão:** 2026-05-21

## Integrações identificadas no código

| Serviço | Endpoint / uso | Dados transferidos | Mitigação técnica |
|---------|----------------|-------------------|-------------------|
| **Nominatim (OSM)** | `ftth_viewer/views.py` | Endereço, lat/lon | Cache local `GeocodingCache`; retenção 90d |
| **OSRM** | `ftth_viewer/utils.py` | Coordenadas de rota | Sem persistência obrigatória |
| **OpenRouteService** | `.env` `OPENROUTESERVICE_API_KEY` | Coordenadas | Opcional |
| **ViaCEP / BrasilAPI** | Frontend preconnect | CEP | Apenas consulta |
| **Sentry** | `SENTRY_DSN` | Stack traces | `send_default_pii=False` |
| **SMTP** | `EMAIL_*` | E-mail destinatário | TLS |
| **Telegram / WhatsApp** | Módulo alertas | Mensagens, telefones | Tokens criptografados; contrato B2B |

## Checklist DPA (jurídico)

- [ ] Contrato de processamento com cada provedor de infraestrutura  
- [ ] Cláusulas de transferência internacional (Nominatim/OSRM/Sentry)  
- [ ] ISP cliente como controlador dos dados de mapas e alertas  
- [ ] Política de privacidade menciona suboperadores  

## Referência legal

Lei 13.709/2018 — arts. 33 a 36 (comunicação e transferência internacional).
