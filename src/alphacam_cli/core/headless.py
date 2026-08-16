from __future__ import annotations

import os
import time
from typing import Any

_HEADLESS_MACRO = "ApplyMachiningAfterNesting.Events.HeadlessProcess"
_MACRO_LOG_DEFAULT = r"C:\temp\ama_macro_log.txt"
_MACRO_STALE_AFTER_S = (
    300.0  # 5 minut bez zakończenia = na pewno zawieszone (normalny czas ~40s, watchdog 330s)
)


def macro_invocation_state(
    log_path: str = _MACRO_LOG_DEFAULT,
    *,
    stale_after_s: float = _MACRO_STALE_AFTER_S,
    now: float | None = None,
) -> dict[str, Any]:
    """Report whether the last headless macro invocation completed.

    ``state`` is ``ok`` when the last sequence ended with ``r``, ``stale`` when
    the last sequence is incomplete and the log is older than ``stale_after_s``,
    ``running`` when incomplete but recent (another client is processing),
    ``missing`` when the log does not exist or contains no ``PN=`` sequence
    (the macro never ran; never blocks), and ``unreadable`` when the log cannot
    be read. ``last_pn`` is the last job name after ``PN=`` and ``last_line``
    the last non-empty log line.
    """
    if not os.path.exists(log_path):
        return {"state": "missing", "last_pn": None, "last_line": "", "mtime": None}
    try:
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            log = fh.read()
    except OSError:
        return {"state": "unreadable", "last_pn": None, "last_line": "", "mtime": None}
    try:
        mtime = os.path.getmtime(log_path)
    except OSError:
        return {"state": "unreadable", "last_pn": None, "last_line": "", "mtime": None}
    last_pn: str | None = None
    last_line = ""
    seen_pn = False
    completed = False
    for line in log.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        last_line = stripped
        if "PN=" in stripped:
            seen_pn = True
            completed = False
            last_pn = stripped.split("PN=", 1)[1].strip()
        elif seen_pn and stripped.split()[-1] == "got":
            completed = False
        elif seen_pn and stripped.split()[-1] == "r":
            completed = True
    if completed:
        state = "ok"
    elif not seen_pn:
        state = "missing"
    else:
        clock = time.time() if now is None else now
        state = "running" if clock - mtime <= stale_after_s else "stale"
    return {"state": state, "last_pn": last_pn, "last_line": last_line, "mtime": mtime}


def _job_log_candidates(job_name: str, output_root: str) -> list[str]:
    """Candidate Automation Manager log paths (forward- and backslash variants)."""
    base = os.path.join(output_root, job_name, f"{job_name}.log")
    candidates: list[str] = []
    for path in (base, base.replace("/", "\\")):
        if path not in candidates:
            candidates.append(path)
    return candidates


def read_job_result(
    job_name: str, output_root: str, min_mtime: float | None = None
) -> dict[str, Any]:
    """Read the Automation Manager job log and return its status as a dict.

    ``status`` is the value after the first colon on the first line containing
    ``"status"`` (case-insensitive, locale-agnostic); ``success`` is True when
    ``status`` contains ``"sukces"`` or ``"success"`` (case-insensitive).
    When ``min_mtime`` is given, log files modified before it are skipped as if
    they did not exist.
    """
    if "/" in job_name or "\\" in job_name or job_name in (".", ".."):
        return {
            "success": False,
            "status": "missing",
            "detail": f"invalid job name: {job_name}",
        }
    candidates = _job_log_candidates(job_name, output_root)
    stale_path: str | None = None
    for path in candidates:
        if not os.path.exists(path):
            continue
        if min_mtime is not None:
            try:
                mtime = os.path.getmtime(path)
            except OSError as e:
                return {"success": False, "status": "read_error", "detail": str(e)}
            if mtime < min_mtime:
                if stale_path is None:
                    stale_path = path
                continue
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                log = fh.read()
        except OSError as e:
            return {"success": False, "status": "read_error", "detail": str(e)}
        status = ""
        for line in log.splitlines():
            if ":" in line and "status" in line.lower():
                status = line.split(":", 1)[1].strip()
                break
        try:
            file_mtime = os.path.getmtime(path)
        except OSError as e:
            return {"success": False, "status": "read_error", "detail": str(e)}
        result: dict[str, Any] = {
            "success": "sukces" in status.lower() or "success" in status.lower(),
            "status": status,
            "log": log,
            "file_mtime": file_mtime,
        }
        return result
    if stale_path is not None:
        return {
            "success": False,
            "status": "missing",
            "detail": f"job log is stale (mtime older than process start): {stale_path}",
        }
    return {
        "success": False,
        "status": "missing",
        "detail": f"job log not found: {candidates[0]}",
    }
