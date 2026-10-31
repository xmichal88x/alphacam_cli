#!/usr/bin/env python3
"""E2E regression scenarios for the `drawing move` and `drawing lint` blocks."""

# ruff: noqa: TRY003

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"
DRY = "DRY"
MASK_SECRET = "***"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_PREFLIGHT = 2

DEFAULT_HOST = "192.168.100.60"
DEFAULT_CLI = "./.venv/bin/alphacam"
DEFAULT_WORKDIR = Path("/tmp/alphacam_e2e")
DEFAULT_SSH_USER = "AlphaCam"
DEFAULT_PORT = 8721
STEP_TIMEOUT = 120.0
SETUP_TIMEOUT = 60.0
BBOX_TOL = 1e-6

STEP_NAMES = (
    "1. preflight",
    "2. move: przesuniecie",
    "3. move: przywrocenie zaznaczenia",
    "4. move: walidacja",
    "5. move: ostrzezenie dz",
    "6. lint: jednostki mm",
    "7. lint: jednostki mm vs inch",
    "8. lint: wymagane --units",
    "9. lint: pusty rysunek",
)

Runner = Callable[[Sequence[str], float], "CommandResult"]


class ScenarioError(RuntimeError):
    """A scenario assertion failed."""


class ScenarioSkipError(RuntimeError):
    """A scenario step could not be executed in this environment."""


def mask_secret(text: str, password: str | None) -> str:
    """Replace every occurrence of the password in text with a placeholder."""
    if not password:
        return text
    return text.replace(password, MASK_SECRET)


def mask_command(args: Sequence[str], password: str | None) -> tuple[str, ...]:
    """Return argv with the password argument replaced by a placeholder."""
    if not password:
        return tuple(str(part) for part in args)
    return tuple(MASK_SECRET if str(part) == password else str(part) for part in args)


def format_command(args: Sequence[str], password: str | None) -> str:
    """Render argv for logs with the password redacted."""
    return " ".join(mask_command(args, password))


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        return "\n".join(part for part in (self.stdout, self.stderr) if part.strip())

    @property
    def detail(self) -> str:
        return self.stderr.strip() or self.stdout.strip() or f"exit {self.returncode}"

    def masked(self, password: str | None) -> CommandResult:
        """Return a copy safe to print or raise: password redacted everywhere."""
        if not password:
            return self
        return CommandResult(
            mask_command(self.args, password),
            self.returncode,
            mask_secret(self.stdout, password),
            mask_secret(self.stderr, password),
        )


@dataclass(frozen=True)
class StepResult:
    name: str
    status: str
    elapsed: float
    detail: str


@dataclass(frozen=True)
class E2EConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    cli: str = DEFAULT_CLI
    workdir: Path = DEFAULT_WORKDIR
    keep: bool = False
    dry_run: bool = False
    ssh_user: str = DEFAULT_SSH_USER
    ssh_bin: str = "ssh"
    scp_bin: str = "scp"
    sshpass_bin: str = "sshpass"
    ssh_key: str | None = None
    password: str | None = field(default=None, repr=False)
    timeout: float = STEP_TIMEOUT


def _as_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return "" if value is None else str(value)


def default_runner(args: Sequence[str], timeout: float) -> CommandResult:
    argv = [str(part) for part in args]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            tuple(argv),
            124,
            _as_text(exc.stdout),
            _as_text(exc.stderr) or f"timeout after {timeout:.0f}s",
        )
    except FileNotFoundError as exc:
        return CommandResult(tuple(argv), 127, "", str(exc))
    except OSError as exc:
        return CommandResult(tuple(argv), 126, "", str(exc))
    return CommandResult(
        tuple(argv),
        completed.returncode,
        completed.stdout or "",
        completed.stderr or "",
    )


def parse_json_output(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        whole = json.loads(stripped)
    except json.JSONDecodeError:
        whole = None
    if isinstance(whole, dict):
        return whole
    for line in reversed(stripped.splitlines()):
        candidate = line.strip()
        if not candidate.startswith("{"):
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _entity_lines(text: str) -> list[str]:
    lines = text.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == "ENTITIES")
    except StopIteration:
        return lines
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].strip() == "ENDSEC":
            end = index
            break
    return lines[start + 1 : end]


def _dxf_pairs(text: str) -> list[tuple[str, str]]:
    lines = _entity_lines(text)
    pairs: list[tuple[str, str]] = []
    for index in range(0, len(lines) - 1, 2):
        code = lines[index].strip()
        value = lines[index + 1].strip()
        if code:
            pairs.append((code, value))
    return pairs


def parse_dxf_bbox(text: str) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for code, value in _dxf_pairs(text):
        try:
            coordinate = float(value)
        except ValueError:
            continue
        if code in ("10", "11"):
            xs.append(coordinate)
        elif code in ("20", "21"):
            ys.append(coordinate)
    if not xs or not ys:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def bbox_close(
    left: Sequence[float],
    right: Sequence[float],
    tol: float = BBOX_TOL,
) -> bool:
    return len(left) == len(right) and all(
        abs(float(a) - float(b)) <= tol for a, b in zip(left, right, strict=True)
    )


def bbox_shift_matches(
    before: Sequence[float],
    after: Sequence[float],
    dx: float,
    dy: float,
    tol: float = BBOX_TOL,
) -> bool:
    expected = (before[0] + dx, before[1] + dy, before[2] + dx, before[3] + dy)
    return bbox_close(expected, after, tol)


def build_ssh_command(config: E2EConfig, remote_command: str) -> list[str]:
    options = ["-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new"]
    if config.ssh_key:
        options.extend(["-i", config.ssh_key])
    command = [config.ssh_bin, *options, f"{config.ssh_user}@{config.host}", remote_command]
    if config.password:
        return [config.sshpass_bin, "-p", config.password, *command]
    return command


def _scp_remote(path: str) -> str:
    return path.replace("\\", "/")


def build_scp_command(
    config: E2EConfig,
    local_path: Path,
    remote_path: str,
    *,
    download: bool,
) -> list[str]:
    options = ["-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new"]
    if config.ssh_key:
        options.extend(["-i", config.ssh_key])
    remote = f"{config.ssh_user}@{config.host}:{_scp_remote(remote_path)}"
    if download:
        command = [config.scp_bin, *options, remote, str(local_path)]
    else:
        command = [config.scp_bin, *options, str(local_path), remote]
    if config.password:
        return [config.sshpass_bin, "-p", config.password, *command]
    return command


def _circle(center_x: float, center_y: float, radius: float) -> list[str]:
    return [
        "0",
        "CIRCLE",
        "8",
        "0",
        "10",
        f"{center_x}",
        "20",
        f"{center_y}",
        "30",
        "0.0",
        "40",
        f"{radius}",
    ]


def _line(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    start_z: float = 0.0,
    end_z: float = 0.0,
) -> list[str]:
    return [
        "0",
        "LINE",
        "8",
        "0",
        "10",
        f"{start_x}",
        "20",
        f"{start_y}",
        "30",
        f"{start_z}",
        "11",
        f"{end_x}",
        "21",
        f"{end_y}",
        "31",
        f"{end_z}",
    ]


def defects_dxf_text() -> str:
    polyline = ["0", "POLYLINE", "8", "0", "66", "1", "70", "0"]
    for x, y in ((20000.0, 0.0), (20010.0, 0.0), (20010.1, 0.0), (19965.549674, 22.699525)):
        polyline.extend(["0", "VERTEX", "8", "0", "10", f"{x}", "20", f"{y}", "30", "0.0"])
    polyline.extend(["0", "SEQEND"])
    lines = [
        "0",
        "SECTION",
        "2",
        "HEADER",
        "9",
        "$ACADVER",
        "1",
        "AC1009",
        "0",
        "ENDSEC",
        "0",
        "SECTION",
        "2",
        "ENTITIES",
        *_circle(0.0, 0.0, 1000.0),
        *_circle(0.0, 0.0, 1000.0),
        *_line(10000.0, 10000.0, 10000.01, 10000.0),
        *polyline,
        *_line(30000.0, 0.0, 30010.0, 0.0, 5.0, 5.0),
        "0",
        "ENDSEC",
        "0",
        "EOF",
    ]
    return "\n".join(lines) + "\n"


class E2E:
    def __init__(self, config: E2EConfig, runner: Runner | None = None) -> None:
        self.config = config
        self._runner = runner or default_runner
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.local_dir = config.workdir / f"e2e_{self.timestamp}"
        self.remote_dir = f"C:/Temp/e2e_{self.timestamp}"
        self.results: list[StepResult] = []
        self.remote_created = False
        self.before_bbox: tuple[float, float, float, float] | None = None
        self.after_bbox: tuple[float, float, float, float] | None = None
        self._cli_bin = self._resolve_cli()

    def _resolve_cli(self) -> str:
        candidate = Path(self.config.cli)
        if candidate.is_file():
            return str(candidate)
        if self.config.cli == DEFAULT_CLI:
            return "alphacam"
        return self.config.cli

    def _cli_args(self, *args: str) -> list[str]:
        return [
            self._cli_bin,
            "--remote",
            "--host",
            self.config.host,
            "--port",
            str(self.config.port),
            *args,
        ]

    def _run(self, args: Sequence[str], timeout: float) -> CommandResult:
        if self.config.dry_run:
            return CommandResult(tuple(str(part) for part in args), 0, "", "").masked(
                self.config.password
            )
        return self._runner(args, timeout).masked(self.config.password)

    def _cli(self, *args: str, timeout: float | None = None) -> CommandResult:
        return self._run(self._cli_args(*args), timeout or self.config.timeout)

    def _ssh(self, command: str, timeout: float = SETUP_TIMEOUT) -> CommandResult:
        return self._run(build_ssh_command(self.config, command), timeout)

    def _scp_download(self, remote: str, local: Path) -> CommandResult:
        return self._run(
            build_scp_command(self.config, local, remote, download=True),
            SETUP_TIMEOUT,
        )

    def _scp_upload(self, local: Path, remote: str) -> CommandResult:
        return self._run(
            build_scp_command(self.config, local, remote, download=False),
            SETUP_TIMEOUT,
        )

    def _remote_win(self, name: str | None = None) -> str:
        base = self.remote_dir.replace("/", "\\")
        return base if name is None else f"{base}\\{name}"

    def _remote_file(self, name: str) -> str:
        return f"{self.remote_dir}/{name}"

    def _require_ok(self, result: CommandResult, action: str) -> None:
        if not result.ok:
            raise ScenarioError(f"{action} failed (exit {result.returncode}): {result.detail}")

    def _prepare_local_dir(self) -> None:
        self.local_dir.mkdir(parents=True, exist_ok=True)

    def _execute(self, name: str, step: Callable[[], str]) -> StepResult:
        started = time.monotonic()
        try:
            detail = step()
            status = PASS
        except ScenarioSkipError as exc:
            status = SKIP
            detail = str(exc)
        except ScenarioError as exc:
            status = FAIL
            detail = str(exc)
        except Exception as exc:  # noqa: BLE001
            status = FAIL
            detail = f"unexpected error: {mask_secret(str(exc), self.config.password)}"
        result = StepResult(name, status, time.monotonic() - started, detail)
        self.results.append(result)
        return result

    def _run_step(self, name: str, step: Callable[[], str]) -> StepResult:
        return self._execute(name, step)

    def _create_remote_dir(self) -> None:
        remote = self._remote_win()
        result = self._ssh(f'cmd /c if not exist "{remote}" mkdir "{remote}"')
        self._require_ok(result, "create remote workdir")
        self.remote_created = True

    def _export(self, name: str) -> None:
        self._require_ok(self._cli("drawing", "export", self._remote_win(name)), f"export {name}")
        self._require_ok(
            self._scp_download(self._remote_file(name), self.local_dir / name),
            f"download {name}",
        )

    def _read_bbox(self, name: str) -> tuple[float, float, float, float]:
        self._export(name)
        text = (self.local_dir / name).read_text(encoding="utf-8", errors="replace")
        bbox = parse_dxf_bbox(text)
        if bbox is None:
            raise ScenarioError(f"no DXF coordinates in {name}")
        return bbox

    def _lint_json(self, units: str) -> dict[str, Any]:
        result = self._cli("drawing", "lint", "--all", "--units", units, "--json")
        self._require_ok(result, f"lint --units {units}")
        payload = parse_json_output(result.stdout)
        if payload is None:
            raise ScenarioError(f"lint --units {units} did not return JSON")
        return payload

    def _step_preflight(self) -> str:
        result = self._cli("health", "health", timeout=SETUP_TIMEOUT)
        self._require_ok(result, "health")
        payload = parse_json_output(result.stdout)
        if payload is None:
            raise ScenarioError("health did not return JSON")
        if payload.get("ok") is not True:
            raise ScenarioError(f"health ok != true: {payload.get('error', 'unknown')}")
        processes = payload.get("acam_processes")
        if processes != 1:
            raise ScenarioError(f"acam_processes={processes!r}, expected 1")
        return f"ok=true, acam_processes=1, version={payload.get('version', '?')}"

    def _step_move(self) -> str:
        self._require_ok(
            self._cli("drawing", "create", "-w", "100", "-h", "50"),
            "drawing create",
        )
        before = self._read_bbox("before.dxf")
        result = self._cli("drawing", "move", "--dx", "10", "--dy", "5", "--all", "--json")
        self._require_ok(result, "drawing move")
        payload = parse_json_output(result.stdout)
        if payload is None:
            raise ScenarioError("drawing move --json did not return JSON")
        moved = payload.get("moved")
        if not isinstance(moved, int) or isinstance(moved, bool) or moved < 1:
            raise ScenarioError(f"moved={moved!r}, expected >= 1")
        after = self._read_bbox("after.dxf")
        self.before_bbox = before
        self.after_bbox = after
        if not bbox_shift_matches(before, after, 10.0, 5.0):
            raise ScenarioError(f"bbox not shifted by (10, 5): before={before}, after={after}")
        return f"moved={moved}, bbox {before} -> {after}"

    def _step_selection(self) -> str:
        result = self._cli("drawing", "lint", "--units", "mm")
        if result.returncode != 1:
            raise ScenarioError(
                f"expected exit 1 without selection, got {result.returncode}: {result.detail}"
            )
        return "exit 1 (brak zaznaczenia)"

    def _step_validation(self) -> str:
        result = self._cli("drawing", "move", "--dx", "nan", "--dy", "5", "--all")
        if result.returncode != 1:
            raise ScenarioError(
                f"expected exit 1 for --dx nan, got {result.returncode}: {result.detail}"
            )
        if self.after_bbox is None:
            raise ScenarioError("after bbox unavailable (step 2 did not produce it)")
        invalid = self._read_bbox("invalid.dxf")
        if not bbox_close(self.after_bbox, invalid):
            raise ScenarioError(
                f"geometry changed after invalid move: after={self.after_bbox}, now={invalid}"
            )
        return "exit 1, geometria nietknieta"

    def _step_dz(self) -> str:
        result = self._cli("drawing", "move", "--dx", "0", "--dy", "0", "--dz", "1", "--all")
        self._require_ok(result, "drawing move --dz")
        if "dz != 0" not in result.output:
            raise ScenarioError("warning 'dz != 0' missing from output")
        return "exit 0, warning 'dz != 0' obecne"

    def _step_lint_mm(self) -> str:
        self._require_ok(
            self._cli("drawing", "create", "-w", "100", "-h", "50", "--fillet", "10"),
            "drawing create --fillet",
        )
        payload = self._lint_json("mm")
        flagged = payload.get("flagged")
        if flagged != 0:
            raise ScenarioError(
                f"flagged={flagged!r}, expected 0 (issues={payload.get('issues_by_type', {})})"
            )
        return "flagged=0"

    def _step_defects(self) -> str:
        local_defects = self.local_dir / "defects.dxf"
        local_defects.write_text(defects_dxf_text(), encoding="utf-8")
        remote_defects = self._remote_win("defects.dxf")
        self._require_ok(
            self._scp_upload(local_defects, remote_defects),
            "upload defects.dxf",
        )
        self._require_ok(
            self._cli("drawing", "import", remote_defects, "--fmt", "dxf"),
            "drawing import defects.dxf",
        )

        mm = self._lint_json("mm")
        inch = self._lint_json("inch")
        mm_counts = mm.get("issues_by_type") or {}
        inch_counts = inch.get("issues_by_type") or {}

        checks: list[str] = []
        if int(mm_counts.get("tiny", 0)) < 1:
            checks.append(f"mm tiny<1 ({mm_counts})")
        if int(mm_counts.get("spike", 0)) < 1:
            checks.append(f"mm spike<1 ({mm_counts})")
        if int(mm_counts.get("nonZeroZ", 0)) != 1:
            checks.append(f"mm nonZeroZ!=1 ({mm_counts})")
        if int(mm_counts.get("duplicates", 0)) != 1:
            checks.append(f"mm duplicates!=1 ({mm_counts})")
        if "bigArc" in mm_counts:
            checks.append(f"mm bigArc present ({mm_counts})")
        if int(inch_counts.get("bigArc", 0)) != 2:
            checks.append(f"inch bigArc!=2 ({inch_counts})")
        if "tiny" in inch_counts:
            checks.append(f"inch tiny present ({inch_counts})")
        if "spike" in inch_counts:
            checks.append(f"inch spike present ({inch_counts})")
        if checks:
            raise ScenarioError("; ".join(checks))
        return f"mm={mm_counts}; inch={inch_counts}"

    def _step_units_required(self) -> str:
        result = self._cli("drawing", "lint", "--all")
        if result.returncode != 2:
            raise ScenarioError(
                f"expected exit 2 without --units, got {result.returncode}: {result.detail}"
            )
        if "--units" not in result.output and "units" not in result.output.lower():
            raise ScenarioError("error message does not mention missing --units")
        return "exit 2, brak --units"

    def _python_for_clearing(self) -> str:
        candidate = Path(self._cli_bin).parent / "python"
        return str(candidate) if candidate.is_file() else sys.executable

    def _remote_clear(self) -> bool:
        script = (
            "from alphacam_cli.gateway.client import RemoteSession\n"
            f"with RemoteSession(host={self.config.host!r}, port={self.config.port}) as session:\n"
            "    session.create_temp_drawing()\n"
        )
        result = self._run([self._python_for_clearing(), "-c", script], SETUP_TIMEOUT)
        return result.ok

    def _fallback_clear(self) -> bool:
        return self._cli("drawing", "create", "-w", "0.001", "-h", "0.001").ok

    def _step_empty(self) -> str:
        if not self._remote_clear():
            self._fallback_clear()
            raise ScenarioSkipError(
                "RemoteSession unavailable; fallback drawing create used (SKIP)"
            )
        payload = self._lint_json("mm")
        scanned = payload.get("scanned")
        if scanned != 0:
            raise ScenarioError(f"scanned={scanned!r}, expected 0")
        return "scanned=0"

    def _step_cleanup(self) -> str:
        problems: list[str] = []
        if self.remote_created:
            if not self._remote_clear() and not self._fallback_clear():
                problems.append("drawing clear failed")
            result = self._ssh(f'cmd /c rmdir /s /q "{self._remote_win()}"')
            if not result.ok:
                problems.append(f"remote rmdir failed (exit {result.returncode}): {result.detail}")
        if self.config.keep:
            detail = "artefakty zachowane (--keep)"
        else:
            try:
                shutil.rmtree(self.local_dir)
            except FileNotFoundError:
                pass
            except OSError as exc:
                problems.append(f"local cleanup failed: {exc}")
            detail = "rysunek wyczyszczony, artefakty usuniete"
        if problems:
            raise ScenarioError("; ".join(problems))
        return detail

    def _check_auth(self) -> str | None:
        if not self.config.password:
            return None
        if shutil.which(self.config.sshpass_bin):
            return None
        return (
            f"{self.config.sshpass_bin} not found in PATH: install it with "
            "`sudo apt install sshpass`, or use key authentication with --ssh-key"
        )

    def _record_dry_run(self) -> None:
        for name in (*STEP_NAMES, "10. cleanup"):
            self.results.append(StepResult(name, DRY, 0.0, "dry-run: nie wykonano"))

    def run(self) -> int:
        if self.config.dry_run:
            self._record_dry_run()
            return EXIT_OK

        auth_error = self._check_auth()
        if auth_error is not None:
            self.results.append(StepResult("1. preflight", FAIL, 0.0, auth_error))
            return EXIT_PREFLIGHT

        exit_code = EXIT_OK
        try:
            self._prepare_local_dir()
            preflight = self._run_step("1. preflight", self._step_preflight)
            if preflight.status != PASS:
                exit_code = EXIT_PREFLIGHT
                return exit_code
            self._create_remote_dir()
            for name, step in (
                ("2. move: przesuniecie", self._step_move),
                ("3. move: przywrocenie zaznaczenia", self._step_selection),
                ("4. move: walidacja", self._step_validation),
                ("5. move: ostrzezenie dz", self._step_dz),
                ("6. lint: jednostki mm", self._step_lint_mm),
                ("7. lint: jednostki mm vs inch", self._step_defects),
                ("8. lint: wymagane --units", self._step_units_required),
                ("9. lint: pusty rysunek", self._step_empty),
            ):
                self._run_step(name, step)
            if any(result.status == FAIL for result in self.results):
                exit_code = EXIT_FAIL
        except Exception as exc:  # noqa: BLE001
            self.results.append(
                StepResult(
                    "setup",
                    FAIL,
                    0.0,
                    f"unexpected error: {mask_secret(str(exc), self.config.password)}",
                )
            )
            exit_code = EXIT_FAIL
        finally:
            self._run_step("10. cleanup", self._step_cleanup)
        return exit_code


def format_results(results: Sequence[StepResult]) -> str:
    header = ("krok", "status", "czas", "szczegoly")
    rows = [
        (
            result.name,
            result.status,
            f"{result.elapsed:.2f}s",
            result.detail.replace("\n", " "),
        )
        for result in results
    ]
    widths = [
        max([len(header[column]), *(len(row[column]) for row in rows)])
        for column in range(len(header))
    ]

    def render(row: Sequence[str]) -> str:
        return " | ".join(value.ljust(widths[index]) for index, value in enumerate(row))

    separator = "-+-".join("-" * width for width in widths)
    return "\n".join([render(header), separator, *(render(row) for row in rows)])


def format_summary(results: Sequence[StepResult]) -> str:
    counted = [result for result in results if result.status in (PASS, FAIL)]
    passed = sum(1 for result in counted if result.status == PASS)
    skipped = sum(1 for result in results if result.status == SKIP)
    suffix = f" ({skipped} SKIP)" if skipped else ""
    if any(result.status == DRY for result in results):
        return "0/0 PASS (dry-run)"
    return f"{passed}/{len(counted)} PASS{suffix}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="E2E regression scenarios for `drawing move` and `drawing lint`."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--cli", default=DEFAULT_CLI)
    parser.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--ssh-user", default=DEFAULT_SSH_USER)
    parser.add_argument("--ssh-bin", default="ssh")
    parser.add_argument("--scp-bin", default="scp")
    parser.add_argument("--sshpass-bin", default="sshpass")
    parser.add_argument("--ssh-key", default=None)
    parser.add_argument("--timeout", type=float, default=STEP_TIMEOUT)
    return parser


def config_from_args(args: argparse.Namespace) -> E2EConfig:
    return E2EConfig(
        host=str(args.host),
        port=int(args.port),
        cli=str(args.cli),
        workdir=Path(args.workdir),
        keep=bool(args.keep),
        dry_run=bool(args.dry_run),
        ssh_user=str(args.ssh_user),
        ssh_bin=str(args.ssh_bin),
        scp_bin=str(args.scp_bin),
        sshpass_bin=str(args.sshpass_bin),
        ssh_key=args.ssh_key,
        password=os.environ.get("ALPHACAM_VM_PASS") or None,
        timeout=float(args.timeout),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scenario = E2E(config_from_args(args))
    exit_code = scenario.run()
    print(format_results(scenario.results))
    print()
    print(format_summary(scenario.results))
    if exit_code == EXIT_PREFLIGHT:
        return EXIT_PREFLIGHT
    if any(result.status == FAIL for result in scenario.results):
        return EXIT_FAIL
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
