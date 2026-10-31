from __future__ import annotations

import subprocess
import tarfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from scripts import deploy_vm125 as deploy


def _completed(
    args: list[str] | tuple[str, ...],
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(list(args), returncode, stdout, stderr)


class FakeRunner:
    def __init__(self, overrides: dict[str, tuple[int, str, str]] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.overrides = overrides or {}

    def __call__(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append([str(part) for part in args])
        joined = " ".join(str(part) for part in args)
        for needle, (code, out, err) in self.overrides.items():
            if needle in joined:
                return _completed(args, code, out, err)
        return _completed(args)

    def joined_calls(self) -> list[str]:
        return [" ".join(call) for call in self.calls]


def _config(**overrides: Any) -> deploy.RemoteConfig:
    data: dict[str, Any] = {
        "host": "192.168.100.60",
        "user": "AlphaCam",
        "remote_dir": "C:/alphacam_cli",
        "service": "AlphaCAMGateway",
        "nssm": "C:/temp/nssm/nssm.exe",
        "timeout": 5.0,
    }
    data.update(overrides)
    return deploy.RemoteConfig(**data)


def test_parser_defaults() -> None:
    args = deploy.build_parser().parse_args([])
    assert args.host == "192.168.100.60"
    assert args.user == "AlphaCam"
    assert args.remote_dir == "C:/alphacam_cli"
    assert args.service == "AlphaCAMGateway"
    assert args.nssm == "C:/temp/nssm/nssm.exe"
    assert args.timeout == 60.0
    assert args.health_timeout == 90.0
    assert args.health_interval == 5.0
    assert args.cli == "./.venv/bin/alphacam"
    assert args.dry_run is False
    assert args.rollback is None


def test_parser_custom_values() -> None:
    args = deploy.build_parser().parse_args(
        [
            "--host",
            "10.0.0.5",
            "--user",
            "Operator",
            "--remote-dir",
            "C:/app",
            "--service",
            "Svc",
            "--nssm",
            "C:/nssm.exe",
            "--timeout",
            "12.5",
            "--dry-run",
            "--rollback",
            "C:/temp/backup",
        ]
    )
    assert args.host == "10.0.0.5"
    assert args.timeout == 12.5
    assert args.dry_run is True
    assert args.rollback == "C:/temp/backup"


def test_parser_cli_override() -> None:
    args = deploy.build_parser().parse_args(["--cli", "C:/tools/alphacam.exe"])
    assert args.cli == "C:/tools/alphacam.exe"


def test_parser_health_options() -> None:
    args = deploy.build_parser().parse_args(
        ["--health-timeout", "12.5", "--health-interval", "0.5"]
    )
    assert args.health_timeout == 12.5
    assert args.health_interval == 0.5


def test_rollback_flag_without_value_uses_state() -> None:
    args = deploy.build_parser().parse_args(["--rollback"])
    assert args.rollback == ""


def test_ssh_command_uses_sshpass_when_password_set() -> None:
    command = deploy.build_ssh_command(_config(password="secret"), "echo ok")
    assert command[:3] == ["sshpass", "-p", "secret"]
    assert command[3] == "ssh"
    assert command[-2] == "AlphaCam@192.168.100.60"
    assert command[-1] == "echo ok"


def test_scp_command_uses_sshpass_when_password_set() -> None:
    command = deploy.build_scp_command(_config(password="secret"), Path("/tmp/x.tgz"), "C:/x.tgz")
    assert command[0] == "sshpass"
    assert command[1] == "-p"
    assert command[2] == "secret"
    assert "scp" in command
    assert command[-1] == "AlphaCam@192.168.100.60:C:/x.tgz"


def test_ssh_command_without_password_has_no_secret() -> None:
    command = deploy.build_ssh_command(_config(), "echo ok")
    assert command[0] == "ssh"
    assert "sshpass" not in command
    assert "BatchMode=yes" in command
    assert "secret" not in " ".join(command)


def test_config_from_args_never_embeds_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPHACAM_VM_PASS", raising=False)
    config = deploy.config_from_args(deploy.build_parser().parse_args([]))
    assert config.password is None
    command = deploy.build_ssh_command(config, "echo ok")
    assert "sshpass" not in command
    assert "-p" not in command


def test_config_from_args_reads_password_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPHACAM_VM_PASS", "from-env")
    config = deploy.config_from_args(deploy.build_parser().parse_args([]))
    assert config.password == "from-env"
    assert config.__repr__().find("from-env") == -1


def test_win_join_normalizes_separators() -> None:
    assert deploy.win_join("C:/alphacam_cli/", "src", "/alphacam_cli") == (
        "C:\\alphacam_cli\\src\\alphacam_cli"
    )


def test_ps_quote_escapes_single_quotes() -> None:
    assert deploy.ps_quote("C:/O'Brien") == "'C:/O''Brien'"


def test_build_hash_script_quotes_windows_path() -> None:
    script = deploy.build_hash_script("C:/alphacam_cli/src/alphacam_cli")
    assert "$root = 'C:\\alphacam_cli\\src\\alphacam_cli'" in script
    assert "Get-FileHash" in script
    assert "SHA256" in script


def test_parse_remote_hashes_accepts_backslashes() -> None:
    digest = "a" * 64
    parsed = deploy.parse_remote_hashes(f"core\\drawing.py|{digest}\r\ncli\\main.py|{'b' * 64}\r\n")
    assert parsed["core/drawing.py"] == digest
    assert parsed["cli/main.py"] == "b" * 64


def test_parse_remote_hashes_ignores_noise() -> None:
    assert deploy.parse_remote_hashes("warning: something\nnonsense\n") == {}


def test_compare_hashes_reports_missing_extra_and_mismatch() -> None:
    local = {"a.py": "1" * 64, "b.py": "2" * 64}
    remote = {"a.py": "3" * 64, "c.py": "4" * 64}
    problems = deploy.compare_hashes(local, remote)
    assert "hash mismatch: a.py" in problems
    assert "missing remotely: b.py" in problems
    assert "unexpected remotely: c.py" in problems


def test_compare_hashes_equal_is_empty() -> None:
    hashes = {"a.py": "1" * 64}
    assert deploy.compare_hashes(hashes, dict(hashes)) == []


def test_create_archive_excludes_pycache(tmp_path: Path) -> None:
    source = tmp_path / "pkg"
    (source / "__pycache__").mkdir(parents=True)
    (source / "main.py").write_text("print(1)\n", encoding="utf-8")
    (source / "py.typed").write_text("", encoding="utf-8")
    (source / "__pycache__" / "main.pyc").write_bytes(b"x")
    archive = tmp_path / "payload.tar.gz"

    count = deploy.create_archive(source, archive)

    assert count == 2
    with tarfile.open(archive, "r:gz") as tar:
        names = sorted(member.name for member in tar.getmembers())
    assert names == ["alphacam_cli/main.py", "alphacam_cli/py.typed"]


def test_create_backup_uses_xcopy_with_quotes() -> None:
    runner = FakeRunner()
    backup_dir = deploy.create_backup(_config(), runner, timestamp="20261031-120000")
    assert backup_dir == "C:\\temp\\deploy_backup_20261031-120000"
    command = runner.joined_calls()[0]
    assert "xcopy /E /I /H /Y" in command
    assert '"C:\\alphacam_cli\\src\\alphacam_cli"' in command
    assert f'"{backup_dir}"' in command


def test_backup_failure_raises() -> None:
    runner = FakeRunner({"xcopy": (4, "", "disk error")})
    with pytest.raises(deploy.DeployError, match="backup failed"):
        deploy.create_backup(_config(), runner, timestamp="20261031-120000")


def test_preflight_fails_on_ssh_error() -> None:
    runner = FakeRunner({"echo ok": (255, "", "connection refused")})
    with pytest.raises(deploy.DeployError, match="SSH connection failed"):
        deploy.preflight(_config(), runner)


def test_preflight_fails_when_directory_missing() -> None:
    runner = FakeRunner({"Test-Path": (3, "", "")})
    with pytest.raises(deploy.DeployError, match="source directory not found"):
        deploy.preflight(_config(), runner)


def test_preflight_fails_when_service_missing() -> None:
    runner = FakeRunner({"Get-Service": (3, "", "")})
    with pytest.raises(deploy.DeployError, match="service not found"):
        deploy.preflight(_config(), runner)


def test_preflight_success() -> None:
    runner = FakeRunner()
    deploy.preflight(_config(), runner)
    assert len(runner.calls) == 3


def test_upload_tree_uses_single_scp_and_swaps(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.py").write_text("x = 1\n", encoding="utf-8")
    (source / "__pycache__").mkdir()
    (source / "__pycache__" / "main.pyc").write_bytes(b"x")
    runner = FakeRunner()

    count = deploy.upload_tree(_config(), runner, timestamp="20261031-120000", local_source=source)

    assert count == 1
    joined = runner.joined_calls()
    scp_calls = [call for call in joined if " scp " in f" {call} "]
    assert len(scp_calls) == 1
    swap = next(call for call in joined if "tar -xzf" in call)
    replace_target = "Remove-Item -LiteralPath 'C:\\alphacam_cli\\src\\alphacam_cli'"
    assert swap.index("tar -xzf") < swap.index(replace_target)
    assert swap.index(replace_target) < swap.index("Move-Item")
    assert "deploy_stage_20261031-120000" in swap
    assert "alphacam_cli" in swap


def test_upload_failure_raises(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.py").write_text("x = 1\n", encoding="utf-8")
    runner = FakeRunner({"scp": (1, "", "permission denied")})
    with pytest.raises(deploy.DeployError, match="upload failed"):
        deploy.upload_tree(_config(), runner, local_source=source)


def test_dry_run_never_invokes_subprocess() -> None:
    with patch("subprocess.run") as mocked:
        exit_code = deploy.deploy(_config(), dry_run=True, out=lambda _: None)
    assert exit_code == deploy.EXIT_OK
    mocked.assert_not_called()


def test_dry_run_plan_mentions_target_and_counts(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.py").write_text("x = 1\n", encoding="utf-8")
    lines: list[str] = []
    deploy.deploy(_config(), dry_run=True, out=lines.append, local_source=source)
    text = "\n".join(lines)
    assert "AlphaCam@192.168.100.60" in text
    assert "files: 1" in text
    assert "AlphaCAMGateway" in text


def test_preflight_failure_returns_exit_2(tmp_path: Path) -> None:
    runner = FakeRunner({"echo ok": (255, "", "down")})
    exit_code = deploy.deploy(
        _config(),
        runner=runner,
        out=lambda _: None,
        state_file=tmp_path / "state.json",
    )
    assert exit_code == deploy.EXIT_PREFLIGHT
    assert not (tmp_path / "state.json").exists()


def test_hash_mismatch_triggers_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.py").write_text("x = 1\n", encoding="utf-8")
    runner = FakeRunner({"sc query": (0, "STATE : 4 RUNNING\n", "")})
    rollbacks: list[deploy.DeployState] = []

    monkeypatch.setattr(
        deploy,
        "collect_remote_hashes",
        lambda *args, **kwargs: {"main.py": "0" * 64},
    )
    monkeypatch.setattr(
        deploy,
        "rollback",
        lambda config, state, runner=None, **kwargs: (
            rollbacks.append(state)
            or {"ok": True, "restored": True, "hashes_ok": True, "service": "Running"}
        ),
    )

    exit_code = deploy.deploy(
        _config(),
        runner=runner,
        out=lambda _: None,
        state_file=tmp_path / "state.json",
        local_source=source,
    )

    assert exit_code == deploy.EXIT_FAIL
    assert len(rollbacks) == 1
    assert rollbacks[0].backup_dir.startswith("C:\\temp\\deploy_backup_")


def test_health_failure_triggers_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.py").write_text("x = 1\n", encoding="utf-8")
    runner = FakeRunner({"sc query": (0, "STATE : 4 RUNNING\n", "")})
    rollbacks: list[deploy.DeployState] = []

    monkeypatch.setattr(
        deploy,
        "collect_remote_hashes",
        lambda *args, **kwargs: deploy.collect_local_hashes(source),
    )
    monkeypatch.setattr(
        deploy,
        "wait_for_health",
        lambda *args, **kwargs: deploy.HealthStatus(available=True, ok=False),
    )
    monkeypatch.setattr(
        deploy,
        "rollback",
        lambda config, state, runner=None, **kwargs: (
            rollbacks.append(state)
            or {"ok": True, "restored": True, "hashes_ok": True, "service": "Running"}
        ),
    )

    exit_code = deploy.deploy(
        _config(),
        runner=runner,
        out=lambda _: None,
        state_file=tmp_path / "state.json",
        local_source=source,
    )

    assert exit_code == deploy.EXIT_FAIL
    assert len(rollbacks) == 1


def test_deploy_success_uploads_and_verifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.py").write_text("x = 1\n", encoding="utf-8")
    runner = FakeRunner({"sc query": (0, "STATE : 4 RUNNING\n", "")})

    monkeypatch.setattr(
        deploy,
        "collect_remote_hashes",
        lambda *args, **kwargs: deploy.collect_local_hashes(source),
    )
    monkeypatch.setattr(
        deploy,
        "wait_for_health",
        lambda *args, **kwargs: deploy.HealthStatus(available=True, ok=True),
    )

    exit_code = deploy.deploy(
        _config(),
        runner=runner,
        out=lambda _: None,
        state_file=tmp_path / "state.json",
        local_source=source,
        executable=None,
    )

    assert exit_code == deploy.EXIT_OK
    state = deploy.load_state(tmp_path / "state.json")
    assert state is not None
    assert state.hashes == deploy.collect_local_hashes(source)
    assert state.backup_dir.startswith("C:\\temp\\deploy_backup_")


def _healthy_sequence(
    monkeypatch: pytest.MonkeyPatch, results: list[bool | deploy.HealthStatus]
) -> list[int]:
    responses = iter(results)
    calls: list[int] = []

    def _probe(*args: Any, **kwargs: Any) -> deploy.HealthStatus:
        calls.append(1)
        value = next(responses, results[-1])
        if isinstance(value, deploy.HealthStatus):
            return value
        return deploy.HealthStatus(available=True, ok=value)

    monkeypatch.setattr(deploy, "probe_health", _probe)
    return calls


def _deploy_source(tmp_path: Path) -> tuple[Path, FakeRunner]:
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.py").write_text("x = 1\n", encoding="utf-8")
    runner = FakeRunner({"sc query": (0, "STATE : 4 RUNNING\n", "")})
    return source, runner


def test_health_retry_succeeds_after_transient_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, runner = _deploy_source(tmp_path)
    monkeypatch.setattr(
        deploy,
        "collect_remote_hashes",
        lambda *args, **kwargs: deploy.collect_local_hashes(source),
    )
    calls = _healthy_sequence(monkeypatch, [False, False, True])
    rollbacks: list[deploy.DeployState] = []
    monkeypatch.setattr(
        deploy,
        "rollback",
        lambda config, state, runner=None, **kwargs: (
            rollbacks.append(state)
            or {"ok": True, "restored": True, "hashes_ok": True, "service": "Running"}
        ),
    )
    output: list[str] = []

    exit_code = deploy.deploy(
        _config(),
        runner=runner,
        out=output.append,
        state_file=tmp_path / "state.json",
        local_source=source,
        sleep=lambda _: None,
    )

    assert exit_code == deploy.EXIT_OK
    assert len(calls) == 3
    assert rollbacks == []
    text = "\n".join(output)
    assert "health attempt 1/18" in text
    assert "health attempt 2/18" in text
    assert "health attempt 3/18: ok" in text


def test_health_always_failing_times_out_and_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, runner = _deploy_source(tmp_path)
    monkeypatch.setattr(
        deploy,
        "collect_remote_hashes",
        lambda *args, **kwargs: deploy.collect_local_hashes(source),
    )
    calls = _healthy_sequence(monkeypatch, [False])
    rollbacks: list[deploy.DeployState] = []
    monkeypatch.setattr(
        deploy,
        "rollback",
        lambda config, state, runner=None, **kwargs: (
            rollbacks.append(state)
            or {"ok": True, "restored": True, "hashes_ok": True, "service": "Running"}
        ),
    )

    exit_code = deploy.deploy(
        _config(),
        runner=runner,
        out=lambda _: None,
        state_file=tmp_path / "state.json",
        local_source=source,
        sleep=lambda _: None,
    )

    assert exit_code == deploy.EXIT_FAIL
    assert len(calls) == 18
    assert len(rollbacks) == 1


def test_health_warns_when_multiple_acam_processes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, runner = _deploy_source(tmp_path)
    monkeypatch.setattr(
        deploy,
        "collect_remote_hashes",
        lambda *args, **kwargs: deploy.collect_local_hashes(source),
    )
    _healthy_sequence(
        monkeypatch,
        [deploy.HealthStatus(available=True, ok=True, payload={"ok": True, "acam_processes": 2})],
    )
    output: list[str] = []

    exit_code = deploy.deploy(
        _config(),
        runner=runner,
        out=output.append,
        state_file=tmp_path / "state.json",
        local_source=source,
        sleep=lambda _: None,
    )

    assert exit_code == deploy.EXIT_OK
    text = "\n".join(output)
    assert "WARNING" in text
    assert "acam_processes=2" in text


def test_health_without_acam_processes_does_not_warn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, runner = _deploy_source(tmp_path)
    monkeypatch.setattr(
        deploy,
        "collect_remote_hashes",
        lambda *args, **kwargs: deploy.collect_local_hashes(source),
    )
    _healthy_sequence(
        monkeypatch,
        [deploy.HealthStatus(available=True, ok=True, payload={"ok": True})],
    )
    output: list[str] = []

    exit_code = deploy.deploy(
        _config(),
        runner=runner,
        out=output.append,
        state_file=tmp_path / "state.json",
        local_source=source,
        sleep=lambda _: None,
    )

    assert exit_code == deploy.EXIT_OK
    assert not any("WARNING" in line for line in output)


def test_deploy_skips_health_when_cli_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.py").write_text("x = 1\n", encoding="utf-8")
    runner = FakeRunner({"sc query": (0, "STATE : 4 RUNNING\n", "")})
    output: list[str] = []

    monkeypatch.setattr(
        deploy,
        "collect_remote_hashes",
        lambda *args, **kwargs: deploy.collect_local_hashes(source),
    )
    monkeypatch.setattr(deploy.shutil, "which", lambda name: None)
    monkeypatch.setattr(deploy.Path, "exists", lambda self: False)

    exit_code = deploy.deploy(
        _config(),
        runner=runner,
        out=output.append,
        state_file=tmp_path / "state.json",
        local_source=source,
    )

    assert exit_code == deploy.EXIT_OK
    assert any("health check skipped" in line for line in output)


def test_rollback_restores_restarts_and_verifies() -> None:
    digest = "a" * 64
    state = deploy.DeployState(
        timestamp="20261031-120000",
        host="192.168.100.60",
        user="AlphaCam",
        remote_dir="C:/alphacam_cli",
        service="AlphaCAMGateway",
        backup_dir="C:\\temp\\deploy_backup_20261031-120000",
        hashes={"main.py": digest},
    )
    runner = FakeRunner(
        {
            "Copy-Item": (0, "", ""),
            "nssm.exe": (0, "", ""),
            "sc query": (0, "STATE : 4 RUNNING\n", ""),
            "Get-FileHash": (0, f"main.py|{digest}\n", ""),
        }
    )

    report = deploy.rollback(_config(), state, runner)

    assert report["ok"] is True
    assert report["restored"] is True
    assert report["hashes_ok"] is True
    assert report["service"] == "RUNNING"


def test_rollback_hash_mismatch_is_reported() -> None:
    state = deploy.DeployState(
        timestamp="20261031-120000",
        host="192.168.100.60",
        user="AlphaCam",
        remote_dir="C:/alphacam_cli",
        service="AlphaCAMGateway",
        backup_dir="C:\\temp\\deploy_backup_20261031-120000",
        hashes={"main.py": "a" * 64},
    )
    runner = FakeRunner(
        {
            "Copy-Item": (0, "", ""),
            "nssm.exe": (0, "", ""),
            "sc query": (0, "STATE : 4 RUNNING\n", ""),
            "Get-FileHash": (0, f"main.py|{'b' * 64}\n", ""),
        }
    )

    report = deploy.rollback(_config(), state, runner)

    assert report["ok"] is False
    assert report["hashes_ok"] is False
    assert "hash mismatch: main.py" in report["problems"]


def test_rollback_fails_when_backup_missing() -> None:
    state = deploy.DeployState(
        timestamp="20261031-120000",
        host="192.168.100.60",
        user="AlphaCam",
        remote_dir="C:/alphacam_cli",
        service="AlphaCAMGateway",
        backup_dir="C:\\temp\\deploy_backup_20261031-120000",
        hashes={"main.py": "a" * 64},
    )
    runner = FakeRunner({"Copy-Item": (4, "", "path not found")})

    report = deploy.rollback(_config(), state, runner)

    assert report["ok"] is False
    assert report["restored"] is False


def test_restart_uses_single_quoted_argument() -> None:
    runner = FakeRunner(
        {
            "nssm.exe": (0, "", ""),
            "sc query": (0, "STATE : 4 RUNNING\n", ""),
        }
    )

    state = deploy.restart_service(_config(), runner, sleep=lambda _: None)

    assert state == "RUNNING"
    restart_calls = [call for call in runner.calls if "nssm.exe" in call[-1]]
    assert len(restart_calls) == 1
    restart = restart_calls[0]
    assert restart[-1] == '"C:\\temp\\nssm\\nssm.exe" restart "AlphaCAMGateway"'
    assert sum(1 for part in restart if "nssm.exe" in part) == 1
    assert "cmd /c" not in restart[-1]


def test_rollback_restart_uses_same_quoted_argument() -> None:
    digest = "a" * 64
    state = deploy.DeployState(
        timestamp="20261031-120000",
        host="192.168.100.60",
        user="AlphaCam",
        remote_dir="C:/alphacam_cli",
        service="AlphaCAMGateway",
        backup_dir="C:\\temp\\deploy_backup_20261031-120000",
        hashes={"main.py": digest},
    )
    runner = FakeRunner(
        {
            "Copy-Item": (0, "", ""),
            "nssm.exe": (0, "", ""),
            "sc query": (0, "STATE : 4 RUNNING\n", ""),
            "Get-FileHash": (0, f"main.py|{digest}\n", ""),
        }
    )

    report = deploy.rollback(_config(), state, runner)

    assert report["ok"] is True
    restart_calls = [call for call in runner.calls if "nssm.exe" in call[-1]]
    assert len(restart_calls) == 1
    assert restart_calls[0][-1] == ('"C:\\temp\\nssm\\nssm.exe" restart "AlphaCAMGateway"')
    assert "cmd /c" not in restart_calls[0][-1]


def test_check_health_prefers_venv_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = FakeRunner()
    monkeypatch.setattr(deploy.Path, "exists", lambda self: True)
    monkeypatch.setattr(deploy.os, "access", lambda path, mode: True)

    result = deploy.check_health(_config(), runner)

    assert result is False
    assert runner.calls[0][0] == ".venv/bin/alphacam"


def test_check_health_explicit_executable_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = FakeRunner()
    monkeypatch.setattr(deploy.Path, "exists", lambda self: True)
    monkeypatch.setattr(deploy.os, "access", lambda path, mode: True)

    deploy.check_health(_config(), runner, executable="C:/tools/alphacam.exe")

    assert runner.calls[0][0] == "C:/tools/alphacam.exe"


def test_check_health_returns_none_without_any_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = FakeRunner()
    monkeypatch.setattr(deploy.Path, "exists", lambda self: False)
    monkeypatch.setattr(deploy.shutil, "which", lambda name: None)

    assert deploy.check_health(_config(), runner) is None
    assert runner.calls == []


def test_state_roundtrip(tmp_path: Path) -> None:
    state = deploy.DeployState(
        timestamp="20261031-120000",
        host="h",
        user="u",
        remote_dir="C:/r",
        service="s",
        backup_dir="C:\\temp\\b",
        hashes={"a.py": "c" * 64},
    )
    path = tmp_path / "state.json"
    deploy.save_state(state, path)
    loaded = deploy.load_state(path)
    assert loaded == state


def test_load_state_missing_file_returns_none(tmp_path: Path) -> None:
    assert deploy.load_state(tmp_path / "missing.json") is None


def test_main_rollback_without_state_returns_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(deploy, "load_state", lambda path=None: None)
    exit_code = deploy.main(["--rollback"])
    assert exit_code == deploy.EXIT_FAIL


def test_main_rollback_with_explicit_backup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[deploy.DeployState] = []
    monkeypatch.setattr(deploy, "load_state", lambda path=None: None)
    monkeypatch.setattr(
        deploy,
        "rollback",
        lambda config, state, runner=None, **kwargs: (
            captured.append(state)
            or {"ok": True, "restored": True, "hashes_ok": None, "service": "Running"}
        ),
    )
    exit_code = deploy.main(["--rollback", "C:\\temp\\deploy_backup_x"])
    assert exit_code == deploy.EXIT_OK
    assert captured[0].backup_dir == "C:\\temp\\deploy_backup_x"
    assert captured[0].hashes == {}


def test_main_dry_run_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch("subprocess.run") as mocked:
        exit_code = deploy.main(["--dry-run"])
    assert exit_code == deploy.EXIT_OK
    mocked.assert_not_called()
