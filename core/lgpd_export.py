"""
Exportação LGPD — payload completo, CSV, ZIP e downloads assinados com expiração.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.signing import BadSignature, TimestampSigner
from django.utils import timezone

from core.audit_trail import record_security_event
from core.lgpd_constants import LEGAL_DOCUMENT_VERSION
from core.models import (
    ConsentRecord,
    CustomUser,
    DataSubjectRequest,
    LgpdExportDownload,
    SecurityAuditEvent,
    Ticket,
    TicketMessage,
)

_EXPORT_SIGNER_SALT = "lgpd-export-download-v1"


def build_user_data_payload(user: CustomUser) -> dict:
    """Portabilidade — minimização onde aplicável (sem log_output OLT bruto)."""
    payload = {
        "exported_at": timezone.now().isoformat(),
        "document_version": LEGAL_DOCUMENT_VERSION,
        "export_version": "3.0",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "role": user.role,
            "is_active": user.is_active,
            "date_joined": user.date_joined.isoformat() if user.date_joined else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
        },
        "company": None,
        "consents": list(
            ConsentRecord.objects.filter(user=user).values(
                "document_type", "document_version", "accepted_at", "ip_address"
            )
        ),
        "data_subject_requests": list(
            DataSubjectRequest.objects.filter(user=user).values(
                "request_type", "status", "created_at", "completed_at", "details"
            )[:50]
        ),
        "security_audit_events": list(
            SecurityAuditEvent.objects.filter(user=user).values(
                "event_type", "severity", "created_at", "request_id"
            )[:200]
        ),
        "tickets_created": [],
        "ticket_messages_sent": [],
        "olt_jobs_summary": [],
    }

    if user.company_id:
        c = user.company
        payload["company"] = {
            "name": c.name,
            "slug": c.slug,
            "email": c.email,
            "phone": c.phone,
        }

    for t in Ticket.objects.filter(created_by=user).order_by("-created_at")[:100]:
        payload["tickets_created"].append({
            "ticket_number": t.ticket_number,
            "title": t.title,
            "description": t.description,
            "status": t.status,
            "priority": t.priority,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "closed_at": t.closed_at.isoformat() if getattr(t, "closed_at", None) else None,
        })

    for m in TicketMessage.objects.filter(sent_by=user).select_related("ticket").order_by("-created_at")[:200]:
        payload["ticket_messages_sent"].append({
            "ticket_number": m.ticket.ticket_number,
            "message": m.message,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })

    try:
        from olt_ops.models import OnuCleanupJob

        for job in OnuCleanupJob.objects.filter(created_by=user).order_by("-created_at")[:50]:
            payload["olt_jobs_summary"].append({
                "id": job.id,
                "status": job.status,
                "gpon_port": job.gpon_port,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "log_bytes": len(job.log_output or ""),
            })
    except Exception:
        pass

    return payload


def payload_to_csv(payload: dict) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["section", "field", "value"])

    def _flatten(prefix: str, obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                _flatten(f"{prefix}.{k}" if prefix else k, v)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _flatten(f"{prefix}[{i}]", item)
        else:
            writer.writerow([prefix.rsplit(".", 1)[0] if "." in prefix else prefix, prefix, obj])

    for key, val in payload.items():
        if isinstance(val, (dict, list)):
            _flatten(key, val)
        else:
            writer.writerow(["meta", key, val])
    return buf.getvalue()


def payload_to_zip_bytes(payload: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("dados.json", json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        zf.writestr("dados.csv", payload_to_csv(payload))
        zf.writestr(
            "LEIA-ME.txt",
            "Exportação LGPD — RM Systems\n"
            f"Gerado em: {payload.get('exported_at')}\n"
            f"Versão legal: {payload.get('document_version')}\n",
        )
    return buf.getvalue()


def _export_storage_dir(user_id: int) -> Path:
    root = Path(settings.MEDIA_ROOT) / "lgpd_exports" / str(user_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _export_ttl_hours() -> int:
    return int(getattr(settings, "LGPD_EXPORT_TTL_HOURS", 24))


def sign_export_token(export_id: int, user_id: int) -> str:
    signer = TimestampSigner(salt=_EXPORT_SIGNER_SALT)
    return signer.sign(f"{export_id}:{user_id}")


def unsign_export_token(token: str) -> tuple[int, int] | None:
    signer = TimestampSigner(salt=_EXPORT_SIGNER_SALT)
    max_age = _export_ttl_hours() * 3600
    try:
        raw = signer.unsign(token, max_age=max_age)
        export_id, user_id = raw.split(":", 1)
        return int(export_id), int(user_id)
    except (BadSignature, ValueError):
        return None


def create_signed_zip_export(user: CustomUser, request=None) -> LgpdExportDownload:
    """Gera ZIP em disco e registro com URL assinada temporária."""
    payload = build_user_data_payload(user)
    data = payload_to_zip_bytes(payload)
    digest = hashlib.sha256(data).hexdigest()

    artifact = LgpdExportDownload.objects.create(
        user=user,
        export_format="zip",
        file_size=len(data),
        checksum_sha256=digest,
        expires_at=timezone.now() + timedelta(hours=_export_ttl_hours()),
        max_downloads=int(getattr(settings, "LGPD_EXPORT_MAX_DOWNLOADS", 5)),
    )
    path = _export_storage_dir(user.pk) / f"export_{artifact.pk}.zip"
    path.write_bytes(data)
    artifact.storage_path = str(path.relative_to(settings.MEDIA_ROOT)).replace("\\", "/")
    artifact.save(update_fields=["storage_path"])

    record_security_event(
        "lgpd_export_created",
        user=user,
        request=request,
        details={
            "export_id": artifact.pk,
            "format": "zip",
            "checksum_sha256": digest[:16],
            "expires_at": artifact.expires_at.isoformat(),
        },
    )
    return artifact


def resolve_export_download(token: str, user: CustomUser) -> Path | None:
    parsed = unsign_export_token(token)
    if not parsed:
        return None
    export_id, user_id = parsed
    if user_id != user.pk:
        return None
    try:
        artifact = LgpdExportDownload.objects.get(pk=export_id, user=user)
    except LgpdExportDownload.DoesNotExist:
        return None
    if artifact.is_expired:
        return None
    if artifact.download_count >= artifact.max_downloads:
        return None
    full = Path(settings.MEDIA_ROOT) / artifact.storage_path
    if not full.is_file():
        return None
    artifact.download_count += 1
    artifact.last_downloaded_at = timezone.now()
    artifact.save(update_fields=["download_count", "last_downloaded_at"])
    return full


def purge_expired_exports() -> int:
    cutoff = timezone.now()
    qs = LgpdExportDownload.objects.filter(expires_at__lt=cutoff)
    removed = 0
    for art in qs.iterator():
        if art.storage_path:
            p = Path(settings.MEDIA_ROOT) / art.storage_path
            if p.is_file():
                p.unlink(missing_ok=True)
        art.delete()
        removed += 1
    return removed
