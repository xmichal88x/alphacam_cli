from __future__ import annotations

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
