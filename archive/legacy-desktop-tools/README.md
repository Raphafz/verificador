# Ferramentas desktop legadas

Scripts Python usados antes da unificação no Django (`olt_ops/`). Mantidos só como referência histórica — **não** fazem parte do deploy do SaaS.

| Arquivo | Uso original |
|---------|----------------|
| `deletar_onu.py`, `deletar_onu_gui.py` | Exclusão ONU (Huawei/ZTE) |
| `huawei_olt.py`, `listar_ont_offline.py` | Listagem CLI Huawei |
| `olt_config.py`, `olt_config_ui.py` | Configuração OLT |
| `montar_venda.py`, `compilar.py` | Build PyInstaller |

A lógica ativa está em `olt_ops/` e `services/olt_worker/`.

**Nota:** binários `.exe` (ex. PuTTY embutido) não são versionados no Git.
