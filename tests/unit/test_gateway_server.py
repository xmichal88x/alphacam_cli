from __future__ import annotations

import os
import pathlib
import sys
import threading
import time
import types
from typing import Any
from unittest import mock
from unittest.mock import MagicMock

import pytest

from alphacam_cli.gateway.server import COMError, GatewayServer


@pytest.fixture
def server_app(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    import alphacam_cli.gateway.server as server_module

    app = MagicMock()
    monkeypatch.setattr(server_module, "_app", app)
    return app


def _mock_nest_com(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    """Install fake win32com.client.gencache modules and return (app, nesting)."""
    gencache = MagicMock()
    app = MagicMock()
    nesting = MagicMock()
    gencache.EnsureDispatch.return_value = app
    app.Nesting = nesting

    client_mod = types.ModuleType("win32com.client")
    client_mod.gencache = gencache  # type: ignore[attr-defined]
    win32com = types.ModuleType("win32com")
    win32com.client = client_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client_mod)
    monkeypatch.setitem(sys.modules, "win32com.client.gencache", gencache)
    return app, nesting


def test_apply_style_handler(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.geometries_count = 3
    server_app.get_active_drawing.return_value = drw
    gw = GatewayServer()
    result = gw._handler_apply_style({"style": r"C:\ALPHACAM\LICOMDIR\Styles\Fronty\Edge_01.ary"})
    assert result == {"success": True, "tool_paths_count": drw.tool_paths_count}
    server_app.apply_mill_style.assert_called_once_with(
        r"C:\ALPHACAM\LICOMDIR\Styles\Fronty\Edge_01.ary"
    )
    drw.zoom_all.assert_called_once()
    for geo in drw.geometries.return_value:
        assert geo.selected is True


def test_apply_style_handler_no_geometries(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.geometries_count = 0
    server_app.get_active_drawing.return_value = drw
    gw = GatewayServer()
    with pytest.raises(COMError, match="No geometries to machine"):
        gw._handler_apply_style({"style": r"C:\ALPHACAM\LICOMDIR\Styles\Edge.ary"})
    server_app.apply_mill_style.assert_not_called()


def test_apply_style_handler_missing_style(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="style is required"):
        gw._handler_apply_style({})


def test_apply_style_handler_tool_full_path(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    drw = MagicMock()
    drw.geometries_count = 1
    server_app.get_active_drawing.return_value = drw
    tool_path = r"C:\ALPHACAM\LICOMDAT\MTools.Alp\Flat - 10mm.art"
    monkeypatch.setattr(os.path, "exists", lambda p: p == tool_path)
    gw = GatewayServer()
    result = gw._handler_apply_style(
        {"style": r"C:\ALPHACAM\LICOMDIR\Styles\Edge.ary", "tool": tool_path}
    )
    assert result["success"] is True
    server_app.select_tool.assert_called_once_with(tool_path)


def test_apply_style_handler_tool_by_name(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    drw = MagicMock()
    drw.geometries_count = 1
    server_app.get_active_drawing.return_value = drw
    files = [r"C:\ALPHACAM\LICOMDAT\MTools.Alp\Flat - 10mm.art"]
    server_app.find_tool_files.return_value = files
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    gw = GatewayServer()
    result = gw._handler_apply_style(
        {"style": r"C:\ALPHACAM\LICOMDIR\Styles\Edge.ary", "tool": "Flat - 10mm"}
    )
    assert result["success"] is True
    server_app.select_tool.assert_called_once_with(files[0])


def test_apply_style_handler_tool_partial_path(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    drw = MagicMock()
    drw.geometries_count = 1
    server_app.get_active_drawing.return_value = drw
    tool_path = r"C:\ALPHACAM\LICOMDAT\RTools.Alp\Reichenbacher\Ball 10mm 2F.art"
    server_app.find_tool_files.return_value = [tool_path]
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    gw = GatewayServer()
    result = gw._handler_apply_style(
        {"style": r"C:\ALPHACAM\LICOMDIR\Styles\Edge.ary", "tool": r"Reichenbacher\Ball 10mm 2F"}
    )
    assert result["success"] is True
    server_app.select_tool.assert_called_once_with(tool_path)


def test_select_tool_handler_by_name(server_app: MagicMock) -> None:
    tool_path = r"C:\ALPHACAM\LICOMDAT\RTools.Alp\Reichenbacher\Ball 10mm 2F.art"
    server_app.find_tool_files.return_value = [tool_path]
    gw = GatewayServer()
    gw._handler_select_tool({"name": "Ball 10mm 2F.art"})
    server_app.select_tool.assert_called_once_with(tool_path)


def test_select_tool_handler_full_path(server_app: MagicMock) -> None:
    tool_path = r"C:\ALPHACAM\LICOMDAT\RTools.Alp\Reichenbacher\Ball 10mm 2F.art"
    server_app.find_tool_files.return_value = [tool_path]
    gw = GatewayServer()
    gw._handler_select_tool({"name": tool_path})
    server_app.select_tool.assert_called_once_with(tool_path)


def test_select_tool_handler_partial_path(server_app: MagicMock) -> None:
    tool_path = r"C:\ALPHACAM\LICOMDAT\RTools.Alp\Reichenbacher\Ball 10mm 2F.art"
    server_app.find_tool_files.return_value = [tool_path]
    gw = GatewayServer()
    gw._handler_select_tool({"name": r"Reichenbacher\Ball 10mm 2F"})
    server_app.select_tool.assert_called_once_with(tool_path)


def test_select_tool_handler_duplicate_basenames(server_app: MagicMock) -> None:
    files = [
        r"C:\ALPHACAM\LICOMDAT\RTools.Alp\SubA\Drill - 10mm dia.art",
        r"C:\ALPHACAM\LICOMDAT\RTools.Alp\SubB\Drill - 10mm dia.art",
    ]
    server_app.find_tool_files.return_value = files
    gw = GatewayServer()
    with pytest.raises(COMError, match="Multiple tools matched"):
        gw._handler_select_tool({"name": "Drill - 10mm dia"})
    server_app.select_tool.assert_not_called()


def test_list_posts_handler(server_app: MagicMock) -> None:
    posts = [
        "C:/ALPHACAM/LICOMDAT/RPosts.Alp/fanuc.arp",
        "C:/ALPHACAM/LICOMDAT/RPosts.Alp/Alpha Reichenbacher.arp",
    ]
    server_app.find_post_files.return_value = posts
    server_app.licomdir_path = "C:/ALPHACAM/LICOMDIR"
    server_app.licomdat_path = "C:/ALPHACAM/LICOMDAT"
    gw = GatewayServer()
    result = gw._handler_list_posts({})
    assert result == [
        {"name": "Alpha Reichenbacher.arp", "path": posts[1]},
        {"name": "fanuc.arp", "path": posts[0]},
    ]
    server_app.find_post_files.assert_called_once_with("*.arp")


def test_list_styles_handler(server_app: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    files = [
        "C:/ALPHACAM/LICOMDIR/Styles/Fronty/Ball_06.ary",
        "C:/ALPHACAM/LICOMDIR/Styles/Edge.ary",
        "C:/ALPHACAM/LICOMDIR/Styles/Fronty_AutoStyl.ara",
    ]
    sizes = {
        files[0]: 30,
        files[1]: 10,
        files[2]: 20,
    }
    server_app.find_style_files.return_value = files
    server_app.licomdir_path = "C:/ALPHACAM/LICOMDIR"
    monkeypatch.setattr(os.path, "getsize", lambda p: sizes[p])
    gw = GatewayServer()
    result = gw._handler_list_styles({})
    assert result == {
        "styles": [
            {
                "name": "Ball_06.ary",
                "directory": "Styles/Fronty",
                "size": 30,
                "path": files[0],
            },
            {
                "name": "Edge.ary",
                "directory": "Styles",
                "size": 10,
                "path": files[1],
            },
            {
                "name": "Fronty_AutoStyl.ara",
                "directory": "Styles",
                "size": 20,
                "path": files[2],
            },
        ]
    }
    server_app.find_style_files.assert_called_once_with()


def test_list_styles_handler_missing_size(server_app: MagicMock) -> None:
    server_app.find_style_files.return_value = ["C:/ALPHACAM/LICOMDIR/Styles/Ghost.ary"]
    server_app.licomdir_path = "C:/ALPHACAM/LICOMDIR"
    gw = GatewayServer()
    result = gw._handler_list_styles({})
    assert result["styles"] == [
        {
            "name": "Ghost.ary",
            "directory": "Styles",
            "size": 0,
            "path": "C:/ALPHACAM/LICOMDIR/Styles/Ghost.ary",
        }
    ]


def test_select_post_handler_by_name(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    post_path = "C:/ALPHACAM/LICOMDAT/RPosts.Alp/fanuc.arp"
    server_app.find_post_files.return_value = [post_path]
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    gw = GatewayServer()
    result = gw._handler_select_post({"name": "fanuc"})
    assert result == {"success": True}
    server_app.select_post.assert_called_once_with(post_path)


def test_select_post_handler_not_found(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    server_app.find_post_files.return_value = []
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    gw = GatewayServer()
    with pytest.raises(COMError, match="No post matching 'missing'"):
        gw._handler_select_post({"name": "missing"})
    server_app.select_post.assert_not_called()


def test_select_post_handler_full_path(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    post_path = "C:/ALPHACAM/LICOMDAT/RPosts.Alp/fanuc.arp"
    monkeypatch.setattr(os.path, "exists", lambda p: p == post_path)
    gw = GatewayServer()
    result = gw._handler_select_post({"name": post_path})
    assert result == {"success": True}
    server_app.select_post.assert_called_once_with(post_path)


def test_drawing_parametric_handler(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.geometries_count = 2
    drw.tool_paths_count = 0
    server_app.create_temp_drawing.return_value = drw
    outer = MagicMock()
    inner = MagicMock()
    outer.tool_in_out = -1
    inner.tool_in_out = 1
    drw.create_panel.return_value = (outer, inner)
    gw = GatewayServer()
    result = gw._handler_drawing_parametric({"width": 800, "height": 400})
    assert result["success"] is True
    assert result["geometries_count"] == 2
    assert result["tool_paths_count"] == 0
    assert result["outer"] == {"tool_in_out": -1}
    assert result["inner"] == {"tool_in_out": 1}
    drw.create_panel.assert_called_once_with(800, 400, 50, 5)
    server_app.create_mill_data.assert_not_called()
    drw.zoom_all.assert_called_once()


def test_drawing_parametric_handler_ignores_machining_params(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.geometries_count = 2
    drw.tool_paths_count = 0
    server_app.create_temp_drawing.return_value = drw
    outer = MagicMock()
    inner = MagicMock()
    outer.tool_in_out = -1
    inner.tool_in_out = 1
    drw.create_panel.return_value = (outer, inner)
    gw = GatewayServer()
    result = gw._handler_drawing_parametric(
        {
            "width": 800,
            "height": 400,
            "depth": -19,
            "tool": "Flat - 20mm",
            "spindle": 18000,
            "feed": 4000,
            "down_feed": 1500,
        }
    )
    assert result["success"] is True
    assert result["tool_paths_count"] == 0
    server_app.select_tool.assert_not_called()
    server_app.create_mill_data.assert_not_called()
    drw.create_panel.assert_called_once_with(800, 400, 50, 5)


def test_drawing_parametric_handler_invalid_size(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="width and height must be positive"):
        gw._handler_drawing_parametric({"width": 0, "height": 400})


def test_output_nc_handler(server_app: MagicMock, tmp_path: pathlib.Path) -> None:
    drw = MagicMock()
    server_app.get_active_drawing.return_value = drw

    def _write_nc(path: str) -> None:
        pathlib.Path(path).write_bytes(b"G0 X0 Y0\n" * 100)

    drw.output_nc.side_effect = _write_nc
    nc_file = tmp_path / "nested" / "out.nc"
    gw = GatewayServer()
    result = gw._handler_output_nc({"path": str(nc_file)})
    assert nc_file.parent.exists()
    assert result == {"success": True, "size": nc_file.stat().st_size, "path": str(nc_file)}
    drw.output_nc.assert_called_once_with(str(nc_file))


def test_output_nc_handler_missing_file(server_app: MagicMock, tmp_path: pathlib.Path) -> None:
    drw = MagicMock()
    server_app.get_active_drawing.return_value = drw
    gw = GatewayServer()
    missing = str(tmp_path / "missing.nc")
    with pytest.raises(COMError, match="NC file not created"):
        gw._handler_output_nc({"path": missing})
    drw.output_nc.assert_called_once_with(missing)


def test_save_active_drawing_handler_creates_parent_dir(
    server_app: MagicMock, tmp_path: pathlib.Path
) -> None:
    drw = MagicMock()
    server_app.get_active_drawing.return_value = drw
    amd_file = tmp_path / "nested" / "file.amd"
    gw = GatewayServer()
    result = gw._handler_save_active_drawing({"path": str(amd_file)})
    assert result == {"success": True}
    assert amd_file.parent.exists()
    drw.save_as.assert_called_once_with(str(amd_file))


def test_open_cad_file_handler(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.geometries_count = 4
    drw.tool_paths_count = 1
    server_app.open_cad_file.return_value = drw
    gw = GatewayServer()
    result = gw._handler_open_cad_file({"path": r"C:\parts\panel.dxf", "fmt": "dxf"})
    assert result == {"geometries_count": 4, "tool_paths_count": 1}
    server_app.open_cad_file.assert_called_once_with(r"C:\parts\panel.dxf", "dxf", clear=False)
    server_app.set_dxf_cabinets.assert_not_called()


def test_open_cad_file_handler_cabinets(server_app: MagicMock) -> None:
    drw = MagicMock()
    server_app.open_cad_file.return_value = drw
    gw = GatewayServer()
    gw._handler_open_cad_file({"path": r"C:\parts\panel.dxf", "fmt": "dxf", "cabinets": True})
    server_app.set_dxf_cabinets.assert_called_once_with(True)


def test_open_cad_file_handler_missing_path(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="path is required"):
        gw._handler_open_cad_file({"fmt": "dxf"})


def test_open_cad_file_handler_missing_fmt(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="fmt is required"):
        gw._handler_open_cad_file({"path": r"C:\parts\panel.dxf"})


def test_open_cad_file_handler_none(server_app: MagicMock) -> None:
    server_app.open_cad_file.return_value = None
    gw = GatewayServer()
    with pytest.raises(COMError, match="Failed to open CAD file"):
        gw._handler_open_cad_file({"path": r"C:\parts\panel.dxf", "fmt": "dxf"})


def test_export_drawing_handler(server_app: MagicMock, tmp_path: pathlib.Path) -> None:
    drw = MagicMock()
    server_app.get_active_drawing.return_value = drw
    dxf_file = tmp_path / "nested" / "out.dxf"
    gw = GatewayServer()
    result = gw._handler_export_drawing({"path": str(dxf_file), "fmt": "dxf"})
    assert result == {"success": True, "path": str(dxf_file)}
    assert dxf_file.parent.exists()
    drw.export.assert_called_once_with(str(dxf_file), "dxf")


def test_export_drawing_handler_no_drawing(server_app: MagicMock) -> None:
    server_app.get_active_drawing.return_value = None
    gw = GatewayServer()
    with pytest.raises(COMError, match="No active drawing"):
        gw._handler_export_drawing({"path": r"C:\parts\out.dxf", "fmt": "dxf"})


def test_export_drawing_handler_missing_path(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="path is required"):
        gw._handler_export_drawing({"fmt": "dxf"})


def test_glob_files_handler(server_app: MagicMock, tmp_path: pathlib.Path) -> None:
    part_a = tmp_path / "a.amd"
    part_b = tmp_path / "b.amd"
    part_a.write_bytes(b"amd")
    part_b.write_bytes(b"amd")
    (tmp_path / "notes.txt").write_bytes(b"txt")
    gw = GatewayServer()
    result = gw._handler_glob_files({"directory": str(tmp_path), "pattern": "*.amd"})
    assert result == [str(part_a), str(part_b)]


def test_glob_files_handler_missing_dir(server_app: MagicMock) -> None:
    gw = GatewayServer()
    result = gw._handler_glob_files({"directory": str(pathlib.Path("C:/no/such/dir"))})
    assert result == []


def test_glob_files_handler_no_dir(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="directory is required"):
        gw._handler_glob_files({})


def test_run_nest_handler(server_app: MagicMock) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw
    nd = MagicMock(name="NestData")
    drw.create_nest_data.return_value = nd
    sheet_geo = MagicMock()
    drw.create_rectangle.return_value = sheet_geo

    gw = GatewayServer()
    result = gw._handler_run_nest(
        {
            "parts": [{"name": "part1.amd", "count": 2}, {"name": "part2.amd", "count": 1}],
            "output_dir": "",
            "sheet_width": 2440,
            "sheet_height": 1220,
        }
    )

    assert result == {"count": 3, "success": True}
    drw.create_nest_data.assert_called_once_with("nest.anl")
    drw.create_rectangle.assert_called_once_with(0, 0, 2440, 1220)
    nd.AddSheet.assert_called_once_with(sheet_geo.raw_dispatch, "MDF", 18, 1)
    nd.DoNest.assert_called_once()
    assert nd.AddPart.call_args_list == [
        mock.call("part1.amd", 2),
        mock.call("part2.amd", 1),
    ]


def test_run_nest_handler_no_add_part_returns_parts(server_app: MagicMock) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw
    nd = MagicMock(spec=["AddSheet", "DoNest"])
    drw.create_nest_data.return_value = nd

    gw = GatewayServer()
    result = gw._handler_run_nest(
        {
            "parts": [{"name": "part.amd", "count": 1}],
            "output_dir": "",
            "sheet_width": 2440,
            "sheet_height": 1220,
        }
    )

    assert result == {"count": 1, "success": True, "parts": [{"name": "part.amd", "count": 1}]}
    nd.AddSheet.assert_called_once()
    nd.DoNest.assert_called_once()


def test_run_nest_handler_sets_gaps(server_app: MagicMock) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw
    nd = MagicMock(name="NestData")
    drw.create_nest_data.return_value = nd
    sheet_geo = MagicMock()
    drw.create_rectangle.return_value = sheet_geo

    gw = GatewayServer()
    result = gw._handler_run_nest(
        {
            "parts": [{"name": "part.amd", "count": 1}],
            "output_dir": "",
            "sheet_width": 2440,
            "sheet_height": 1220,
            "gap": 2.5,
            "edge_gap": 0.5,
            "lead_gap": 1.0,
        }
    )

    assert result == {"count": 1, "success": True}
    assert nd.Gap == 2.5
    assert nd.EdgeGap == 0.5
    assert nd.LeadGap == 1.0
    nd.DoNest.assert_called_once()


def test_run_nest_handler_no_gaps_does_not_set(server_app: MagicMock) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw
    nd = MagicMock(name="NestData")
    drw.create_nest_data.return_value = nd
    sheet_geo = MagicMock()
    drw.create_rectangle.return_value = sheet_geo

    gw = GatewayServer()
    gw._handler_run_nest(
        {
            "parts": [{"name": "part.amd", "count": 1}],
            "output_dir": "",
            "sheet_width": 2440,
            "sheet_height": 1220,
        }
    )

    nd.DoNest.assert_called_once()
    nd.Gap.assert_not_called()


def test_run_nest_handler_set_gaps_failed(server_app: MagicMock) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw
    nd = MagicMock(name="NestData")
    drw.create_nest_data.return_value = nd
    sheet_geo = MagicMock()
    drw.create_rectangle.return_value = sheet_geo

    gw = GatewayServer()
    with pytest.raises(COMError, match=r"nest: set gaps failed: could not convert"):
        gw._handler_run_nest(
            {
                "parts": [{"name": "part.amd", "count": 1}],
                "gap": "not-a-number",
            }
        )
    nd.DoNest.assert_not_called()


def test_run_nest_handler_create_nest_data_failed(server_app: MagicMock) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw
    drw.create_nest_data.side_effect = RuntimeError("boom")

    gw = GatewayServer()
    with pytest.raises(COMError, match=r"nest: create_nest_data failed: boom"):
        gw._handler_run_nest({"parts": [{"name": "part.amd", "count": 1}]})


def test_run_nest_handler_add_sheet_failed(server_app: MagicMock) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw
    nd = MagicMock(name="NestData")
    drw.create_nest_data.return_value = nd
    nd.AddSheet.side_effect = RuntimeError("boom")

    gw = GatewayServer()
    with pytest.raises(COMError, match=r"nest: add_sheet failed: boom"):
        gw._handler_run_nest({"parts": [{"name": "part.amd", "count": 1}]})
    nd.DoNest.assert_not_called()


def test_run_nest_handler_do_nest_failed(server_app: MagicMock) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw
    nd = MagicMock(name="NestData")
    drw.create_nest_data.return_value = nd
    nd.DoNest.side_effect = RuntimeError("boom")

    gw = GatewayServer()
    with pytest.raises(COMError, match=r"nest: do_nest failed: boom"):
        gw._handler_run_nest({"parts": [{"name": "part.amd", "count": 1}]})


def test_run_nest_handler_advanced(server_app: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw
    sheet_geo = MagicMock()
    drw.create_rectangle.return_value = sheet_geo

    _, nesting = _mock_nest_com(monkeypatch)
    nl = MagicMock(name="NestList")
    part1_nest = MagicMock(name="NestPart1", Required=-1)
    part2_nest = MagicMock(name="NestPart2", Required=-1)
    nl.AddFile.side_effect = [part1_nest, part2_nest]
    sl = MagicMock(name="SheetList")
    nest_result = MagicMock(name="NestResult")
    nest_result.Count = 1
    nesting.NewNestList.return_value = nl
    nesting.NewSheetList.return_value = sl
    nesting.Nest.return_value = nest_result

    gw = GatewayServer()
    result = gw._handler_run_nest(
        {
            "parts": [{"name": "part1.amd", "count": 2}, {"name": "part2.amd", "count": 1}],
            "output_dir": "",
            "sheet_width": 2440,
            "sheet_height": 1220,
            "advanced": True,
            "part_gap": 5.0,
            "optimise_level": 1,
            "use_subroutines": False,
            "prevent_aperture_nest": True,
        }
    )

    assert result == {
        "success": True,
        "count": 1,
        "parts": [{"name": "part1.amd", "count": 2}, {"name": "part2.amd", "count": 1}],
    }
    assert nesting.SuppressDialogs is True
    nesting.NewNestList.assert_called_once_with("nest_full.anl")
    assert nl.AddFile.call_args_list == [mock.call("part1.amd"), mock.call("part2.amd")]
    assert part1_nest.Required == 2
    assert part2_nest.Required == 1
    assert nl.PartGap == 5.0
    assert nl.OptimiseLevel == 1
    assert nl.UseSubroutines is False
    assert nl.PreventApertureNest is True
    nesting.NewSheetList.assert_called_once()
    sl.Add.assert_called_once_with(sheet_geo.raw_dispatch)
    assert sl.Add.return_value.Thickness == 18.0
    assert sl.Add.return_value.Required == 1
    nesting.Nest.assert_called_once_with(nl, sl)
    nesting.DeleteAllNestLists.assert_called_once()


def test_run_nest_handler_advanced_gap_alias(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw
    drw.create_rectangle.return_value = MagicMock()

    _, nesting = _mock_nest_com(monkeypatch)
    nl = MagicMock(name="NestList")
    nesting.NewNestList.return_value = nl
    nesting.NewSheetList.return_value = MagicMock(name="SheetList")
    nesting.Nest.return_value = MagicMock(Count=0)

    gw = GatewayServer()
    result = gw._handler_run_nest(
        {
            "parts": [{"name": "part.amd", "count": 1}],
            "advanced": True,
            "gap": 3.5,
        }
    )

    assert result == {
        "success": True,
        "count": 0,
        "parts": [{"name": "part.amd", "count": 1}],
    }
    assert nl.PartGap == 3.5


def test_run_nest_handler_advanced_sheet_from_library(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw

    _, nesting = _mock_nest_com(monkeypatch)
    nl = MagicMock(name="NestList")
    sl = MagicMock(name="SheetList")
    sheet = MagicMock(name="Sheet")
    sheet.Thickness.Thickness = 22.0
    nesting.NewNestList.return_value = nl
    nesting.NewSheetList.return_value = sl
    nesting.SheetDatabase.FindSheet.return_value = sheet
    nesting.Nest.return_value = MagicMock(Count=2)

    gw = GatewayServer()
    result = gw._handler_run_nest(
        {
            "parts": [{"name": "part.amd", "count": 1}],
            "advanced": True,
            "sheet_name": "MDF_18",
        }
    )

    assert result == {"success": True, "count": 2, "parts": [{"name": "part.amd", "count": 1}]}
    nesting.SheetDatabase.FindSheet.assert_called_once_with("MDF_18")
    sheet.InsertInActiveDrawingAtPoint.assert_called_once_with(0.0, 0.0)
    sl.Add.assert_called_once_with(sheet.InsertInActiveDrawingAtPoint.return_value.Item(1))
    assert sl.Add.return_value.Thickness == 22.0
    drw.create_rectangle.assert_not_called()


def test_run_nest_handler_advanced_nest_failed_cleans_up(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw
    drw.create_rectangle.return_value = MagicMock()

    _, nesting = _mock_nest_com(monkeypatch)
    nesting.NewNestList.return_value = MagicMock(name="NestList")
    nesting.NewSheetList.return_value = MagicMock(name="SheetList")
    nesting.Nest.side_effect = RuntimeError("boom")

    gw = GatewayServer()
    with pytest.raises(COMError, match=r"nest\[advanced\]: nest failed: boom"):
        gw._handler_run_nest(
            {
                "parts": [{"name": "part.amd", "count": 1}],
                "advanced": True,
            }
        )
    nesting.DeleteAllNestLists.assert_called_once()


def test_run_nest_handler_advanced_add_file_failed(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw

    _, nesting = _mock_nest_com(monkeypatch)
    nl = MagicMock(name="NestList")
    nl.AddFile.side_effect = RuntimeError("boom")
    nesting.NewNestList.return_value = nl

    gw = GatewayServer()
    with pytest.raises(COMError, match=r"nest\[advanced\]: add_file failed: boom"):
        gw._handler_run_nest(
            {
                "parts": [{"name": "part.amd", "count": 1}],
                "advanced": True,
            }
        )
    nesting.DeleteAllNestLists.assert_not_called()


def test_run_nest_handler_save_ard(server_app: MagicMock, tmp_path: pathlib.Path) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw
    nd = MagicMock(name="NestData")
    drw.create_nest_data.return_value = nd
    drw.create_rectangle.return_value = MagicMock()
    server_app.nest_inspect.return_value = {"success": True, "sheets": [], "total_parts": 0}

    save_path = tmp_path / "nested" / "x.ard"
    gw = GatewayServer()
    result = gw._handler_run_nest(
        {
            "parts": [{"name": "part.amd", "count": 1}],
            "output_dir": "",
            "sheet_width": 2440,
            "sheet_height": 1220,
            "save_ard": str(save_path),
        }
    )

    assert save_path.parent.exists()
    drw.save_as.assert_called_once_with(str(save_path))
    assert result["save_ard"] == str(save_path)
    assert result["nest"] == {"success": True, "sheets": [], "total_parts": 0}
    assert result["success"] is True


def test_run_nest_handler_nest_results(server_app: MagicMock) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw
    nd = MagicMock(name="NestData")
    drw.create_nest_data.return_value = nd
    drw.create_rectangle.return_value = MagicMock()
    inspected = {"success": True, "sheets": [], "total_parts": 0}
    server_app.nest_inspect.return_value = inspected

    gw = GatewayServer()
    result = gw._handler_run_nest(
        {
            "parts": [{"name": "part.amd", "count": 1}],
            "output_dir": "",
            "sheet_width": 2440,
            "sheet_height": 1220,
        }
    )

    assert result["nest"] == inspected
    server_app.nest_inspect.assert_called_once()
    assert result["success"] is True


def test_run_nest_handler_nest_results_fallback(server_app: MagicMock) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw
    nd = MagicMock(name="NestData")
    drw.create_nest_data.return_value = nd
    drw.create_rectangle.return_value = MagicMock()
    server_app.nest_inspect.side_effect = Exception("boom")

    gw = GatewayServer()
    result = gw._handler_run_nest(
        {
            "parts": [{"name": "part.amd", "count": 1}],
            "output_dir": "",
            "sheet_width": 2440,
            "sheet_height": 1220,
        }
    )

    assert result["success"] is True
    assert result["nest"] == {"success": False, "error": "boom"}


def test_run_nest_handler_advanced_save_ard(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    drw = MagicMock()
    server_app.create_temp_drawing.return_value = drw
    drw.create_rectangle.return_value = MagicMock()
    server_app.nest_inspect.return_value = {"success": True, "sheets": [], "total_parts": 0}

    _, nesting = _mock_nest_com(monkeypatch)
    nl = MagicMock(name="NestList")
    sl = MagicMock(name="SheetList")
    nesting.NewNestList.return_value = nl
    nesting.NewSheetList.return_value = sl
    nesting.Nest.return_value = MagicMock(Count=1)

    save_path = tmp_path / "nested" / "x.ard"
    gw = GatewayServer()
    result = gw._handler_run_nest(
        {
            "parts": [{"name": "part.amd", "count": 1}],
            "advanced": True,
            "save_ard": str(save_path),
        }
    )

    assert save_path.parent.exists()
    drw.save_as.assert_called_once_with(str(save_path))
    assert result["save_ard"] == str(save_path)
    assert result["nest"] == {"success": True, "sheets": [], "total_parts": 0}
    assert result["success"] is True
    assert result["count"] == 1


def test_mill_saw_handler(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.geometries_count = 3
    drw.tool_paths_count = 5
    server_app.get_active_drawing.return_value = drw
    gw = GatewayServer()
    result = gw._handler_mill_saw(
        {
            "depth": -10,
            "spindle": 12000,
            "feed": 3000,
            "down_feed": 2000,
            "saw_angle": 15,
            "internal_corners": 1,
            "external_corners": 2,
            "head_position": 1,
        }
    )
    assert result == {"tool_paths_count": 5}
    drw.select_all_geometries.assert_called_once()
    md = server_app.create_mill_data.return_value
    assert md.final_depth == -10
    assert md.saw_angle == 15
    assert md.saw_internal_corners == 1
    assert md.saw_external_corners == 2
    assert md.saw_head_position == 1
    md.saw.assert_called_once_with()
    drw.zoom_all.assert_called_once()


def test_mill_saw_handler_no_drawing(server_app: MagicMock) -> None:
    server_app.get_active_drawing.return_value = None
    gw = GatewayServer()
    with pytest.raises(COMError, match="No active drawing"):
        gw._handler_mill_saw({})


def test_mill_saw_handler_no_geometries(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.geometries_count = 0
    server_app.get_active_drawing.return_value = drw
    gw = GatewayServer()
    with pytest.raises(COMError, match="No geometries to machine"):
        gw._handler_mill_saw({})


def test_mill_engrave_handler(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.geometries_count = 2
    drw.tool_paths_count = 4
    server_app.get_active_drawing.return_value = drw
    gw = GatewayServer()
    result = gw._handler_mill_engrave(
        {
            "depth": -0.5,
            "engrave_type": 1,
            "step_length": 0.05,
            "chord_error": 0.01,
        }
    )
    assert result == {"tool_paths_count": 4}
    md = server_app.create_mill_data.return_value
    assert md.final_depth == -0.5
    assert md.engrave_type == 1
    assert md.step_length == 0.05
    assert md.chord_error == 0.01
    md.engrave.assert_called_once_with()
    drw.zoom_all.assert_called_once()


def test_mill_engrave_handler_no_drawing(server_app: MagicMock) -> None:
    server_app.get_active_drawing.return_value = None
    gw = GatewayServer()
    with pytest.raises(COMError, match="No active drawing"):
        gw._handler_mill_engrave({})


def test_mill_engrave_handler_no_geometries(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.geometries_count = 0
    server_app.get_active_drawing.return_value = drw
    gw = GatewayServer()
    with pytest.raises(COMError, match="No geometries to machine"):
        gw._handler_mill_engrave({})


def test_reports_create_handler(server_app: MagicMock) -> None:
    server_app.reports_create.return_value = {
        "success": True,
        "job": "ok",
        "active_drawing": True,
        "settings_file": "raport_test.acreps",
    }
    gw = GatewayServer()
    result = gw._handler_reports_create({})
    assert result == {
        "success": True,
        "job": "ok",
        "active_drawing": True,
        "settings_file": "raport_test.acreps",
    }
    server_app.reports_create.assert_called_once_with(job_name=None)


def test_reports_create_handler_job_name(server_app: MagicMock) -> None:
    server_app.reports_create.return_value = {
        "success": True,
        "job": "ok",
        "active_drawing": True,
        "settings_file": "raport_test.acreps",
    }
    gw = GatewayServer()
    result = gw._handler_reports_create({"job_name": "  Fronty  "})
    assert result["success"] is True
    server_app.reports_create.assert_called_once_with(job_name="Fronty")


def test_reports_create_handler_failure(server_app: MagicMock) -> None:
    server_app.reports_create.side_effect = RuntimeError("boom")
    gw = GatewayServer()
    with pytest.raises(COMError, match="reports: create failed: boom"):
        gw._handler_reports_create({})
    server_app.reports_create.assert_called_once_with(job_name=None)


def test_nc_configs_handler(server_app: MagicMock) -> None:
    server_app.nc_configs.return_value = {"count": 2, "configs": ["Alpha", "Beta"]}
    gw = GatewayServer()
    result = gw._handler_nc_configs({})
    assert result == {"count": 2, "configs": ["Alpha", "Beta"]}
    server_app.nc_configs.assert_called_once_with()


def test_auto_style_apply_handler(server_app: MagicMock) -> None:
    server_app.auto_style_apply.return_value = {"success": True, "file": r"C:\styles\auto.style"}
    gw = GatewayServer()
    result = gw._handler_auto_style_apply({"file": r"C:\styles\auto.style"})
    assert result == {"success": True, "file": r"C:\styles\auto.style"}
    server_app.auto_style_apply.assert_called_once_with(r"C:\styles\auto.style")


def test_auto_style_apply_handler_missing_file(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="file is required"):
        gw._handler_auto_style_apply({})
    server_app.auto_style_apply.assert_not_called()


def test_auto_style_apply_handler_invalid_file(server_app: MagicMock) -> None:
    server_app.auto_style_apply.side_effect = RuntimeError(
        "failed to apply auto-style 'x': invalid or unrecognized "
        "AutoStyles file (check format .ara)"
    )
    gw = GatewayServer()
    with pytest.raises(COMError, match="invalid or unrecognized AutoStyles file"):
        gw._handler_auto_style_apply({"file": "x"})


def test_create_layer_handler(server_app: MagicMock) -> None:
    drw = MagicMock()
    server_app.get_active_drawing.return_value = drw
    gw = GatewayServer()
    result = gw._handler_create_layer({"name": "KONTUR"})
    assert result == {"success": True, "layer": "KONTUR"}
    drw.create_layer.assert_called_once_with("KONTUR")


def test_create_layer_handler_missing_name(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="name is required"):
        gw._handler_create_layer({})


def test_create_layer_handler_no_drawing(server_app: MagicMock) -> None:
    server_app.get_active_drawing.return_value = None
    gw = GatewayServer()
    with pytest.raises(COMError, match="No active drawing"):
        gw._handler_create_layer({"name": "KONTUR"})


def test_create_layer_handler_failure(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.create_layer.side_effect = RuntimeError("boom")
    server_app.get_active_drawing.return_value = drw
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"create_layer failed: boom"):
        gw._handler_create_layer({"name": "KONTUR"})


def test_drawing_query_handler(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.run_query.return_value = 7
    server_app.get_active_drawing.return_value = drw
    gw = GatewayServer()
    result = gw._handler_drawing_query({"file": r"C:\ALPHACAM\LICOMDIR\Queries\test.agq"})
    assert result == {"success": True, "count": 7}
    drw.run_query.assert_called_once_with(r"C:\ALPHACAM\LICOMDIR\Queries\test.agq")


def test_drawing_query_handler_missing_file(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="file is required"):
        gw._handler_drawing_query({})
    server_app.get_active_drawing.assert_not_called()


def test_drawing_query_handler_no_drawing(server_app: MagicMock) -> None:
    server_app.get_active_drawing.return_value = None
    gw = GatewayServer()
    with pytest.raises(COMError, match="No active drawing"):
        gw._handler_drawing_query({"file": r"C:\ALPHACAM\LICOMDIR\Queries\test.agq"})


def test_drawing_query_handler_failure(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.run_query.side_effect = RuntimeError("boom")
    server_app.get_active_drawing.return_value = drw
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"drawing query failed: boom"):
        gw._handler_drawing_query({"file": r"C:\ALPHACAM\LICOMDIR\Queries\test.agq"})


def test_create_cdm_job_handler(server_app: MagicMock) -> None:
    server_app.create_cdm_job.return_value = {
        "success": True,
        "job_name": "JOB-001",
        "config": "Fronty",
        "material": "MDF_18",
        "warnings": [],
    }
    gw = GatewayServer()
    result = gw._handler_create_cdm_job(
        {
            "job_name": "JOB-001",
            "config": "Fronty",
            "material": "MDF_18",
            "customer": "Klient A",
            "po": "PO-1",
            "due_date": "2026-08-10",
            "description": "opis",
        }
    )
    assert result == {
        "success": True,
        "job_name": "JOB-001",
        "config": "Fronty",
        "material": "MDF_18",
        "warnings": [],
    }
    server_app.create_cdm_job.assert_called_once_with(
        job_name="JOB-001",
        config="Fronty",
        material="MDF_18",
        customer="Klient A",
        po="PO-1",
        due_date="2026-08-10",
        description="opis",
    )


def test_create_cdm_job_handler_defaults(server_app: MagicMock) -> None:
    server_app.create_cdm_job.return_value = {"success": True}
    gw = GatewayServer()
    result = gw._handler_create_cdm_job({"job_name": "JOB-001"})
    assert result == {"success": True}
    server_app.create_cdm_job.assert_called_once_with(
        job_name="JOB-001",
        config=None,
        material=None,
        customer=None,
        po=None,
        due_date=None,
        description=None,
    )


def test_create_cdm_job_handler_blank_params(server_app: MagicMock) -> None:
    server_app.create_cdm_job.return_value = {"success": True}
    gw = GatewayServer()
    gw._handler_create_cdm_job(
        {
            "job_name": " JOB-001 ",
            "config": "  ",
            "material": "",
            "customer": " ",
            "po": "",
            "due_date": " ",
            "description": "",
        }
    )
    server_app.create_cdm_job.assert_called_once_with(
        job_name="JOB-001",
        config=None,
        material=None,
        customer=None,
        po=None,
        due_date=None,
        description=None,
    )


def test_create_cdm_job_handler_missing_job_name(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: job_name is required"):
        gw._handler_create_cdm_job({})
    server_app.create_cdm_job.assert_not_called()


def test_create_cdm_job_handler_forbidden_name(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(
        COMError, match=r"invalid job name: 'Zadanie/1' \(forbidden characters: /\)"
    ):
        gw._handler_create_cdm_job({"job_name": "Zadanie/1"})
    server_app.create_cdm_job.assert_not_called()


def test_create_cdm_job_handler_invalid_due_date(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: invalid due date"):
        gw._handler_create_cdm_job({"job_name": "JOB-001", "due_date": "2026-13-40"})
    server_app.create_cdm_job.assert_not_called()


def test_create_cdm_job_handler_com_failure(server_app: MagicMock) -> None:
    server_app.create_cdm_job.side_effect = RuntimeError("cdm: job already exists: JOB-001")
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"^cdm: job already exists: JOB-001$"):
        gw._handler_create_cdm_job({"job_name": "JOB-001", "config": "Fronty"})


def test_cdm_types_handler_delegates(server_app: MagicMock) -> None:
    payload = {
        "types": [{"id": 1, "name": "Typ Frontu 1"}, {"id": 2, "name": "L_B_10mm"}],
        "source": "vdb5+com",
    }
    server_app.cdm_types.return_value = payload
    gw = GatewayServer()
    assert gw._handler_cdm_types({}) == payload
    server_app.cdm_types.assert_called_once_with()


def test_cdm_types_handler_empty(server_app: MagicMock) -> None:
    server_app.cdm_types.return_value = {"types": [], "note": "no CDM door types found"}
    gw = GatewayServer()
    assert gw._handler_cdm_types({}) == {"types": [], "note": "no CDM door types found"}


def test_cdm_types_handler_failure(server_app: MagicMock) -> None:
    server_app.cdm_types.side_effect = RuntimeError("cdm: read door types failed: boom")
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: read door types failed: boom"):
        gw._handler_cdm_types({})


def test_cdm_jobs_handler_delegates(server_app: MagicMock) -> None:
    payload = {"jobs": [{"id": 1, "name": "JOB-001"}, {"id": 2, "name": "JOB-002"}]}
    server_app.cdm_jobs.return_value = payload
    gw = GatewayServer()
    assert gw._handler_cdm_jobs({}) == payload
    server_app.cdm_jobs.assert_called_once_with()


def test_cdm_jobs_handler_empty(server_app: MagicMock) -> None:
    server_app.cdm_jobs.return_value = {"jobs": []}
    gw = GatewayServer()
    assert gw._handler_cdm_jobs({}) == {"jobs": []}


def test_cdm_jobs_handler_failure(server_app: MagicMock) -> None:
    server_app.cdm_jobs.side_effect = RuntimeError("cdm: list jobs failed: boom")
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: list jobs failed: boom"):
        gw._handler_cdm_jobs({})


def test_cdm_import_csv_handler_missing_csv(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: csv path is required"):
        gw._handler_cdm_import_csv({})
    server_app.import_cdm_csv.assert_not_called()


def test_cdm_import_csv_handler_delegates(server_app: MagicMock, tmp_path: pathlib.Path) -> None:
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0\n", encoding="utf-8")
    server_app.import_cdm_csv.return_value = {
        "success": True,
        "job_name": "order",
        "items": 1,
        "material": None,
        "errors": ["job order: no material set (required for processing)"],
        "import_setting": "Fronty CSV",
    }
    gw = GatewayServer()
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result == server_app.import_cdm_csv.return_value
    server_app.import_cdm_csv.assert_called_once_with(
        csv=str(csv_file),
        job=None,
        name=None,
        config=None,
        separator=None,
        has_header=False,
        material=None,
        import_setting=None,
        preview=False,
    )


def test_cdm_import_csv_handler_full_params_delegation(
    server_app: MagicMock, tmp_path: pathlib.Path
) -> None:
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    server_app.import_cdm_csv.return_value = {
        "success": True,
        "job_name": "Zadanie-7",
        "items": 1,
        "material": "MDF_18",
        "errors": [],
        "import_setting": "Fronty CSV",
    }
    gw = GatewayServer()
    result = gw._handler_cdm_import_csv(
        {
            "csv": str(csv_file),
            "job": "X",
            "config": "Fronty",
            "separator": ";",
            "has_header": True,
            "material": "MDF_18",
            "import_setting": 3,
        }
    )
    assert result == server_app.import_cdm_csv.return_value
    server_app.import_cdm_csv.assert_called_once_with(
        csv=str(csv_file),
        job="X",
        name=None,
        config="Fronty",
        separator=";",
        has_header=True,
        material="MDF_18",
        import_setting=3,
        preview=False,
    )


def test_cdm_import_csv_handler_preview_delegates(
    server_app: MagicMock, tmp_path: pathlib.Path
) -> None:
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(_MAPPED_CSV_ROW + "\n", encoding="utf-8")
    server_app.import_cdm_csv.return_value = {"success": True, "items": 1, "job": "X"}
    gw = GatewayServer()
    result = gw._handler_cdm_import_csv(
        {"csv": str(csv_file), "job": "X", "preview": True, "import_setting": "Fronty CSV"}
    )
    assert result == server_app.import_cdm_csv.return_value
    server_app.import_cdm_csv.assert_called_once_with(
        csv=str(csv_file),
        job="X",
        name=None,
        config=None,
        separator=None,
        has_header=False,
        material=None,
        import_setting="Fronty CSV",
        preview=True,
    )


def test_cdm_import_csv_handler_whitespace_params_normalized(
    server_app: MagicMock, tmp_path: pathlib.Path
) -> None:
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    server_app.import_cdm_csv.return_value = {"success": True, "items": 1}
    gw = GatewayServer()
    result = gw._handler_cdm_import_csv(
        {"csv": str(csv_file), "job": "   ", "name": "X", "separator": "", "config": ""}
    )
    assert result["success"] is True
    server_app.import_cdm_csv.assert_called_once_with(
        csv=str(csv_file),
        job=None,
        name="X",
        config=None,
        separator=None,
        has_header=False,
        material=None,
        import_setting=None,
        preview=False,
    )


def test_cdm_import_csv_handler_name_and_job_conflict(
    server_app: MagicMock, tmp_path: pathlib.Path
) -> None:
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    gw = GatewayServer()
    with pytest.raises(COMError, match="mutually exclusive"):
        gw._handler_cdm_import_csv({"csv": str(csv_file), "job": "X", "name": "Y"})
    server_app.import_cdm_csv.assert_not_called()


def test_cdm_import_csv_handler_forbidden_name(
    server_app: MagicMock, tmp_path: pathlib.Path
) -> None:
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"invalid job name: 'A/B' \(forbidden characters: /\)"):
        gw._handler_cdm_import_csv({"csv": str(csv_file), "name": "A/B"})
    server_app.import_cdm_csv.assert_not_called()


def test_cdm_import_csv_handler_forbidden_job(
    server_app: MagicMock, tmp_path: pathlib.Path
) -> None:
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"invalid job name: .*forbidden characters"):
        gw._handler_cdm_import_csv({"csv": str(csv_file), "job": "A\\B"})
    server_app.import_cdm_csv.assert_not_called()


def test_cdm_import_csv_handler_file_not_found(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: csv file not found"):
        gw._handler_cdm_import_csv({"csv": r"C:\temp\nonexistent.csv"})
    server_app.import_cdm_csv.assert_not_called()


def test_cdm_import_csv_handler_import_setting_type_validated(
    server_app: MagicMock, tmp_path: pathlib.Path
) -> None:
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    gw = GatewayServer()
    with pytest.raises(COMError, match="import_setting must be an int or str"):
        gw._handler_cdm_import_csv({"csv": str(csv_file), "import_setting": 1.5})
    server_app.import_cdm_csv.assert_not_called()


def test_cdm_import_csv_handler_error_wrapped(
    server_app: MagicMock, tmp_path: pathlib.Path
) -> None:
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    server_app.import_cdm_csv.side_effect = RuntimeError("cdm: material not found: MDF_18")
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: material not found: MDF_18"):
        gw._handler_cdm_import_csv({"csv": str(csv_file), "material": "MDF_18"})


def test_cdm_import_csv_handler_job_exists_wrapped(
    server_app: MagicMock, tmp_path: pathlib.Path
) -> None:
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    server_app.import_cdm_csv.side_effect = RuntimeError(
        "cdm: job already exists: order (use --job to import into the existing job)"
    )
    gw = GatewayServer()
    with pytest.raises(
        COMError,
        match=r"cdm: job already exists: order \(use --job to import into the existing job\)",
    ):
        gw._handler_cdm_import_csv({"csv": str(csv_file)})


def test_cdm_import_preview_handler_delegates(
    server_app: MagicMock, tmp_path: pathlib.Path
) -> None:
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(_MAPPED_CSV_ROW + "\n", encoding="utf-8")
    server_app.import_cdm_preview.return_value = {
        "success": True,
        "items": 1,
        "job_name": "Zadanie-7",
        "config": "Fronty",
        "material": "MDF_18",
        "field_map": [],
        "rows": [],
        "errors": [],
        "job": None,
    }
    gw = GatewayServer()
    result = gw._handler_cdm_import_preview(
        {"csv": str(csv_file), "import_setting": "Fronty CSV", "separator": ","}
    )
    assert result == server_app.import_cdm_preview.return_value
    server_app.import_cdm_preview.assert_called_once_with(
        csv=str(csv_file),
        import_setting="Fronty CSV",
        separator=",",
        has_header=False,
        job=None,
        name=None,
        config=None,
        material=None,
    )


def test_cdm_import_preview_handler_missing_csv(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: csv path is required"):
        gw._handler_cdm_import_preview({})
    server_app.import_cdm_preview.assert_not_called()


def test_cdm_import_preview_handler_name_and_job_conflict(
    server_app: MagicMock, tmp_path: pathlib.Path
) -> None:
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    gw = GatewayServer()
    with pytest.raises(COMError, match="mutually exclusive"):
        gw._handler_cdm_import_preview({"csv": str(csv_file), "job": "X", "name": "Y"})
    server_app.import_cdm_preview.assert_not_called()


def test_cdm_import_preview_handler_forbidden_job_name(
    server_app: MagicMock, tmp_path: pathlib.Path
) -> None:
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"invalid job name: .*forbidden characters"):
        gw._handler_cdm_import_preview({"csv": str(csv_file), "job": "A/B"})
    server_app.import_cdm_preview.assert_not_called()


def test_cdm_import_preview_handler_forbidden_name_param(
    server_app: MagicMock, tmp_path: pathlib.Path
) -> None:
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"invalid job name: .*forbidden characters"):
        gw._handler_cdm_import_preview({"csv": str(csv_file), "name": "A`B"})
    server_app.import_cdm_preview.assert_not_called()


def test_cdm_import_preview_handler_file_not_found(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: csv file not found"):
        gw._handler_cdm_import_preview({"csv": r"C:\temp\nonexistent.csv"})
    server_app.import_cdm_preview.assert_not_called()


def test_cdm_import_preview_handler_error_wrapped(
    server_app: MagicMock, tmp_path: pathlib.Path
) -> None:
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    server_app.import_cdm_preview.side_effect = RuntimeError("cdm: import csv failed: boom")
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: import csv failed: boom"):
        gw._handler_cdm_import_preview({"csv": str(csv_file)})


_MAPPED_CSV_ROW = "P003,1,500,500,1;2;3,MDF_18,Zadanie-7,Fronty,Klient A,CF1,CF2,CF3"


def _fake_import_setting() -> dict[str, Any]:
    return {
        "id": 3,
        "name": "Fronty CSV",
        "delimiter_char": ",",
        "sub_delimiter_char": ";",
        "create_job": True,
        "selected": False,
        "ignore_header": False,
        "is_cdm_import": True,
        "fields": [
            {"column_number": 1, "parameter_type": 256},
            {"column_number": 2, "parameter_type": 259},
            {"column_number": 3, "parameter_type": 257},
            {"column_number": 4, "parameter_type": 258},
            {"column_number": 5, "parameter_type": 264},
            {"column_number": 6, "parameter_type": 524},
            {"column_number": 7, "parameter_type": 512},
            {"column_number": 8, "parameter_type": 513},
            {"column_number": 9, "parameter_type": 261},
            {"column_number": 10, "parameter_type": 266},
            {"column_number": 11, "parameter_type": 267},
            {"column_number": 12, "parameter_type": 275},
        ],
    }


def test_cdm_import_settings_handler(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.import_settings", lambda: [_fake_import_setting()]
    )
    gw = GatewayServer()
    result = gw._handler_cdm_import_settings({})
    settings = result["settings"]
    assert len(settings) == 1
    setting = settings[0]
    assert setting["id"] == 3
    assert setting["name"] == "Fronty CSV"
    assert setting["delimiter_char"] == ","
    assert setting["create_job"] is True
    assert setting["fields_count"] == 12
    assert setting["fields"] == (
        "1→door_type, 2→door_quantity, 3→door_width, 4→door_height, "
        "5→door_design_dimensions, 6→job_material_id, 7→job_name, "
        "8→job_config_id, 9→door_customer_name, 10→door_custom_field_1, "
        "11→door_custom_field_2, 12→door_custom_field_3"
    )


def test_cdm_delete_job_handler(server_app: MagicMock) -> None:
    server_app.delete_cdm_job.return_value = {"success": True, "job_name": "JOB-001"}
    gw = GatewayServer()
    result = gw._handler_cdm_delete_job({"job_name": "JOB-001"})
    assert result == {"success": True, "job_name": "JOB-001"}
    server_app.delete_cdm_job.assert_called_once_with("JOB-001")


def test_cdm_delete_job_handler_missing_name(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: job_name is required"):
        gw._handler_cdm_delete_job({})
    server_app.delete_cdm_job.assert_not_called()


def test_cdm_delete_job_handler_not_found(server_app: MagicMock) -> None:
    server_app.delete_cdm_job.side_effect = RuntimeError("cdm: job not found: NOPE")
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: job not found: NOPE"):
        gw._handler_cdm_delete_job({"job_name": "NOPE"})
    server_app.delete_cdm_job.assert_called_once_with("NOPE")


def test_cdm_delete_job_handler_failed(server_app: MagicMock) -> None:
    server_app.delete_cdm_job.side_effect = RuntimeError("cdm: delete job failed: locked")
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: delete job failed: locked"):
        gw._handler_cdm_delete_job({"job_name": "JOB-001"})
    server_app.delete_cdm_job.assert_called_once_with("JOB-001")


def test_cdm_delete_job_handler_no_delete_method(server_app: MagicMock) -> None:
    server_app.delete_cdm_job.side_effect = RuntimeError("cdm: DeleteFromDB unavailable on job")
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: DeleteFromDB unavailable on job"):
        gw._handler_cdm_delete_job({"job_name": "JOB-001"})
    server_app.delete_cdm_job.assert_called_once_with("JOB-001")


def test_cdm_delete_job_handler_forbidden_name(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(
        COMError, match=r"invalid job name: 'Zadanie/1' \(forbidden characters: /\)"
    ):
        gw._handler_cdm_delete_job({"job_name": "Zadanie/1"})
    server_app.delete_cdm_job.assert_not_called()


def test_manifest_list_handler(server_app: MagicMock) -> None:
    server_app.manifest_list.return_value = {
        "success": True,
        "directory": r"C:\Reports\Data",
        "manifests": [
            {
                "path": r"C:\Reports\Data\Fronty - MDF_18.acrepd",
                "job_name": "Fronty",
                "material": "MDF_18",
                "size": 1000,
                "mtime": 1700000000.0,
            }
        ],
    }
    gw = GatewayServer()
    result = gw._handler_manifest_list({"data_dir": r"C:\Reports\Data"})
    assert result == server_app.manifest_list.return_value
    server_app.manifest_list.assert_called_once_with(r"C:\Reports\Data")


def test_manifest_list_handler_no_params(server_app: MagicMock) -> None:
    server_app.manifest_list.return_value = {"success": True, "manifests": []}
    gw = GatewayServer()
    result = gw._handler_manifest_list({})
    assert result == {"success": True, "manifests": []}
    server_app.manifest_list.assert_called_once_with(None)


def test_manifest_list_handler_failure(server_app: MagicMock) -> None:
    server_app.manifest_list.side_effect = RuntimeError("boom")
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"manifest: list failed: boom"):
        gw._handler_manifest_list({})
    server_app.manifest_list.assert_called_once_with(None)


def test_manifest_read_handler(server_app: MagicMock) -> None:
    server_app.manifest_read.return_value = {
        "success": True,
        "manifest": {
            "job_name": "Fronty",
            "material": "MDF_18",
            "sheets": [],
            "total_parts": 0,
            "unmatched_parts": [],
            "path": r"C:\Reports\Data\Fronty - MDF_18.acrepd",
        },
    }
    gw = GatewayServer()
    result = gw._handler_manifest_read(
        {"job_name": "Fronty", "material": "MDF_18", "data_dir": r"C:\Reports\Data"}
    )
    assert result == server_app.manifest_read.return_value
    server_app.manifest_read.assert_called_once_with(
        job_name="Fronty",
        material="MDF_18",
        data_dir=r"C:\Reports\Data",
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_manifest_read_handler_no_params(server_app: MagicMock) -> None:
    server_app.manifest_read.return_value = {"success": True, "manifest": {}}
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"manifest: job_name required"):
        gw._handler_manifest_read({})
    server_app.manifest_read.assert_not_called()


def test_manifest_read_handler_failure(server_app: MagicMock) -> None:
    server_app.manifest_read.side_effect = RuntimeError("boom")
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"manifest: read failed: boom"):
        gw._handler_manifest_read({"job_name": "Fronty"})
    server_app.manifest_read.assert_called_once_with(
        job_name="Fronty",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_manifest_read_handler_nc_root(server_app: MagicMock) -> None:
    server_app.manifest_read.return_value = {"success": True, "manifest": {}}
    gw = GatewayServer()
    result = gw._handler_manifest_read({"job_name": "Fronty", "nc_root": r"C:\NC\Out"})
    assert result == server_app.manifest_read.return_value
    server_app.manifest_read.assert_called_once_with(
        job_name="Fronty",
        material=None,
        data_dir=None,
        nc_root=r"C:\NC\Out",
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_manifest_read_handler_by_token(server_app: MagicMock) -> None:
    server_app.manifest_read.return_value = {"success": True, "manifest": {}, "by_token": []}
    gw = GatewayServer()
    result = gw._handler_manifest_read({"job_name": "Fronty", "by_token": True})
    assert result == server_app.manifest_read.return_value
    server_app.manifest_read.assert_called_once_with(
        job_name="Fronty",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=True,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_manifest_read_handler_fill_threshold(server_app: MagicMock) -> None:
    server_app.manifest_read.return_value = {"success": True, "manifest": {}}
    gw = GatewayServer()
    result = gw._handler_manifest_read({"job_name": "Fronty", "fill_threshold": 50})
    assert result == server_app.manifest_read.return_value
    server_app.manifest_read.assert_called_once_with(
        job_name="Fronty",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=50,
        validate=False,
        token_qty=None,
    )


def test_manifest_read_handler_forbidden_job_name(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"invalid job name: 'Fronty/1' \(forbidden characters: /\)"):
        gw._handler_manifest_read({"job_name": "Fronty/1"})
    server_app.manifest_read.assert_not_called()


def test_manifest_read_handler_fill_threshold_non_int(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(
        COMError, match=r"manifest: fill_threshold must be an integer between 0 and 100"
    ):
        gw._handler_manifest_read({"job_name": "Fronty", "fill_threshold": "abc"})
    server_app.manifest_read.assert_not_called()


def test_manifest_read_handler_fill_threshold_bool(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(
        COMError, match=r"manifest: fill_threshold must be an integer between 0 and 100"
    ):
        gw._handler_manifest_read({"job_name": "Fronty", "fill_threshold": True})
    server_app.manifest_read.assert_not_called()


def test_manifest_read_handler_fill_threshold_out_of_range(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(
        COMError, match=r"manifest: fill_threshold must be an integer between 0 and 100"
    ):
        gw._handler_manifest_read({"job_name": "Fronty", "fill_threshold": 150})
    server_app.manifest_read.assert_not_called()


def test_manifest_read_handler_validate(server_app: MagicMock) -> None:
    server_app.manifest_read.return_value = {
        "success": True,
        "manifest": {},
        "validation": {"valid": True, "warnings": [], "errors": []},
    }
    gw = GatewayServer()
    result = gw._handler_manifest_read(
        {"job_name": "Fronty", "validate": True, "token_qty": {"ABC": 4}}
    )
    assert result == server_app.manifest_read.return_value
    server_app.manifest_read.assert_called_once_with(
        job_name="Fronty",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=True,
        token_qty={"ABC": 4},
    )


def test_manifest_read_handler_by_token_false_string(server_app: MagicMock) -> None:
    server_app.manifest_read.return_value = {"success": True, "manifest": {}}
    gw = GatewayServer()
    result = gw._handler_manifest_read(
        {"job_name": "Fronty", "by_token": "false", "validate": "false"}
    )
    assert result == server_app.manifest_read.return_value
    server_app.manifest_read.assert_called_once_with(
        job_name="Fronty",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_manifest_read_handler_token_qty_string_values(server_app: MagicMock) -> None:
    server_app.manifest_read.return_value = {"success": True, "manifest": {}}
    gw = GatewayServer()
    result = gw._handler_manifest_read({"job_name": "Fronty", "token_qty": {"ABC": "4", 7: "2"}})
    assert result == server_app.manifest_read.return_value
    server_app.manifest_read.assert_called_once_with(
        job_name="Fronty",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty={"ABC": 4, "7": 2},
    )


def test_manifest_read_handler_token_qty_not_dict(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"manifest: token_qty must be a dict"):
        gw._handler_manifest_read({"job_name": "Fronty", "token_qty": ["ABC", "4"]})
    server_app.manifest_read.assert_not_called()


def test_manifest_read_handler_token_qty_bad_value(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"manifest: token_qty values must be integers"):
        gw._handler_manifest_read({"job_name": "Fronty", "token_qty": {"ABC": "many"}})
    server_app.manifest_read.assert_not_called()


def test_manifest_read_handler_token_qty_negative(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"manifest: token_qty values must be non-negative integers"):
        gw._handler_manifest_read({"job_name": "Fronty", "token_qty": {"ABC": -1}})
    server_app.manifest_read.assert_not_called()


def test_manifest_read_handler_token_qty_bool(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"manifest: token_qty values must be non-negative integers"):
        gw._handler_manifest_read({"job_name": "Fronty", "token_qty": {"ABC": True}})
    server_app.manifest_read.assert_not_called()


def test_manifest_read_handler_relative_nc_root(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"manifest: nc_root must be an absolute path"):
        gw._handler_manifest_read({"job_name": "Fronty", "nc_root": "nc/out"})
    server_app.manifest_read.assert_not_called()


def test_manifest_read_handler_relative_data_dir(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"manifest: data_dir must be an absolute path"):
        gw._handler_manifest_read({"job_name": "Fronty", "data_dir": "Reports/Data"})
    server_app.manifest_read.assert_not_called()


def test_manifest_list_handler_relative_data_dir(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"manifest: data_dir must be an absolute path"):
        gw._handler_manifest_list({"data_dir": "Reports/Data"})
    server_app.manifest_list.assert_not_called()


def test_manifest_list_handler_unc_data_dir(server_app: MagicMock) -> None:
    server_app.manifest_list.return_value = {"success": True, "manifests": []}
    gw = GatewayServer()
    result = gw._handler_manifest_list({"data_dir": r"\\server\share\Reports\Data"})
    assert result == server_app.manifest_list.return_value
    server_app.manifest_list.assert_called_once_with(r"\\server\share\Reports\Data")


def test_manifest_list_handler_unc_forward_slash_data_dir(server_app: MagicMock) -> None:
    server_app.manifest_list.return_value = {"success": True, "manifests": []}
    gw = GatewayServer()
    result = gw._handler_manifest_list({"data_dir": "//server/share/Reports/Data"})
    assert result == server_app.manifest_list.return_value
    server_app.manifest_list.assert_called_once_with("//server/share/Reports/Data")


def test_set_nest_list_options_bool_false_strings() -> None:
    nl = MagicMock(name="NestList")
    gw = GatewayServer()
    gw._set_nest_list_options(nl, {"use_subroutines": "false", "inner_first": "off"})
    assert nl.UseSubroutines is False
    assert nl.InnerFirst is False


def test_set_nest_list_options_bool_none_skipped() -> None:
    nl = MagicMock(name="NestList")
    gw = GatewayServer()
    gw._set_nest_list_options(nl, {"use_subroutines": None})
    nl.UseSubroutines.assert_not_called()


def test_nest_inspect_handler_single_prefix(server_app: MagicMock) -> None:
    server_app.nest_inspect.side_effect = RuntimeError("nest: inspect failed: boom")
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"^nest: inspect failed: boom$"):
        gw._handler_nest_inspect({})
    server_app.nest_inspect.assert_called_once_with()


def test_batch_process_handler_null_files(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"batch: invalid files"):
        gw._handler_batch_process({"files": None})
    server_app.open_drawing.assert_not_called()


def test_process_cdm_job_handler(server_app: MagicMock) -> None:
    server_app.process_cdm_job.return_value = {
        "success": True,
        "job_name": "JOB-001",
        "processed": True,
    }
    gw = GatewayServer()
    result = gw._handler_process_cdm_job({"job_name": "JOB-001"})
    assert result == {"success": True, "job_name": "JOB-001", "processed": True}
    server_app.process_cdm_job.assert_called_once_with(job_name="JOB-001")


def test_process_cdm_job_handler_strips_whitespace(server_app: MagicMock) -> None:
    server_app.process_cdm_job.return_value = {
        "success": True,
        "job_name": "JOB-001",
        "processed": True,
    }
    gw = GatewayServer()
    result = gw._handler_process_cdm_job({"job_name": "  JOB-001  "})
    assert result == {"success": True, "job_name": "JOB-001", "processed": True}
    server_app.process_cdm_job.assert_called_once_with(job_name="JOB-001")


def test_process_cdm_job_handler_missing_job_name(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: job_name is required"):
        gw._handler_process_cdm_job({})
    server_app.process_cdm_job.assert_not_called()


def test_process_cdm_job_handler_blank_job_name(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: job_name is required"):
        gw._handler_process_cdm_job({"job_name": "   "})
    server_app.process_cdm_job.assert_not_called()


def test_process_cdm_job_handler_forbidden_name(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(
        COMError, match=r"invalid job name: 'Zadanie/1' \(forbidden characters: /\)"
    ):
        gw._handler_process_cdm_job({"job_name": "Zadanie/1"})
    server_app.process_cdm_job.assert_not_called()


def test_process_cdm_job_handler_com_failure(server_app: MagicMock) -> None:
    server_app.process_cdm_job.side_effect = RuntimeError("cdm: job not found: NOPE")
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"^cdm: job not found: NOPE$"):
        gw._handler_process_cdm_job({"job_name": "NOPE"})


def test_process_cdm_job_handler_full_params(server_app: MagicMock) -> None:
    server_app.process_cdm_job.return_value = {
        "success": True,
        "job_name": "JOB-001",
        "processed": True,
    }
    gw = GatewayServer()
    result = gw._handler_process_cdm_job(
        {
            "job_name": "JOB-001",
            "timeout_seconds": 600,
            "output_root": "C:/out",
        }
    )
    assert result == {"success": True, "job_name": "JOB-001", "processed": True}
    server_app.process_cdm_job.assert_called_once_with(
        job_name="JOB-001",
        timeout_seconds=600,
        output_root="C:/out",
    )


def test_process_cdm_job_handler_unknown_machine_method_params_ignored(
    server_app: MagicMock,
) -> None:
    server_app.process_cdm_job.return_value = {
        "success": True,
        "job_name": "JOB-001",
        "processed": True,
    }
    gw = GatewayServer()
    result = gw._handler_process_cdm_job(
        {
            "job_name": "JOB-001",
            "machine": {"psexec": "C:/temp/PsExec64.exe", "use_shell": True},
            "method": "vbs",
        }
    )
    assert result == {"success": True, "job_name": "JOB-001", "processed": True}
    server_app.process_cdm_job.assert_called_once_with(job_name="JOB-001")


def test_process_cdm_job_handler_invalid_timeout_type(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: timeout_seconds must be a positive int"):
        gw._handler_process_cdm_job({"job_name": "JOB-001", "timeout_seconds": "600"})
    server_app.process_cdm_job.assert_not_called()


def test_process_cdm_job_handler_bool_timeout_rejected(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: timeout_seconds must be a positive int"):
        gw._handler_process_cdm_job({"job_name": "JOB-001", "timeout_seconds": True})
    server_app.process_cdm_job.assert_not_called()


def test_process_cdm_job_handler_negative_timeout_rejected(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: timeout_seconds must be a positive int"):
        gw._handler_process_cdm_job({"job_name": "JOB-001", "timeout_seconds": -5})
    server_app.process_cdm_job.assert_not_called()


def test_process_cdm_job_handler_zero_timeout_rejected(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: timeout_seconds must be a positive int"):
        gw._handler_process_cdm_job({"job_name": "JOB-001", "timeout_seconds": 0})
    server_app.process_cdm_job.assert_not_called()


def test_process_cdm_job_handler_blank_output_root_rejected(
    server_app: MagicMock,
) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"cdm: output_root must be an absolute path"):
        gw._handler_process_cdm_job({"job_name": "JOB-001", "output_root": "   "})
    server_app.process_cdm_job.assert_not_called()


def test_process_cdm_job_handler_relative_output_root_rejected(
    server_app: MagicMock,
) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"cdm: output_root must be an absolute path"):
        gw._handler_process_cdm_job({"job_name": "JOB-001", "output_root": "out/dir"})
    server_app.process_cdm_job.assert_not_called()


def test_process_cdm_job_handler_non_string_output_root_rejected(
    server_app: MagicMock,
) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"cdm: output_root must be an absolute path"):
        gw._handler_process_cdm_job({"job_name": "JOB-001", "output_root": 123})
    server_app.process_cdm_job.assert_not_called()


def test_process_cdm_job_handler_watchdog_armed_and_cancelled(server_app: MagicMock) -> None:
    server_app.process_cdm_job.return_value = {"success": True}
    gw = GatewayServer()
    watchdog = MagicMock()
    gw._watchdog_arm = MagicMock(return_value=watchdog)
    gw._handler_process_cdm_job({"job_name": "JOB-001", "timeout_seconds": 600})
    gw._watchdog_arm.assert_called_once()
    assert gw._watchdog_arm.call_args.args[0] == 630.0
    assert gw._watchdog_arm.call_args.args[1] == "process_cdm_job(JOB-001)"
    watchdog.cancel.assert_called_once()


def test_process_cdm_job_handler_watchdog_default_budget(server_app: MagicMock) -> None:
    server_app.process_cdm_job.return_value = {"success": True}
    gw = GatewayServer()
    watchdog = MagicMock()
    gw._watchdog_arm = MagicMock(return_value=watchdog)
    gw._handler_process_cdm_job({"job_name": "JOB-001"})
    assert gw._watchdog_arm.call_args.args[0] == 330.0
    watchdog.cancel.assert_called_once()


def test_process_cdm_job_handler_watchdog_cancelled_on_error(server_app: MagicMock) -> None:
    server_app.process_cdm_job.side_effect = RuntimeError("cdm: boom")
    gw = GatewayServer()
    watchdog = MagicMock()
    gw._watchdog_arm = MagicMock(return_value=watchdog)
    with pytest.raises(COMError, match="cdm: boom"):
        gw._handler_process_cdm_job({"job_name": "JOB-001"})
    watchdog.cancel.assert_called_once()


class _FakeTimer:
    instances: list[_FakeTimer] = []

    def __init__(
        self,
        interval: float,
        function: Any,
        args: Any = None,
        kwargs: Any = None,
    ) -> None:
        self.interval = interval
        self.function = function
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.daemon = False
        self.started = False
        _FakeTimer.instances.append(self)

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        pass


def test_process_cdm_job_handler_stale_macro_returns_restart_response(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    import alphacam_cli.gateway.server as server_module

    _FakeTimer.instances = []
    monkeypatch.setattr(server_module.threading, "Timer", _FakeTimer)
    server_app.process_cdm_job.side_effect = RuntimeError(
        "cdm: STALE_MACRO: previous headless macro invocation did not complete "
        "(last log line: 'RUN'); AlphaCAM VBA host is hung"
    )
    gw = GatewayServer()
    watchdog = MagicMock()
    gw._watchdog_arm = MagicMock(return_value=watchdog)

    result = gw._handler_process_cdm_job({"job_name": "JOB-001"})

    assert result == {
        "success": False,
        "status": "stale_macro",
        "job_name": "JOB-001",
        "detail": "previous macro invocation hung — gateway auto-restarting, retry in ~60s",
        "auto_restart": True,
    }
    server_app.process_cdm_job.assert_called_once_with(job_name="JOB-001")
    assert len(_FakeTimer.instances) == 1
    timer = _FakeTimer.instances[0]
    assert timer.interval == 3.0
    assert timer.function is os._exit
    assert timer.args == (1,)
    assert timer.daemon is True
    assert timer.started is True
    watchdog.cancel.assert_called_once()


def test_process_cdm_job_handler_plain_error_no_restart(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    import alphacam_cli.gateway.server as server_module

    _FakeTimer.instances = []
    monkeypatch.setattr(server_module.threading, "Timer", _FakeTimer)
    server_app.process_cdm_job.side_effect = RuntimeError("cdm: job not found: NOPE")
    gw = GatewayServer()
    watchdog = MagicMock()
    gw._watchdog_arm = MagicMock(return_value=watchdog)

    with pytest.raises(COMError, match=r"^cdm: job not found: NOPE$"):
        gw._handler_process_cdm_job({"job_name": "NOPE"})

    assert _FakeTimer.instances == []
    watchdog.cancel.assert_called_once()


def test_process_cdm_job_handler_success_no_restart(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    import alphacam_cli.gateway.server as server_module

    _FakeTimer.instances = []
    monkeypatch.setattr(server_module.threading, "Timer", _FakeTimer)
    server_app.process_cdm_job.return_value = {
        "success": True,
        "job_name": "JOB-001",
        "processed": True,
    }
    gw = GatewayServer()
    watchdog = MagicMock()
    gw._watchdog_arm = MagicMock(return_value=watchdog)

    result = gw._handler_process_cdm_job({"job_name": "JOB-001"})

    assert result == {"success": True, "job_name": "JOB-001", "processed": True}
    assert _FakeTimer.instances == []
    watchdog.cancel.assert_called_once()


def _patch_sta_call_queue(gw: GatewayServer, monkeypatch: pytest.MonkeyPatch) -> None:
    """Execute queued calls synchronously so _com_call needs no real STA thread."""

    def fake_put(item: tuple[Any, Any, str]) -> None:
        fn, result_q, desc = item
        try:
            result_q.put(fn())
        except Exception as exc:
            result_q.put(exc)

    monkeypatch.setattr(gw._call_queue, "put", fake_put)


def test_com_call_returns_result(monkeypatch: pytest.MonkeyPatch) -> None:
    gw = GatewayServer()
    _patch_sta_call_queue(gw, monkeypatch)
    result = gw._com_call(lambda: {"ok": 1})
    assert result == {"ok": 1}


def test_com_call_re_raises_worker_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise RuntimeError("boom")

    gw = GatewayServer()
    _patch_sta_call_queue(gw, monkeypatch)
    with pytest.raises(RuntimeError, match="boom"):
        gw._com_call(boom)


def test_com_call_dead_sta_thread_raises_com_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import alphacam_cli.gateway.server as server_module

    gw = GatewayServer()
    dead_thread = MagicMock()
    dead_thread.is_alive.return_value = False
    gw._sta_thread = dead_thread
    monkeypatch.setattr(server_module, "_COM_CALL_POLL", 0.01)
    with pytest.raises(COMError, match="STA worker died"):
        gw._com_call(lambda: 1)


def test_com_call_no_sta_thread_raises_com_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import alphacam_cli.gateway.server as server_module

    gw = GatewayServer()
    gw._sta_thread = None
    monkeypatch.setattr(server_module, "_COM_CALL_POLL", 0.01)
    with pytest.raises(COMError, match="STA worker died"):
        gw._com_call(lambda: 1)


def test_com_call_alive_sta_thread_waits_for_slow_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import alphacam_cli.gateway.server as server_module

    gw = GatewayServer()
    alive_thread = MagicMock()
    alive_thread.is_alive.return_value = True
    gw._sta_thread = alive_thread
    monkeypatch.setattr(server_module, "_COM_CALL_POLL", 0.01)

    def delayed_put(item: tuple[Any, Any, str]) -> None:
        fn, result_q, desc = item

        def run() -> None:
            time.sleep(0.05)
            try:
                result_q.put(fn())
            except Exception as exc:
                result_q.put(exc)

        threading.Thread(target=run, daemon=True).start()

    monkeypatch.setattr(gw._call_queue, "put", delayed_put)
    result = gw._com_call(lambda: 42, timeout=0.02)
    assert result == 42
