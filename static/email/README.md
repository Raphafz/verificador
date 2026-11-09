# Assets de e-mail transacional (RM Systems)

| Arquivo | Uso |
|---------|-----|
| `letreiro-email.png` | Letreiro RM Systems sem fundo (cabeçalho, ~300px, embutido via CID) |
| `logo-email.png` | Cópia do letreiro (legado / fallback) |
| `banner.jpg` | Banner superior (600×337, embutido no HTML) |

Originais em `logos-rmsys/` na raiz do projeto.

```env
EMAIL_LETTREIRO_URL=/static/email/letreiro-email.png
EMAIL_ICON_URL=/static/email/icon-email.png
EMAIL_EMBED_IMAGES=true
```

Com `EMAIL_EMBED_IMAGES=true`, logo e banner vão **dentro do e-mail** (base64). Funciona no Gmail mesmo em dev, sem depender de `127.0.0.1`.

Em produção com `rmsys.app` no ar, pode usar `EMAIL_EMBED_IMAGES=false` e URLs públicas `https://rmsys.app/static/...`.
