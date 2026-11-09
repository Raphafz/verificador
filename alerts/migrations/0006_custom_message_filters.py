from django.db import migrations, models


def migrate_old_filters(apps, schema_editor):
    Config = apps.get_model("alerts", "AlertBridgeConfig")
    for cfg in Config.objects.all():
        if cfg.alert_filter_enabled:
            lines = []
            kw = (cfg.alert_event_keyword or "").strip()
            if kw:
                lines.append(kw)
            for part in (cfg.alert_links or "").split(","):
                part = part.strip()
                if part:
                    lines.append(f"({part})" if not part.startswith("(") else part)
            cfg.filter_enabled = True
            cfg.filter_rules = "\n".join(lines)
            cfg.filter_match_all = True
        else:
            cfg.filter_enabled = False
            cfg.filter_rules = ""
            cfg.filter_match_all = False
        cfg.save(
            update_fields=["filter_enabled", "filter_rules", "filter_match_all"]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("alerts", "0005_alter_alertbridgeconfig_whatsapp_alert_phones_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="alertbridgeconfig",
            name="filter_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Se desmarcado, encaminha todas as mensagens de texto do grupo.",
                verbose_name="Usar filtro personalizado",
            ),
        ),
        migrations.AddField(
            model_name="alertbridgeconfig",
            name="filter_rules",
            field=models.TextField(
                blank=True,
                help_text="Uma condição por linha: a mensagem deve conter esse texto (trecho exato).",
                verbose_name="Regras de filtro",
            ),
        ),
        migrations.AddField(
            model_name="alertbridgeconfig",
            name="filter_match_all",
            field=models.BooleanField(
                default=False,
                help_text="Marcado: todas as linhas devem aparecer na mensagem. Desmarcado: basta uma linha.",
                verbose_name="Exigir todas as regras (E)",
            ),
        ),
        migrations.RunPython(migrate_old_filters, migrations.RunPython.noop),
        migrations.RemoveField(model_name="alertbridgeconfig", name="alert_filter_enabled"),
        migrations.RemoveField(model_name="alertbridgeconfig", name="alert_links"),
        migrations.RemoveField(model_name="alertbridgeconfig", name="alert_event_keyword"),
    ]
