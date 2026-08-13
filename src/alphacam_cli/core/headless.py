from __future__ import annotations

import os
import subprocess
from typing import Any

DEFAULT_VBS_DIR = "C:/temp"

DEFAULT_MACHINE: dict[str, Any] = {
    "psexec": "C:/temp/PsExec64.exe",
    "psexec_args": ["-accepteula", "-i", "1", "-s"],
    "cscript": "cscript",
    "use_shell": False,
}

_HEADLESS_MACRO = "ApplyMachiningAfterNesting.Events.HeadlessProcess"


def _vbs_quote(value: str) -> str:
    """Escape a value for embedding inside a double-quoted VBS string literal."""
    return value.replace('"', '""')


def build_vbs(job_name: str, out_log: str) -> str:
    """Return the headless VBScript text.

    The script attaches to the running AlphaCAM instance, runs the
    ``ApplyMachiningAfterNesting.Events.HeadlessProcess`` macro with
    ``job_name`` and writes a diagnostic log to ``out_log``.
    """
    escaped_job = _vbs_quote(job_name)
    escaped_log = _vbs_quote(out_log)
    return (
        "Option Explicit\n"
        "On Error Resume Next\n"
        "Dim fso, f, app, t0\n"
        'Set fso = CreateObject("Scripting.FileSystemObject")\n'
        f'Set f = fso.CreateTextFile("{escaped_log}", True)\n'
        'Set app = GetObject(, "Ar5axaps.Application")\n'
        'f.WriteLine "GetObject err=" & Err.Number & " " & Err.Description\n'
        "Err.Clear\n"
        "t0 = Timer\n"
        f'app.Run "{_HEADLESS_MACRO}", "{escaped_job}"\n'
        'f.WriteLine "Run err=" & Err.Number & " " & Err.Description'
        ' & " in " & Round(Timer - t0, 1) & "s"\n'
        "f.Close\n"
        'WScript.Echo "done"\n'
    )


def run_headless(
    machine: dict[str, Any],
    out_vbs: str,
    timeout_seconds: int = 300,
) -> subprocess.CompletedProcess[str]:
    """Run the headless VBScript on the machine via PsExec (Session 1 as SYSTEM)."""
    psexec = machine.get("psexec", DEFAULT_MACHINE["psexec"])
    psexec_args = list(machine.get("psexec_args", DEFAULT_MACHINE["psexec_args"]))
    cscript = machine.get("cscript", DEFAULT_MACHINE["cscript"])
    use_shell = bool(machine.get("use_shell", DEFAULT_MACHINE["use_shell"]))
    return subprocess.run(
        [psexec] + psexec_args + [cscript, "//nologo", out_vbs],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
        shell=use_shell,
    )


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

    ``status`` is the value after ``"Status przetwarzania zadania:"`` (stripped);
    ``success`` is True only when ``status`` contains ``"Sukces"`` (case-sensitive).
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
            if "Status przetwarzania zadania:" in line:
                status = line.split(":", 1)[1].strip()
                break
        try:
            file_mtime = os.path.getmtime(path)
        except OSError as e:
            return {"success": False, "status": "read_error", "detail": str(e)}
        result: dict[str, Any] = {
            "success": "Sukces" in status,
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
