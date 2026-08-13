from __future__ import annotations

import os
import pathlib
import sys
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
    }
    gw = GatewayServer()
    result = gw._handler_reports_create({})
    assert result == {"success": True, "job": "ok", "active_drawing": True}
    server_app.reports_create.assert_called_once_with()


def test_reports_create_handler_failure(server_app: MagicMock) -> None:
    server_app.reports_create.side_effect = RuntimeError("boom")
    gw = GatewayServer()
    with pytest.raises(COMError, match="reports: create failed: boom"):
        gw._handler_reports_create({})
    server_app.reports_create.assert_called_once_with()


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


def _mock_cdm_com(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Install fake pythoncom/win32com.client and return (ai, addins, am)."""
    pythoncom = MagicMock()
    pythoncom.MakeIID.return_value = "CDM-CLSID"
    pythoncom.CoCreateInstance.return_value = object()
    pythoncom.CLSCTX_ALL = 23
    pythoncom.IID_IDispatch = "IDispatch"

    w32 = MagicMock()
    ai = MagicMock()
    addins = MagicMock()
    am = MagicMock()
    w32.Dispatch.return_value = ai
    ai.GetAddInsInterface.return_value = addins
    addins.GetAutomationManagerAddInGUI.return_value = am

    client_mod = types.ModuleType("win32com.client")
    client_mod.Dispatch = w32.Dispatch  # type: ignore[attr-defined]
    win32com = types.ModuleType("win32com")
    win32com.client = client_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client_mod)
    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
    import alphacam_cli.gateway.server as server_module

    if server_module._app is None:
        server_module._app = MagicMock()
    server_module._app.get_automation_manager_addin.return_value = am
    am.Jobs.Count = 0
    return ai, addins, am


def _mock_vdb5_run(
    monkeypatch: pytest.MonkeyPatch, stdout: str = "[]", returncode: int = 0
) -> MagicMock:
    run = MagicMock(return_value=types.SimpleNamespace(stdout=stdout, returncode=returncode))
    monkeypatch.setattr("subprocess.run", run)
    return run


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


def test_cdm_types_handler(server_app: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    _mock_vdb5_run(monkeypatch)
    d1 = MagicMock()
    d1.TypeName = "Typ Frontu 1"
    d2 = MagicMock()
    d2.TypeName = "L_B_10mm"
    details = MagicMock()
    details.Count = 2
    details.Item.side_effect = [d1, d2]
    job1 = MagicMock()
    job1.CDMOrderDetails = details
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job1
    am.Jobs = jobs
    gw = GatewayServer()
    result = gw._handler_cdm_types({})
    assert result == {
        "types": [{"id": 1, "name": "Typ Frontu 1"}, {"id": 2, "name": "L_B_10mm"}],
        "source": "vdb5+com",
    }


def test_cdm_types_handler_dedup(server_app: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    _mock_vdb5_run(monkeypatch)
    d1 = MagicMock()
    d1.TypeName = "Typ Frontu 1"
    d2 = MagicMock()
    d2.TypeName = "Typ Frontu 1"
    details = MagicMock()
    details.Count = 2
    details.Item.side_effect = [d1, d2]
    job1 = MagicMock()
    job1.CDMOrderDetails = details
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job1
    am.Jobs = jobs
    gw = GatewayServer()
    result = gw._handler_cdm_types({})
    assert result == {
        "types": [{"id": 1, "name": "Typ Frontu 1"}],
        "source": "vdb5+com",
    }


def test_cdm_types_handler_empty(server_app: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    _mock_vdb5_run(monkeypatch)
    am.Jobs.Count = 0
    gw = GatewayServer()
    result = gw._handler_cdm_types({})
    assert result == {"types": [], "note": "no CDM door types found"}


def test_cdm_types_handler_vdb5(server_app: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    _mock_vdb5_run(monkeypatch, stdout='[{"TypeName": "Typ Frontu 1"}, {"TypeName": "L_B_10mm"}]')
    am.Jobs.Count = 0
    gw = GatewayServer()
    result = gw._handler_cdm_types({})
    assert result == {
        "types": [{"id": 1, "name": "Typ Frontu 1"}, {"id": 2, "name": "L_B_10mm"}],
        "source": "vdb5+com",
    }


def test_cdm_types_handler_vdb5_merge(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    _mock_vdb5_run(monkeypatch, stdout='[{"TypeName": "Typ Frontu 1"}, {"TypeName": "M_01"}]')
    d1 = MagicMock()
    d1.TypeName = "M_01"
    d2 = MagicMock()
    d2.TypeName = "Typ Frontu 47"
    details = MagicMock()
    details.Count = 2
    details.Item.side_effect = [d1, d2]
    job1 = MagicMock()
    job1.CDMOrderDetails = details
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job1
    am.Jobs = jobs
    gw = GatewayServer()
    result = gw._handler_cdm_types({})
    assert result == {
        "types": [
            {"id": 1, "name": "Typ Frontu 1"},
            {"id": 2, "name": "M_01"},
            {"id": 3, "name": "Typ Frontu 47"},
        ],
        "source": "vdb5+com",
    }


def test_cdm_types_handler_vdb5_fallback(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    monkeypatch.setattr("subprocess.run", MagicMock(side_effect=FileNotFoundError("powershell")))
    d1 = MagicMock()
    d1.TypeName = "Typ Frontu 47"
    details = MagicMock()
    details.Count = 1
    details.Item.return_value = d1
    job1 = MagicMock()
    job1.CDMOrderDetails = details
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job1
    am.Jobs = jobs
    gw = GatewayServer()
    result = gw._handler_cdm_types({})
    assert result == {
        "types": [{"id": 1, "name": "Typ Frontu 47"}],
        "note": "vdb5 read failed; types from jobs only",
        "source": "com",
    }


def test_cdm_types_handler_vdb5_returncode_nonzero(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    _mock_vdb5_run(monkeypatch, stdout="[]", returncode=1)
    d1 = MagicMock()
    d1.TypeName = "Typ Frontu 47"
    details = MagicMock()
    details.Count = 1
    details.Item.return_value = d1
    job1 = MagicMock()
    job1.CDMOrderDetails = details
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job1
    am.Jobs = jobs
    gw = GatewayServer()
    result = gw._handler_cdm_types({})
    assert result == {
        "types": [{"id": 1, "name": "Typ Frontu 47"}],
        "note": "vdb5 read failed; types from jobs only",
        "source": "com",
    }


def test_cdm_types_handler_vdb5_empty_stdout(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    _mock_vdb5_run(monkeypatch, stdout="")
    d1 = MagicMock()
    d1.TypeName = "Typ Frontu 47"
    details = MagicMock()
    details.Count = 1
    details.Item.return_value = d1
    job1 = MagicMock()
    job1.CDMOrderDetails = details
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job1
    am.Jobs = jobs
    gw = GatewayServer()
    result = gw._handler_cdm_types({})
    assert result == {
        "types": [{"id": 1, "name": "Typ Frontu 47"}],
        "note": "vdb5 read failed; types from jobs only",
        "source": "com",
    }


def test_cdm_types_handler_vdb5_non_list_rows(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    _mock_vdb5_run(monkeypatch, stdout="not json array")
    d1 = MagicMock()
    d1.TypeName = "Typ Frontu 47"
    details = MagicMock()
    details.Count = 1
    details.Item.return_value = d1
    job1 = MagicMock()
    job1.CDMOrderDetails = details
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job1
    am.Jobs = jobs
    gw = GatewayServer()
    result = gw._handler_cdm_types({})
    assert result == {
        "types": [{"id": 1, "name": "Typ Frontu 47"}],
        "note": "vdb5 read failed; types from jobs only",
        "source": "com",
    }


def test_cdm_types_handler_vdb5_row_not_dict(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    _mock_vdb5_run(monkeypatch, stdout="[42]")
    d1 = MagicMock()
    d1.TypeName = "Typ Frontu 47"
    details = MagicMock()
    details.Count = 1
    details.Item.return_value = d1
    job1 = MagicMock()
    job1.CDMOrderDetails = details
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job1
    am.Jobs = jobs
    gw = GatewayServer()
    result = gw._handler_cdm_types({})
    assert result == {
        "types": [{"id": 1, "name": "Typ Frontu 47"}],
        "source": "vdb5+com",
    }


def test_cdm_types_handler_vdb5_skips_system_row(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    _mock_vdb5_run(
        monkeypatch,
        stdout=(
            '[{"TypeName": "Typ Frontu 1"},'
            ' {"TypeName": "Alphacam Created System Database Field - Do not delete"}]'
        ),
    )
    am.Jobs.Count = 0
    gw = GatewayServer()
    result = gw._handler_cdm_types({})
    assert result == {"types": [{"id": 1, "name": "Typ Frontu 1"}], "source": "vdb5+com"}


def test_cdm_types_handler_vdb5_value_wrap(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    _mock_vdb5_run(monkeypatch, stdout='{"value": [{"TypeName": "Typ Frontu 1"}]}')
    am.Jobs.Count = 0
    gw = GatewayServer()
    result = gw._handler_cdm_types({})
    assert result == {"types": [{"id": 1, "name": "Typ Frontu 1"}], "source": "vdb5+com"}


def test_cdm_types_handler_vdb5_single_object(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    _mock_vdb5_run(monkeypatch, stdout='{"TypeName": "Typ Frontu 1"}')
    am.Jobs.Count = 0
    gw = GatewayServer()
    result = gw._handler_cdm_types({})
    assert result == {"types": [{"id": 1, "name": "Typ Frontu 1"}], "source": "vdb5+com"}


def test_cdm_jobs_handler(server_app: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    j1 = MagicMock()
    j1.JobName = "JOB-001"
    j2 = MagicMock()
    j2.JobName = "JOB-002"
    jobs = MagicMock()
    jobs.Count = 2
    jobs.Item.side_effect = [j1, j2]
    am.Jobs = jobs
    gw = GatewayServer()
    result = gw._handler_cdm_jobs({})
    assert result == {"jobs": [{"id": 1, "name": "JOB-001"}, {"id": 2, "name": "JOB-002"}]}


def test_cdm_jobs_handler_empty(server_app: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    am.Jobs.Count = 0
    gw = GatewayServer()
    result = gw._handler_cdm_jobs({})
    assert result == {"jobs": []}


def test_cdm_import_csv_handler_missing_csv(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: csv path is required"):
        gw._handler_cdm_import_csv({})


def test_cdm_import_csv_handler_single_job(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result == {
        "success": True,
        "job_name": "order",
        "items": 1,
        "material": None,
        "errors": ["job order: no material set (required for processing)"],
        "import_setting": "Fronty CSV",
    }
    assert job.JobName == "order"
    job.SaveToDatabase.assert_called_once_with()
    job.AddCDMOrderDetail.assert_called_once_with("P003")
    assert detail.Width == 500.0
    assert detail.Length == 500.0
    assert detail.Quantity == 1
    assert len(detail.UserVariableString.split(";")) == 50
    assert detail.UserVariableString.startswith("1;18;0;0;")
    assert detail.UserVariableString.endswith(";0;0")
    detail.SaveToDatabase.assert_called_once_with()


def test_cdm_import_csv_handler_auto_create_with_name(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    am.NewCDMJob.return_value = job
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file), "name": "Zadanie 132"})
    assert result["success"] is True
    assert result["job_name"] == "Zadanie 132"
    assert job.JobName == "Zadanie 132"


def test_cdm_import_csv_handler_auto_create_with_config(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    am.NewCDMJob.return_value = job
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file), "config": "Fronty"})
    assert result["success"] is True
    am.ConfigurationSettings.GetByName.assert_called_once_with("Fronty")
    assert job.ConfigurationSetting == am.ConfigurationSettings.GetByName.return_value


def test_cdm_import_csv_handler_default_config(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    am.NewCDMJob.return_value = job
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF18 - 2800 x 2070": 4}
    )
    run = _mock_vdb5_run(monkeypatch, stdout="rows: 1\ndetail_rows: 1")
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is True
    am.ConfigurationSettings.GetByName.assert_called_once_with("Fronty")
    assert job.ConfigurationSetting == am.ConfigurationSettings.GetByName.return_value
    assert run.call_count == 1
    args, _ = run.call_args
    assert "-JobName:order" in args[0]
    assert "-MaterialID:4" in args[0]


def test_cdm_import_csv_handler_defaults_material(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    am.NewCDMJob.return_value = job
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF18 - 2800 x 2070": 4}
    )
    run = _mock_vdb5_run(monkeypatch, stdout="rows: 1\ndetail_rows: 1")
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is True
    assert result["material"] == "MDF18 - 2800 x 2070"
    assert result["errors"] == []
    am.ConfigurationSettings.GetByName.assert_called_once_with("Fronty")
    assert run.call_count == 1
    args, _ = run.call_args
    assert "-JobName:order" in args[0]
    assert "-MaterialID:4" in args[0]


def test_cdm_import_csv_handler_defaults_fetched_once(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    defaults = MagicMock(return_value={"config_name": "Fronty", "material_id": 4})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.vdb5_job_defaults", defaults)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF18 - 2800 x 2070": 4}
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is True
    assert result["material"] == "MDF18 - 2800 x 2070"
    defaults.assert_called_once_with()
    am.ConfigurationSettings.GetByName.assert_called_once_with("Fronty")


def test_cdm_import_csv_handler_no_defaults(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    am.NewCDMJob.return_value = job
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": None, "material_id": None},
    )
    with pytest.raises(COMError, match="cdm: no default configuration found"):
        gw._handler_cdm_import_csv({"csv": str(csv_file)})


def test_cdm_import_csv_handler_config_flag_overrides_default(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    am.NewCDMJob.return_value = job
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0,MDF_18\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch, fields=_LEGACY_FIELDS_MATERIAL)
    gw = GatewayServer()
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 3})
    defaults = MagicMock(return_value={"config_name": "Fronty", "material_id": 4})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.vdb5_job_defaults", defaults)
    _mock_vdb5_run(monkeypatch, stdout="rows: 1\ndetail_rows: 1")
    result = gw._handler_cdm_import_csv({"csv": str(csv_file), "config": "Custom"})
    assert result["success"] is True
    am.ConfigurationSettings.GetByName.assert_called_once_with("Custom")
    defaults.assert_not_called()


def test_cdm_import_csv_handler_job_lookup(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    detail = MagicMock()
    job.JobName = "X"
    job.AddCDMOrderDetail.return_value = detail
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job
    am.Jobs = jobs
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file), "job": "X"})
    assert result == {
        "success": True,
        "job_name": "X",
        "items": 1,
        "material": None,
        "errors": ["job X: no material set (required for processing)"],
        "import_setting": "Fronty CSV",
    }
    am.NewCDMJob.assert_not_called()
    job.SaveToDatabase.assert_not_called()
    job.AddCDMOrderDetail.assert_called_once_with("P003")
    assert detail.Width == 500.0


def test_cdm_import_csv_handler_job_not_found(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    jobs = MagicMock()
    jobs.Count = 0
    am.Jobs = jobs
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    with pytest.raises(COMError, match="cdm: job not found: X"):
        gw._handler_cdm_import_csv({"csv": str(csv_file), "job": "X"})


def test_cdm_import_csv_handler_name_and_job_conflict(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0\n", encoding="utf-8")
    gw = GatewayServer()
    with pytest.raises(COMError, match="mutually exclusive"):
        gw._handler_cdm_import_csv({"csv": str(csv_file), "job": "X", "name": "Y"})


def test_cdm_import_csv_handler_multi_row_single_job(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    am.NewCDMJob.return_value = job
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(
        "P003,1,500,500,1;18;0;0\nP004,2,600,400,1;0\nP005,1,300,300,\n",
        encoding="utf-8",
    )
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is True
    assert result["job_name"] == "order"
    assert result["items"] == 3
    assert result["material"] is None
    assert result["errors"] == ["job order: no material set (required for processing)"]
    am.NewCDMJob.assert_called_once_with()
    job.AddCDMOrderDetail.assert_any_call("P003")
    job.AddCDMOrderDetail.assert_any_call("P004")
    job.AddCDMOrderDetail.assert_any_call("P005")


def test_cdm_import_csv_handler_extra_columns_ignored(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0,MDF_18,ImportE2E 001,Fronty\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch, fields=_LEGACY_FIELDS_MATERIAL)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 3})
    _mock_vdb5_run(monkeypatch, stdout="rows: 1\ndetail_rows: 1")
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is True
    assert result["items"] == 1
    assert result["material"] == "MDF_18"
    assert result["errors"] == []
    assert not any("material" in e for e in result["errors"])
    job.AddCDMOrderDetail.assert_called_once_with("P003")
    assert detail.Width == 500.0


def test_cdm_import_csv_handler_bad_type(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    job.AddCDMOrderDetail.side_effect = RuntimeError("type does not exist")
    am.NewCDMJob.return_value = job
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("XYZ,1,500,500,1;2;3\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is False
    assert result["items"] == 0
    assert any("door type not found: XYZ" in e for e in result["errors"])


def test_cdm_import_csv_handler_all_details_fail_deletes_job(
    server_app: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    job.JobName = "order"
    job.AddCDMOrderDetail.side_effect = RuntimeError("type does not exist")
    am.NewCDMJob.return_value = job
    cleanup = MagicMock(return_value=(True, ""))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.cleanup_created_job", cleanup)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\nP004,1,600,400,1;2;3\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is False
    assert result["items"] == 0
    assert result["errors"].count("job order: no valid order details, deleted") == 1
    assert any("door type not found: P003" in e for e in result["errors"])
    assert any("door type not found: P004" in e for e in result["errors"])
    args, kwargs = cleanup.call_args
    assert args == (am, job, "order")
    assert callable(kwargs.get("log"))
    assert not any(
        record.levelname == "INFO" and "cdm import cleanup:" in record.getMessage()
        for record in caplog.records
    )


def test_cdm_import_csv_handler_all_details_fail_delete_via_lookup(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    job.JobName = "order"
    job.AddCDMOrderDetail.side_effect = RuntimeError("type does not exist")
    am.NewCDMJob.return_value = job
    cleanup = MagicMock(return_value=(True, ""))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.cleanup_created_job", cleanup)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is False
    assert result["items"] == 0
    assert result["errors"].count("job order: no valid order details, deleted") == 1
    args, kwargs = cleanup.call_args
    assert args == (am, job, "order")
    assert callable(kwargs.get("log"))


def test_cdm_import_csv_handler_all_details_fail_cleanup_still_present(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    job.JobName = "order"
    job.AddCDMOrderDetail.side_effect = RuntimeError("type does not exist")
    am.NewCDMJob.return_value = job
    cleanup = MagicMock(return_value=(False, "failed"))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.cleanup_created_job", cleanup)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is False
    assert result["items"] == 0
    assert result["errors"].count("job order: no valid order details, cleanup failed") == 1
    assert not any("no valid order details, deleted" in e for e in result["errors"])
    args, kwargs = cleanup.call_args
    assert args == (am, job, "order")
    assert callable(kwargs.get("log"))


def test_cdm_import_csv_handler_all_details_fail_cleanup_unverified(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    job.JobName = "order"
    job.AddCDMOrderDetail.side_effect = RuntimeError("type does not exist")
    am.NewCDMJob.return_value = job
    cleanup = MagicMock(return_value=(False, "unverified"))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.cleanup_created_job", cleanup)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is False
    assert result["items"] == 0
    assert result["errors"].count("job order: no valid order details, cleanup unverified") == 1
    args, kwargs = cleanup.call_args
    assert args == (am, job, "order")
    assert callable(kwargs.get("log"))


def test_cdm_import_csv_handler_all_details_fail_keeps_existing_job(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    job.JobName = "X"
    job.AddCDMOrderDetail.side_effect = RuntimeError("type does not exist")
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job
    am.Jobs = jobs
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\nP004,1,600,400,1;2;3\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file), "job": "X"})
    assert result["success"] is False
    assert result["items"] == 0
    assert not any("no valid order details" in e for e in result["errors"])
    am.NewCDMJob.assert_not_called()
    job.DeleteFromDB.assert_not_called()


def test_cdm_import_csv_handler_cleanup_failure(
    server_app: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    job.JobName = "order"
    job.AddCDMOrderDetail.side_effect = RuntimeError("type does not exist")
    job.DeleteFromDB.side_effect = RuntimeError("db locked")
    am.NewCDMJob.return_value = job
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.find_cdm_job",
        MagicMock(return_value=job),
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is False
    assert result["items"] == 0
    assert any("cleanup failed" in e for e in result["errors"])
    assert not any("db locked" in e for e in result["errors"])
    job.DeleteFromDB.assert_called_once_with()
    assert any(
        record.levelname == "WARNING"
        and "cdm import: cleanup failed:" in record.getMessage()
        and "db locked" in record.getMessage()
        for record in caplog.records
    )


def test_cdm_import_csv_handler_all_rows_invalid(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1\nP004,abc,400,300,0\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is False
    assert result["items"] == 0
    assert result["job_name"] == ""
    assert any("expected at least 3 columns" in e for e in result["errors"])
    assert any("invalid quantity" in e for e in result["errors"])
    am.NewCDMJob.assert_not_called()


def test_cdm_import_csv_handler_file_not_found(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: csv file not found"):
        gw._handler_cdm_import_csv({"csv": r"C:\temp\nonexistent.csv"})


def test_cdm_import_csv_handler_header(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    am.NewCDMJob.return_value = job
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(
        "Style,Quantity,Width,Length,DesignDimensions\nP003,1,500,500,1;18;0;0\n",
        encoding="utf-8",
    )
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file), "has_header": True})
    assert result["success"] is True
    assert result["job_name"] == "order"
    assert result["items"] == 1
    job.AddCDMOrderDetail.assert_called_once_with("P003")


def test_cdm_import_csv_handler_short_row(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    am.NewCDMJob.return_value = job
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(
        "P003,1\nP004,2,600,400,1;2;3;4;5;6;7,MDF,JOB-A,Fronty\n",
        encoding="utf-8",
    )
    _mock_selected_import_setting(monkeypatch, fields=_LEGACY_FIELDS_MATERIAL)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF": 7})
    _mock_vdb5_run(monkeypatch, stdout="rows: 1\ndetail_rows: 1")
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is True
    assert result["items"] == 1
    assert result["material"] == "MDF"
    assert any("expected at least 3 columns" in e for e in result["errors"])


def test_cdm_import_csv_handler_material_from_csv(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(
        "P003,1,500,500,1;18;0;0,MDF_18\nP004,2,600,400,1;0,MDF_18\n", encoding="utf-8"
    )
    _mock_selected_import_setting(monkeypatch, fields=_LEGACY_FIELDS_MATERIAL)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 2})
    run = _mock_vdb5_run(monkeypatch, stdout="rows: 1\ndetail_rows: 1")
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is True
    assert result["job_name"] == "order"
    assert result["items"] == 2
    assert result["material"] == "MDF_18"
    assert result["errors"] == []
    assert run.call_count == 1
    args, _ = run.call_args
    assert "-JobName:order" in args[0]
    assert "-MaterialID:2" in args[0]


def test_cdm_import_csv_handler_material_cli_overrides(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0,MDF_18\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch, fields=_LEGACY_FIELDS_MATERIAL)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.sheet_materials",
        lambda: {"MDF_18": 3, "Material 3 - 2440 x 1220": 5},
    )
    run = _mock_vdb5_run(monkeypatch, stdout="rows: 1\ndetail_rows: 1")
    result = gw._handler_cdm_import_csv(
        {"csv": str(csv_file), "material": "Material 3 - 2440 x 1220"}
    )
    assert result["material"] == "Material 3 - 2440 x 1220"
    assert result["errors"] == []
    args, _ = run.call_args
    assert "-JobName:order" in args[0]
    assert "-MaterialID:5" in args[0]


def test_cdm_import_csv_handler_material_not_found(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    am.NewCDMJob.return_value = job
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {})
    with pytest.raises(COMError, match="cdm: material not found: MDF_18"):
        gw._handler_cdm_import_csv({"csv": str(csv_file), "material": "MDF_18"})


def test_cdm_import_csv_handler_material_warning(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    am.NewCDMJob.return_value = job
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is True
    assert result["material"] is None
    assert any("no material set" in e for e in result["errors"])


def test_cdm_delete_job_handler(server_app: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    job.JobName = "JOB-001"
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job
    am.Jobs = jobs
    gw = GatewayServer()
    result = gw._handler_cdm_delete_job({"job_name": "JOB-001"})
    assert result == {"success": True, "job_name": "JOB-001"}
    jobs.Item.assert_called_once_with(1)
    job.DeleteFromDB.assert_called_once_with()


def test_cdm_delete_job_handler_missing_name(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: job_name is required"):
        gw._handler_cdm_delete_job({})


def test_cdm_delete_job_handler_not_found(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    am.Jobs.Count = 0
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: job not found: NOPE"):
        gw._handler_cdm_delete_job({"job_name": "NOPE"})


def test_cdm_delete_job_handler_failed(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    job.JobName = "JOB-001"
    job.DeleteFromDB.side_effect = RuntimeError("locked")
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job
    am.Jobs = jobs
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"cdm: delete job failed: locked"):
        gw._handler_cdm_delete_job({"job_name": "JOB-001"})


def test_cdm_delete_job_handler_no_delete_method(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    del job.DeleteFromDB
    job.JobName = "JOB-001"
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job
    am.Jobs = jobs
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: DeleteFromDB unavailable on job"):
        gw._handler_cdm_delete_job({"job_name": "JOB-001"})


_LEGACY_FIELDS = [
    (1, 256),
    (2, 259),
    (3, 257),
    (4, 258),
    (5, 264),
]
_LEGACY_FIELDS_MATERIAL = _LEGACY_FIELDS + [(6, 524)]


def _mock_selected_import_setting(
    monkeypatch: pytest.MonkeyPatch,
    *,
    create_job: bool = True,
    fields: list[tuple[int, int]] | None = None,
) -> dict[str, Any]:
    setting = {
        "id": 1,
        "name": "Fronty CSV",
        "delimiter_char": ",",
        "sub_delimiter_char": ";",
        "create_job": create_job,
        "selected": True,
        "ignore_header": False,
        "is_cdm_import": True,
        "fields": [
            {"column_number": col, "parameter_type": ptype}
            for col, ptype in (fields or _LEGACY_FIELDS)
        ],
    }
    monkeypatch.setattr("alphacam_cli.core.cdm_db.import_settings", lambda: [setting])
    return setting


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


_MAPPED_CSV_ROW = "P003,1,500,500,1;2;3,MDF_18,Zadanie-7,Fronty,Klient A,CF1,CF2,CF3"


def test_cdm_import_csv_handler_mapped_setting(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(_MAPPED_CSV_ROW + "\n", encoding="utf-8")
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.import_settings", lambda: [_fake_import_setting()]
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 2})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", lambda job_name, mid: True)
    result = gw._handler_cdm_import_csv({"csv": str(csv_file), "import_setting": 3})
    assert result == {
        "success": True,
        "job_name": "Zadanie-7",
        "items": 1,
        "material": "MDF_18",
        "errors": [],
        "import_setting": "Fronty CSV",
    }
    assert job.JobName == "Zadanie-7"
    job.SaveToDatabase.assert_called_once_with()
    am.ConfigurationSettings.GetByName.assert_called_once_with("Fronty")
    job.AddCDMOrderDetail.assert_called_once_with("P003")
    assert detail.Width == 500.0
    assert detail.Length == 500.0
    assert detail.Quantity == 1
    assert detail.UserVariableString == ";".join(["1", "2", "3"] + ["0"] * 47)
    assert detail.CSV_CustomerName == "Klient A"
    assert detail.CustomField1 == "CF1"
    assert detail.CustomField2 == "CF2"
    assert detail.CustomField3 == "CF3"
    detail.SaveToDatabase.assert_called_once_with()


def test_cdm_import_csv_handler_mapped_not_cdm_setting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    setting = _fake_import_setting()
    setting["is_cdm_import"] = False
    monkeypatch.setattr("alphacam_cli.core.cdm_db.import_settings", lambda: [setting])
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(_MAPPED_CSV_ROW + "\n", encoding="utf-8")
    gw = GatewayServer()
    with pytest.raises(COMError, match="is not a CDM import setting"):
        gw._handler_cdm_import_csv({"csv": str(csv_file), "import_setting": 3})


def test_cdm_import_csv_handler_sets_has_drilling(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    setting = {
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
            {"column_number": 6, "parameter_type": 298},
        ],
    }
    monkeypatch.setattr("alphacam_cli.core.cdm_db.import_settings", lambda: [setting])
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 2})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", lambda job_name, mid: True)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 2},
    )
    set_has_drilling = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_has_drilling", set_has_drilling)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3,1\nP004,1,600,400,1;2;3,0\n", encoding="utf-8")
    gw = GatewayServer()
    result = gw._handler_cdm_import_csv({"csv": str(csv_file), "import_setting": 3})
    assert result["success"] is True
    assert result["items"] == 2
    assert result["errors"] == []
    assert set_has_drilling.call_count == 1
    assert set_has_drilling.call_args.args == ("order", [True, False])


def test_cdm_import_csv_handler_preview(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(_MAPPED_CSV_ROW + "\n", encoding="utf-8")
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.import_settings", lambda: [_fake_import_setting()]
    )
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 2})
    am_getter = MagicMock()
    monkeypatch.setattr(gw, "_cdm_automation_manager", am_getter)
    result = gw._handler_cdm_import_csv(
        {"csv": str(csv_file), "import_setting": 3, "preview": True}
    )
    assert result["success"] is True
    assert result["items"] == 1
    assert result["setting"]["id"] == 3
    assert result["setting"]["name"] == "Fronty CSV"
    assert result["setting"]["delimiter_char"] == ","
    assert result["job_name"] == "Zadanie-7"
    assert result["config"] == "Fronty"
    assert result["material"] == "MDF_18"
    assert result["rows"][0]["customer_name"] == "Klient A"
    assert result["errors"] == []
    am_getter.assert_not_called()
    assert am.NewCDMJob.call_count == 0


def test_cdm_import_preview_handler(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(_MAPPED_CSV_ROW + "\n", encoding="utf-8")
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.import_settings", lambda: [_fake_import_setting()]
    )
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 2})
    am_getter = MagicMock()
    monkeypatch.setattr(gw, "_cdm_automation_manager", am_getter)
    result = gw._handler_cdm_import_preview({"csv": str(csv_file), "import_setting": "Fronty CSV"})
    assert result["success"] is True
    assert result["items"] == 1
    assert result["job_name"] == "Zadanie-7"
    assert result["config"] == "Fronty"
    assert result["material"] == "MDF_18"
    assert result["field_map"][0] == {"column": 1, "field": "door_type", "required": True}
    assert result["rows"][0]["custom_fields"] == {"1": "CF1", "2": "CF2", "3": "CF3"}
    assert result["errors"] == []
    am_getter.assert_not_called()
    assert am.NewCDMJob.call_count == 0


def test_cdm_import_preview_handler_no_setting_uses_selected(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": None, "material_id": None},
    )
    gw = GatewayServer()
    result = gw._handler_cdm_import_preview({"csv": str(csv_file)})
    assert result["success"] is False
    assert result["setting"]["id"] == 1
    assert result["setting"]["name"] == "Fronty CSV"
    assert result["setting"]["create_job"] is True
    assert result["setting"]["selected"] is True
    assert len(result["field_map"]) == 5
    assert "job" in result
    assert result["job"] is None
    assert result["job_name"] == "order"
    assert result["config"] is None
    assert result["material"] is None
    assert result["items"] == 1
    assert result["rows"][0]["style"] == "P003"
    assert result["errors"] == [
        "job order: no material set (required for processing)",
        "cdm: no default configuration found",
    ]
    assert am.NewCDMJob.call_count == 0


def test_cdm_import_csv_handler_create_job_false_requires_job(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch, create_job=False)
    gw = GatewayServer()
    with pytest.raises(
        COMError,
        match="cdm: job is required \\(import setting 'Fronty CSV' does not create jobs\\)",
    ):
        gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert am.NewCDMJob.call_count == 0


def test_cdm_import_preview_handler_create_job_false_requires_job(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch, create_job=False)
    gw = GatewayServer()
    with pytest.raises(
        COMError,
        match="cdm: job is required \\(import setting 'Fronty CSV' does not create jobs\\)",
    ):
        gw._handler_cdm_import_preview({"csv": str(csv_file)})
    assert am.NewCDMJob.call_count == 0


def test_cdm_import_preview_handler_create_job_false_with_job_succeeds(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch, create_job=False)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": None, "material_id": None},
    )
    gw = GatewayServer()
    result = gw._handler_cdm_import_preview({"csv": str(csv_file), "job": "EXISTING"})
    assert result["success"] is True
    assert result["items"] == 1
    assert result["job_name"] == "EXISTING"
    assert result["job"] == "EXISTING"
    assert result["config"] is None
    assert result["errors"] == ["job EXISTING: no material set (required for processing)"]
    assert am.NewCDMJob.call_count == 0


def test_cdm_import_preview_handler_empty_job_string_requires_job(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch, create_job=False)
    gw = GatewayServer()
    with pytest.raises(
        COMError,
        match="cdm: job is required \\(import setting 'Fronty CSV' does not create jobs\\)",
    ):
        gw._handler_cdm_import_preview({"csv": str(csv_file), "job": ""})
    assert am.NewCDMJob.call_count == 0


def test_cdm_import_csv_handler_create_job_false_with_job_succeeds(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    detail = MagicMock()
    job.JobName = "X"
    job.AddCDMOrderDetail.return_value = detail
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job
    am.Jobs = jobs
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch, create_job=False)
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    result = gw._handler_cdm_import_csv({"csv": str(csv_file), "job": "X"})
    assert result == {
        "success": True,
        "job_name": "X",
        "items": 1,
        "material": None,
        "errors": ["job X: no material set (required for processing)"],
        "import_setting": "Fronty CSV",
    }
    am.NewCDMJob.assert_not_called()
    job.SaveToDatabase.assert_not_called()
    job.AddCDMOrderDetail.assert_called_once_with("P003")


def test_cdm_import_csv_handler_empty_job_string_requires_job(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch, create_job=False)
    gw = GatewayServer()
    with pytest.raises(
        COMError,
        match="cdm: job is required \\(import setting 'Fronty CSV' does not create jobs\\)",
    ):
        gw._handler_cdm_import_csv({"csv": str(csv_file), "job": ""})
    assert am.NewCDMJob.call_count == 0


def test_cdm_import_preview_handler_material_not_found(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(_MAPPED_CSV_ROW + "\n", encoding="utf-8")
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.import_settings", lambda: [_fake_import_setting()]
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {})
    am_getter = MagicMock()
    monkeypatch.setattr(gw, "_cdm_automation_manager", am_getter)
    result = gw._handler_cdm_import_preview({"csv": str(csv_file), "import_setting": 3})
    assert result["success"] is False
    assert result["errors"] == ["cdm: material not found: MDF_18"]
    assert result["material"] == "MDF_18"
    am_getter.assert_not_called()


def test_cdm_import_preview_handler_no_default_config(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": None, "material_id": 4},
    )
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF18 - 2800 x 2070": 4}
    )
    gw = GatewayServer()
    result = gw._handler_cdm_import_preview({"csv": str(csv_file)})
    assert result["success"] is False
    assert result["errors"] == ["cdm: no default configuration found"]
    assert result["config"] is None
    assert result["material"] == "MDF18 - 2800 x 2070"
    assert am.NewCDMJob.call_count == 0


def test_cdm_import_preview_handler_material_from_defaults(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    _mock_selected_import_setting(monkeypatch)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF18 - 2800 x 2070": 4}
    )
    gw = GatewayServer()
    result = gw._handler_cdm_import_preview({"csv": str(csv_file)})
    assert result["success"] is True
    assert result["errors"] == []
    assert result["config"] == "Fronty"
    assert result["material"] == "MDF18 - 2800 x 2070"
    assert am.NewCDMJob.call_count == 0


def test_cdm_import_csv_handler_no_selected_setting_lists_available(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    setting = _fake_import_setting()
    setting["selected"] = False
    monkeypatch.setattr("alphacam_cli.core.cdm_db.import_settings", lambda: [setting])
    gw = GatewayServer()
    with pytest.raises(
        COMError,
        match=(
            "cdm: no import setting selected; pass --import-setting or select one in "
            "Automation Manager \\(available: 3 'Fronty CSV'\\)"
        ),
    ):
        gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert am.NewCDMJob.call_count == 0


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


def test_cdm_order_details_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"job_name": "X", "door_type": "P1"}]
    monkeypatch.setattr("alphacam_cli.core.cdm_db.order_details", lambda job_name: rows)
    gw = GatewayServer()
    am_getter = MagicMock()
    monkeypatch.setattr(gw, "_cdm_automation_manager", am_getter)
    result = gw._handler_cdm_order_details({"job_name": "X"})
    assert result["order_details"] == rows
    assert result["job_name"] == "X"
    am_getter.assert_not_called()


def test_cdm_order_details_handler_no_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("alphacam_cli.core.cdm_db.order_details", lambda job_name: [])
    gw = GatewayServer()
    result = gw._handler_cdm_order_details({})
    assert result["order_details"] == []
    assert result["job_name"] is None


def test_cdm_door_paths_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"type_name": "T1", "path": "dir"}]
    monkeypatch.setattr("alphacam_cli.core.cdm_db.door_paths", lambda type_name: rows)
    gw = GatewayServer()
    result = gw._handler_cdm_door_paths({"type_name": "T1"})
    assert result["door_paths"] == rows
    assert result["type_name"] == "T1"


def test_cdm_materials_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"id": 1, "name": "MDF_18"}]
    monkeypatch.setattr("alphacam_cli.core.cdm_db.materials", lambda: rows)
    gw = GatewayServer()
    am_getter = MagicMock()
    monkeypatch.setattr(gw, "_cdm_automation_manager", am_getter)
    result = gw._handler_cdm_materials({})
    assert result["materials"] == rows
    am_getter.assert_not_called()


def test_cdm_configs_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"config_name": "Fronty"}]
    monkeypatch.setattr("alphacam_cli.core.cdm_db.configs", lambda show: rows)
    gw = GatewayServer()
    result = gw._handler_cdm_configs({"show": "all"})
    assert result["configs"] == rows
    assert result["show"] == "all"


def test_handler_cdm_configs_show_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []

    def fake_configs(show: str | None) -> list[dict[str, Any]]:
        calls.append(show)
        return [{"config_name": "Fronty"}]

    monkeypatch.setattr("alphacam_cli.core.cdm_db.configs", fake_configs)
    gw = GatewayServer()
    result = gw._handler_cdm_configs({"show": ""})
    assert calls == [""]
    assert result == {"configs": [{"config_name": "Fronty"}], "show": ""}


def test_cdm_lookups_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    lookups = {"edge_types": [{"id": 1, "label": "Prosty"}]}
    monkeypatch.setattr("alphacam_cli.core.cdm_db.lookups", lambda: lookups)
    gw = GatewayServer()
    result = gw._handler_cdm_lookups({})
    assert result["lookups"] == lookups


def test_cdm_order_details_handler_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(job_name: str | None) -> list[dict[str, Any]]:
        raise RuntimeError("db locked")  # noqa: TRY003

    monkeypatch.setattr("alphacam_cli.core.cdm_db.order_details", boom)
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: read order details failed: db locked"):
        gw._handler_cdm_order_details({"job_name": "X"})


def test_cdm_import_csv_handler_setting_not_found(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003;1;500;500\n", encoding="utf-8")
    gw = GatewayServer()
    monkeypatch.setattr("alphacam_cli.core.cdm_db.import_settings", lambda: [])
    with pytest.raises(COMError, match="cdm: import settings not found: 3"):
        gw._handler_cdm_import_csv({"csv": str(csv_file), "import_setting": 3})


def test_cdm_import_csv_handler_mapped_job_lookup(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    detail = MagicMock()
    am.Jobs.Count = 0
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.find_cdm_job", lambda am, name: job if name == "X" else None
    )
    job.AddCDMOrderDetail.return_value = detail
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(_MAPPED_CSV_ROW + "\n", encoding="utf-8")
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.import_settings", lambda: [_fake_import_setting()]
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 2})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", lambda job_name, mid: True)
    result = gw._handler_cdm_import_csv({"csv": str(csv_file), "job": "X", "import_setting": 3})
    assert result["success"] is True
    assert result["job_name"] == "X"
    assert result["items"] == 1
    assert result["import_setting"] == "Fronty CSV"
    am.NewCDMJob.assert_not_called()
    job.AddCDMOrderDetail.assert_called_once_with("P003")
    assert detail.CSV_CustomerName == "Klient A"


def test_cdm_import_csv_handler_setter_warning_keeps_detail(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    type(detail).CSV_CustomerName = mock.PropertyMock(side_effect=RuntimeError("boom"))
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(_MAPPED_CSV_ROW + "\n", encoding="utf-8")
    gw = GatewayServer()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.import_settings", lambda: [_fake_import_setting()]
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 2})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", lambda job_name, mid: True)
    result = gw._handler_cdm_import_csv({"csv": str(csv_file), "import_setting": 3})
    assert result["success"] is True
    assert result["items"] == 1
    assert any("CSV_CustomerName failed: boom" in e for e in result["errors"])
    detail.SaveToDatabase.assert_called_once_with()


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
    server_app.manifest_read.assert_called_once_with("Fronty", "MDF_18", r"C:\Reports\Data")


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
    server_app.manifest_read.assert_called_once_with("Fronty", None, None)


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
    machine = {
        "psexec": "C:/temp/PsExec64.exe",
        "psexec_args": ["-accepteula", "-i", "1", "-s"],
        "cscript": "cscript",
        "use_shell": False,
    }
    gw = GatewayServer()
    result = gw._handler_process_cdm_job(
        {
            "job_name": "JOB-001",
            "machine": machine,
            "timeout_seconds": 600,
            "output_root": "C:/out",
        }
    )
    assert result == {"success": True, "job_name": "JOB-001", "processed": True}
    server_app.process_cdm_job.assert_called_once_with(
        job_name="JOB-001",
        machine=machine,
        timeout_seconds=600,
        output_root="C:/out",
    )


def test_process_cdm_job_handler_invalid_machine_type(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: machine must be a dict"):
        gw._handler_process_cdm_job({"job_name": "JOB-001", "machine": "PsExec64.exe"})
    server_app.process_cdm_job.assert_not_called()


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


def test_process_cdm_job_handler_machine_sanitized(server_app: MagicMock) -> None:
    server_app.process_cdm_job.return_value = {"success": True}
    gw = GatewayServer()
    result = gw._handler_process_cdm_job(
        {
            "job_name": "JOB-001",
            "machine": {
                "psexec": "C:/temp/PsExec64.exe",
                "psexec_args": ["-accepteula", "-i", "1", "-s"],
                "use_shell": True,
                "evil": "run",
            },
        }
    )
    assert result == {"success": True}
    server_app.process_cdm_job.assert_called_once_with(
        job_name="JOB-001",
        machine={
            "psexec": "C:/temp/PsExec64.exe",
            "psexec_args": ["-accepteula", "-i", "1", "-s"],
            "use_shell": False,
        },
    )


def test_process_cdm_job_handler_machine_invalid_psexec_args(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"cdm: machine.psexec_args must be a list of str"):
        gw._handler_process_cdm_job(
            {"job_name": "JOB-001", "machine": {"psexec_args": ["ok", 123]}}
        )
    server_app.process_cdm_job.assert_not_called()


def test_process_cdm_job_handler_machine_invalid_psexec(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"cdm: machine.psexec must be a str"):
        gw._handler_process_cdm_job({"job_name": "JOB-001", "machine": {"psexec": 123}})
    server_app.process_cdm_job.assert_not_called()


def test_process_cdm_job_handler_invalid_output_root_type(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: output_root must be a str"):
        gw._handler_process_cdm_job({"job_name": "JOB-001", "output_root": 123})
    server_app.process_cdm_job.assert_not_called()


def test_process_cdm_job_handler_method(server_app: MagicMock) -> None:
    server_app.process_cdm_job.return_value = {
        "success": True,
        "job_name": "JOB-001",
        "processed": True,
    }
    gw = GatewayServer()
    result = gw._handler_process_cdm_job({"job_name": "JOB-001", "method": "vbs"})
    assert result == {"success": True, "job_name": "JOB-001", "processed": True}
    server_app.process_cdm_job.assert_called_once_with(job_name="JOB-001", method="vbs")


def test_process_cdm_job_handler_invalid_method_type(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: method must be a str"):
        gw._handler_process_cdm_job({"job_name": "JOB-001", "method": 123})
    server_app.process_cdm_job.assert_not_called()


def test_process_cdm_job_handler_invalid_method_value(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: method must be 'inproc' or 'vbs'"):
        gw._handler_process_cdm_job({"job_name": "JOB-001", "method": "xyz"})
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


def test_process_cdm_job_handler_watchdog_min_budget(server_app: MagicMock) -> None:
    server_app.process_cdm_job.return_value = {"success": True}
    gw = GatewayServer()
    watchdog = MagicMock()
    gw._watchdog_arm = MagicMock(return_value=watchdog)
    gw._handler_process_cdm_job({"job_name": "JOB-001"})
    assert gw._watchdog_arm.call_args.args[0] == 90.0
    watchdog.cancel.assert_called_once()


def test_process_cdm_job_handler_watchdog_cancelled_on_error(server_app: MagicMock) -> None:
    server_app.process_cdm_job.side_effect = RuntimeError("cdm: boom")
    gw = GatewayServer()
    watchdog = MagicMock()
    gw._watchdog_arm = MagicMock(return_value=watchdog)
    with pytest.raises(COMError, match="cdm: boom"):
        gw._handler_process_cdm_job({"job_name": "JOB-001"})
    watchdog.cancel.assert_called_once()
