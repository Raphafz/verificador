from django.db import migrations
from django.contrib.auth.hashers import make_password
from django.conf import settings
import os


def _seed_users_from_env():
    """Cria superusuários RM apenas se variáveis RM_SEED_* estiverem no ambiente."""
    users = []
    for i in range(1, 6):
        username = os.getenv(f"RM_SEED_USER_{i}_USERNAME", "").strip()
        email = os.getenv(f"RM_SEED_USER_{i}_EMAIL", "").strip()
        password = os.getenv(f"RM_SEED_USER_{i}_PASSWORD", "").strip()
        if username and email and password:
            users.append({"username": username, "email": email, "password": password})
    return users


def create_rm_superusers(apps, schema_editor):
    if not getattr(settings, "DEBUG", False):
        return
    if os.getenv("RM_SEED_SUPERUSERS", "").lower() not in ("1", "true", "yes", "on"):
        return

    users_data = _seed_users_from_env()
    if not users_data:
        return

    CustomUser = apps.get_model("core", "CustomUser")
    for data in users_data:
        user, created = CustomUser.objects.get_or_create(
            username=data["username"],
            defaults={
                "email": data["email"],
                "role": "RM",
                "is_superuser": True,
                "is_staff": True,
                "is_active": True,
                "password": make_password(data["password"]),
                "company_id": None,
            },
        )
        if not created:
            user.email = data["email"]
            user.role = "RM"
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.password = make_password(data["password"])
            user.company_id = None
            user.save()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_add_fibramar_company"),
    ]

    operations = [
        migrations.RunPython(create_rm_superusers, noop_reverse),
    ]
