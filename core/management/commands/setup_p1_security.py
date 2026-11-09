"""

Aplica checklist P1 (RELATORIO-P1.md): dependências, chave de criptografia e migrations.

"""

import os

import re

from pathlib import Path



from django.conf import settings

from django.core.management import call_command

from django.core.management.base import BaseCommand



from core.field_encryption import normalize_fernet_key





class Command(BaseCommand):

    help = "Checklist de segurança P1: FIELD_ENCRYPTION_KEY, migrate, verificação"



    def add_arguments(self, parser):

        parser.add_argument(

            "--write-key",

            action="store_true",

            help="Grava ou corrige FIELD_ENCRYPTION_KEY no .env (ausente, inválida ou sem padding)",

        )

        parser.add_argument(

            "--force",

            action="store_true",

            help="Com --write-key: gera chave Fernet nova mesmo se já existir uma (invalida dados criptografados)",

        )

        parser.add_argument(

            "--migrate",

            action="store_true",

            help="Executa python manage.py migrate após verificações",

        )



    def _write_env_key(self, env_path: Path, new_key: str) -> None:

        content = env_path.read_text(encoding="utf-8")

        if "FIELD_ENCRYPTION_KEY=" in content:

            content = re.sub(

                r"^FIELD_ENCRYPTION_KEY=.*$",

                f"FIELD_ENCRYPTION_KEY={new_key}",

                content,

                flags=re.MULTILINE,

            )

        else:

            content = content.rstrip() + f"\n\nFIELD_ENCRYPTION_KEY={new_key}\n"

        env_path.write_text(content, encoding="utf-8")

        os.environ["FIELD_ENCRYPTION_KEY"] = new_key



    def _fernet_valid(self, key: str) -> bool:

        from cryptography.fernet import Fernet



        try:

            Fernet(key.encode("utf-8"))

            return True

        except Exception:

            return False



    def handle(self, *args, **options):

        base = Path(settings.BASE_DIR)

        env_path = base / ".env"

        key = os.getenv("FIELD_ENCRYPTION_KEY", "").strip()



        if not key:

            self.stdout.write(self.style.WARNING("FIELD_ENCRYPTION_KEY não definida."))

            if options["write_key"] and env_path.is_file():

                from cryptography.fernet import Fernet



                new_key = Fernet.generate_key().decode()

                self._write_env_key(env_path, new_key)

                self.stdout.write(self.style.SUCCESS("FIELD_ENCRYPTION_KEY gravada no .env"))

            else:

                self.stdout.write(

                    "Gere com: python -c \"from cryptography.fernet import Fernet; "

                    "print(Fernet.generate_key().decode())\""

                )

                self.stdout.write("Ou execute: python manage.py setup_p1_security --write-key")

        elif self._fernet_valid(key):

            self.stdout.write(self.style.SUCCESS("FIELD_ENCRYPTION_KEY: formato Fernet válido"))

        else:

            padded = normalize_fernet_key(key)

            if not options["force"] and padded != key and self._fernet_valid(padded):

                self.stdout.write(

                    self.style.WARNING(

                        f"FIELD_ENCRYPTION_KEY com padding incorreto ({len(key)} chars). "

                        f"Corrija com: python manage.py setup_p1_security --write-key"

                    )

                )

                if options["write_key"] and env_path.is_file():

                    self._write_env_key(env_path, padded)

                    self.stdout.write(

                        self.style.SUCCESS(

                            f"FIELD_ENCRYPTION_KEY corrigida no .env ({len(padded)} chars, padding '=')"

                        )

                    )

                else:

                    self.stdout.write(

                        "Execute com --write-key para gravar a correção no .env sem trocar a chave."

                    )

            else:

                self.stdout.write(

                    self.style.ERROR(

                        f"FIELD_ENCRYPTION_KEY inválida ({len(key)} chars). "

                        "Use --write-key (corrige padding) ou --write-key --force (chave nova)."

                    )

                )

                if options["write_key"] and options["force"] and env_path.is_file():

                    from cryptography.fernet import Fernet



                    new_key = Fernet.generate_key().decode()

                    self._write_env_key(env_path, new_key)

                    self.stdout.write(self.style.SUCCESS("Nova FIELD_ENCRYPTION_KEY gravada no .env"))

                    self.stdout.write(

                        self.style.WARNING(

                            "Re-salve tokens OLT/VPN/Telegram no painel (dados antigos não descriptografam)."

                        )

                    )

                elif options["write_key"] and not options["force"]:

                    self.stdout.write("Tente: python manage.py setup_p1_security --write-key")

                elif options["write_key"] and options["force"]:

                    pass  # already handled

                else:

                    self.stdout.write(

                        "Ou: python manage.py setup_p1_security --write-key --force (gera chave nova)"

                    )



        bridge = os.getenv("ALERT_BRIDGE_API_TOKEN", "").strip()

        if not bridge or bridge == "defina-um-token-longo-aleatorio":

            self.stdout.write(

                self.style.WARNING("ALERT_BRIDGE_API_TOKEN fraco ou ausente — altere no .env")

            )

        else:

            self.stdout.write(self.style.SUCCESS("ALERT_BRIDGE_API_TOKEN: definido"))



        if options["migrate"]:

            self.stdout.write("Executando migrate...")

            call_command("migrate", verbosity=1)

            self.stdout.write(self.style.SUCCESS("Migrations aplicadas."))



        self.stdout.write("")

        self.stdout.write("Checklist P1 manual restante:")

        self.stdout.write("  - Rotacionar senhas que estiveram na migration 0005 antiga")

        self.stdout.write("  - Confirmar que .env não está no Git remoto")

        self.stdout.write("  - Re-salvar tokens OLT/VPN/Telegram no painel após migrate ou --force")


