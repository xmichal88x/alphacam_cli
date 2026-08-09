from __future__ import annotations

import pathlib
import sys
import types
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
    import alphacam_cli.gateway.server as server_module

    drw = MagicMock()
    drw.geometries_count = 1
    server_app.get_active_drawing.return_value = drw
    tool_path = r"C:\ALPHACAM\LICOMDAT\MTools.Alp\Flat - 10mm.art"
    monkeypatch.setattr(server_module.os.path, "exists", lambda p: p == tool_path)
    gw = GatewayServer()
    result = gw._handler_apply_style(
        {"style": r"C:\ALPHACAM\LICOMDIR\Styles\Edge.ary", "tool": tool_path}
    )
    assert result["success"] is True
    server_app.select_tool.assert_called_once_with(tool_path)


def test_apply_style_handler_tool_by_name(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    import alphacam_cli.gateway.server as server_module

    drw = MagicMock()
    drw.geometries_count = 1
    server_app.get_active_drawing.return_value = drw
    files = [r"C:\ALPHACAM\LICOMDAT\MTools.Alp\Flat - 10mm.art"]
    server_app.find_tool_files.return_value = files
    monkeypatch.setattr(server_module.os.path, "exists", lambda p: False)
    gw = GatewayServer()
    result = gw._handler_apply_style(
        {"style": r"C:\ALPHACAM\LICOMDIR\Styles\Edge.ary", "tool": "Flat - 10mm"}
    )
    assert result["success"] is True
    server_app.select_tool.assert_called_once_with(files[0])


def test_apply_style_handler_tool_partial_path(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    import alphacam_cli.gateway.server as server_module

    drw = MagicMock()
    drw.geometries_count = 1
    server_app.get_active_drawing.return_value = drw
    tool_path = r"C:\ALPHACAM\LICOMDAT\RTools.Alp\Reichenbacher\Ball 10mm 2F.art"
    server_app.find_tool_files.return_value = [tool_path]
    monkeypatch.setattr(server_module.os.path, "exists", lambda p: False)
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
    import alphacam_cli.gateway.server as server_module

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
    monkeypatch.setattr(server_module.os.path, "getsize", lambda p: sizes[p])
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
    import alphacam_cli.gateway.server as server_module

    post_path = "C:/ALPHACAM/LICOMDAT/RPosts.Alp/fanuc.arp"
    server_app.find_post_files.return_value = [post_path]
    monkeypatch.setattr(server_module.os.path, "exists", lambda p: False)
    gw = GatewayServer()
    result = gw._handler_select_post({"name": "fanuc"})
    assert result == {"success": True}
    server_app.select_post.assert_called_once_with(post_path)


def test_select_post_handler_not_found(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    import alphacam_cli.gateway.server as server_module

    server_app.find_post_files.return_value = []
    monkeypatch.setattr(server_module.os.path, "exists", lambda p: False)
    gw = GatewayServer()
    with pytest.raises(COMError, match="No post matching 'missing'"):
        gw._handler_select_post({"name": "missing"})
    server_app.select_post.assert_not_called()


def test_select_post_handler_full_path(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    import alphacam_cli.gateway.server as server_module

    post_path = "C:/ALPHACAM/LICOMDAT/RPosts.Alp/fanuc.arp"
    monkeypatch.setattr(server_module.os.path, "exists", lambda p: p == post_path)
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


def test_drawing_parametric_handler_machines(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.geometries_count = 2
    drw.tool_paths_count = 2
    server_app.create_temp_drawing.return_value = drw
    outer = MagicMock()
    inner = MagicMock()
    outer.tool_in_out = -1
    inner.tool_in_out = 1
    drw.create_panel.return_value = (outer, inner)
    from alphacam_cli.core.machining import MillData

    md = MillData(MagicMock())
    server_app.create_mill_data.return_value = md
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
    server_app.select_tool.assert_called_once_with("Flat - 20mm")
    assert md._md.SafeRapidLevel == 10
    assert md._md.RapidDownTo == 2
    assert md._md.MaterialTop == 0
    assert md._md.FinalDepth == -19
    assert md._md.SpindleSpeed == 18000
    assert md._md.CutFeed == 4000
    assert md._md.DownFeed == 1500
    assert md._md.RoughFinish.call_count == 2
    assert outer.selected is False
    assert inner.selected is False
    assert result["tool_paths_count"] == 2


def test_drawing_parametric_handler_invalid_size(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="width and height must be positive"):
        gw._handler_drawing_parametric({"width": 0, "height": 400})


def test_drawing_parametric_handler_positive_depth(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="depth must be negative"):
        gw._handler_drawing_parametric({"width": 800, "height": 400, "depth": 5})


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

    assert result == {"count": 1, "success": True}
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
    assert nl.AddFile.return_value.Required == 1
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


def test_machining_pipeline_handler(server_app: MagicMock) -> None:
    server_app.machining_pipeline.return_value = {
        "success": True,
        "geometries_count": 2,
        "tool_paths_count": 4,
    }
    gw = GatewayServer()
    result = gw._handler_machining_pipeline(
        {
            "agq": r"C:\ALPHACAM\LICOMDIR\Queries\test.agq",
            "ara": r"C:\ALPHACAM\LICOMDIR\Styles\Fronty_AutoStyl.ara",
            "layer_map": "KONTUR:1,2;EDGE_F45:3",
        }
    )
    assert result == {"success": True, "geometries_count": 2, "tool_paths_count": 4}
    server_app.machining_pipeline.assert_called_once_with(
        agq=r"C:\ALPHACAM\LICOMDIR\Queries\test.agq",
        ara=r"C:\ALPHACAM\LICOMDIR\Styles\Fronty_AutoStyl.ara",
        layer_map="KONTUR:1,2;EDGE_F45:3",
    )


def test_machining_pipeline_handler_optional_params(server_app: MagicMock) -> None:
    server_app.machining_pipeline.return_value = {"success": True}
    gw = GatewayServer()
    gw._handler_machining_pipeline({"ara": r"C:\styles\auto.ara"})
    server_app.machining_pipeline.assert_called_once_with(
        agq=None, ara=r"C:\styles\auto.ara", layer_map=None
    )


def test_machining_pipeline_handler_missing_ara(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="ara is required"):
        gw._handler_machining_pipeline({})
    server_app.machining_pipeline.assert_not_called()


def test_machining_pipeline_handler_failure(server_app: MagicMock) -> None:
    server_app.machining_pipeline.side_effect = RuntimeError("boom")
    gw = GatewayServer()
    with pytest.raises(COMError, match=r"machining pipeline failed: boom"):
        gw._handler_machining_pipeline({"ara": r"C:\styles\auto.ara"})


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
    return ai, addins, am


def _mock_vdb5_run(
    monkeypatch: pytest.MonkeyPatch, stdout: str = "[]", returncode: int = 0
) -> MagicMock:
    run = MagicMock(return_value=types.SimpleNamespace(stdout=stdout, returncode=returncode))
    monkeypatch.setattr("subprocess.run", run)
    return run


def test_run_cdm_handler(server_app: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    gw = GatewayServer()
    result = gw._handler_run_cdm(
        {
            "job_name": "JOB-001",
            "type_name": "Typ Frontu 1",
            "width": 500,
            "length": 320,
            "quantity": 2,
            "bypass_nest": True,
        }
    )
    assert result == {
        "success": True,
        "job_name": "JOB-001",
        "type_name": "Typ Frontu 1",
        "width": 500.0,
        "length": 320.0,
        "quantity": 2,
    }
    assert job.JobName == "JOB-001"
    job.SaveToDatabase.assert_called_once_with()
    job.AddCDMOrderDetail.assert_called_once_with("Typ Frontu 1")
    assert detail.Width == 500.0
    assert detail.Length == 320.0
    assert detail.Quantity == 2
    assert detail.ByPassNest is True
    detail.SaveToDatabase.assert_called_once_with()


def test_run_cdm_handler_defaults(server_app: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    gw = GatewayServer()
    result = gw._handler_run_cdm({"job_name": "JOB-001", "type_name": "Typ Frontu 1"})
    assert result["width"] == 400.0
    assert result["length"] == 300.0
    assert result["quantity"] == 1
    assert detail.ByPassNest is False


def test_run_cdm_handler_missing_job_name(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: job_name is required"):
        gw._handler_run_cdm({"type_name": "Typ Frontu 1"})


def test_run_cdm_handler_missing_type_name(server_app: MagicMock) -> None:
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: type_name is required"):
        gw._handler_run_cdm({"job_name": "JOB-001"})


def test_run_cdm_handler_am_unavailable(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, addins, _ = _mock_cdm_com(monkeypatch)
    addins.GetAutomationManagerAddInGUI.side_effect = RuntimeError("no license")
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: automation manager unavailable"):
        gw._handler_run_cdm({"job_name": "JOB-001", "type_name": "Typ Frontu 1"})


def test_run_cdm_handler_job_failed(server_app: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    am.NewCDMJob.side_effect = RuntimeError("db locked")
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: create job failed: db locked"):
        gw._handler_run_cdm({"job_name": "JOB-001", "type_name": "Typ Frontu 1"})


def test_run_cdm_handler_door_type_not_found(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    job.AddCDMOrderDetail.side_effect = RuntimeError("FOREIGN KEY constraint failed")
    am.NewCDMJob.return_value = job
    am.Jobs.Count = 0
    gw = GatewayServer()
    with pytest.raises(COMError, match="cdm: door type not found: XYZ"):
        gw._handler_run_cdm({"job_name": "JOB-001", "type_name": "XYZ"})


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
    gw = GatewayServer()
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result == {
        "success": True,
        "job_name": "order",
        "items": 1,
        "material": None,
        "errors": ["job order: no material set (required for processing)"],
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
    gw = GatewayServer()
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
    gw = GatewayServer()
    result = gw._handler_cdm_import_csv({"csv": str(csv_file), "config": "Fronty"})
    assert result["success"] is True
    am.ConfigurationSettings.GetByName.assert_called_once_with("Fronty")
    assert job.ConfigurationSetting == am.ConfigurationSettings.GetByName.return_value


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
    gw = GatewayServer()
    result = gw._handler_cdm_import_csv({"csv": str(csv_file), "job": "X"})
    assert result == {
        "success": True,
        "job_name": "X",
        "items": 1,
        "material": None,
        "errors": ["job X: no material set (required for processing)"],
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
    gw = GatewayServer()
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
    gw = GatewayServer()
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
    gw = GatewayServer()
    gw._sheet_materials = lambda: {"MDF_18": 3}  # type: ignore[method-assign]
    _mock_vdb5_run(monkeypatch, stdout="rows: 1")
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
    gw = GatewayServer()
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is False
    assert result["items"] == 0
    assert any("door type not found: XYZ" in e for e in result["errors"])


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
    gw = GatewayServer()
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
    gw = GatewayServer()
    gw._sheet_materials = lambda: {"MDF": 7}  # type: ignore[method-assign]
    _mock_vdb5_run(monkeypatch, stdout="rows: 1")
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is True
    assert result["items"] == 1
    assert result["material"] == "MDF"
    assert any("expected at least 5 columns" in e for e in result["errors"])


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
    gw = GatewayServer()
    gw._sheet_materials = lambda: {"MDF_18": 2}  # type: ignore[method-assign]
    run = _mock_vdb5_run(monkeypatch, stdout="rows: 1")
    result = gw._handler_cdm_import_csv({"csv": str(csv_file)})
    assert result["success"] is True
    assert result["job_name"] == "order"
    assert result["items"] == 2
    assert result["material"] == "MDF_18"
    assert result["errors"] == []
    assert run.call_count == 1
    args, _ = run.call_args
    assert "-JobName" in args[0]
    assert args[0][args[0].index("-JobName") + 1] == "order"
    assert "-MaterialID" in args[0]
    assert args[0][args[0].index("-MaterialID") + 1] == "2"


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
    gw = GatewayServer()
    gw._sheet_materials = lambda: {"MDF_18": 3, "Material 3 - 2440 x 1220": 5}  # type: ignore[method-assign]
    run = _mock_vdb5_run(monkeypatch, stdout="rows: 1")
    result = gw._handler_cdm_import_csv(
        {"csv": str(csv_file), "material": "Material 3 - 2440 x 1220"}
    )
    assert result["material"] == "Material 3 - 2440 x 1220"
    assert result["errors"] == []
    args, _ = run.call_args
    assert args[0][args[0].index("-JobName") + 1] == "order"
    assert args[0][args[0].index("-MaterialID") + 1] == "5"


def test_cdm_import_csv_handler_material_not_found(
    server_app: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _, _, am = _mock_cdm_com(monkeypatch)
    job = MagicMock()
    am.NewCDMJob.return_value = job
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0\n", encoding="utf-8")
    gw = GatewayServer()
    gw._sheet_materials = lambda: {}  # type: ignore[method-assign]
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
    gw = GatewayServer()
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
