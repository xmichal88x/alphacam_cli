from __future__ import annotations

import os
import sys
import types
from typing import Any
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

    app_dispatch = MagicMock(name="app-dispatch")
    ac = Application(app_dispatch)
    result = ac.get_addins()

    assert result is addins
    gencache.EnsureModule.assert_any_call("{D216BAAC-A717-4793-92D3-1AE37AE3AC2E}", 0, 1, 0)
    gencache.EnsureModule.assert_any_call("{A87DD4DB-67C9-4F1B-BC79-A71EE8C7D1E5}", 0, 1, 0)
    gencache.EnsureDispatch.assert_not_called()
    pythoncom_mod.MakeIID.assert_called_once_with("{39BFE38A-D3E4-43EA-89D0-584C776B97A9}")
    client_mod.Dispatch.assert_called_once_with("co-created-instance")
    addins_interface.GetAddInsInterface.assert_called_once_with(app_dispatch)


def test_get_addins_fallback_on_interface_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    gencache, pythoncom_mod, client_mod, addins_interface = _mock_addin_com(monkeypatch)
    addins = MagicMock(name="IAddIns")
    addins_interface.GetAddInsInterface.side_effect = [RuntimeError("boom"), addins]
    pythoncom_mod.CoCreateInstance.return_value = "co-created-instance"

    app_dispatch = MagicMock(name="app-dispatch")
    ac = Application(app_dispatch)
    result = ac.get_addins()

    assert result is addins
    gencache.EnsureDispatch.assert_called_once_with("Ar5axaps.Application")
    assert addins_interface.GetAddInsInterface.call_args_list[0].args == (app_dispatch,)
    assert addins_interface.GetAddInsInterface.call_args_list[1].args == ("app-dispatch",)


def test_get_addins_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    gencache, pythoncom_mod, client_mod, addins_interface = _mock_addin_com(monkeypatch)
    addins = MagicMock(name="IAddIns")
    addins_interface.GetAddInsInterface.return_value = addins

    ac = Application(MagicMock())
    assert ac.get_addins() is addins
    assert ac.get_addins() is addins

    gencache.EnsureDispatch.assert_not_called()
    addins_interface.GetAddInsInterface.assert_called_once()


def test_get_addins_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    gencache, pythoncom_mod, client_mod, addins_interface = _mock_addin_com(monkeypatch)
    gencache.EnsureModule.side_effect = RuntimeError("typelib unavailable")

    ac = Application(MagicMock())
    with pytest.raises(RuntimeError, match="Failed to connect to AlphaCAM add-ins"):
        ac.get_addins()


def test_get_cdm_automation_manager_retries_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gencache, pythoncom_mod, client_mod, addins_interface = _mock_addin_com(monkeypatch)
    addins = MagicMock(name="IAddIns")
    am = MagicMock(name="AutomationManager")
    pythoncom_mod.CoCreateInstance.return_value = "co-created-instance"
    addins_interface.GetAddInsInterface.return_value = addins
    addins.GetAutomationManagerAddInGUI.return_value = am
    gencache.EnsureDispatch.side_effect = [
        RuntimeError("first"),
        RuntimeError("second"),
        "app-dispatch",
    ]
    monkeypatch.setattr("alphacam_cli.core.application.time.sleep", lambda _: None)

    ac = Application(MagicMock())
    result = ac.get_cdm_automation_manager()

    assert result is am
    assert gencache.EnsureDispatch.call_count == 3


def test_get_cdm_automation_manager_retries_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gencache, _, _, _ = _mock_addin_com(monkeypatch)
    gencache.EnsureDispatch.side_effect = RuntimeError("down")
    monkeypatch.setattr("alphacam_cli.core.application.time.sleep", lambda _: None)

    ac = Application(MagicMock())
    with pytest.raises(RuntimeError, match="cdm: automation manager unavailable"):
        ac.get_cdm_automation_manager()
    assert gencache.EnsureDispatch.call_count == 3


def _make_addins_mock(monkeypatch: pytest.MonkeyPatch, addins: MagicMock) -> None:
    _, _, _, addins_interface = _mock_addin_com(monkeypatch)
    addins_interface.GetAddInsInterface.return_value = addins


def _mock_reports_settings(
    monkeypatch: pytest.MonkeyPatch,
    licomdir: str,
    *,
    primary_exists: bool = True,
) -> str:
    """Mock the filesystem so reports_create resolves the settings directory.

    ``licomdir`` is the AlphaCAM root (``LicomdirPath``), as on the machine.
    Returns the resolved settings directory (LICOMDIR\\Reports\\Settings when
    ``primary_exists``, else the Reports\\Settings fallback).
    """
    primary = os.path.join(licomdir, "LICOMDIR", "Reports", "Settings")
    fallback = os.path.join(licomdir, "Reports", "Settings")
    settings_dir = primary if primary_exists else fallback
    monkeypatch.setattr(
        "alphacam_cli.core.application.os.path.isdir",
        lambda path: path == settings_dir,
    )
    monkeypatch.setattr(
        "alphacam_cli.core.application.glob.glob",
        lambda pattern: (
            [os.path.join(settings_dir, "raport_test.acreps")]
            if pattern.endswith("*.acreps")
            else []
        ),
    )
    return settings_dir


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
    drw.Geometries.Count = 2
    drw.ToolPaths.Count = 0
    app_mock = MagicMock()
    app_mock.ActiveDrawing = drw
    app_mock.LicomdirPath = "C:/ALPHACAM"
    _mock_reports_settings(monkeypatch, "C:/ALPHACAM")

    ac = Application(app_mock)
    result = ac.reports_create()

    assert result == {
        "success": True,
        "job": "ok",
        "active_drawing": True,
        "settings_file": "raport_test.acreps",
    }
    reports_mock = addins.GetNewReportsAddIn.return_value
    reports_mock.Settings.SetDataOutputSettingsFromFile.assert_called_once_with(
        r"C:/ALPHACAM/LICOMDIR/Reports/Settings/raport_test.acreps"
    )
    reports_mock.CreateReportsJob.assert_called_once_with(drw)
    job_mock = reports_mock.CreateReportsJob.return_value
    job_mock.Save.assert_called_once_with()
    job_mock.CreateReports.assert_called_once_with()


def test_reports_create_no_drawing(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    _make_addins_mock(monkeypatch, addins)
    app_mock = MagicMock()
    app_mock.ActiveDrawing = None
    app_mock.LicomdirPath = "C:/ALPHACAM"
    _mock_reports_settings(monkeypatch, "C:/ALPHACAM")

    ac = Application(app_mock)
    with pytest.raises(RuntimeError, match="active drawing has no geometry or tool paths"):
        ac.reports_create()
    reports_mock = addins.GetNewReportsAddIn.return_value
    reports_mock.CreateReportsJob.assert_not_called()


def test_reports_create_no_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    _make_addins_mock(monkeypatch, addins)
    app_mock = MagicMock()
    app_mock.LicomdirPath = "C:/ALPHACAM"
    monkeypatch.setattr("alphacam_cli.core.application.os.path.isdir", lambda path: False)
    monkeypatch.setattr("alphacam_cli.core.application.glob.glob", lambda pattern: [])

    ac = Application(app_mock)
    with pytest.raises(RuntimeError, match="no data output settings found"):
        ac.reports_create()
    reports_mock = addins.GetNewReportsAddIn.return_value
    reports_mock.CreateReportsJob.assert_not_called()


def test_reports_create_empty_drawing(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    _make_addins_mock(monkeypatch, addins)
    drw = MagicMock(name="Drawing")
    drw.Geometries.Count = 0
    drw.ToolPaths.Count = 0
    app_mock = MagicMock()
    app_mock.ActiveDrawing = drw
    app_mock.LicomdirPath = "C:/ALPHACAM"
    _mock_reports_settings(monkeypatch, "C:/ALPHACAM")

    ac = Application(app_mock)
    with pytest.raises(RuntimeError, match="active drawing has no geometry or tool paths"):
        ac.reports_create()
    reports_mock = addins.GetNewReportsAddIn.return_value
    reports_mock.CreateReportsJob.assert_not_called()


def test_reports_create_save_false(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    _make_addins_mock(monkeypatch, addins)
    drw = MagicMock(name="Drawing")
    drw.Geometries.Count = 2
    drw.ToolPaths.Count = 0
    app_mock = MagicMock()
    app_mock.ActiveDrawing = drw
    app_mock.LicomdirPath = "C:/ALPHACAM"
    _mock_reports_settings(monkeypatch, "C:/ALPHACAM")
    addins.GetNewReportsAddIn.return_value.CreateReportsJob.return_value.Save.return_value = False

    ac = Application(app_mock)
    with pytest.raises(RuntimeError, match="no report data saved"):
        ac.reports_create()
    reports_mock = addins.GetNewReportsAddIn.return_value
    job_mock = reports_mock.CreateReportsJob.return_value
    job_mock.CreateReports.assert_not_called()


def test_reports_create_job_name(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    _make_addins_mock(monkeypatch, addins)
    drw = MagicMock(name="Drawing")
    drw.Geometries.Count = 2
    drw.ToolPaths.Count = 0
    app_mock = MagicMock()
    app_mock.ActiveDrawing = drw
    app_mock.LicomdirPath = "C:/ALPHACAM"
    _mock_reports_settings(monkeypatch, "C:/ALPHACAM")

    ac = Application(app_mock)
    result = ac.reports_create(job_name="  Fronty  ")

    assert result["settings_file"] == "raport_test.acreps"
    job_mock = addins.GetNewReportsAddIn.return_value.CreateReportsJob.return_value
    assert job_mock.Settings.JobName == "Fronty"
    reports_mock = addins.GetNewReportsAddIn.return_value
    reports_mock.CreateReportsJob.assert_called_once_with(drw)


def test_reports_create_settings_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    addins = MagicMock(name="IAddIns")
    _make_addins_mock(monkeypatch, addins)
    drw = MagicMock(name="Drawing")
    drw.Geometries.Count = 2
    drw.ToolPaths.Count = 0
    app_mock = MagicMock()
    app_mock.ActiveDrawing = drw
    app_mock.LicomdirPath = "C:/ALPHACAM"
    fallback_dir = _mock_reports_settings(monkeypatch, "C:/ALPHACAM", primary_exists=False)

    ac = Application(app_mock)
    result = ac.reports_create()

    assert result["settings_file"] == "raport_test.acreps"
    reports_mock = addins.GetNewReportsAddIn.return_value
    reports_mock.Settings.SetDataOutputSettingsFromFile.assert_called_once_with(
        os.path.join(fallback_dir, "raport_test.acreps")
    )


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


def test_run_query_active_drawing(monkeypatch: pytest.MonkeyPatch) -> None:
    drw = MagicMock(name="Drawing")
    drw.run_query.return_value = 7
    monkeypatch.setattr(Application, "get_active_drawing", lambda self: drw)

    ac = Application(MagicMock())
    active = ac.get_active_drawing()
    assert active is not None
    result = active.run_query(r"C:\ALPHACAM\LICOMDIR\Queries\Menadżer_Warstw_Fronty.agq")

    assert result == 7
    drw.run_query.assert_called_once_with(
        r"C:\ALPHACAM\LICOMDIR\Queries\Menadżer_Warstw_Fronty.agq"
    )


def _mock_manifest_read(
    monkeypatch: pytest.MonkeyPatch, manifest: dict[str, Any], details: list[dict[str, Any]]
) -> None:
    monkeypatch.setattr(
        "alphacam_cli.core.application.acrepd._reports_data_dir",
        lambda *args, **kwargs: os.path.abspath("."),
    )
    monkeypatch.setattr(
        "alphacam_cli.core.application.acrepd.find_manifest",
        lambda *args, **kwargs: "x.acrepd",
    )
    monkeypatch.setattr(
        "alphacam_cli.core.application.acrepd.parse_manifest",
        lambda *args, **kwargs: manifest,
    )
    monkeypatch.setattr(
        "alphacam_cli.core.application.cdm_db.order_details",
        lambda *args, **kwargs: details,
    )


def _manifest_with_parts(*parts: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_name": "CusPO 002",
        "material": "MDF_18",
        "sheets": [{"id": 1, "parts": list(parts)}],
        "total_parts": len(parts),
        "unmatched_parts": [],
        "path": "x.acrepd",
    }


def _empty_cdm_part(name: str) -> dict[str, Any]:
    return {
        "id": 1,
        "sheet_id": 1,
        "name": name,
        "csv_customer_name": None,
        "csv_order_number": None,
        "csv_item_number": None,
    }


def test_manifest_read_enriches_parts_from_order_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest_with_parts(
        _empty_cdm_part("CusPO 002_Typ Frontu 3_1"),
        _empty_cdm_part("CusPO 002_Typ Frontu 3_2"),
    )
    details = [
        {
            "style_name": "Typ Frontu 3",
            "cdm_pk": 2,
            "csv_customer_name": "Klient A",
            "csv_order_number": "ZAM-100",
            "csv_item_number": "IT-2",
        },
        {
            "style_name": "Typ Frontu 3",
            "cdm_pk": 1,
            "csv_customer_name": "Klient B",
            "csv_order_number": "ZAM-200",
            "csv_item_number": "IT-1",
        },
    ]
    _mock_manifest_read(monkeypatch, manifest, details)
    monkeypatch.setattr("alphacam_cli.core.application.cdm_db.custom_field_names", lambda: {})

    ac = Application(MagicMock())
    result = ac.manifest_read("CusPO 002")

    parts = result["manifest"]["sheets"][0]["parts"]
    assert parts[0]["csv_customer_name"] == "Klient B"
    assert parts[0]["csv_order_number"] == "ZAM-200"
    assert parts[0]["csv_item_number"] == "IT-1"
    assert parts[1]["csv_customer_name"] == "Klient A"
    assert parts[1]["csv_order_number"] == "ZAM-100"
    assert parts[1]["csv_item_number"] == "IT-2"


def test_manifest_read_keeps_existing_and_unmatched_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with_xml = _empty_cdm_part("CusPO 002_Typ Frontu 3_1")
    with_xml["csv_customer_name"] = "Klient z XML"
    with_xml["csv_order_number"] = ""
    manifest = _manifest_with_parts(
        _empty_cdm_part("OtherJob_Style_1"),
        with_xml,
        _empty_cdm_part("CusPO 002_Bad Name"),
        _empty_cdm_part("CusPO 002_Typ Frontu 3_9"),
    )
    details = [
        {
            "style_name": "Typ Frontu 3",
            "cdm_pk": 1,
            "csv_customer_name": "Klient A",
            "csv_order_number": "ZAM-100",
            "csv_item_number": "IT-1",
        },
    ]
    _mock_manifest_read(monkeypatch, manifest, details)
    monkeypatch.setattr("alphacam_cli.core.application.cdm_db.custom_field_names", lambda: {})

    ac = Application(MagicMock())
    result = ac.manifest_read("CusPO 002")

    parts = result["manifest"]["sheets"][0]["parts"]
    assert parts[0]["csv_customer_name"] is None
    assert parts[0]["csv_order_number"] is None
    assert parts[1]["csv_customer_name"] == "Klient z XML"
    assert parts[1]["csv_order_number"] == "ZAM-100"
    assert parts[1]["csv_item_number"] == "IT-1"
    assert parts[2]["csv_customer_name"] is None
    assert parts[2]["csv_order_number"] is None
    assert parts[3]["csv_customer_name"] is None
    assert parts[3]["csv_order_number"] is None


def test_manifest_read_enriches_by_type_name_with_mismatched_style_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest_with_parts(_empty_cdm_part("CusPO 002_P003_1"))
    details = [
        {
            "type_name": "P003",
            "style_name": "PS_03",
            "cdm_pk": 68,
            "csv_customer_name": "Klient A",
            "csv_order_number": "196",
            "csv_item_number": "IT-1",
        },
    ]
    _mock_manifest_read(monkeypatch, manifest, details)
    monkeypatch.setattr("alphacam_cli.core.application.cdm_db.custom_field_names", lambda: {})

    ac = Application(MagicMock())
    result = ac.manifest_read("CusPO 002")

    part = result["manifest"]["sheets"][0]["parts"][0]
    assert part["csv_customer_name"] == "Klient A"
    assert part["csv_order_number"] == "196"
    assert part["csv_item_number"] == "IT-1"


def test_manifest_read_falls_back_to_style_name_without_type_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest_with_parts(_empty_cdm_part("CusPO 002_Typ Frontu 3_1"))
    details = [
        {
            "style_name": "Typ Frontu 3",
            "cdm_pk": 1,
            "csv_customer_name": "Klient A",
            "csv_order_number": "ZAM-100",
            "csv_item_number": "IT-1",
        },
    ]
    _mock_manifest_read(monkeypatch, manifest, details)
    monkeypatch.setattr("alphacam_cli.core.application.cdm_db.custom_field_names", lambda: {})

    ac = Application(MagicMock())
    result = ac.manifest_read("CusPO 002")

    part = result["manifest"]["sheets"][0]["parts"][0]
    assert part["csv_customer_name"] == "Klient A"
    assert part["csv_order_number"] == "ZAM-100"
    assert part["csv_item_number"] == "IT-1"


def test_manifest_read_order_details_failure_keeps_manifest(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    manifest = _manifest_with_parts(_empty_cdm_part("CusPO 002_Typ Frontu 3_1"))
    _mock_manifest_read(monkeypatch, manifest, [])
    monkeypatch.setattr(
        "alphacam_cli.core.application.cdm_db.order_details",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("vdb5 down")),
    )

    ac = Application(MagicMock())
    with caplog.at_level("WARNING", logger="alphacam"):
        result = ac.manifest_read("CusPO 002")

    assert result["success"] is True
    part = result["manifest"]["sheets"][0]["parts"][0]
    assert part["csv_customer_name"] is None
    assert part["csv_order_number"] is None
    assert "order details read failed" in caplog.text


def _cdm_part_with_custom_fields(name: str) -> dict[str, Any]:
    part = _empty_cdm_part(name)
    for n in range(1, 26):
        part[f"custom_field_{n}"] = None
    return part


def test_manifest_read_custom_fields_with_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest_with_parts(_cdm_part_with_custom_fields("CusPO 002_Typ Frontu 3_1"))
    details = [
        {
            "type_name": "Typ Frontu 3",
            "custom_fields": {"1": "tok_abc", "5": "wart5"},
            "production_comment": "kom",
            "csv_customer_name": "A",
            "csv_order_number": "Z",
            "csv_item_number": "I",
            "cdm_pk": 1,
        },
    ]
    _mock_manifest_read(monkeypatch, manifest, details)
    monkeypatch.setattr(
        "alphacam_cli.core.application.cdm_db.custom_field_names",
        lambda: {1: "project_token", 5: "inne"},
    )

    ac = Application(MagicMock())
    result = ac.manifest_read("CusPO 002")

    part = result["manifest"]["sheets"][0]["parts"][0]
    assert part["custom_field_1"] == "tok_abc"
    assert part["custom_field_5"] == "wart5"
    assert part["production_comment"] == "kom"
    assert part["custom_fields"] == {"project_token": "tok_abc", "inne": "wart5"}


def test_manifest_read_custom_fields_fallback_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest_with_parts(_cdm_part_with_custom_fields("CusPO 002_Typ Frontu 3_1"))
    details = [
        {
            "type_name": "Typ Frontu 3",
            "custom_fields": {"1": "tok_abc"},
            "cdm_pk": 1,
        },
    ]
    _mock_manifest_read(monkeypatch, manifest, details)
    monkeypatch.setattr("alphacam_cli.core.application.cdm_db.custom_field_names", lambda: {})

    ac = Application(MagicMock())
    result = ac.manifest_read("CusPO 002")

    part = result["manifest"]["sheets"][0]["parts"][0]
    assert part["custom_field_1"] == "tok_abc"
    assert part["custom_fields"] == {"custom_field_1": "tok_abc"}


def test_manifest_read_custom_fields_empty_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest_with_parts(_cdm_part_with_custom_fields("CusPO 002_Typ Frontu 3_1"))
    details = [
        {
            "type_name": "Typ Frontu 3",
            "custom_fields": {"1": ""},
            "cdm_pk": 1,
        },
    ]
    _mock_manifest_read(monkeypatch, manifest, details)
    monkeypatch.setattr("alphacam_cli.core.application.cdm_db.custom_field_names", lambda: {})

    ac = Application(MagicMock())
    result = ac.manifest_read("CusPO 002")

    part = result["manifest"]["sheets"][0]["parts"][0]
    assert part["custom_field_1"] is None
    assert part["custom_fields"] == {}


def test_manifest_read_custom_fields_keeps_existing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    part = _cdm_part_with_custom_fields("CusPO 002_Typ Frontu 3_1")
    part["custom_field_1"] = "z XML"
    manifest = _manifest_with_parts(part)
    details = [
        {
            "type_name": "Typ Frontu 3",
            "custom_fields": {"1": "z DB"},
            "cdm_pk": 1,
        },
    ]
    _mock_manifest_read(monkeypatch, manifest, details)
    monkeypatch.setattr("alphacam_cli.core.application.cdm_db.custom_field_names", lambda: {})

    ac = Application(MagicMock())
    result = ac.manifest_read("CusPO 002")

    part = result["manifest"]["sheets"][0]["parts"][0]
    assert part["custom_field_1"] == "z XML"
    assert part["custom_fields"] == {"custom_field_1": "z XML"}


def test_manifest_read_rejects_invalid_job_name() -> None:
    ac = Application(MagicMock())
    with pytest.raises(RuntimeError, match="cdm: invalid job name"):
        ac.manifest_read("a/b")
    with pytest.raises(RuntimeError, match="cdm: job_name is required"):
        ac.manifest_read("   ")
