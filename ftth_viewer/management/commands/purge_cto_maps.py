"""Remove mapas CTO (banco, arquivos, caches) para re-upload limpo."""
import shutil
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand

from core.models import Company, CTOMapFile
from ftth_viewer.models import ViabilidadeCache
from ftth_viewer.utils import invalidate_ftth_map_caches


class Command(BaseCommand):
    help = "Remove todos os mapas CTO de uma empresa (ou de todas) e limpa caches relacionados"

    def add_arguments(self, parser):
        parser.add_argument(
            "--company",
            type=str,
            help="Slug da empresa (ex.: fibramar). Omita para limpar todas.",
        )
        parser.add_argument(
            "--legacy-dirs",
            action="store_true",
            help="Também esvazia pastas legadas Mapas/kml, kmz, csv, etc.",
        )

    def handle(self, *args, **options):
        slug = options.get("company")
        companies = Company.objects.all()
        if slug:
            companies = companies.filter(slug=slug)
            if not companies.exists():
                self.stderr.write(self.style.ERROR(f"Empresa não encontrada: {slug}"))
                return

        total_maps = 0
        total_files = 0

        for company in companies:
            maps = CTOMapFile.objects.filter(company=company)
            count = maps.count()
            for mapa in maps:
                if mapa.file:
                    try:
                        path = Path(mapa.file.path)
                        if path.is_file():
                            path.unlink()
                            total_files += 1
                    except (OSError, ValueError):
                        pass
            deleted, _ = maps.delete()
            total_maps += deleted

            via_deleted, _ = ViabilidadeCache.objects.filter(company=company).delete()
            invalidate_ftth_map_caches(company, company_slug=company.slug)
            self.stdout.write(
                f"  {company.slug}: {deleted} mapa(s), {via_deleted} cache(s) de viabilidade"
            )

            cto_dir = Path(settings.MEDIA_ROOT) / "cto_maps" / str(company.id)
            if cto_dir.is_dir():
                shutil.rmtree(cto_dir, ignore_errors=True)
                self.stdout.write(f"  {company.slug}: pasta media/cto_maps/{company.id} removida")

        cache.clear()
        self.stdout.write(self.style.SUCCESS("Cache Django limpo (global)"))

        if options.get("legacy_dirs"):
            for attr in (
                "FTTH_KML_DIR",
                "FTTH_KMZ_DIR",
                "FTTH_CSV_DIR",
                "FTTH_XLS_DIR",
                "FTTH_XLSX_DIR",
            ):
                directory = getattr(settings, attr, None)
                if not directory:
                    continue
                path = Path(directory)
                if not path.is_dir():
                    continue
                for item in path.iterdir():
                    if item.is_file():
                        item.unlink()
                        total_files += 1
                self.stdout.write(f"  Legado esvaziado: {path}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Concluído — {total_maps} registro(s) de mapa, {total_files} arquivo(s) em disco."
            )
        )
        self.stdout.write(
            "No navegador: Ctrl+Shift+R no verificador (ou aba anônima) para limpar cache local."
        )
