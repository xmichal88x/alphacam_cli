from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from alphacam_cli.cli.diagnose import app

runner = CliRunner()


def _make_app_mock() -> MagicMock:
    app = MagicMock()
    app.Visible = False
    app.AlphacamVersion = "2024.1"
    app.FullName = "C:\\AlphaCAM\\alphaCAM.exe"
    app.Name = "AlphaCAM"
    app.ProgramLevel = 3
    app.ProgramLetter = 82
    app.LicomdatPath = "C:\\Licomdat"
    app.LicomdirPath = "C:\\Licomdir"
    app.PostFileName = "fanuc.pst"
    app.ApiVersion = 20240315

    md = MagicMock()
    app.CreateMillData.return_value = md

    return app


@contextmanager
def _mock_alphacam_context() -> Iterator[MagicMock]:
    app_mock = _make_app_mock()

    @contextmanager
    def fake_context(visible: bool = False, prog_id: str | None = None) -> Iterator[MagicMock]:
        yield app_mock

    with patch("alphacam_cli.cli.diagnose.alphacam_context", fake_context):
        yield app_mock


def test_diagnose_success() -> None:
    with _mock_alphacam_context():
        result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "AlphaCAM Diagnostics" in result.stderr


def test_diagnose_no_com_connection() -> None:
    from alphacam_cli.com.manager import AlphacamConnectionError

    @contextmanager
    def failing_context(*args: object, **kwargs: object) -> Iterator[MagicMock]:
        raise AlphacamConnectionError("No AlphaCAM available")  # noqa: TRY003

    with patch("alphacam_cli.cli.diagnose.alphacam_context", failing_context):
        result = runner.invoke(app, [])
    assert result.exit_code == 1
    assert "No AlphaCAM COM connection" in result.stderr


def test_diagnose_win32com_not_installed() -> None:
    with patch("alphacam_cli.cli.diagnose.win32com", None), _mock_alphacam_context():
        result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "NOT INSTALLED" in result.stderr


def test_diagnose_create_temp_drawing_none() -> None:
    with _mock_alphacam_context() as app_mock:
        app_mock.ActiveDrawing = None
        result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "CreateTempDrawing returned None" in result.stderr


def test_diagnose_create_mill_data_fails() -> None:
    with _mock_alphacam_context() as app_mock:
        app_mock.CreateMillData.side_effect = Exception("Simulated failure")
        result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "create failed" in result.stderr


def test_diagnose_win32com_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import sys

    import alphacam_cli.cli.diagnose as diagnose_module

    original = sys.modules.get("win32com")
    monkeypatch.setitem(sys.modules, "win32com", None)
    monkeypatch.setitem(sys.modules, "win32com.client", None)
    importlib.reload(diagnose_module)
    try:
        assert diagnose_module.win32com is None  # type: ignore[attr-defined]
    finally:
        if original is not None:
            sys.modules["win32com"] = original
            sys.modules["win32com.client"] = original.client
            importlib.reload(diagnose_module)
