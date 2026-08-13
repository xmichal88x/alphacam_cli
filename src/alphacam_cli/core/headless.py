from __future__ import annotations

import os
from typing import Any

_HEADLESS_MACRO = "ApplyMachiningAfterNesting.Events.HeadlessProcess"


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
