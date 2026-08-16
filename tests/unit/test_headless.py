from __future__ import annotations

import os
import pathlib
import time
from typing import Any

import pytest

from alphacam_cli.core import headless


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


def test_read_job_result_getmtime_error(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_name = "Job-G"
    (tmp_path / job_name).mkdir()
    (tmp_path / job_name / f"{job_name}.log").write_text(
        "Status przetwarzania zadania: Sukces\n", encoding="utf-8"
    )

    def boom(path: str) -> float:
        raise OSError("stat failed")  # noqa: TRY003

    monkeypatch.setattr(headless.os.path, "getmtime", boom)
    result = headless.read_job_result(job_name, str(tmp_path), min_mtime=0)
    assert result == {"success": False, "status": "read_error", "detail": "stat failed"}


def test_read_job_result_open_error(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_name = "Job-H"
    (tmp_path / job_name).mkdir()
    (tmp_path / job_name / f"{job_name}.log").write_text(
        "Status przetwarzania zadania: Sukces\n", encoding="utf-8"
    )

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise OSError("open failed")  # noqa: TRY003

    monkeypatch.setattr("builtins.open", boom)
    result = headless.read_job_result(job_name, str(tmp_path))
    assert result == {"success": False, "status": "read_error", "detail": "open failed"}


def test_read_job_result_missing(tmp_path: pathlib.Path) -> None:
    result = headless.read_job_result("Job-C", str(tmp_path))
    assert result["success"] is False
    assert result["status"] == "missing"
    assert "detail" in result


def test_read_job_result_min_mtime_stale(tmp_path: pathlib.Path) -> None:
    job_name = "Job-D"
    (tmp_path / job_name).mkdir()
    log_path = tmp_path / job_name / f"{job_name}.log"
    log_path.write_text("Status przetwarzania zadania: Sukces\n", encoding="utf-8")
    result = headless.read_job_result(job_name, str(tmp_path), min_mtime=time.time() + 1000)
    assert result["success"] is False
    assert result["status"] == "missing"
    assert result["detail"] == (f"job log is stale (mtime older than process start): {log_path}")


def test_read_job_result_min_mtime_fresh(tmp_path: pathlib.Path) -> None:
    job_name = "Job-E"
    (tmp_path / job_name).mkdir()
    (tmp_path / job_name / f"{job_name}.log").write_text(
        "Status przetwarzania zadania: Sukces\n", encoding="utf-8"
    )
    result = headless.read_job_result(job_name, str(tmp_path), min_mtime=0)
    assert result["success"] is True
    assert result["status"] == "Sukces"


def test_read_job_result_first_candidate_stale_second_fresh(tmp_path: pathlib.Path) -> None:
    job_name = "Job-F"
    (tmp_path / job_name).mkdir()
    candidates = headless._job_log_candidates(job_name, str(tmp_path))
    if len(candidates) < 2:
        pytest.skip("platform with a single log candidate path")
    stale_path = pathlib.Path(candidates[0])
    fresh_path = pathlib.Path(candidates[1])
    stale_path.write_text("Status przetwarzania zadania: Błąd\n", encoding="utf-8")
    fresh_path.write_text("Status przetwarzania zadania: Sukces\n", encoding="utf-8")
    now = time.time()
    os.utime(stale_path, (now - 1000, now - 1000))
    result = headless.read_job_result(job_name, str(tmp_path), min_mtime=now - 500)
    assert result["success"] is True
    assert result["status"] == "Sukces"
    assert "Status przetwarzania zadania: Sukces" in result["log"]


@pytest.mark.parametrize(
    ("log_text", "expected_status", "expected_success"),
    [
        ("Status przetwarzania zadania: sukces\n", "sukces", True),
        ("Status przetwarzania zadania: SUKCES\n", "SUKCES", True),
        ("Job processing status: Success\n", "Success", True),
        ("Job processing status: FAILED\n", "FAILED", False),
    ],
)
def test_read_job_result_status_locale_insensitive(
    tmp_path: pathlib.Path,
    log_text: str,
    expected_status: str,
    expected_success: bool,
) -> None:
    job_name = "Job-L"
    (tmp_path / job_name).mkdir()
    (tmp_path / job_name / f"{job_name}.log").write_text(log_text, encoding="utf-8")
    result = headless.read_job_result(job_name, str(tmp_path))
    assert result["success"] is expected_success
    assert result["status"] == expected_status


@pytest.mark.parametrize(
    "log_text",
    [
        "Zadanie przetworzone pomyślnie\n",
        "Processing finished OK\n",
        "status processing done\n",
    ],
)
def test_read_job_result_no_status_line(tmp_path: pathlib.Path, log_text: str) -> None:
    job_name = "Job-M"
    (tmp_path / job_name).mkdir()
    (tmp_path / job_name / f"{job_name}.log").write_text(log_text, encoding="utf-8")
    result = headless.read_job_result(job_name, str(tmp_path))
    assert result["success"] is False
    assert result["status"] == ""


@pytest.mark.parametrize(
    "job_name",
    ["../evil", "a/b", "a\\b", ".", ".."],
)
def test_read_job_result_invalid_job_name(tmp_path: pathlib.Path, job_name: str) -> None:
    result = headless.read_job_result(job_name, str(tmp_path))
    assert result["success"] is False
    assert result["status"] == "missing"
    assert result["detail"] == f"invalid job name: {job_name}"


def test_macro_invocation_state_missing(tmp_path: pathlib.Path) -> None:
    result = headless.macro_invocation_state(str(tmp_path / "f.log"))
    assert result == {"state": "missing", "last_pn": None, "last_line": "", "mtime": None}


def test_macro_invocation_state_ok(tmp_path: pathlib.Path) -> None:
    log_path = tmp_path / "f.log"
    log_path.write_text("09:52:49 PN=Prod E2E 01\n09:52:51 got\n09:53:26 r\n", encoding="utf-8")
    result = headless.macro_invocation_state(str(log_path))
    assert result["state"] == "ok"
    assert result["last_pn"] == "Prod E2E 01"
    assert isinstance(result["mtime"], float)


def test_macro_invocation_state_stale_after_got(tmp_path: pathlib.Path) -> None:
    log_path = tmp_path / "f.log"
    log_path.write_text("PN=X\ngot\n", encoding="utf-8")
    now = time.time()
    os.utime(log_path, (now - 600, now - 600))
    result = headless.macro_invocation_state(str(log_path), now=now)
    assert result["state"] == "stale"
    assert result["last_pn"] == "X"


def test_macro_invocation_state_running_after_got(tmp_path: pathlib.Path) -> None:
    log_path = tmp_path / "f.log"
    log_path.write_text("PN=X\ngot\n", encoding="utf-8")
    now = time.time()
    os.utime(log_path, (now - 10, now - 10))
    result = headless.macro_invocation_state(str(log_path), now=now)
    assert result["state"] == "running"
    assert result["last_pn"] == "X"


def test_macro_invocation_state_stale_before_got(tmp_path: pathlib.Path) -> None:
    log_path = tmp_path / "f.log"
    log_path.write_text("PN=X\n", encoding="utf-8")
    now = time.time()
    os.utime(log_path, (now - 600, now - 600))
    result = headless.macro_invocation_state(str(log_path), now=now)
    assert result["state"] == "stale"
    assert result["last_pn"] == "X"


def test_macro_invocation_state_ok_after_many_sequences(tmp_path: pathlib.Path) -> None:
    log_path = tmp_path / "f.log"
    log_path.write_text("PN=Old\ngot\nr\nPN=New\ngot\nr\n", encoding="utf-8")
    result = headless.macro_invocation_state(str(log_path))
    assert result["state"] == "ok"
    assert result["last_pn"] == "New"


def test_macro_invocation_state_stale_last_incomplete(tmp_path: pathlib.Path) -> None:
    log_path = tmp_path / "f.log"
    log_path.write_text("PN=Old\ngot\nr\nPN=New\ngot\n", encoding="utf-8")
    now = time.time()
    os.utime(log_path, (now - 600, now - 600))
    result = headless.macro_invocation_state(str(log_path), now=now)
    assert result["state"] == "stale"
    assert result["last_pn"] == "New"


def test_macro_invocation_state_unreadable(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_path = tmp_path / "f.log"
    log_path.write_text("PN=X\n", encoding="utf-8")

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise PermissionError("open failed")  # noqa: TRY003

    monkeypatch.setattr("builtins.open", boom)
    result = headless.macro_invocation_state(str(log_path))
    assert result["state"] == "unreadable"
    assert result["last_pn"] is None


def test_macro_invocation_state_last_pn(tmp_path: pathlib.Path) -> None:
    log_path = tmp_path / "f.log"
    log_path.write_text("23:59:22 PN=RAP E2E 012\n23:59:25 got\n", encoding="utf-8")
    result = headless.macro_invocation_state(str(log_path))
    assert result["last_pn"] == "RAP E2E 012"
    assert result["last_line"] == "23:59:25 got"


def test_macro_invocation_state_ignores_padding_lines(tmp_path: pathlib.Path) -> None:
    log_path = tmp_path / "f.log"
    log_path.write_text("\nPN=X\n\ngot\nsome noise\nr\n\n", encoding="utf-8")
    result = headless.macro_invocation_state(str(log_path))
    assert result["state"] == "ok"
    assert result["last_pn"] == "X"
    assert result["last_line"] == "r"


def test_macro_invocation_state_empty_log_no_stale(tmp_path: pathlib.Path) -> None:
    log_path = tmp_path / "f.log"
    log_path.write_text("", encoding="utf-8")
    now = time.time()
    os.utime(log_path, (now - 600, now - 600))
    result = headless.macro_invocation_state(str(log_path), now=now)
    assert result["state"] == "missing"
    assert result["last_pn"] is None
    assert isinstance(result["mtime"], float)


def test_macro_invocation_state_no_pn_no_stale(tmp_path: pathlib.Path) -> None:
    log_path = tmp_path / "f.log"
    log_path.write_text("some noise\njunk\n", encoding="utf-8")
    now = time.time()
    os.utime(log_path, (now - 600, now - 600))
    result = headless.macro_invocation_state(str(log_path), now=now)
    assert result["state"] == "missing"
    assert result["last_pn"] is None
    assert result["last_line"] == "junk"
    assert isinstance(result["mtime"], float)


def test_macro_invocation_state_noise_with_pn_counts_as_stale(
    tmp_path: pathlib.Path,
) -> None:
    log_path = tmp_path / "f.log"
    log_path.write_text("noise PN= junk\n", encoding="utf-8")
    now = time.time()
    os.utime(log_path, (now - 600, now - 600))
    result = headless.macro_invocation_state(str(log_path), now=now)
    assert result["state"] == "stale"
    assert result["last_pn"] == "junk"
    assert result["last_line"] == "noise PN= junk"
