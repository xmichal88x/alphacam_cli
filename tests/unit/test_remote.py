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


def test_remote_drawing_parametric() -> None:
    session = MagicMock()
    session.drawing_parametric.return_value = {
        "success": True,
        "geometries_count": 2,
        "tool_paths_count": 2,
    }
    app = RemoteApplication(session)
    result = app.drawing_parametric(800, 400, offset=60, fillet=3, depth=-19)
    assert result["success"] is True
    session.drawing_parametric.assert_called_once_with(
        800, 400, offset=60, fillet=3, depth=-19, tool=None, spindle=None, feed=None, down_feed=None
    )


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


def test_remote_select_tool_sends_full_path() -> None:
    session = MagicMock()
    session.select_tool.return_value = {
        "name": "Drill - 10mm dia",
        "diameter": 10.0,
        "number": 1,
        "length": 50.0,
        "tool_type": 0,
    }
    app = RemoteApplication(session)
    tool = app.select_tool(
        r"C:\ALPHACAM\LICOMDAT\rtools.alp\Inch\Drills - Twist\Drill - 10mm dia.art"
    )
    assert tool is not None
    assert isinstance(tool, _ToolProxy)
    session.select_tool.assert_called_once_with(
        r"C:\ALPHACAM\LICOMDAT\rtools.alp\Inch\Drills - Twist\Drill - 10mm dia.art"
    )


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


def test_remote_drawing_proxy_output_nc_returns_dict() -> None:
    session = MagicMock()
    session.get_active_drawing.return_value = {"geometries_count": 1}
    session.output_nc.return_value = {"success": True, "size": 387}
    app = RemoteApplication(session)
    drw = app.get_active_drawing()
    assert drw is not None
    result = drw.output_nc(r"C:\temp\out.nc")
    assert result == {"success": True, "size": 387}
    session.output_nc.assert_called_once_with(r"C:\temp\out.nc")


def test_remote_glob_files() -> None:
    session = MagicMock()
    session.glob_files.return_value = ["C:/parts/a.amd", "C:/parts/b.amd"]
    app = RemoteApplication(session)
    result = app.glob_files("C:/parts", "*.amd")
    assert result == ["C:/parts/a.amd", "C:/parts/b.amd"]
    session.glob_files.assert_called_once_with("C:/parts", "*.amd")


def test_remote_open_cad_file() -> None:
    session = MagicMock()
    session.open_cad_file.return_value = {"geometries_count": 5, "tool_paths_count": 2}
    app = RemoteApplication(session)
    drw = app.open_cad_file(r"C:\parts\panel.dxf", "dxf")
    assert drw is not None
    assert isinstance(drw, _DrawingProxy)
    assert drw.geometries_count == 5
    assert drw.tool_paths_count == 2
    session.open_cad_file.assert_called_once_with(
        r"C:\parts\panel.dxf", "dxf", clear=False, cabinets=False
    )


def test_remote_open_cad_file_none() -> None:
    session = MagicMock()
    session.open_cad_file.return_value = None
    app = RemoteApplication(session)
    assert app.open_cad_file(r"C:\parts\panel.dxf", "dxf") is None


def test_remote_drawing_proxy_export() -> None:
    session = MagicMock()
    session.get_active_drawing.return_value = {"geometries_count": 1}
    session.export_drawing.return_value = {"success": True, "path": r"C:\parts\out.dxf"}
    app = RemoteApplication(session)
    drw = app.get_active_drawing()
    assert drw is not None
    result = drw.export(r"C:\parts\out.dxf", "dxf")
    assert result == {"success": True, "path": r"C:\parts\out.dxf"}
    session.export_drawing.assert_called_once_with(r"C:\parts\out.dxf", "dxf")
