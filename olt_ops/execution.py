"""Resolução de modo de execução OLT (host vs container) por empresa."""
from __future__ import annotations

from django.conf import settings

from .models import CompanyOltExecutionConfig


def get_execution_config(company) -> CompanyOltExecutionConfig | None:
    try:
        return company.olt_execution
    except CompanyOltExecutionConfig.DoesNotExist:
        return None


def get_execution_mode(company) -> str:
    cfg = get_execution_config(company)
    if cfg and cfg.worker_mode:
        return cfg.worker_mode
    return getattr(settings, "OLT_EXECUTION_MODE", "host")


def get_max_concurrent_jobs(company) -> int:
    cfg = get_execution_config(company)
    if cfg and cfg.max_concurrent_jobs:
        return int(cfg.max_concurrent_jobs)
    return int(getattr(settings, "OLT_MAX_PARALLEL_JOBS", 5))


def company_needs_vpn(company) -> bool:
    try:
        vpn = company.vpn_config
    except Exception:
        return False
    return bool(vpn and vpn.is_configured())


def docker_available() -> bool:
    import shutil

    binary = getattr(settings, "OLT_DOCKER_BINARY", "docker")
    return shutil.which(binary) is not None


def effective_execution_mode(company) -> str:
    """Container só se Docker existir; senão host com mutex VPN."""
    mode = get_execution_mode(company)
    if mode == "container" and not docker_available():
        return "host"
    return mode
