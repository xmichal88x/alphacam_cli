from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from alphacam_cli.main import app
from tests.unit.test_cli import _MOCK_PATCHES, _make_app_mock

runner = CliRunner()

_BATCH_PATCHES = _MOCK_PATCHES + [
    ("alphacam_cli.cli.batch", "require_platform"),
    ("alphacam_cli.cli.batch", "alphacam_context"),
]


@contextmanager
def _mock_com_batch(app_mock: MagicMock | None = None) -> Iterator[MagicMock]:
    if app_mock is None:
        app_mock = _make_app_mock()

    @contextmanager
    def fake_context(visible: bool = False, prog_id: str | None = None) -> Iterator[MagicMock]:
        yield app_mock

    with ExitStack() as stack:
        for mod, attr in _BATCH_PATCHES:
            if attr == "alphacam_context":
                stack.enter_context(patch(f"{mod}.{attr}", fake_context))
            else:
                stack.enter_context(patch(f"{mod}.{attr}"))
        yield app_mock


def test_batch_process_no_files() -> None:
    with (
        _mock_com_batch(),
        patch("alphacam_cli.cli.batch.glob.glob", return_value=[]),
    ):
        result = runner.invoke(app, ["batch", "process", "/nonexistent"])
    assert result.exit_code == 1
    assert "No files matching" in result.stderr


def test_batch_process_success() -> None:
    with (
        _mock_com_batch(),
        patch("alphacam_cli.cli.batch.glob.glob", return_value=["file1.amd", "file2.amd"]),
        patch(
            "alphacam_cli.cli.batch._process_file",
            return_value={"file": "test.amd", "status": "OK", "error": ""},
        ),
    ):
        result = runner.invoke(app, ["batch", "process", "."])
    assert result.exit_code == 0
    assert "OK: 2" in result.stderr
    assert "Done: 2" in result.stderr


def test_batch_process_continue_on_error() -> None:
    def mock_process_file(_ac: object, file_path: str, _output_dir: str) -> dict[str, str]:
        if "fail" in file_path:
            return {"file": file_path, "status": "FAIL", "error": "Something went wrong"}
        return {"file": file_path, "status": "OK", "error": ""}

    with (
        _mock_com_batch(),
        patch(
            "alphacam_cli.cli.batch.glob.glob",
            return_value=["fail1.amd", "ok1.amd"],
        ),
        patch("alphacam_cli.cli.batch._process_file", side_effect=mock_process_file),
    ):
        result = runner.invoke(app, ["batch", "process", ".", "--continue-on-error"])
    assert result.exit_code == 1
    assert "OK: 1" in result.stderr
    assert "FAIL: 1" in result.stderr
    assert "Something went wrong" in result.stderr


def test_batch_process_break_on_first_error() -> None:
    mock_process = MagicMock(
        side_effect=[{"file": "file1.amd", "status": "FAIL", "error": "First error"}],
    )
    with (
        _mock_com_batch(),
        patch(
            "alphacam_cli.cli.batch.glob.glob",
            return_value=["file1.amd", "file2.amd", "file3.amd"],
        ),
        patch("alphacam_cli.cli.batch._process_file", mock_process),
    ):
        result = runner.invoke(app, ["batch", "process", "."])
    assert result.exit_code == 1
    assert "FAIL: 1" in result.stderr
    assert "First error" in result.stderr
    assert "Done: 1" in result.stderr
    # Verify break happened — only 1 file processed, not 3
    assert mock_process.call_count == 1


def test_batch_process_custom_output_dir() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = os.path.join(tmpdir, "output")
        with (
            _mock_com_batch(),
            patch("alphacam_cli.cli.batch.glob.glob", return_value=["test.amd"]),
            patch(
                "alphacam_cli.cli.batch._process_file",
                return_value={"file": "test.amd", "status": "OK", "error": ""},
            ),
        ):
            result = runner.invoke(app, ["batch", "process", ".", "--output", out_dir])
        assert result.exit_code == 0
        assert os.path.isdir(out_dir)
        assert out_dir in result.stderr


def test_batch_process_post_processor() -> None:
    post_path = "C:/ALPHACAM/LICOMDAT/RPosts.Alp/fanuc.arp"
    with (
        _mock_com_batch(),
        patch("alphacam_cli.cli.batch.glob.glob", return_value=["test.amd"]),
        patch(
            "alphacam_cli.cli.batch._process_file",
            return_value={"file": "test.amd", "status": "OK", "error": ""},
        ),
        patch("alphacam_cli.core.application.glob.glob", return_value=[post_path]),
    ):
        result = runner.invoke(app, ["batch", "process", ".", "--post", "fanuc"])
    assert result.exit_code == 0
    assert "Post selected: fanuc" in result.stderr
