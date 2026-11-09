"""
Mensagens amigáveis para o usuário — OLT/ONU e VPN.
Evita expor detalhes técnicos na UI; o log técnico permanece no job.
"""
from __future__ import annotations

import re

JOB_STATUS_USER = {
    "draft": "Aguardando",
    "queued": "Na fila",
    "listing": "Buscando ONUs offline",
    "ready": "Lista pronta",
    "running": "Excluindo ONUs",
    "done": "Concluído",
    "failed": "Não concluído",
}

JOB_STATUS_HINT = {
    "draft": "Preencha os dados e inicie a operação.",
    "queued": "Outra operação OLT está em andamento. Este job iniciará automaticamente quando houver slot.",
    "listing": "Conectando na OLT e buscando equipamentos offline…",
    "ready": "Copie os números de série para o painel de exclusão.",
    "running": "Removendo ONUs na OLT. Isso pode levar alguns minutos.",
    "done": "Operação finalizada. Confira o resumo abaixo.",
    "failed": "Algo não foi concluído. Veja o resumo ou o log técnico.",
}


def job_status_label(status: str) -> str:
    return JOB_STATUS_USER.get(status, status)


def job_status_hint(status: str, *, running: bool = False) -> str:
    if running:
        return JOB_STATUS_HINT.get(status, "Processando…")
    return JOB_STATUS_HINT.get(status, "Operação finalizada.")


def parse_job_summary(log: str) -> str:
    """Extrai uma linha de resumo legível do log técnico."""
    if not log:
        return ""
    for line in reversed(log.splitlines()):
        t = line.strip()
        if not t:
            continue
        if t.startswith("Resumo:"):
            return _friendly_summary_line(t)
        if "removida(s)" in t.lower() or "falha(s)" in t.lower():
            return _friendly_summary_line(t)
        if t.startswith("ERRO VPN:"):
            low = t.lower()
            if "não respondeu" in low or "nao respondeu" in low or "timed out" in low:
                return (
                    "A VPN conectou, mas a OLT não respondeu (SSH/Telnet). "
                    "Confira IP, protocolo e porta no cadastro da OLT — ou use o teste em VPN da empresa."
                )
            return "Não foi possível conectar na VPN. Verifique usuário, senha e servidor em VPN da empresa."
        if t.startswith("ERRO:"):
            return "Não foi possível concluir a operação. Abra o log técnico para detalhes."
    if "Teste concluído" in log:
        return "Conexão VPN e OLT funcionando."
    if "Falha:" in log:
        return "Teste de VPN não passou. Revise servidor, usuário e senha."
    return ""


def _friendly_summary_line(line: str) -> str:
    m = re.search(
        r"(\d+)\s+removida\(s\).*?(\d+)\s+falha",
        line,
        re.I,
    )
    if m:
        ok, fail = int(m.group(1)), int(m.group(2))
        parts = [f"{ok} ONU(s) removida(s) com sucesso"]
        if fail:
            parts.append(
                f"{fail} não encontrada(s) ou já tinham sido removidas"
            )
        return ". ".join(parts) + "."
    if "não localizado" in line.lower() or "does not exist" in line.lower():
        return "Algumas ONUs já não existem na OLT (podem ter sido removidas antes)."
    return line.replace("Resumo:", "").strip()


def vpn_test_message(ok: bool) -> tuple[str, str]:
    if ok:
        return (
            "Conexão OK",
            "A VPN e a OLT responderam corretamente.",
        )
    return (
        "Conexão falhou",
        "Não foi possível alcançar a OLT pela VPN. Confira os dados e tente de novo.",
    )


def sanitize_vpn_test_log(log: str) -> str:
    """Remove ruído técnico do log de teste VPN para exibição opcional."""
    if not log:
        return ""
    skip_fragments = ("CLIXML", "<Objs", "xmlns", "Preparing modules", "#<")
    lines = []
    for ln in log.splitlines():
        s = ln.strip()
        if not s:
            continue
        if any(f in s for f in skip_fragments):
            continue
        if s.startswith("<") or s.startswith("{"):
            continue
        lines.append(ln)
    return "\n".join(lines[-25:])
