from __future__ import annotations

import pathlib
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
    nd.AddSheet.assert_called_once_with(sheet_geo, "MDF", 0.25, 2)
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
