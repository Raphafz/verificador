"""Listagem offline e exclusão de ONUs na OLT."""
from __future__ import annotations

from collections.abc import Callable

from django.utils import timezone

from .gpon_parse import (
    GponPort,
    OnuTarget,
    onu_target_from_zte_job_line,
    parse_huawei_offline_serials,
    parse_zte_by_sn,
    parse_zte_offline_onu_ids,
    zte_onu_id_from_job_line,
)
from .huawei_delete import run_huawei_delete_batch
from .models import OnuCleanupJob, OltEquipment
from .olt_session import OltConnectionError, OltSession
from .operational_log import append_to_job_log, log_to_operations_file, sanitize_chunk


def _append_log(
    job: OnuCleanupJob,
    lines: list[str],
    log_sink: Callable[[str], None] | None = None,
) -> None:
    block = sanitize_chunk("\n".join(lines).strip())
    if not block:
        return
    if log_sink:
        stamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sink(f"[{stamp}]")
        for line in block.splitlines():
            log_sink(line)
        return
    stamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    chunk = f"\n[{stamp}]\n{block}\n"
    job.log_output = append_to_job_log(job.log_output or "", chunk)
    job.save(update_fields=["log_output", "updated_at"])
    log_to_operations_file(job.pk, chunk)


def _huawei_list_command(gpon: GponPort, custom: str) -> str:
    """Comando igual ao archive/legacy-desktop-tools/listar_ont_offline.py (sem | include)."""
    if custom.strip():
        return custom.strip()
    return f"display ont info {gpon.frame} {gpon.slot} {gpon.port} all"


def list_offline_onus(
    job: OnuCleanupJob,
    log_sink: Callable[[str], None] | None = None,
) -> None:
    olt: OltEquipment = job.olt
    gpon = GponPort.parse(job.gpon_port)
    job.status = "listing"
    job.save(update_fields=["status", "updated_at"])

    session = OltSession(olt, log_sink=log_sink)
    try:
        session.connect()
        if olt.vendor == "huawei":
            cmd = _huawei_list_command(gpon, olt.list_command)
            output = session.run_huawei_offline_list(cmd, max_total=600.0)
            entries = parse_huawei_offline_serials(output, gpon)
            label = "SN(s)"
        else:
            pon = gpon.zte_pon_id()
            iface = f"gpon-olt_{pon}"
            cmd = (
                olt.list_command.strip()
                if olt.list_command.strip()
                else f"show pon power olt-rx {iface}"
            )
            power_out = session.run_zte_offline_list(
                pon,
                command=cmd if olt.list_command.strip() else None,
            )
            onu_ids = parse_zte_offline_onu_ids(power_out, gpon)
            entries = [str(oid) for oid in onu_ids]
            label = "ONU(s) offline (no signal)"
            for oid in onu_ids:
                session._log(f"offline: gpon-onu_{pon}:{oid} (no signal)")
            if onu_ids:
                session._log(f"IDs: {', '.join(str(i) for i in onu_ids)}")

        job.serial_numbers = "\n".join(entries)
        job.status = "ready" if job.serial_numbers.strip() else "draft"
        summary = [
            f"--- Listagem concluída: {len(job.serial_list())} {label} (no signal) ---",
            f"--- Comando: {cmd} ---",
        ]
        if log_sink:
            for line in summary:
                log_sink(line)
        else:
            _append_log(job, session.log + summary)
        job.save(update_fields=["serial_numbers", "status", "updated_at"])
    except OltConnectionError as exc:
        job.status = "failed"
        if log_sink:
            log_sink(f"ERRO: {exc}")
        else:
            _append_log(job, session.log + [f"ERRO: {exc}"])
        job.save(update_fields=["status", "log_output", "updated_at"])
        raise
    finally:
        session.close()


def _zte_delete_commands(target: OnuTarget, olt: OltEquipment) -> list[str]:
    """interface gpon-olt_F/S/P → no onu N → exit."""
    pon = target.pon_id or f"{target.frame}/{target.slot}/{target.port}"
    onu_num = target.onu_number or 0
    enable_pw = olt.zte_enable_secret()
    return [
        "enable",
        enable_pw,
        "conf t",
        f"interface gpon-olt_{pon}",
        f"no onu {onu_num}",
        "exit",
    ]


def _zte_delete_batch_commands(
    gpon: GponPort,
    onu_ids: list[int],
    olt: OltEquipment,
) -> list[str]:
    """Uma interface; vários ``no onu``; exit."""
    pon = gpon.zte_pon_id()
    enable_pw = olt.zte_enable_secret()
    cmds = ["enable", enable_pw, "conf t", f"interface gpon-olt_{pon}"]
    for onu_num in onu_ids:
        cmds.append(f"no onu {onu_num}")
    cmds.append("exit")
    return cmds


def _optional_gpon_port(raw: str) -> GponPort | None:
    text = (raw or "").strip()
    if not text or text in ("0/0/0", "-", "—"):
        return None
    try:
        return GponPort.parse(text)
    except ValueError:
        return None


def delete_onus(
    job: OnuCleanupJob,
    log_sink: Callable[[str], None] | None = None,
) -> dict:
    olt: OltEquipment = job.olt
    gpon_hint = _optional_gpon_port(job.gpon_port)
    serials = job.serial_list()
    if not serials:
        raise ValueError("Nenhum serial para excluir.")

    job.status = "running"
    job.save(update_fields=["status", "updated_at"])

    session = OltSession(olt, log_sink=log_sink)
    try:
        session.connect()
        if olt.vendor == "huawei":
            if not session._channel:
                raise OltConnectionError("Canal SSH indisponível")
            result = run_huawei_delete_batch(
                session._channel,
                olt.password,
                serials,
                log_fn=log_sink or session._log,
            )
        else:
            gpon = gpon_hint or GponPort.parse(job.gpon_port)
            onu_ids: list[int] = []
            legacy_sns: list[str] = []
            for line in serials:
                oid = zte_onu_id_from_job_line(line)
                if oid is not None:
                    onu_ids.append(oid)
                else:
                    legacy_sns.append(line)

            ok = 0
            fail = 0
            if onu_ids:
                session._log(
                    f"--- Exclusão ZTE: {len(onu_ids)} ONU(s) em gpon-olt_{gpon.zte_pon_id()} ---"
                )
                try:
                    session.run_commands(
                        _zte_delete_batch_commands(gpon, onu_ids, olt),
                        pause=0.8,
                        idle_wait=20.0,
                    )
                    for oid in onu_ids:
                        session._log(f"ONU {oid}: OK (no onu {oid})")
                    ok += len(onu_ids)
                except Exception as exc:
                    session._log(f"Lote ZTE: ERRO {exc}")
                    fail += len(onu_ids)

            for sn in legacy_sns:
                session._log(f"--- SN {sn} (legado) ---")
                try:
                    enable_pw = olt.zte_enable_secret()
                    lookup = session.run_commands(
                        ["enable", enable_pw, "conf t", f"show gpon onu by sn {sn}"],
                        pause=1.0,
                        idle_wait=15.0,
                    )
                    target = parse_zte_by_sn(lookup, sn, gpon)
                    if not target:
                        session._log(f"SN {sn}: não localizado (ZTE)")
                        fail += 1
                        continue
                    session.run_commands(
                        _zte_delete_commands(target, olt),
                        pause=0.8,
                        idle_wait=12.0,
                    )
                    session._log(f"SN {sn}: OK")
                    ok += 1
                except Exception as exc:
                    session._log(f"SN {sn}: ERRO {exc}")
                    fail += 1
            result = {"ok": ok, "fail": fail, "total": len(serials)}

        ok = result["ok"]
        fail = result["fail"]
        job.status = "done" if fail == 0 else ("failed" if ok == 0 else "done")
        summary = (
            f"Resumo: {ok} removida(s), {fail} falha(s) ou já inexistente(s), "
            f"total {len(serials)}"
        )
        if log_sink:
            log_sink(summary)
        else:
            _append_log(job, [summary])
        job.save(update_fields=["status", "updated_at"])
        return result
    except OltConnectionError as exc:
        job.status = "failed"
        if log_sink:
            log_sink(f"ERRO: {exc}")
        else:
            _append_log(job, session.log + [f"ERRO: {exc}"])
        job.save(update_fields=["status", "updated_at"])
        raise
    finally:
        session.close()
