from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from alphacam_cli.gateway.remote import (
    RemoteApplication,
    _basename,
    _DrawingProxy,
    _ToolProxy,
)


def test_remote_new_drawing() -> None:
    session = MagicMock()
    session.new_drawing.return_value = {"geometries_count": 3}
    app = RemoteApplication(session)
    drw = app.new_drawing(200, 100, 5, "Hello")
    assert drw is not None
    assert isinstance(drw, _DrawingProxy)
    assert drw.geometries_count == 3
    session.new_drawing.assert_called_once_with(200, 100, 5, "Hello")


def test_remote_new_drawing_defaults() -> None:
    session = MagicMock()
    session.new_drawing.return_value = {"geometries_count": 0}
    app = RemoteApplication(session)
    drw = app.new_drawing()
    assert drw is not None
    session.new_drawing.assert_called_once_with(100, 50, 0, "")


def test_remote_new_drawing_none() -> None:
    session = MagicMock()
    session.new_drawing.return_value = None
    app = RemoteApplication(session)
    assert app.new_drawing() is None


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (r"C:\A\B\file.art", "file.art"),
        ("/a/b/file.art", "file.art"),
        ("file.art", "file.art"),
        ("C:/A\\B\\file.art", "file.art"),
        (r"C:\ALPHACAM\LICOMDAT\RTools.Alp\Ball End - 10mm.art", "Ball End - 10mm.art"),
        ("", ""),
    ],
)
def test_basename_windows_and_posix(path: str, expected: str) -> None:
    assert _basename(path) == expected


def test_remote_select_tool_sends_basename_only() -> None:
    session = MagicMock()
    session.select_tool.return_value = {
        "name": "Ball End - 10mm",
        "diameter": 10.0,
        "number": 1,
        "length": 50.0,
        "tool_type": 0,
    }
    app = RemoteApplication(session)
    tool = app.select_tool(r"C:\ALPHACAM\LICOMDAT\RTools.Alp\Ball End - 10mm.art")
    assert tool is not None
    assert isinstance(tool, _ToolProxy)
    session.select_tool.assert_called_once_with("Ball End - 10mm.art")


def test_remote_select_tool_none() -> None:
    session = MagicMock()
    session.select_tool.return_value = None
    app = RemoteApplication(session)
    assert app.select_tool(r"C:\tools\Flat-10mm.amt") is None


def test_remote_mill_data_sends_xy_corners_and_start_point() -> None:
    from alphacam_cli.gateway.remote import _RemoteMillData

    session = MagicMock()
    md = _RemoteMillData(session)
    md.xy_corners = 1
    md.start_x = 50.0
    md.start_y = 100.0
    md.rough_finish()
    session.mill_rough.assert_called_once_with(xy_corners=1, start_x=50.0, start_y=100.0)
