"""Slots e mutex para operações OLT/VPN (host e containers paralelos)."""
from __future__ import annotations

import logging
import time

from django.core.cache import cache

logger = logging.getLogger(__name__)

HOST_VPN_LOCK_KEY = "olt:host:vpn_mutex"
SLOT_KEY_PREFIX = "olt:container:slot:"
SLOT_TTL_SEC = 7200


class OltSlotBusyError(Exception):
    """Não foi possível adquirir slot/mutex dentro do timeout."""


def _slot_key(index: int) -> str:
    return f"{SLOT_KEY_PREFIX}{index}"


def acquire_host_vpn_lock(job_id: int, *, wait_timeout: float = 600) -> None:
    """Uma VPN no host por vez (multi-tenant na mesma VPS)."""
    deadline = time.time() + wait_timeout
    while time.time() < deadline:
        if cache.add(HOST_VPN_LOCK_KEY, str(job_id), SLOT_TTL_SEC):
            logger.debug("Host VPN lock adquirido job=%s", job_id)
            return
        holder = cache.get(HOST_VPN_LOCK_KEY)
        if holder == str(job_id):
            return
        time.sleep(2.0)
    raise OltSlotBusyError(
        "Outra operação OLT com VPN está em andamento. Tente novamente em alguns minutos."
    )


def release_host_vpn_lock(job_id: int) -> None:
    holder = cache.get(HOST_VPN_LOCK_KEY)
    if holder == str(job_id):
        cache.delete(HOST_VPN_LOCK_KEY)
        logger.debug("Host VPN lock liberado job=%s", job_id)


def acquire_container_slot(job_id: int, max_parallel: int, *, wait_timeout: float = 120) -> int:
    """Reserva um slot de container (até max_parallel jobs simultâneos)."""
    if max_parallel < 1:
        max_parallel = 1
    deadline = time.time() + wait_timeout
    token = str(job_id)
    while time.time() < deadline:
        for index in range(max_parallel):
            key = _slot_key(index)
            if cache.add(key, token, SLOT_TTL_SEC):
                logger.debug("Container slot %s job=%s", index, job_id)
                return index
            if cache.get(key) == token:
                return index
        time.sleep(1.0)
    raise OltSlotBusyError(
        f"Limite de {max_parallel} operação(ões) OLT em paralelo atingido. Aguarde e tente de novo."
    )


def release_container_slot(job_id: int, slot_index: int | None) -> None:
    if slot_index is None:
        return
    key = _slot_key(slot_index)
    if cache.get(key) == str(job_id):
        cache.delete(key)
        logger.debug("Container slot %s liberado job=%s", slot_index, job_id)
