from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from scripts import e2e_drawing as e2e

BEFORE_DXF = """0
SECTION
2
HEADER
9
$EXTMIN
10
-999.0
20
-999.0
0
ENDSEC
0
SECTION
2
ENTITIES
0
LINE
8
0
10
0.0
20
0.0
11
100.0
21
50.0
0
ENDSEC
0
EOF
"""

AFTER_DXF = (
    BEFORE_DXF.replace("10\n0.0", "10\n10.0")
    .replace("20\n0.0", "20\n5.0")
    .replace("11\n100.0", "11\n110.0")
    .replace("21\n50.0", "21\n55.0")
)

HEALTH_OK = json.dumps({"ok": True, "acam_processes": 1, "version": "2025.2"})


def _result(
    args: Sequence[str],
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> e2e.CommandResult:
    return e2e.CommandResult(tuple(str(part) for part in args), returncode, stdout, stderr)


class ScriptedRunner:
    def __init__(self, handler: Any) -> None:
        self.calls: list[list[str]] = []
        self.handler = handler

    def __call__(self, args: Sequence[str], timeout: float) -> e2e.CommandResult:
        del timeout
        call = [str(part) for part in args]
        self.calls.append(call)
        return self.handler(call)

    def joined(self) -> list[str]:
        return [" ".join(call) for call in self.calls]


class ExplodingRunner:
    def __call__(self, args: Sequence[str], timeout: float) -> e2e.CommandResult:
        del args, timeout
        raise AssertionError("runner must not be called")  # noqa: TRY003


class HappyHandler:
    def __init__(self) -> None:
        self.lint_index = 0
        self.fix_index = 0
        self.info_counts: list[int] = [7, 7]
        self.backup_exists = True
        self.lint_payloads = [
            {"flagged": 0, "issues_by_type": {}},
            {
                "flagged": 6,
                "scanned": 7,
                "issues_by_type": {
                    "tiny": 1,
                    "spike": 1,
                    "nonZeroZ": 1,
                    "duplicates": 1,
                    "nearlyClosed": 1,
                    "selfIntersect": 1,
                },
            },
            {"flagged": 2, "issues_by_type": {"bigArc": 2}},
            {"scanned": 6, "issues_by_type": {"selfIntersect": 1}},
            {"flagged": 0, "scanned": 0, "issues_by_type": {}},
        ]
        self.dry_run_payload = {
            "success": True,
            "units": "mm",
            "fixed": _zero_fixed(),
            "skipped": [],
            "failed": [],
            "deleted_paths": [],
            "backup": None,
            "remaining": {"tiny": 1, "spike": 1, "nonZeroZ": 1, "duplicates": 1},
            "warnings": [],
            "would_fix": {
                "duplicates": 1,
                "tiny": 1,
                "spike": 1,
                "gap": 0,
                "nearlyClosed": 1,
                "nonZeroZ": 1,
            },
        }
        self.fix_payload = {
            "success": True,
            "units": "mm",
            "fixed": {
                "duplicates": 1,
                "tiny": 1,
                "spike": 1,
                "gap": 0,
                "nearlyClosed": 1,
                "nonZeroZ": 1,
            },
            "skipped": [{"index": 6, "types": ["selfIntersect"], "reason": "no automatic fix"}],
            "failed": [],
            "deleted_paths": [4],
            "backup": "C:\\Temp\\alphacam_lint_backup_20261031-000000.dxf",
            "remaining": {"selfIntersect": 1},
            "warnings": [],
        }
        self.clean_fix_payload = {
            "success": True,
            "units": "mm",
            "fixed": _zero_fixed(),
            "skipped": [],
            "failed": [],
            "deleted_paths": [],
            "backup": None,
            "remaining": {},
            "warnings": [],
        }

    def __call__(self, call: list[str]) -> e2e.CommandResult:
        joined = " ".join(call)
        if "health health" in joined:
            return _result(call, stdout=HEALTH_OK)
        if "Test-Path" in joined:
            return _result(call, stdout="True\n" if self.backup_exists else "False\n")
        if "drawing info" in joined:
            count = self.info_counts.pop(0) if self.info_counts else 7
            return _result(call, stdout=f" Active Drawing \n Geometries: {count}\n")
        if "drawing move" in joined:
            if "nan" in joined:
                return _result(call, 1, stderr="Error: --dx must be a finite number")
            if "--dz" in joined:
                return _result(call, 0, stderr="Warning: dz != 0: geometry moved off Z=0 plane")
            return _result(call, 0, stdout=json.dumps({"success": True, "moved": 4}))
        if "drawing lint" in joined:
            if "--units" not in joined:
                return _result(call, 2, stderr="Missing option '--units'.")
            if "--fix" in call:
                if "--dry-run" in call:
                    return _result(call, 0, stdout=json.dumps(self.dry_run_payload))
                self.fix_index += 1
                payload = self.fix_payload if self.fix_index == 1 else self.clean_fix_payload
                return _result(call, 0, stdout=json.dumps(payload))
            if "--all" not in joined:
                return _result(call, 1, stderr="No selected geometries")
            payload = self.lint_payloads[self.lint_index % len(self.lint_payloads)]
            self.lint_index += 1
            return _result(call, 0, stdout=json.dumps(payload))
        if call and call[0] == "scp":
            destination = call[-1]
            if ":" not in destination and destination.endswith(".dxf"):
                content = BEFORE_DXF
                if "after.dxf" in joined or "invalid.dxf" in joined:
                    content = AFTER_DXF
                Path(destination).write_text(content, encoding="utf-8")
            return _result(call)
        return _result(call)


def _zero_fixed() -> dict[str, int]:
    return {"duplicates": 0, "tiny": 0, "spike": 0, "gap": 0, "nearlyClosed": 0, "nonZeroZ": 0}


def _failing_handler(call: list[str]) -> e2e.CommandResult:
    joined = " ".join(call)
    if "health health" in joined:
        return _result(call, stdout=HEALTH_OK)
    if "drawing create" in joined:
        return _result(call, 1, stderr="create boom")
    return _result(call)


def test_parse_dxf_bbox_uses_entities_section() -> None:
    assert e2e.parse_dxf_bbox(BEFORE_DXF) == (0.0, 0.0, 100.0, 50.0)


def test_parse_dxf_bbox_polyline_vertices() -> None:
    text = """0
SECTION
2
ENTITIES
0
LWPOLYLINE
8
0
10
1.0
20
2.0
10
3.0
20
4.0
0
ENDSEC
0
EOF
"""
    assert e2e.parse_dxf_bbox(text) == (1.0, 2.0, 3.0, 4.0)


def test_parse_dxf_bbox_without_coordinates() -> None:
    assert e2e.parse_dxf_bbox("0\nSECTION\n2\nENTITIES\n0\nENDSEC\n") is None


def test_bbox_shift_matches_tolerance() -> None:
    before = (0.0, 0.0, 100.0, 50.0)
    assert e2e.bbox_shift_matches(before, (10.0, 5.0, 110.0, 55.0), 10.0, 5.0)
    assert not e2e.bbox_shift_matches(before, (10.000002, 5.0, 110.0, 55.0), 10.0, 5.0)
    assert not e2e.bbox_shift_matches(before, (9.0, 5.0, 110.0, 55.0), 10.0, 5.0)


def test_bbox_close_uses_inclusive_tolerance() -> None:
    assert e2e.bbox_close((0.0, 0.0), (1e-6, 1e-6))
    assert not e2e.bbox_close((0.0, 0.0), (2e-6, 0.0))


def test_build_ssh_command_targets_user_host() -> None:
    config = e2e.E2EConfig(host="10.0.0.5", ssh_user="AlphaCam", ssh_key="/tmp/key")
    command = e2e.build_ssh_command(config, "echo ok")
    assert command[-1] == "echo ok"
    assert "AlphaCam@10.0.0.5" in command
    assert "-i" in command


def test_build_scp_command_converts_windows_paths() -> None:
    config = e2e.E2EConfig(host="10.0.0.5", ssh_user="AlphaCam")
    upload = e2e.build_scp_command(
        config, Path("/tmp/a.dxf"), "C:\\Temp\\e2e\\a.dxf", download=False
    )
    download = e2e.build_scp_command(
        config, Path("/tmp/a.dxf"), "C:\\Temp\\e2e\\a.dxf", download=True
    )
    expected = "AlphaCam@10.0.0.5:C:/Temp/e2e/a.dxf"
    assert upload[-1] == expected
    assert download[-2] == expected


def test_ssh_key_is_passed_as_identity() -> None:
    config = e2e.E2EConfig(ssh_key="/tmp/id_ed25519")
    command = e2e.build_ssh_command(config, "echo ok")
    index = command.index("-i")
    assert command[index + 1] == "/tmp/id_ed25519"


def test_env_password_wraps_ssh_and_scp_with_sshpass(monkeypatch: Any) -> None:
    monkeypatch.setenv("ALPHACAM_VM_PASS", "s3cret-pass")
    config = e2e.config_from_args(e2e.build_parser().parse_args([]))

    assert config.password == "s3cret-pass"
    ssh = e2e.build_ssh_command(config, "echo ok")
    upload = e2e.build_scp_command(config, Path("/tmp/a.dxf"), "C:\\Temp\\a.dxf", download=False)
    for command in (ssh, upload):
        assert command[:3] == ["sshpass", "-p", "s3cret-pass"]


def test_no_env_password_keeps_plain_ssh_and_scp(monkeypatch: Any) -> None:
    monkeypatch.delenv("ALPHACAM_VM_PASS", raising=False)
    config = e2e.config_from_args(e2e.build_parser().parse_args([]))

    assert config.password is None
    ssh = e2e.build_ssh_command(config, "echo ok")
    download = e2e.build_scp_command(config, Path("/tmp/a.dxf"), "C:\\Temp\\a.dxf", download=True)
    assert "sshpass" not in ssh
    assert "sshpass" not in download


def test_password_is_masked_in_command_and_result() -> None:
    password = "top-secret-value"
    args = ("sshpass", "-p", password, "ssh", "AlphaCam@host", "echo ok")

    formatted = e2e.format_command(args, password)
    assert password not in formatted
    assert e2e.MASK_SECRET in formatted

    result = e2e.CommandResult(args, 1, f"stdout {password}", f"stderr {password}")
    masked = result.masked(password)
    assert password not in " ".join(masked.args)
    assert password not in masked.stdout
    assert password not in masked.stderr
    assert password not in masked.detail


def test_config_repr_hides_password() -> None:
    config = e2e.E2EConfig(password="top-secret-value")
    assert "top-secret-value" not in repr(config)


def test_missing_sshpass_fails_preflight_with_exit_2(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(e2e.shutil, "which", lambda name: None)
    scenario = e2e.E2E(
        e2e.E2EConfig(workdir=tmp_path, password="s3cret-pass"),
        runner=ExplodingRunner(),
    )

    assert scenario.run() == e2e.EXIT_PREFLIGHT
    assert scenario.results[-1].status == e2e.FAIL
    detail = scenario.results[-1].detail
    assert "sshpass" in detail
    assert "apt install sshpass" in detail
    assert "s3cret-pass" not in detail


def test_execute_classifies_pass_fail_and_skip(tmp_path: Path) -> None:
    scenario = e2e.E2E(e2e.E2EConfig(workdir=tmp_path), runner=ExplodingRunner())

    passed = scenario._execute("pass", lambda: "fine")
    failed = scenario._execute("fail", _raise_failure)
    skipped = scenario._execute("skip", _raise_skip)

    assert passed.status == e2e.PASS
    assert failed.status == e2e.FAIL
    assert failed.detail == "boom"
    assert skipped.status == e2e.SKIP


def _raise_failure() -> str:
    raise e2e.ScenarioError("boom")


def _raise_skip() -> str:
    raise e2e.ScenarioSkipError("skip")


def test_dry_run_executes_nothing(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    scenario = e2e.E2E(
        e2e.E2EConfig(workdir=workdir, dry_run=True),
        runner=ExplodingRunner(),
    )

    assert scenario.run() == e2e.EXIT_OK
    assert all(result.status == e2e.DRY for result in scenario.results)
    assert not workdir.exists()


def test_dry_run_main_does_not_call_subprocess(
    tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    calls: list[Any] = []

    def fake_run(*args: Any, **kwargs: Any) -> None:
        del kwargs
        calls.append(args)

    monkeypatch.setattr(e2e.subprocess, "run", fake_run)

    assert e2e.main(["--dry-run", "--workdir", str(tmp_path / "work")]) == e2e.EXIT_OK
    assert calls == []
    capsys.readouterr()


def test_full_scenario_passes(tmp_path: Path) -> None:
    runner = ScriptedRunner(HappyHandler())
    scenario = e2e.E2E(
        e2e.E2EConfig(workdir=tmp_path, cli="alphacam", timeout=5.0),
        runner=runner,
    )

    assert scenario.run() == e2e.EXIT_OK
    assert all(result.status == e2e.PASS for result in scenario.results)
    assert e2e.format_summary(scenario.results) == "13/13 PASS"
    assert any("rmdir /s /q" in call for call in runner.joined())
    assert not scenario.local_dir.exists()


def test_cleanup_runs_after_failure(tmp_path: Path) -> None:
    runner = ScriptedRunner(_failing_handler)
    scenario = e2e.E2E(
        e2e.E2EConfig(workdir=tmp_path, cli="alphacam", timeout=5.0),
        runner=runner,
    )

    assert scenario.run() == e2e.EXIT_FAIL
    statuses = {result.name: result.status for result in scenario.results}
    assert statuses["2. move: przesuniecie"] == e2e.FAIL
    assert statuses["13. cleanup"] == e2e.PASS
    assert any("rmdir /s /q" in call for call in runner.joined())
    assert not scenario.local_dir.exists()


def test_preflight_failure_returns_exit_2(tmp_path: Path) -> None:
    def handler(call: list[str]) -> e2e.CommandResult:
        joined = " ".join(call)
        if "health health" in joined:
            return _result(call, stdout=json.dumps({"ok": False, "acam_processes": 0}))
        return _result(call)

    scenario = e2e.E2E(
        e2e.E2EConfig(workdir=tmp_path, cli="alphacam"),
        runner=ScriptedRunner(handler),
    )

    assert scenario.run() == e2e.EXIT_PREFLIGHT
    statuses = {result.name: result.status for result in scenario.results}
    assert statuses["1. preflight"] == e2e.FAIL
    assert "2. move: przesuniecie" not in statuses


def _run_handler(handler: HappyHandler, tmp_path: Path) -> e2e.E2E:
    scenario = e2e.E2E(
        e2e.E2EConfig(workdir=tmp_path, cli="alphacam", timeout=5.0),
        runner=ScriptedRunner(handler),
    )
    scenario.run()
    return scenario


def _status(scenario: e2e.E2E, name: str) -> str:
    return {result.name: result.status for result in scenario.results}[name]


def test_parse_geometry_count_from_info_table() -> None:
    assert e2e.parse_geometry_count("| Geometries | 7 |") == 7
    assert e2e.parse_geometry_count(" Geometries: 12\n") == 12
    assert e2e.parse_geometry_count("Active Drawing") is None


def _polylines(text: str) -> list[dict[str, Any]]:
    polylines: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for code, value in e2e._dxf_pairs(text):
        if code == "0" and value == "POLYLINE":
            current = {"flags": [], "vertices": []}
            polylines.append(current)
            continue
        if current is None:
            continue
        if code == "0" and value == "SEQEND":
            current = None
            continue
        if code == "70":
            current["flags"].append(int(value))
        elif code == "10":
            current["vertices"].append([float(value), None])
        elif code == "20" and current["vertices"]:
            current["vertices"][-1][1] = float(value)
    return polylines


def test_defects_dxf_contains_closed_self_intersecting_polyline() -> None:
    polylines = _polylines(e2e.defects_dxf_text())
    closed = [poly for poly in polylines if 1 in poly["flags"]]

    assert len(closed) == 1
    assert closed[0]["vertices"] == [
        [0.0, 3000.0],
        [100.0, 3100.0],
        [100.0, 3000.0],
        [0.0, 3100.0],
    ]


def test_defects_step_fails_without_self_intersect_in_mm(tmp_path: Path) -> None:
    handler = HappyHandler()
    del handler.lint_payloads[1]["issues_by_type"]["selfIntersect"]
    scenario = _run_handler(handler, tmp_path)

    assert _status(scenario, "7. lint: jednostki mm vs inch") == e2e.FAIL
    assert "selfIntersect" in scenario.results[6].detail


def test_fix_steps_pass_with_self_intersect_remaining(tmp_path: Path) -> None:
    scenario = _run_handler(HappyHandler(), tmp_path)

    assert _status(scenario, "8. lint fix: dry-run") == e2e.PASS
    assert _status(scenario, "9. lint fix: naprawa") == e2e.PASS
    assert _status(scenario, "10. lint fix: czysty rysunek") == e2e.PASS


def test_dry_run_geometry_change_fails(tmp_path: Path) -> None:
    handler = HappyHandler()
    handler.info_counts = [7, 8]
    scenario = _run_handler(handler, tmp_path)

    assert _status(scenario, "8. lint fix: dry-run") == e2e.FAIL
    assert "geometry count" in scenario.results[7].detail


def test_dry_run_nonzero_fixed_fails(tmp_path: Path) -> None:
    handler = HappyHandler()
    handler.dry_run_payload["fixed"]["tiny"] = 1
    scenario = _run_handler(handler, tmp_path)

    assert _status(scenario, "8. lint fix: dry-run") == e2e.FAIL


@pytest.mark.parametrize("name", ["duplicates", "tiny", "spike"])
def test_dry_run_would_fix_below_one_fails(name: str, tmp_path: Path) -> None:
    handler = HappyHandler()
    handler.dry_run_payload["would_fix"][name] = 0
    scenario = _run_handler(handler, tmp_path)

    assert _status(scenario, "8. lint fix: dry-run") == e2e.FAIL


@pytest.mark.parametrize("name", ["duplicates", "tiny", "spike", "nonZeroZ"])
def test_fix_fixed_below_one_fails(name: str, tmp_path: Path) -> None:
    handler = HappyHandler()
    handler.fix_payload["fixed"][name] = 0
    scenario = _run_handler(handler, tmp_path)

    assert _status(scenario, "9. lint fix: naprawa") == e2e.FAIL


@pytest.mark.parametrize("name", ["tiny", "spike", "nonZeroZ", "duplicates", "nearlyClosed"])
def test_unfixable_issue_remaining_after_fix_fails(name: str, tmp_path: Path) -> None:
    handler = HappyHandler()
    handler.lint_payloads[3] = {"scanned": 6, "issues_by_type": {"selfIntersect": 1, name: 1}}
    scenario = _run_handler(handler, tmp_path)

    assert _status(scenario, "9. lint fix: naprawa") == e2e.FAIL
    assert name in scenario.results[8].detail


def test_self_intersect_remaining_after_fix_is_tolerated(tmp_path: Path) -> None:
    handler = HappyHandler()
    handler.lint_payloads[3] = {"scanned": 6, "issues_by_type": {"selfIntersect": 1}}
    scenario = _run_handler(handler, tmp_path)

    assert _status(scenario, "9. lint fix: naprawa") == e2e.PASS


def test_missing_backup_on_vm_fails(tmp_path: Path) -> None:
    handler = HappyHandler()
    handler.backup_exists = False
    scenario = _run_handler(handler, tmp_path)

    assert _status(scenario, "9. lint fix: naprawa") == e2e.FAIL
    assert "backup does not exist" in scenario.results[8].detail


def test_clean_fix_with_nonzero_fixed_fails(tmp_path: Path) -> None:
    handler = HappyHandler()
    handler.clean_fix_payload["fixed"]["tiny"] = 1
    scenario = _run_handler(handler, tmp_path)

    assert _status(scenario, "10. lint fix: czysty rysunek") == e2e.FAIL
