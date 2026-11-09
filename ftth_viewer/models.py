from django.db import models
from django.utils import timezone


class GeocodingCache(models.Model):
    """Cache de geocodificação — chave hash, TTL, sem endereço completo persistido."""

    QUERY_ADDRESS = "address"
    QUERY_REVERSE = "reverse"
    QUERY_TYPE_CHOICES = [
        (QUERY_ADDRESS, "Endereço → coordenadas"),
        (QUERY_REVERSE, "Coordenadas → região"),
    ]

    cache_key_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name="Hash da consulta (SHA-256)",
    )
    query_type = models.CharField(
        max_length=16,
        choices=QUERY_TYPE_CHOICES,
        default=QUERY_ADDRESS,
        db_index=True,
    )
    lat = models.FloatField()
    lng = models.FloatField()
    locality_hint = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Região anonimizada",
        help_text="Apenas cidade/UF/país — sem logradouro",
    )
    expires_at = models.DateTimeField(db_index=True, verbose_name="Expira em")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cache de Geocodificação"
        verbose_name_plural = "Cache de Geocodificações"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["expires_at", "query_type"]),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self):
        hint = self.locality_hint or f"{self.lat:.4f},{self.lng:.4f}"
        return f"{self.get_query_type_display()} — {hint[:60]}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def to_dict(self):
        """Compatível com API FTTH — endereco_completo traz apenas região anonimizada do cache."""
        return {
            "lat": self.lat,
            "lng": self.lng,
            "endereco_completo": self.locality_hint or "",
            "from_cache": True,
            "anonymized": bool(self.locality_hint),
        }


class CTOFile(models.Model):
    """Model para armazenar informações sobre arquivos de CTOs"""
    TIPO_CHOICES = [
        ('kml', 'KML'),
        ('kmz', 'KMZ'),
        ('csv', 'CSV'),
        ('xls', 'XLS'),
        ('xlsx', 'XLSX'),
    ]

    nome = models.CharField(max_length=255)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    caminho = models.FilePathField(path='', max_length=1000)
    total_pontos = models.IntegerField(default=0)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Arquivo CTO'
        verbose_name_plural = 'Arquivos CTO'
        unique_together = ['nome', 'tipo']
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.tipo}) - {self.total_pontos} pontos"


class ViabilidadeCache(models.Model):
    """Cache de verificações de viabilidade - separado por empresa e mapas ativos"""
    lat = models.FloatField()
    lon = models.FloatField()
    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='viability_caches',
        null=False,
        verbose_name="Empresa"
    )
    mapas_hash = models.CharField(
        max_length=500,
        blank=True,
        default='',
        db_index=True,
        help_text="Hash dos IDs dos mapas ativos quando a verificação foi feita"
    )
    resultado = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cache de Viabilidade'
        verbose_name_plural = 'Cache de Viabilidades'
        unique_together = [['lat', 'lon', 'company', 'mapas_hash']]
        indexes = [
            models.Index(fields=['lat', 'lon', 'company', 'mapas_hash']),
        ]

    def __str__(self):
        status = self.resultado.get('viabilidade', {}).get('status', 'N/A')
        company_name = self.company.name if self.company else 'N/A'
        mapas_info = f" - {len(self.mapas_hash.split(','))} mapa(s)" if self.mapas_hash else ""
        return f"({self.lat:.6f}, {self.lon:.6f}) - {company_name}{mapas_info} - {status}"
