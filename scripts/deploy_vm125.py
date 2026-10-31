#!/usr/bin/env python3
"""Deterministic deployment of alphacam_cli to a remote Windows host."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_PREFLIGHT = 2

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SRC = REPO_ROOT / "src" / "alphacam_cli"
DEFAULT_STATE_FILE = Path.home() / ".alphacam_deploy_state.json"
DEFAULT_BACKUP_ROOT = "C:/temp"
SERVICE_POLL_SECONDS = 2.0
SERVICE_WAIT_SECONDS = 40.0
HEALTH_TIMEOUT_SECONDS = 90.0
HEALTH_INTERVAL_SECONDS = 5.0
NO_REMOTE_HASHES = "remote hash collection returned no .py files"
DEFAULT_CLI = Path("./.venv/bin/alphacam")

Runner = Callable[..., subprocess.CompletedProcess[str]]


class DeployError(RuntimeError):
    """Raised when a deployment step cannot be completed."""


@dataclass(frozen=True)
class CommandResult:
    """Result of a single local or remote command invocation."""

    args: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        """Return True when the command exited with status 0."""
        return self.returncode == 0

    @property
    def detail(self) -> str:
        """Return a compact diagnostic string for error messages."""
        return self.stderr.strip() or self.stdout.strip() or f"exit {self.returncode}"


@dataclass(frozen=True)
class HealthStatus:
    """Outcome of one remote health probe."""

    available: bool
    ok: bool
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RemoteConfig:
    """Connection and target settings for a remote deployment."""

    host: str = "192.168.100.60"
    user: str = "AlphaCam"
    remote_dir: str = "C:/alphacam_cli"
    service: str = "AlphaCAMGateway"
    nssm: str = "C:/temp/nssm/nssm.exe"
    timeout: float = 60.0
    password: str | None = field(default=None, repr=False)

    @property
    def target(self) -> str:
        """Return the ssh/scp target in user@host form."""
        return f"{self.user}@{self.host}"

    @property
    def remote_source(self) -> str:
        """Return the remote source directory as a Windows path."""
        return win_join(self.remote_dir, "src", "alphacam_cli")


@dataclass(frozen=True)
class DeployState:
    """Locally persisted record of the most recent deployment."""

    timestamp: str
    host: str
    user: str
    remote_dir: str
    service: str
    backup_dir: str
    hashes: dict[str, str]

    def to_json(self) -> dict[str, Any]:
        """Serialize the state to a JSON-compatible mapping."""
        return {
            "timestamp": self.timestamp,
            "host": self.host,
            "user": self.user,
            "remote_dir": self.remote_dir,
            "service": self.service,
            "backup_dir": self.backup_dir,
            "hashes": self.hashes,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> DeployState:
        """Build a state object from a JSON mapping."""
        hashes = data.get("hashes") or {}
        return cls(
            timestamp=str(data.get("timestamp", "")),
            host=str(data.get("host", "")),
            user=str(data.get("user", "")),
            remote_dir=str(data.get("remote_dir", "")),
            service=str(data.get("service", "")),
            backup_dir=str(data.get("backup_dir", "")),
            hashes={str(k): str(v) for k, v in hashes.items()},
        )


def win_join(base: str, *parts: str) -> str:
    """Join Windows path parts with backslashes."""
    cleaned = [base.replace("/", "\\").rstrip("\\")]
    cleaned.extend(part.replace("/", "\\").strip("\\") for part in parts)
    return "\\".join(cleaned)


def ps_quote(value: str) -> str:
    """Quote a value as a PowerShell single-quoted string literal."""
    return "'" + value.replace("'", "''") + "'"


def cmd_quote(value: str) -> str:
    """Quote a value for cmd.exe, always using double quotes."""
    return '"' + value.replace('"', '""') + '"'


def build_restart_command(config: RemoteConfig) -> str:
    """Return the nssm restart command as one quoted remote-shell argument."""
    nssm = config.nssm.replace("/", "\\")
    return f"{cmd_quote(nssm)} restart {cmd_quote(config.service)}"


def resolve_cli(executable: str | None = None) -> str | None:
    """Resolve the alphacam CLI path: explicit, then venv, then PATH."""
    if executable:
        return executable
    if DEFAULT_CLI.exists() and os.access(DEFAULT_CLI, os.X_OK):
        return str(DEFAULT_CLI)
    return shutil.which("alphacam")


def scp_remote_path(path: str) -> str:
    """Normalize a Windows path for use in an scp remote argument."""
    return path.replace("\\", "/")


def build_ssh_command(config: RemoteConfig, remote_command: str) -> list[str]:
    """Build an ssh invocation, optionally wrapped with sshpass."""
    options = ["-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new"]
    if config.password:
        return ["sshpass", "-p", config.password, "ssh", *options, config.target, remote_command]
    return ["ssh", *options, "-o", "BatchMode=yes", config.target, remote_command]


def build_scp_command(config: RemoteConfig, local_path: Path, remote_path: str) -> list[str]:
    """Build an scp invocation, optionally wrapped with sshpass."""
    options = ["-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new"]
    remote = f"{config.target}:{scp_remote_path(remote_path)}"
    if config.password:
        return ["sshpass", "-p", config.password, "scp", *options, str(local_path), remote]
    return ["scp", *options, "-o", "BatchMode=yes", str(local_path), remote]


def run_command(args: Sequence[str], timeout: float, runner: Runner | None = None) -> CommandResult:
    """Run a command without raising, converting failures into results."""
    invoke = runner if runner is not None else subprocess.run
    argv = [str(part) for part in args]
    try:
        completed = invoke(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return CommandResult(argv, 127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        return CommandResult(argv, 124, _as_text(exc.stdout), _as_text(exc.stderr))
    except OSError as exc:
        return CommandResult(argv, 126, "", str(exc))
    return CommandResult(
        argv,
        int(completed.returncode),
        _as_text(completed.stdout),
        _as_text(completed.stderr),
    )


def _as_text(value: str | bytes | None) -> str:
    """Normalize captured process output to text."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_ssh(
    config: RemoteConfig, remote_command: str, runner: Runner | None = None
) -> CommandResult:
    """Run one command on the remote host over ssh."""
    return run_command(build_ssh_command(config, remote_command), config.timeout, runner)


def run_powershell(
    config: RemoteConfig, script: str, runner: Runner | None = None
) -> CommandResult:
    """Run one PowerShell script on the remote host."""
    remote = f'powershell -NoProfile -NonInteractive -Command "{script}"'
    return run_ssh(config, remote, runner)


def preflight(config: RemoteConfig, runner: Runner | None = None) -> None:
    """Verify connectivity, remote directory, and service existence."""
    probe = run_ssh(config, "cmd /c echo ok", runner)
    if not probe.ok:
        raise DeployError("SSH connection failed: " + probe.detail)

    directory = run_powershell(
        config,
        f"if (-not (Test-Path -LiteralPath {ps_quote(config.remote_source)})) {{ exit 3 }}",
        runner,
    )
    if not directory.ok:
        detail = config.remote_source + " (" + directory.detail + ")"
        raise DeployError("remote source directory not found: " + detail)

    service = run_powershell(
        config,
        "if (-not (Get-Service -Name "
        f"{ps_quote(config.service)} -ErrorAction SilentlyContinue)) {{ exit 3 }}",
        runner,
    )
    if not service.ok:
        raise DeployError("service not found: " + config.service + " (" + service.detail + ")")


def create_backup(
    config: RemoteConfig,
    runner: Runner | None = None,
    *,
    timestamp: str | None = None,
    backup_root: str = DEFAULT_BACKUP_ROOT,
) -> str:
    """Copy the remote source tree to a timestamped backup directory."""
    stamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = win_join(backup_root, f"deploy_backup_{stamp}")
    command = (
        f"cmd /c xcopy /E /I /H /Y {cmd_quote(config.remote_source)} {cmd_quote(backup_dir)} >NUL"
    )
    result = run_ssh(config, command, runner)
    if not result.ok:
        raise DeployError("backup failed: " + result.detail)
    return backup_dir


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA256 hex digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_local_hashes(root: Path = LOCAL_SRC) -> dict[str, str]:
    """Map relative POSIX paths of local .py files to their SHA256 digests."""
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*.py")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        hashes[path.relative_to(root).as_posix()] = sha256_file(path)
    return hashes


def build_hash_script(root: str) -> str:
    """Build PowerShell that prints '<relative>|<sha256>' for every .py file."""
    normalized = root.replace("/", "\\").rstrip("\\")
    return (
        f"$root = {ps_quote(normalized)}; "
        "Get-ChildItem -LiteralPath $root -Recurse -File | "
        "Where-Object { $_.Extension -eq '.py' } | "
        "ForEach-Object { "
        "$rel = $_.FullName.Substring($root.Length).TrimStart('\\'); "
        "$hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower(); "
        "Write-Output ($rel.Replace('\\', '/') + '|' + $hash) }"
    )


def parse_remote_hashes(output: str) -> dict[str, str]:
    """Parse '<relative>|<sha256>' lines from remote PowerShell output."""
    hashes: dict[str, str] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if "|" not in line:
            continue
        name, digest = line.rsplit("|", 1)
        name = name.strip().replace("\\", "/").lstrip("./")
        digest = digest.strip().lower()
        if name and len(digest) == 64:
            hashes[name] = digest
    return hashes


def collect_remote_hashes(
    config: RemoteConfig,
    remote_source: str | None = None,
    runner: Runner | None = None,
) -> dict[str, str]:
    """Return SHA256 digests for every remote .py file in one PowerShell pass."""
    root = remote_source or config.remote_source
    result = run_powershell(config, build_hash_script(root), runner)
    if not result.ok:
        raise DeployError("remote hash collection failed: " + result.detail)
    hashes = parse_remote_hashes(result.stdout)
    if not hashes:
        raise DeployError(NO_REMOTE_HASHES)
    return hashes


def compare_hashes(local: dict[str, str], remote: dict[str, str]) -> list[str]:
    """Return human-readable differences between two hash maps."""
    problems: list[str] = []
    for name in sorted(set(local) - set(remote)):
        problems.append(f"missing remotely: {name}")
    for name in sorted(set(remote) - set(local)):
        problems.append(f"unexpected remotely: {name}")
    for name in sorted(set(local) & set(remote)):
        if local[name] != remote[name]:
            problems.append(f"hash mismatch: {name}")
    return problems


def create_archive(source: Path, destination: Path) -> int:
    """Pack a source tree into a tar.gz archive and return the file count."""
    count = 0
    with tarfile.open(destination, "w:gz") as archive:
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(source)
            if "__pycache__" in relative.parts or path.suffix == ".pyc":
                continue
            archive.add(path, arcname=f"alphacam_cli/{relative.as_posix()}")
            count += 1
    return count


def upload_tree(
    config: RemoteConfig,
    runner: Runner | None = None,
    *,
    timestamp: str | None = None,
    local_source: Path = LOCAL_SRC,
) -> int:
    """Upload an archive and atomically replace the remote source tree."""
    if not local_source.is_dir():
        raise DeployError("local source directory not found: " + str(local_source))
    stamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    remote_archive = f"C:/temp/deploy_{stamp}.tgz"
    stage_dir = win_join("C:/temp", f"deploy_stage_{stamp}")
    with tempfile.TemporaryDirectory(prefix="alphacam-deploy-") as tmp:
        archive_path = Path(tmp) / "payload.tar.gz"
        file_count = create_archive(local_source, archive_path)
        if file_count == 0:
            raise DeployError("no files to upload from " + str(local_source))
        upload = run_command(
            build_scp_command(config, archive_path, remote_archive),
            config.timeout,
            runner,
        )
        if not upload.ok:
            raise DeployError("upload failed: " + upload.detail)

    target = config.remote_source
    staged_tree = win_join(stage_dir, "alphacam_cli")
    script = (
        f"if (Test-Path -LiteralPath {ps_quote(stage_dir)}) {{ "
        f"Remove-Item -LiteralPath {ps_quote(stage_dir)} -Recurse -Force }}; "
        f"New-Item -ItemType Directory -Force -Path {ps_quote(stage_dir)} | Out-Null; "
        f"tar -xzf {ps_quote(remote_archive)} -C {ps_quote(stage_dir)}; "
        f"if (-not (Test-Path -LiteralPath {ps_quote(staged_tree)})) {{ exit 3 }}; "
        f"if (Test-Path -LiteralPath {ps_quote(target)}) {{ "
        f"Remove-Item -LiteralPath {ps_quote(target)} -Recurse -Force }}; "
        f"Move-Item -LiteralPath {ps_quote(staged_tree)} -Destination {ps_quote(target)}; "
        f"Remove-Item -LiteralPath {ps_quote(stage_dir)} -Recurse -Force"
    )
    swap = run_powershell(config, script, runner)
    if not swap.ok:
        raise DeployError("remote swap failed: " + swap.detail)
    return file_count


def service_status(config: RemoteConfig, runner: Runner | None = None) -> str | None:
    """Return the service state token reported by sc query, or None."""
    result = run_ssh(config, "cmd /c sc query " + cmd_quote(config.service), runner)
    if not result.ok:
        return None
    match = re.search(
        r"\b(RUNNING|STOPPED|START_PENDING|STOP_PENDING|PAUSED|CONTINUE_PENDING)\b",
        result.stdout,
        re.IGNORECASE,
    )
    return match.group(1) if match else None


def restart_service(
    config: RemoteConfig,
    runner: Runner | None = None,
    *,
    wait_seconds: float = SERVICE_WAIT_SECONDS,
    poll_seconds: float = SERVICE_POLL_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Restart the service and poll until it reports RUNNING."""
    result = run_ssh(config, build_restart_command(config), runner)
    if not result.ok:
        raise DeployError("service restart failed: " + result.detail)

    deadline = time.monotonic() + wait_seconds
    last = "unknown"
    while True:
        status = service_status(config, runner)
        last = status or "unknown"
        if last.lower() == "running":
            return last
        if time.monotonic() >= deadline:
            break
        sleep(poll_seconds)
    raise DeployError("service did not reach RUNNING: " + config.service + " (last: " + last + ")")


def parse_last_json(text: str) -> dict[str, Any] | None:
    """Return the last JSON object found in text, or None."""
    for raw_line in reversed(text.strip().splitlines()):
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def probe_health(
    config: RemoteConfig,
    runner: Runner | None = None,
    *,
    executable: str | None = None,
) -> HealthStatus:
    """Run one health probe and return its availability, verdict, and payload."""
    cli = resolve_cli(executable)
    if not cli:
        return HealthStatus(available=False, ok=False)
    result = run_command(
        [cli, "--remote", "--host", config.host, "health", "health"],
        config.timeout,
        runner,
    )
    if not result.ok:
        return HealthStatus(available=True, ok=False)
    payload = parse_last_json(result.stdout)
    return HealthStatus(
        available=True,
        ok=bool(payload and payload.get("ok") is True),
        payload=payload or {},
    )


def check_health(
    config: RemoteConfig,
    runner: Runner | None = None,
    *,
    executable: str | None = None,
) -> bool | None:
    """Return True when remote health is ok, None when the CLI is unavailable."""
    status = probe_health(config, runner, executable=executable)
    if not status.available:
        return None
    return status.ok


def wait_for_health(
    config: RemoteConfig,
    runner: Runner | None = None,
    *,
    executable: str | None = None,
    timeout: float = HEALTH_TIMEOUT_SECONDS,
    interval: float = HEALTH_INTERVAL_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    out: Callable[[str], None] = print,
) -> HealthStatus:
    """Poll health until ok, the time budget is exhausted, or the CLI is missing."""
    attempts = max(1, math.ceil(timeout / interval)) if interval > 0 else 1
    status = HealthStatus(available=False, ok=False)
    for attempt in range(1, attempts + 1):
        status = probe_health(config, runner, executable=executable)
        if not status.available:
            return status
        verdict = "ok" if status.ok else "not ok"
        out(f"  health attempt {attempt}/{attempts}: {verdict}")
        if status.ok:
            return status
        if attempt < attempts and interval > 0:
            sleep(interval)
    return status


def save_state(state: DeployState, path: Path = DEFAULT_STATE_FILE) -> None:
    """Persist deployment state locally as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_json(), indent=2), encoding="utf-8")


def load_state(path: Path = DEFAULT_STATE_FILE) -> DeployState | None:
    """Load locally persisted deployment state, if any."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    state = DeployState.from_json(data)
    return state if state.backup_dir else None


def rollback(
    config: RemoteConfig,
    state: DeployState,
    runner: Runner | None = None,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Restore the source tree from backup, restart, and verify hashes."""
    report: dict[str, Any] = {
        "restored": False,
        "service": None,
        "hashes_ok": None,
        "ok": False,
    }
    target = win_join(state.remote_dir, "src", "alphacam_cli")
    script = (
        f"if (-not (Test-Path -LiteralPath {ps_quote(state.backup_dir)})) {{ exit 4 }}; "
        f"if (Test-Path -LiteralPath {ps_quote(target)}) {{ "
        f"Remove-Item -LiteralPath {ps_quote(target)} -Recurse -Force }}; "
        f"New-Item -ItemType Directory -Force -Path {ps_quote(target)} | Out-Null; "
        "Copy-Item -Path (Join-Path "
        f"{ps_quote(state.backup_dir)} '*') -Destination {ps_quote(target)} -Recurse -Force"
    )
    restore = run_powershell(config, script, runner)
    report["restored"] = restore.ok
    if not restore.ok:
        report["error"] = f"restore failed: {restore.detail}"
        return report

    effective = replace(
        config,
        remote_dir=state.remote_dir or config.remote_dir,
        service=state.service or config.service,
    )
    try:
        report["service"] = restart_service(effective, runner, sleep=sleep)
    except DeployError as exc:
        report["service_error"] = str(exc)

    if state.hashes:
        try:
            restored_hashes = collect_remote_hashes(effective, target, runner)
        except DeployError as exc:
            report["hash_error"] = str(exc)
        else:
            problems = compare_hashes(state.hashes, restored_hashes)
            report["hashes_ok"] = not problems
            if problems:
                report["problems"] = problems
    else:
        report["hash_note"] = "no reference hashes available, verification skipped"

    verified = report["hashes_ok"] is True or "hash_note" in report
    report["ok"] = bool(report["restored"] and "service_error" not in report and verified)
    return report


def describe_plan(
    config: RemoteConfig,
    local_source: Path,
    executable: str | None = None,
    *,
    health_timeout: float = HEALTH_TIMEOUT_SECONDS,
    health_interval: float = HEALTH_INTERVAL_SECONDS,
) -> list[str]:
    """Return the human-readable dry-run plan without touching the remote host."""
    files = [
        path
        for path in sorted(local_source.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ]
    total_bytes = sum(path.stat().st_size for path in files)
    stamp = "<YYYYmmdd-HHMMSS>"
    return [
        f"target: {config.target}",
        f"remote dir: {config.remote_dir}",
        f"service: {config.service} (nssm: {config.nssm})",
        f"files: {len(files)} ({total_bytes} bytes)",
        f"auth: {'sshpass (ALPHACAM_VM_PASS)' if config.password else 'ssh key'}",
        f"backup: {win_join(DEFAULT_BACKUP_ROOT, f'deploy_backup_{stamp}')}",
        f"upload: tar.gz -> {config.target}:C:/temp/deploy_{stamp}.tgz",
        f"swap: extract to C:/temp/deploy_stage_{stamp}, replace {config.remote_source}",
        f"verify: SHA256 of {len([f for f in files if f.suffix == '.py'])} .py files",
        f"restart: {build_restart_command(config)} (wait <= {SERVICE_WAIT_SECONDS:.0f}s)",
        f"health: {resolve_cli(executable) or 'alphacam'}"
        f" --remote --host {config.host} health health"
        f" (every {health_interval:.0f}s up to {health_timeout:.0f}s)",
        "commands:",
        f'  ssh {config.target} "cmd /c echo ok"',
        f'  xcopy /E /I /H /Y "{config.remote_source}" "<backup>"',
        f"  scp payload.tar.gz {config.target}:C:/temp/deploy_{stamp}.tgz",
        f"  tar -xzf deploy_{stamp}.tgz -C deploy_stage_{stamp}",
        f"  {build_restart_command(config)}",
    ]


def _print_report(
    out: Callable[[str], None],
    *,
    uploaded: int,
    backup_dir: str,
    service: str,
    health: bool | None,
    elapsed: float,
    dry_run: bool,
) -> None:
    """Print the final deployment summary."""
    if health is True:
        health_text = "ok"
    elif health is False:
        health_text = "FAILED"
    else:
        health_text = "skipped (alphacam CLI not found)"
    mode = "dry-run" if dry_run else "deploy"
    out("")
    out(f"--- summary ({mode}) ---")
    out(f"files uploaded: {uploaded}")
    out(f"backup: {backup_dir}")
    out(f"service: {service}")
    out(f"health: {health_text}")
    out(f"elapsed: {elapsed:.1f}s")


def deploy(
    config: RemoteConfig,
    *,
    dry_run: bool = False,
    runner: Runner | None = None,
    out: Callable[[str], None] = print,
    state_file: Path = DEFAULT_STATE_FILE,
    local_source: Path = LOCAL_SRC,
    executable: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
    health_timeout: float = HEALTH_TIMEOUT_SECONDS,
    health_interval: float = HEALTH_INTERVAL_SECONDS,
) -> int:
    """Run the full deployment sequence and return an exit code."""
    started = time.monotonic()

    if dry_run:
        out("[1/7] preflight: skipped (dry-run)")
        out("[2/7] backup: skipped (dry-run)")
        out("[3/7] upload: skipped (dry-run)")
        out("[4/7] verify: skipped (dry-run)")
        out("[5/7] restart: skipped (dry-run)")
        out("[6/7] health: skipped (dry-run)")
        out("[7/7] summary: skipped (dry-run)")
        out("")
        out("plan:")
        for line in describe_plan(
            config,
            local_source,
            executable,
            health_timeout=health_timeout,
            health_interval=health_interval,
        ):
            out(f"  {line}")
        return EXIT_OK

    out(f"[1/7] preflight: {config.target}")
    try:
        preflight(config, runner)
    except DeployError as exc:
        out(f"  FAILED: {exc}")
        return EXIT_PREFLIGHT
    out("  ok")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out("[2/7] backup remote source tree")
    try:
        backup_dir = create_backup(config, runner, timestamp=stamp)
        reference_hashes = collect_remote_hashes(config, config.remote_source, runner)
    except DeployError as exc:
        out(f"  FAILED: {exc}")
        out("  nothing was modified")
        return EXIT_FAIL
    state = DeployState(
        timestamp=stamp,
        host=config.host,
        user=config.user,
        remote_dir=config.remote_dir,
        service=config.service,
        backup_dir=backup_dir,
        hashes=reference_hashes,
    )
    save_state(state, state_file)
    out(f"  backup: {backup_dir}")
    out(f"  reference files: {len(reference_hashes)}")

    uploaded = 0
    service_state = "unknown"
    health: bool | None = None
    failure: str | None = None

    out("[3/7] upload and swap source tree")
    try:
        uploaded = upload_tree(config, runner, timestamp=stamp, local_source=local_source)
        out(f"  uploaded: {uploaded} files")
    except DeployError as exc:
        failure = str(exc)
        out(f"  FAILED: {failure}")

    if failure is None:
        out("[4/7] verify SHA256 of .py files")
        try:
            local_hashes = collect_local_hashes(local_source)
            remote_hashes = collect_remote_hashes(config, config.remote_source, runner)
        except DeployError as exc:
            failure = str(exc)
            out(f"  FAILED: {failure}")
        else:
            problems = compare_hashes(local_hashes, remote_hashes)
            if problems:
                for problem in problems[:20]:
                    out(f"  DIFF: {problem}")
                failure = str(len(problems)) + " hash mismatch(es)"
                out(f"  FAILED: {failure}")
            else:
                out(f"  verified: {len(local_hashes)} files")

    if failure is None:
        out("[5/7] restart service")
        try:
            service_state = restart_service(config, runner, sleep=sleep)
            out(f"  status: {service_state}")
        except DeployError as exc:
            failure = str(exc)
            out(f"  FAILED: {failure}")

    if failure is None:
        out("[6/7] health check")
        status = wait_for_health(
            config,
            runner,
            executable=executable,
            timeout=health_timeout,
            interval=health_interval,
            sleep=sleep,
            out=out,
        )
        if not status.available:
            health = None
            out("  WARNING: alphacam CLI not found, health check skipped")
        elif status.ok:
            health = True
            out("  ok")
            acam_processes = status.payload.get("acam_processes")
            if (
                isinstance(acam_processes, int)
                and not isinstance(acam_processes, bool)
                and acam_processes > 1
            ):
                out(
                    f"  WARNING: acam_processes={acam_processes} (>1), possible stale "
                    "AlphaCAM instance; check health output and gateway logs"
                )
        else:
            health = False
            failure = "health check returned ok=false"
            out("  FAILED")

    if failure is not None:
        out("")
        out("[rollback] restoring backup")
        report = rollback(config, state, runner, sleep=sleep)
        out(f"  restored: {report['restored']}")
        out(f"  service: {report.get('service') or report.get('service_error') or 'unknown'}")
        if report.get("hashes_ok") is True:
            out("  hashes: verified")
        elif report.get("hashes_ok") is False:
            out(f"  hashes: MISMATCH ({report.get('problems')})")
        else:
            out(f"  hashes: {report.get('hash_note', report.get('hash_error', 'skipped'))}")
        out(f"  rollback ok: {report['ok']}")
        _print_report(
            out,
            uploaded=uploaded,
            backup_dir=backup_dir,
            service=report.get("service") or service_state,
            health=health,
            elapsed=time.monotonic() - started,
            dry_run=False,
        )
        out(f"deployment FAILED: {failure}")
        return EXIT_FAIL

    out("[7/7] summary")
    _print_report(
        out,
        uploaded=uploaded,
        backup_dir=backup_dir,
        service=service_state,
        health=health,
        elapsed=time.monotonic() - started,
        dry_run=False,
    )
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="deploy_vm125.py",
        description="Deterministic alphacam_cli deployment with backup, verification, rollback.",
    )
    parser.add_argument("--host", default="192.168.100.60", help="remote host")
    parser.add_argument("--user", default="AlphaCam", help="remote user")
    parser.add_argument("--remote-dir", default="C:/alphacam_cli", help="remote repo dir")
    parser.add_argument("--service", default="AlphaCAMGateway", help="Windows service name")
    parser.add_argument("--nssm", default="C:/temp/nssm/nssm.exe", help="remote nssm.exe")
    parser.add_argument("--timeout", type=float, default=60.0, help="command timeout [s]")
    parser.add_argument(
        "--health-timeout",
        type=float,
        default=HEALTH_TIMEOUT_SECONDS,
        help="max seconds to wait for a healthy gateway [s]",
    )
    parser.add_argument(
        "--health-interval",
        type=float,
        default=HEALTH_INTERVAL_SECONDS,
        help="seconds between health probes [s]",
    )
    parser.add_argument(
        "--cli",
        default="./.venv/bin/alphacam",
        help="local alphacam CLI used for the health check",
    )
    parser.add_argument("--dry-run", action="store_true", help="print plan, change nothing")
    parser.add_argument(
        "--rollback",
        nargs="?",
        const="",
        default=None,
        metavar="BACKUP",
        help="restore from backup (default: last recorded state)",
    )
    return parser


def config_from_args(args: argparse.Namespace) -> RemoteConfig:
    """Build a RemoteConfig from parsed arguments and the environment."""
    password = os.environ.get("ALPHACAM_VM_PASS") or None
    return RemoteConfig(
        host=str(args.host),
        user=str(args.user),
        remote_dir=str(args.remote_dir),
        service=str(args.service),
        nssm=str(args.nssm),
        timeout=float(args.timeout),
        password=password,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the deployment script."""
    args = build_parser().parse_args(argv)
    config = config_from_args(args)

    if args.dry_run:
        return deploy(
            config,
            dry_run=True,
            executable=str(args.cli) or None,
            health_timeout=float(args.health_timeout),
            health_interval=float(args.health_interval),
        )
    if args.rollback is not None:
        state = load_state()
        if state is None and not args.rollback:
            print("rollback failed: no local deployment state found", file=sys.stderr)
            return EXIT_FAIL
        if state is None:
            state = DeployState(
                timestamp="",
                host=config.host,
                user=config.user,
                remote_dir=config.remote_dir,
                service=config.service,
                backup_dir=args.rollback,
                hashes={},
            )
        elif args.rollback:
            state = replace(state, backup_dir=args.rollback)
        print(f"[rollback] restoring {state.backup_dir} -> {state.remote_dir}")
        report = rollback(config, state)
        print(json.dumps(report, indent=2))
        return EXIT_OK if report["ok"] else EXIT_FAIL
    return deploy(
        config,
        executable=str(args.cli) or None,
        health_timeout=float(args.health_timeout),
        health_interval=float(args.health_interval),
    )


if __name__ == "__main__":
    sys.exit(main())
