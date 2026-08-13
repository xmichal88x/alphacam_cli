from __future__ import annotations

import pathlib
import types
from typing import Any
from unittest.mock import MagicMock

import pytest

from alphacam_cli.core import headless

_HEADLESS_MACRO = "ApplyMachiningAfterNesting.Events.HeadlessProcess"


def test_build_vbs_basic() -> None:
    vbs = headless.build_vbs("Job-A", "C:/temp/run.vbs", "C:/temp/run.log")
    assert 'GetObject(, "Ar5axaps.Application")' in vbs
    assert f'app.Run "{_HEADLESS_MACRO}", "Job-A"' in vbs
    assert 'Set f = fso.CreateTextFile("C:/temp/run.log", True)' in vbs
    assert vbs.endswith('WScript.Echo "done"\n')


def test_build_vbs_escaping() -> None:
    vbs = headless.build_vbs('Job "X"', "out.vbs", "out.log")
    assert 'app.Run "' + _HEADLESS_MACRO + '", "Job ""X"""' in vbs
    assert '"Job "X"' not in vbs


def _mock_run(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    run = MagicMock(return_value=types.SimpleNamespace(stdout="", returncode=0))
    monkeypatch.setattr("alphacam_cli.core.headless.subprocess.run", run)
    return run


def test_run_headless_args(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _mock_run(monkeypatch)
    machine: dict[str, Any] = {
        "psexec": "C:/temp/PsExec64.exe",
        "psexec_args": ["-accepteula", "-i", "1", "-s"],
        "cscript": "cscript",
        "use_shell": False,
    }
    headless.run_headless(machine, "C:/temp/run.vbs", timeout_seconds=120)
    run.assert_called_once_with(
        [
            "C:/temp/PsExec64.exe",
            "-accepteula",
            "-i",
            "1",
            "-s",
            "cscript",
            "//nologo",
            "C:/temp/run.vbs",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
        shell=False,
    )


def test_run_headless_timeout_param(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _mock_run(monkeypatch)
    headless.run_headless(headless.DEFAULT_MACHINE, "C:/temp/run.vbs")
    assert run.call_args.kwargs["timeout"] == 300
    assert run.call_args.kwargs["shell"] is False


def test_read_job_result_success(tmp_path: pathlib.Path) -> None:
    job_name = "Job-A"
    (tmp_path / job_name).mkdir()
    (tmp_path / job_name / f"{job_name}.log").write_text(
        "Status przetwarzania zadania: Sukces\n", encoding="utf-8"
    )
    result = headless.read_job_result(job_name, str(tmp_path))
    assert result["success"] is True
    assert result["status"] == "Sukces"
    assert "Status przetwarzania zadania: Sukces" in result["log"]
    assert isinstance(result["file_mtime"], float)


def test_read_job_result_failure(tmp_path: pathlib.Path) -> None:
    job_name = "Job-B"
    (tmp_path / job_name).mkdir()
    (tmp_path / job_name / f"{job_name}.log").write_text(
        "Status przetwarzania zadania: Nieudane\n", encoding="utf-8"
    )
    result = headless.read_job_result(job_name, str(tmp_path))
    assert result["success"] is False
    assert result["status"] == "Nieudane"


def test_read_job_result_missing(tmp_path: pathlib.Path) -> None:
    result = headless.read_job_result("Job-C", str(tmp_path))
    assert result["success"] is False
    assert result["status"] == "missing"
    assert "detail" in result
