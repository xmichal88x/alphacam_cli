from __future__ import annotations

import sys
import types
from typing import Any
from unittest import mock
from unittest.mock import MagicMock

import pytest

from alphacam_cli.core.application import Application


def _mock_addin_com(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """Install fake win32com/pythoncom modules for the add-ins interface.

    Returns (gencache, pythoncom, client_module, addins_interface).
    """
    gencache = MagicMock(name="gencache")
    gencache.EnsureDispatch.return_value = "app-dispatch"

    client_mod = MagicMock(name="win32com.client")
    client_mod.gencache = gencache

    win32com_mod = types.ModuleType("win32com")
    win32com_mod.client = client_mod  # type: ignore[attr-defined]

    pythoncom_mod = MagicMock(name="pythoncom")
    pythoncom_mod.MakeIID.return_value = "addins-clsid"
    pythoncom_mod.CLSCTX_ALL = 0x10
    pythoncom_mod.IID_IDispatch = "iid-idispatch"

    addins_interface = MagicMock(name="AddInsInterface")
    client_mod.Dispatch.return_value = addins_interface

    monkeypatch.setitem(sys.modules, "win32com", win32com_mod)
    monkeypatch.setitem(sys.modules, "win32com.client", client_mod)
    monkeypatch.setitem(sys.modules, "win32com.client.gencache", gencache)
    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom_mod)
    return gencache, pythoncom_mod, client_mod, addins_interface


def test_get_addins_connects_interface(monkeypatch: pytest.MonkeyPatch) -> None:
    gencache, pythoncom_mod, client_mod, addins_interface = _mock_addin_com(monkeypatch)
    addins = MagicMock(name="IAddIns")
    addins_interface.GetAddInsInterface.return_value = addins
    pythoncom_mod.CoCreateInstance.return_value = "co-created-instance"

    ac = Application(MagicMock())
    result = ac.get_addins()

    assert result is addins
    gencache.EnsureModule.assert_any_call("{D216BAAC-A717-4793-92D3-1AE37AE3AC2E}", 0, 1, 0)
    gencache.EnsureModule.assert_any_call("{A87DD4DB-67C9-4F1B-BC79-A71EE8C7D1E5}", 0, 1, 0)
    gencache.EnsureDispatch.assert_called_once_with("Ar5axaps.Application")
    pythoncom_mod.MakeIID.assert_called_once_with("{39BFE38A-D3E4-43EA-89D0-584C776B97A9}")
    client_mod.Dispatch.assert_called_once_with("co-created-instance")
    addins_interface.GetAddInsInterface.assert_called_once_with("app-dispatch")


def test_get_addins_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    gencache, pythoncom_mod, client_mod, addins_interface = _mock_addin_com(monkeypatch)
    addins = MagicMock(name="IAddIns")
    addins_interface.GetAddInsInterface.return_value = addins

    ac = Application(MagicMock())
    assert ac.get_addins() is addins
    assert ac.get_addins() is addins

    gencache.EnsureDispatch.assert_called_once()
    addins_interface.GetAddInsInterface.assert_called_once()


def test_get_addins_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    gencache, pythoncom_mod, client_mod, addins_interface = _mock_addin_com(monkeypatch)
    gencache.EnsureModule.side_effect = RuntimeError("typelib unavailable")

    ac = Application(MagicMock())
    with pytest.raises(RuntimeError, match="Failed to connect to AlphaCAM add-ins"):
        ac.get_addins()


def _make_addins_mock(monkeypatch: pytest.MonkeyPatch, addins: MagicMock) -> None:
    _, _, _, addins_interface = _mock_addin_com(monkeypatch)
    addins_interface.GetAddInsInterface.return_value = addins


def test_get_reports_addin(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    addins.GetNewReportsAddIn.return_value = "reports-addin"
    _make_addins_mock(monkeypatch, addins)

    ac = Application(MagicMock())
    assert ac.get_reports_addin() == "reports-addin"
    addins.GetNewReportsAddIn.assert_called_once_with()


def test_get_nc_output_manager_addin(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    addins.GetNcOutputManagerAddIn.return_value = "ncman-addin"
    _make_addins_mock(monkeypatch, addins)

    ac = Application(MagicMock())
    assert ac.get_nc_output_manager_addin() == "ncman-addin"
    addins.GetNcOutputManagerAddIn.assert_called_once_with()


def test_get_auto_styles_addin(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    addins.GetAutoStylesAddIn.return_value = "astyles-addin"
    _make_addins_mock(monkeypatch, addins)

    ac = Application(MagicMock())
    assert ac.get_auto_styles_addin() == "astyles-addin"
    addins.GetAutoStylesAddIn.assert_called_once_with()


def test_reports_create(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    _make_addins_mock(monkeypatch, addins)
    drw = MagicMock(name="Drawing")
    app_mock = MagicMock()
    app_mock.ActiveDrawing = drw

    ac = Application(app_mock)
    result = ac.reports_create()

    assert result == {"success": True, "job": "ok", "active_drawing": True}
    reports_mock = addins.GetNewReportsAddIn.return_value
    reports_mock.CreateReportsJob.assert_called_once_with(drw, False, True)
    reports_mock.CreateReportsJob.return_value.CreateReports.assert_called_once_with()


def test_reports_create_no_drawing(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    _make_addins_mock(monkeypatch, addins)
    app_mock = MagicMock()
    app_mock.ActiveDrawing = None

    ac = Application(app_mock)
    result = ac.reports_create()

    assert result == {"success": True, "job": "ok", "active_drawing": False}
    reports_mock = addins.GetNewReportsAddIn.return_value
    reports_mock.CreateReportsJob.assert_called_once_with(None, False, True)
    reports_mock.CreateReportsJob.return_value.CreateReports.assert_called_once_with()


def test_nc_configs(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    _make_addins_mock(monkeypatch, addins)
    coll: Any = (
        addins.GetNcOutputManagerAddIn.return_value.GetOutputConfigurationsCollection.return_value
    )
    coll.Count = 2
    coll.Item.side_effect = lambda i: [MagicMock(Name="Alpha"), MagicMock(Name="Beta")][i - 1]

    ac = Application(MagicMock())
    result = ac.nc_configs()

    assert result == {"count": 2, "configs": ["Alpha", "Beta"]}
    assert coll.Item.call_args_list[0].args == (1,)
    assert coll.Item.call_args_list[1].args == (2,)


class _NoNameItem:
    @property
    def Name(self) -> str:  # noqa: N802
        raise AttributeError("no Name property")  # noqa: TRY003


def test_nc_configs_item_name_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    _make_addins_mock(monkeypatch, addins)
    coll: Any = (
        addins.GetNcOutputManagerAddIn.return_value.GetOutputConfigurationsCollection.return_value
    )
    coll.Count = 2
    coll.Item.side_effect = lambda i: [_NoNameItem(), MagicMock(Name="Beta")][i - 1]

    ac = Application(MagicMock())
    result = ac.nc_configs()

    assert result == {"count": 2, "configs": ["config_1", "Beta"]}


def test_auto_style_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    _make_addins_mock(monkeypatch, addins)

    ac = Application(MagicMock())
    result = ac.auto_style_apply(r"C:\styles\auto.style")

    assert result == {"success": True, "file": r"C:\styles\auto.style"}
    addins.GetAutoStylesAddIn.return_value.Apply.assert_called_once_with(r"C:\styles\auto.style")


def test_auto_style_apply_invalid_file(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    _make_addins_mock(monkeypatch, addins)
    addins.GetAutoStylesAddIn.return_value.Apply.side_effect = OSError(
        "Nierozpoznany lub nieprawidłowy plik AutoStylu."
    )

    ac = Application(MagicMock())
    with pytest.raises(RuntimeError, match="invalid or unrecognized AutoStyles file"):
        ac.auto_style_apply("x")


def test_auto_style_apply_other_error(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    _make_addins_mock(monkeypatch, addins)
    addins.GetAutoStylesAddIn.return_value.Apply.side_effect = RuntimeError("boom")

    ac = Application(MagicMock())
    with pytest.raises(
        RuntimeError,
        match="failed to apply auto-style 'x': invalid or unrecognized AutoStyles file",
    ):
        ac.auto_style_apply("x")


@pytest.mark.parametrize(
    ("layer_map", "expected"),
    [
        ("KONTUR:1,2;EDGE_F45:3", {"KONTUR": [1, 2], "EDGE_F45": [3]}),
        ("KONTUR:1", {"KONTUR": [1]}),
        ("KONTUR:", {"KONTUR": []}),
        (" A : 1, 2 ; B:3 ", {"A": [1, 2], "B": [3]}),
    ],
)
def test_parse_layer_map(layer_map: str, expected: dict[str, list[int]]) -> None:
    from alphacam_cli.core.application import _parse_layer_map

    assert _parse_layer_map(layer_map) == expected


@pytest.mark.parametrize("bad", ["KONTUR1,2", ":3", "KONTUR:x"])
def test_parse_layer_map_invalid(bad: str) -> None:
    from alphacam_cli.core.application import _parse_layer_map

    with pytest.raises(ValueError):
        _parse_layer_map(bad)


def test_machining_pipeline_full(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    _make_addins_mock(monkeypatch, addins)
    drw = MagicMock(name="Drawing")
    geo1 = MagicMock(name="geo1")
    geo2 = MagicMock(name="geo2")
    drw.geometries.return_value = [geo1, geo2]
    drw.geometries_count = 2
    drw.tool_paths_count = 4
    layer_contour = MagicMock(name="layer-KONTUR")
    layer_edge = MagicMock(name="layer-EDGE_F45")
    drw.create_layer.side_effect = [layer_contour, layer_edge]
    monkeypatch.setattr(Application, "get_active_drawing", lambda self: drw)

    ac = Application(MagicMock())
    result = ac.machining_pipeline(
        agq=r"C:\ALPHACAM\LICOMDIR\Queries\Menadżer_Warstw_Fronty.agq",
        ara=r"C:\ALPHACAM\LICOMDIR\Styles\Fronty_AutoStyl.ara",
        layer_map="KONTUR:1,2;EDGE_F45:1",
    )

    assert result == {"success": True, "geometries_count": 2, "tool_paths_count": 4}
    assert drw.create_layer.call_args_list == [mock.call("KONTUR"), mock.call("EDGE_F45")]
    assert geo1.set_layer.call_args_list == [mock.call(layer_contour), mock.call(layer_edge)]
    geo2.set_layer.assert_called_once_with(layer_contour)
    drw.run_query.assert_called_once_with(
        r"C:\ALPHACAM\LICOMDIR\Queries\Menadżer_Warstw_Fronty.agq"
    )
    addins.GetAutoStylesAddIn.return_value.Apply.assert_called_once_with(
        r"C:\ALPHACAM\LICOMDIR\Styles\Fronty_AutoStyl.ara"
    )


def test_machining_pipeline_apply_only(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    _make_addins_mock(monkeypatch, addins)
    drw = MagicMock(name="Drawing")
    drw.geometries_count = 1
    drw.tool_paths_count = 2
    monkeypatch.setattr(Application, "get_active_drawing", lambda self: drw)

    ac = Application(MagicMock())
    result = ac.machining_pipeline(ara=r"C:\styles\auto.ara")

    assert result == {"success": True, "geometries_count": 1, "tool_paths_count": 2}
    drw.create_layer.assert_not_called()
    drw.run_query.assert_not_called()
    addins.GetAutoStylesAddIn.return_value.Apply.assert_called_once_with(r"C:\styles\auto.ara")


def test_machining_pipeline_no_drawing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Application, "get_active_drawing", lambda self: None)

    ac = Application(MagicMock())
    with pytest.raises(RuntimeError, match="No active drawing"):
        ac.machining_pipeline(ara="x")


def test_machining_pipeline_ara_required(monkeypatch: pytest.MonkeyPatch) -> None:
    drw = MagicMock(name="Drawing")
    app_mock = MagicMock()
    app_mock.ActiveDrawing = drw

    ac = Application(app_mock)
    with pytest.raises(RuntimeError, match="ara is required"):
        ac.machining_pipeline()


def test_machining_pipeline_index_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    _make_addins_mock(monkeypatch, addins)
    drw = MagicMock(name="Drawing")
    geo = MagicMock(name="geo")
    drw.geometries.return_value = [geo]
    drw.geometries_count = 1
    layer_contour = MagicMock(name="layer-KONTUR")
    drw.create_layer.return_value = layer_contour
    monkeypatch.setattr(Application, "get_active_drawing", lambda self: drw)

    ac = Application(MagicMock())
    with pytest.raises(RuntimeError, match="geometry index 5 out of range"):
        ac.machining_pipeline(ara="x", layer_map="KONTUR:5")
