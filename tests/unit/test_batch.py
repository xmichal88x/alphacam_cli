from __future__ import annotations

from unittest.mock import MagicMock

from alphacam_cli.cli.batch import _process_file
from alphacam_cli.core.application import Application


def test_process_file_ok(mock_com: MagicMock) -> None:
    from win32com.client import Dispatch

    drw = MagicMock()
    drw.OutputNC = MagicMock()
    drw.SaveAs = MagicMock()

    ac = Application(Dispatch())
    ac._app.OpenDrawing.return_value = drw

    result = _process_file(ac, "test.amd", "/tmp")

    assert result["status"] == "OK"
    assert result["error"] == ""
    drw.OutputNC.assert_called_once()
    drw.SaveAs.assert_called_once()


def test_process_file_open_fails(mock_com: MagicMock) -> None:
    from win32com.client import Dispatch

    ac = Application(Dispatch())
    ac._app.OpenDrawing.side_effect = Exception("Cannot open")
    result = _process_file(ac, "test.amd", "/tmp")

    assert result["status"] == "FAIL"
    assert "Cannot open" in result["error"]


def test_process_file_open_returns_none(mock_com: MagicMock) -> None:
    from win32com.client import Dispatch

    ac = Application(Dispatch())
    ac._app.OpenDrawing.return_value = None
    result = _process_file(ac, "test.amd", "/tmp")

    assert result["status"] == "FAIL"
    assert "Could not open drawing" in result["error"]


def test_process_file_nc_fails(mock_com: MagicMock) -> None:
    from win32com.client import Dispatch

    drw = MagicMock()
    drw.OutputNC.side_effect = Exception("NC error")
    drw.SaveAs = MagicMock()

    ac = Application(Dispatch())
    ac._app.OpenDrawing.return_value = drw

    result = _process_file(ac, "test.amd", "/tmp")

    assert result["status"] == "FAIL"
    assert "NC output failed" in result["error"]


def test_process_file_save_as_fails_but_nc_ok(mock_com: MagicMock) -> None:
    from win32com.client import Dispatch

    drw = MagicMock()
    drw.OutputNC = MagicMock()
    drw.SaveAs.side_effect = Exception("Save error")

    ac = Application(Dispatch())
    ac._app.OpenDrawing.return_value = drw

    result = _process_file(ac, "test.amd", "/tmp")

    assert result["status"] == "OK"
    assert "Drawing save failed" in result["error"]
    drw.OutputNC.assert_called_once()
