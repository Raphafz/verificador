from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import CustomUser

class Command(BaseCommand):
    help = "Normaliza privilégios: remove superuser/staff de usuários de empresas e corrige RM com empresa."

    def handle(self, *args, **options):
        with transaction.atomic():
            # Remover superuser/staff de usuários que não são RM
            bad_supers = CustomUser.objects.filter(is_superuser=True).exclude(role='RM')
            bad_staff = CustomUser.objects.filter(is_staff=True).exclude(role='RM')

            supers_count = bad_supers.count()
            staff_count = bad_staff.count()

            for u in bad_supers:
                u.is_superuser = False
                # Não deixar staff para empresas
                if u.is_staff:
                    u.is_staff = False
                u.save()

            for u in bad_staff.exclude(id__in=bad_supers.values_list('id', flat=True)):
                u.is_staff = False
                u.save()

            # Corrigir RM com empresa associada
            rm_with_company = CustomUser.objects.filter(role='RM').exclude(company__isnull=True)
            rm_company_count = rm_with_company.count()
            for u in rm_with_company:
                u.company = None
                # RM costuma ser staff administrativo
                if not u.is_staff:
                    u.is_staff = True
                u.save()

        self.stdout.write(self.style.SUCCESS(
            f"Normalização concluída: removidos superuser={supers_count}, staff={staff_count} de não-RM; RM sem empresa corrigidos={rm_company_count}."
        ))