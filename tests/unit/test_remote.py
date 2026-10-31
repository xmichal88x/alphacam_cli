from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from alphacam_cli.com.manager import AlphacamComError, AlphacamConnectionError
from alphacam_cli.gateway import client as client_module
from alphacam_cli.gateway.client import (
    RemoteComError,
    RemoteConnectionError,
    RemoteProtocolError,
    RemoteServerError,
    RemoteSession,
)
from alphacam_cli.gateway.remote import (
    RemoteApplication,
    _basename,
    _DrawingProxy,
    _ToolProxy,
)


def test_remote_new_drawing() -> None:
    session = MagicMock()
    session.new_drawing.return_value = {"geometries_count": 3}
    session.get_active_drawing.return_value = {"geometries_count": 3}
    app = RemoteApplication(session)
    drw = app.new_drawing(200, 100, 5, "Hello")
    assert drw is not None
    assert isinstance(drw, _DrawingProxy)
    assert drw.geometries_count == 3
    session.new_drawing.assert_called_once_with(200, 100, 5, "Hello")


def test_remote_offcut_operations() -> None:
    session = MagicMock()
    session.cdm_stock_offcut_create.return_value = {"success": False, "status": "blocked"}
    session.cdm_stock_offcut_delete.return_value = {
        "success": True,
        "status": "deleted",
        "sheet_id": 123,
    }
    app = RemoteApplication(session)
    assert app.stock_offcut_create("MDF", 18, 100, 200, 1, "offcut") == {
        "success": False,
        "status": "blocked",
    }
    assert app.stock_offcut_delete(123)["sheet_id"] == 123
    session.cdm_stock_offcut_create.assert_called_once_with(
        material_name="MDF",
        thickness=18,
        width=100,
        height=200,
        quantity=1,
        name="offcut",
    )
    session.cdm_stock_offcut_delete.assert_called_once_with(123)


def test_remote_session_offcut_methods_send_stable_id_and_parameters() -> None:
    session = RemoteSession()
    session._call = MagicMock(return_value={"success": False, "status": "blocked"})  # type: ignore[method-assign]
    session.cdm_stock_offcut_create("MDF", 18, 100, 200, 1, "offcut")
    session.cdm_stock_offcut_delete(123)
    assert session._call.call_args_list == [
        (  # type: ignore[attr-defined]
            (
                "cdm_stock_offcut_create",
                {
                    "material_name": "MDF",
                    "thickness": 18,
                    "width": 100,
                    "height": 200,
                    "quantity": 1,
                    "name": "offcut",
                },
            ),
            {},
        ),
        (("cdm_stock_offcut_delete", {"sheet_id": 123}), {}),  # type: ignore[attr-defined]
    ]


def test_remote_stock_material_add_delegates() -> None:
    session = MagicMock()
    session.cdm_stock_material_add.return_value = {
        "success": True,
        "material": "MDF",
        "id": 5,
        "thickness": 18.0,
        "thickness_units": 0,
        "thickness_id": 9,
    }
    app = RemoteApplication(session)
    assert app.stock_material_add("MDF", 18.0) == {
        "success": True,
        "material": "MDF",
        "id": 5,
        "thickness": 18.0,
        "thickness_units": 0,
        "thickness_id": 9,
    }
    session.cdm_stock_material_add.assert_called_once_with(
        name="MDF", thickness=18.0, thickness_units=0
    )


def test_remote_stock_material_add_passes_units() -> None:
    session = MagicMock()
    session.cdm_stock_material_add.return_value = {"success": True, "id": 6}
    app = RemoteApplication(session)
    assert app.stock_material_add("MDF", 18.0, 3) == {"success": True, "id": 6}
    session.cdm_stock_material_add.assert_called_once_with(
        name="MDF", thickness=18.0, thickness_units=3
    )


def test_remote_session_stock_material_add_sends_params() -> None:
    session = RemoteSession()
    session._call = MagicMock(return_value={"success": True, "id": 5})  # type: ignore[method-assign]
    session.cdm_stock_material_add("MDF", 18.0, 0)
    session._call.assert_called_once_with(
        "cdm_stock_material_add",
        {"name": "MDF", "thickness": 18.0, "thickness_units": 0},
    )


def test_remote_stock_material_delete_delegates() -> None:
    session = MagicMock()
    session.cdm_stock_material_delete.return_value = {
        "success": True,
        "deleted": "MDF_18",
        "id": 2,
        "thicknesses": 1,
        "sheets": 1,
    }
    app = RemoteApplication(session)
    assert app.stock_material_delete("MDF_18") == {
        "success": True,
        "deleted": "MDF_18",
        "id": 2,
        "thicknesses": 1,
        "sheets": 1,
    }
    session.cdm_stock_material_delete.assert_called_once_with(name="MDF_18")


def test_remote_session_stock_material_delete_sends_params() -> None:
    session = RemoteSession()
    session._call = MagicMock(return_value={"success": True, "deleted": "MDF_18"})  # type: ignore[method-assign]
    session.cdm_stock_material_delete("MDF_18")
    session._call.assert_called_once_with("cdm_stock_material_delete", {"name": "MDF_18"})


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
    result = app.drawing_parametric(800, 400, offset=60, fillet=3)
    assert result["success"] is True
    session.drawing_parametric.assert_called_once_with(800, 400, offset=60, fillet=3)


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


def test_remote_find_style_files() -> None:
    session = MagicMock()
    session.list_styles.return_value = {
        "styles": [
            {
                "name": "Edge.ary",
                "directory": "Styles",
                "size": 10,
                "path": "C:/ALPHACAM/LICOMDIR/Styles/Edge.ary",
            },
            {
                "name": "Ball_06.ary",
                "directory": "Styles/Fronty",
                "size": 30,
                "path": "C:/ALPHACAM/LICOMDIR/Styles/Fronty/Ball_06.ary",
            },
        ]
    }
    app = RemoteApplication(session)
    assert app.find_style_files() == [
        "C:/ALPHACAM/LICOMDIR/Styles/Edge.ary",
        "C:/ALPHACAM/LICOMDIR/Styles/Fronty/Ball_06.ary",
    ]
    session.list_styles.assert_called_once_with()


def test_remote_find_style_files_empty() -> None:
    session = MagicMock()
    session.list_styles.return_value = {"styles": []}
    app = RemoteApplication(session)
    assert app.find_style_files() == []


def test_remote_open_cad_file() -> None:
    session = MagicMock()
    session.open_cad_file.return_value = {"geometries_count": 5, "tool_paths_count": 2}
    session.get_active_drawing.return_value = {"geometries_count": 5, "tool_paths_count": 2}
    app = RemoteApplication(session)
    drw = app.open_cad_file(r"C:\parts\panel.dxf", "dxf")
    assert drw is not None
    assert isinstance(drw, _DrawingProxy)
    assert drw.geometries_count == 5
    assert drw.tool_paths_count == 2
    session.open_cad_file.assert_called_once_with(
        r"C:\parts\panel.dxf", "dxf", clear=False, cabinets=False
    )


def test_remote_drawing_proxy_reports_live_counts() -> None:
    session = MagicMock()
    drw = _DrawingProxy(session, {"geometries_count": 1, "tool_paths_count": 0})
    session.get_active_drawing.return_value = {"geometries_count": 1, "tool_paths_count": 0}
    assert drw.geometries_count == 1
    assert drw.tool_paths_count == 0
    session.get_active_drawing.return_value = {"geometries_count": 2, "tool_paths_count": 1}
    assert drw.geometries_count == 2
    assert drw.tool_paths_count == 1


def test_remote_drawing_proxy_raises_when_active_drawing_gone() -> None:
    session = MagicMock()
    session.get_active_drawing.return_value = None
    drw = _DrawingProxy(session, {"geometries_count": 1, "tool_paths_count": 0})
    with pytest.raises(RuntimeError, match="active drawing is gone"):
        _ = drw.geometries_count
    with pytest.raises(RuntimeError, match="active drawing is gone"):
        _ = drw.tool_paths_count


@pytest.mark.parametrize("missing", ["geometries_count", "tool_paths_count"])
def test_remote_drawing_proxy_raises_on_missing_contract_key(missing: str) -> None:
    info = {"geometries_count": 1, "tool_paths_count": 0}
    del info[missing]
    session = MagicMock()
    session.get_active_drawing.return_value = info
    drw = _DrawingProxy(session, info)
    with pytest.raises(RuntimeError, match=missing):
        _ = getattr(drw, missing)


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


def test_remote_reports_create() -> None:
    session = MagicMock()
    session.reports_create.return_value = {"success": True, "job": "ok", "active_drawing": True}
    app = RemoteApplication(session)
    result = app.reports_create()
    assert result == {"success": True, "job": "ok", "active_drawing": True}
    session.reports_create.assert_called_once_with(job_name=None)
    app.reports_create(job_name="Fronty")
    session.reports_create.assert_called_with(job_name="Fronty")


def test_remote_nc_configs() -> None:
    session = MagicMock()
    session.nc_configs.return_value = {"count": 2, "configs": ["Alpha", "Beta"]}
    app = RemoteApplication(session)
    result = app.nc_configs()
    assert result == {"count": 2, "configs": ["Alpha", "Beta"]}
    session.nc_configs.assert_called_once_with()


def test_remote_auto_style_apply() -> None:
    session = MagicMock()
    session.auto_style_apply.return_value = {"success": True, "file": r"C:\styles\auto.style"}
    app = RemoteApplication(session)
    result = app.auto_style_apply(r"C:\styles\auto.style")
    assert result == {"success": True, "file": r"C:\styles\auto.style"}
    session.auto_style_apply.assert_called_once_with(r"C:\styles\auto.style")


def test_remote_create_layer() -> None:
    session = MagicMock()
    session.create_layer.return_value = {"success": True, "layer": "KONTUR"}
    app = RemoteApplication(session)
    result = app.create_layer("KONTUR")
    assert result == {"success": True, "layer": "KONTUR"}
    session.create_layer.assert_called_once_with("KONTUR")


def test_remote_drawing_proxy_create_layer() -> None:
    session = MagicMock()
    session.create_layer.return_value = {"success": True, "layer": "KONTUR"}
    drw = _DrawingProxy(session, {"geometries_count": 2})
    result = drw.create_layer("KONTUR")
    assert result == {"success": True, "layer": "KONTUR"}
    session.create_layer.assert_called_once_with("KONTUR")


def test_remote_run_query() -> None:
    session = MagicMock()
    session.drawing_query.return_value = {"success": True, "count": 7}
    app = RemoteApplication(session)
    result = app.run_query(r"C:\ALPHACAM\LICOMDIR\Queries\test.agq")
    assert result == {"success": True, "count": 7}
    session.drawing_query.assert_called_once_with(r"C:\ALPHACAM\LICOMDIR\Queries\test.agq")


def test_remote_drawing_proxy_run_query() -> None:
    session = MagicMock()
    session.drawing_query.return_value = {"success": True, "count": 7}
    drw = _DrawingProxy(session, {"geometries_count": 2})
    result = drw.run_query(r"C:\ALPHACAM\LICOMDIR\Queries\test.agq")
    assert result == 7
    session.drawing_query.assert_called_once_with(r"C:\ALPHACAM\LICOMDIR\Queries\test.agq")


def test_remote_drawing_proxy_run_query_missing_count() -> None:
    session = MagicMock()
    session.drawing_query.return_value = {"success": True}
    drw = _DrawingProxy(session, {"geometries_count": 2})
    result = drw.run_query(r"C:\ALPHACAM\LICOMDIR\Queries\test.agq")
    assert result == 0


def test_remote_create_cdm_job() -> None:
    session = MagicMock()
    session.create_cdm_job.return_value = {
        "success": True,
        "job_name": "JOB-001",
        "config": "Fronty",
        "material": "MDF_18",
        "warnings": [],
    }
    app = RemoteApplication(session)
    result = app.create_cdm_job(
        job_name="JOB-001",
        config="Fronty",
        material="MDF_18",
        customer="Klient A",
        po="PO-1",
        due_date="2026-08-10",
        description="opis",
    )
    assert result["success"] is True
    assert result["job_name"] == "JOB-001"
    session.create_cdm_job.assert_called_once_with(
        job_name="JOB-001",
        config="Fronty",
        material="MDF_18",
        customer="Klient A",
        po="PO-1",
        due_date="2026-08-10",
        description="opis",
        material_group=None,
        include_offcuts=False,
        prefer_offcuts=False,
        sheets=None,
        sheet_order=None,
    )


def test_remote_create_cdm_job_exclude_offcuts() -> None:
    session = MagicMock()
    session.create_cdm_job.return_value = {"success": True}
    app = RemoteApplication(session)
    app.create_cdm_job(
        job_name="JOB-001",
        material_group="MDF_18",
        include_offcuts=True,
        exclude_offcuts=["118", "MDF_18, Odciecie 1"],
    )
    session.create_cdm_job.assert_called_once_with(
        job_name="JOB-001",
        config=None,
        material=None,
        customer=None,
        po=None,
        due_date=None,
        description=None,
        material_group="MDF_18",
        include_offcuts=True,
        prefer_offcuts=False,
        sheets=None,
        sheet_order=None,
        exclude_offcuts=["118", "MDF_18, Odciecie 1"],
    )


def test_remote_create_cdm_job_defaults() -> None:
    session = MagicMock()
    session.create_cdm_job.return_value = {"success": True}
    app = RemoteApplication(session)
    app.create_cdm_job(job_name="JOB-001")
    session.create_cdm_job.assert_called_once_with(
        job_name="JOB-001",
        config=None,
        material=None,
        customer=None,
        po=None,
        due_date=None,
        description=None,
        material_group=None,
        include_offcuts=False,
        prefer_offcuts=False,
        sheets=None,
        sheet_order=None,
    )


def test_remote_create_cdm_job_material() -> None:
    session = MagicMock()
    session.create_cdm_job.return_value = {
        "success": True,
        "job_name": "JOB-001",
        "config": "Fronty",
        "material": "MDF_18",
        "warnings": [],
    }
    app = RemoteApplication(session)
    result = app.create_cdm_job(job_name="JOB-001", material="MDF_18")
    assert result["material"] == "MDF_18"
    session.create_cdm_job.assert_called_once_with(
        job_name="JOB-001",
        config=None,
        material="MDF_18",
        customer=None,
        po=None,
        due_date=None,
        description=None,
        material_group=None,
        include_offcuts=False,
        prefer_offcuts=False,
        sheets=None,
        sheet_order=None,
    )


def test_remote_create_cdm_job_material_group() -> None:
    session = MagicMock()
    session.create_cdm_job.return_value = {"success": True}
    app = RemoteApplication(session)
    app.create_cdm_job(
        job_name="JOB-001",
        material_group="MDF_18",
        include_offcuts=True,
        prefer_offcuts=True,
        sheets="2:0,7:1",
        sheet_order="picked",
    )
    session.create_cdm_job.assert_called_once_with(
        job_name="JOB-001",
        config=None,
        material=None,
        customer=None,
        po=None,
        due_date=None,
        description=None,
        material_group="MDF_18",
        include_offcuts=True,
        prefer_offcuts=True,
        sheets="2:0,7:1",
        sheet_order="picked",
    )


def test_remote_cdm_types() -> None:
    session = MagicMock()
    session.cdm_types.return_value = {
        "types": [{"id": 1, "name": "Typ Frontu 1"}, {"id": 2, "name": "L_B_10mm"}]
    }
    app = RemoteApplication(session)
    result = app.cdm_types()
    assert result == {"types": [{"id": 1, "name": "Typ Frontu 1"}, {"id": 2, "name": "L_B_10mm"}]}
    session.cdm_types.assert_called_once_with()


def test_remote_cdm_jobs() -> None:
    session = MagicMock()
    session.cdm_jobs.return_value = {"jobs": [{"id": 1, "name": "JOB-001"}]}
    app = RemoteApplication(session)
    result = app.cdm_jobs()
    assert result == {"jobs": [{"id": 1, "name": "JOB-001"}]}
    session.cdm_jobs.assert_called_once_with()


def test_remote_import_cdm_csv() -> None:
    session = MagicMock()
    session.import_cdm_csv.return_value = {
        "success": True,
        "job_name": "JOB-001",
        "items": 2,
        "errors": [],
    }
    app = RemoteApplication(session)
    result = app.import_cdm_csv(r"C:\temp\order.csv", job="JOB-001")
    assert result["success"] is True
    assert result["job_name"] == "JOB-001"
    assert result["items"] == 2
    session.import_cdm_csv.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        job="JOB-001",
        name=None,
        config=None,
        separator=None,
        has_header=False,
        material=None,
        import_setting=None,
        preview=False,
        material_group=None,
        include_offcuts=False,
        prefer_offcuts=False,
        sheets=None,
        sheet_order=None,
    )


def test_remote_import_cdm_csv_material() -> None:
    session = MagicMock()
    session.import_cdm_csv.return_value = {
        "success": True,
        "job_name": "order",
        "items": 1,
        "material": "MDF_18",
        "errors": [],
    }
    app = RemoteApplication(session)
    result = app.import_cdm_csv(r"C:\temp\order.csv", material="MDF_18")
    assert result["material"] == "MDF_18"
    session.import_cdm_csv.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        job=None,
        name=None,
        config=None,
        separator=None,
        has_header=False,
        material="MDF_18",
        import_setting=None,
        preview=False,
        material_group=None,
        include_offcuts=False,
        prefer_offcuts=False,
        sheets=None,
        sheet_order=None,
    )


def test_remote_delete_cdm_job() -> None:
    session = MagicMock()
    session.delete_cdm_job.return_value = {"success": True, "job_name": "JOB-001"}
    app = RemoteApplication(session)
    result = app.delete_cdm_job(job_name="JOB-001")
    assert result == {"success": True, "job_name": "JOB-001"}
    session.delete_cdm_job.assert_called_once_with(job_name="JOB-001")


def test_remote_import_cdm_csv_defaults() -> None:
    session = MagicMock()
    session.import_cdm_csv.return_value = {
        "success": True,
        "job_name": "order",
        "items": 1,
        "errors": [],
    }
    app = RemoteApplication(session)
    result = app.import_cdm_csv("x.csv")
    assert result["job_name"] == "order"
    session.import_cdm_csv.assert_called_once_with(
        csv="x.csv",
        job=None,
        name=None,
        config=None,
        separator=None,
        has_header=False,
        material=None,
        import_setting=None,
        preview=False,
        material_group=None,
        include_offcuts=False,
        prefer_offcuts=False,
        sheets=None,
        sheet_order=None,
    )


def test_remote_import_cdm_csv_name_config() -> None:
    session = MagicMock()
    session.import_cdm_csv.return_value = {
        "success": True,
        "job_name": "Zadanie 132",
        "items": 4,
        "errors": [],
    }
    app = RemoteApplication(session)
    result = app.import_cdm_csv(r"C:\temp\order.csv", name="Zadanie 132", config="Fronty")
    assert result["items"] == 4
    session.import_cdm_csv.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        job=None,
        name="Zadanie 132",
        config="Fronty",
        separator=None,
        has_header=False,
        material=None,
        import_setting=None,
        preview=False,
        material_group=None,
        include_offcuts=False,
        prefer_offcuts=False,
        sheets=None,
        sheet_order=None,
    )


def test_remote_import_cdm_csv_mapped() -> None:
    session = MagicMock()
    session.import_cdm_csv.return_value = {
        "success": True,
        "job_name": "Zadanie-7",
        "items": 1,
        "material": "MDF_18",
        "errors": [],
        "import_setting": "Fronty CSV",
    }
    app = RemoteApplication(session)
    result = app.import_cdm_csv(
        r"C:\temp\order.csv", separator=";", import_setting=3, has_header=True
    )
    assert result["job_name"] == "Zadanie-7"
    session.import_cdm_csv.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        job=None,
        name=None,
        config=None,
        separator=";",
        has_header=True,
        material=None,
        import_setting=3,
        preview=False,
        material_group=None,
        include_offcuts=False,
        prefer_offcuts=False,
        sheets=None,
        sheet_order=None,
    )


def test_remote_import_cdm_csv_preview() -> None:
    session = MagicMock()
    session.import_cdm_csv.return_value = {
        "success": True,
        "job_name": "Zadanie-7",
        "items": 1,
        "errors": [],
    }
    app = RemoteApplication(session)
    result = app.import_cdm_csv(r"C:\temp\order.csv", import_setting=3, preview=True)
    assert result["items"] == 1
    session.import_cdm_csv.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        job=None,
        name=None,
        config=None,
        separator=None,
        has_header=False,
        material=None,
        import_setting=3,
        preview=True,
        material_group=None,
        include_offcuts=False,
        prefer_offcuts=False,
        sheets=None,
        sheet_order=None,
    )


def test_remote_import_cdm_preview() -> None:
    session = MagicMock()
    session.import_cdm_preview.return_value = {
        "success": True,
        "job_name": "Zadanie-7",
        "items": 1,
        "rows": [],
        "errors": [],
    }
    app = RemoteApplication(session)
    result = app.import_cdm_preview(r"C:\temp\order.csv", import_setting=3)
    assert result["items"] == 1
    session.import_cdm_preview.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        import_setting=3,
        separator=None,
        has_header=False,
        job=None,
        name=None,
        config=None,
        material=None,
        material_group=None,
        include_offcuts=False,
        prefer_offcuts=False,
        sheets=None,
    )


def test_remote_import_cdm_csv_material_group() -> None:
    session = MagicMock()
    session.import_cdm_csv.return_value = {"success": True, "items": 1, "errors": []}
    app = RemoteApplication(session)
    result = app.import_cdm_csv(
        r"C:\temp\order.csv",
        material_group="MDF_18",
        include_offcuts=True,
        prefer_offcuts=True,
        sheets="2:0,7:1",
        sheet_order="picked",
    )
    assert result["items"] == 1
    session.import_cdm_csv.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        job=None,
        name=None,
        config=None,
        separator=None,
        has_header=False,
        material=None,
        import_setting=None,
        preview=False,
        material_group="MDF_18",
        include_offcuts=True,
        prefer_offcuts=True,
        sheets="2:0,7:1",
        sheet_order="picked",
    )


def test_remote_import_cdm_preview_material_group() -> None:
    session = MagicMock()
    session.import_cdm_preview.return_value = {
        "success": True,
        "items": 1,
        "rows": [],
        "errors": [],
    }
    app = RemoteApplication(session)
    result = app.import_cdm_preview(
        r"C:\temp\order.csv", material_group="MDF_18", include_offcuts=True, sheets="2:0"
    )
    assert result["items"] == 1
    session.import_cdm_preview.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        import_setting=None,
        separator=None,
        has_header=False,
        job=None,
        name=None,
        config=None,
        material=None,
        material_group="MDF_18",
        include_offcuts=True,
        prefer_offcuts=False,
        sheets="2:0",
    )


def test_remote_cdm_import_settings() -> None:
    session = MagicMock()
    session.cdm_import_settings.return_value = {
        "settings": [{"id": 3, "name": "Fronty CSV", "fields_count": 2}]
    }
    app = RemoteApplication(session)
    result = app.cdm_import_settings()
    assert result["settings"][0]["name"] == "Fronty CSV"
    session.cdm_import_settings.assert_called_once_with()


def test_remote_session_drawing_lint_requires_units() -> None:
    session = RemoteSession()

    with pytest.raises(TypeError):
        session.drawing_lint()  # type: ignore[call-arg]


def test_remote_session_import_cdm_csv_digit_string_setting() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"success": True})  # type: ignore[method-assign]
    client.import_cdm_csv(r"C:\temp\order.csv", import_setting="3")
    client._call.assert_called_once_with(
        "cdm_import_csv",
        {"csv": r"C:\temp\order.csv", "has_header": False, "import_setting": 3},
    )


def test_remote_session_import_cdm_csv_name_setting_unchanged() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"success": True})  # type: ignore[method-assign]
    client.import_cdm_csv(r"C:\temp\order.csv", import_setting="sklep CSV")
    client._call.assert_called_once_with(
        "cdm_import_csv",
        {"csv": r"C:\temp\order.csv", "has_header": False, "import_setting": "sklep CSV"},
    )


def test_remote_session_import_cdm_preview_digit_string_setting() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"success": True})  # type: ignore[method-assign]
    client.import_cdm_preview(r"C:\temp\order.csv", import_setting="7")
    client._call.assert_called_once_with(
        "cdm_import_preview",
        {"csv": r"C:\temp\order.csv", "has_header": False, "import_setting": 7},
    )


def test_remote_session_import_cdm_csv_material_group_params() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"success": True})  # type: ignore[method-assign]
    client.import_cdm_csv(
        r"C:\temp\order.csv",
        material_group="MDF_18",
        include_offcuts=True,
        prefer_offcuts=True,
        sheets="2:0,7:1",
        sheet_order="picked",
    )
    client._call.assert_called_once_with(
        "cdm_import_csv",
        {
            "csv": r"C:\temp\order.csv",
            "has_header": False,
            "material_group": "MDF_18",
            "include_offcuts": True,
            "prefer_offcuts": True,
            "sheets": "2:0,7:1",
            "sheet_order": "picked",
        },
    )


def test_remote_session_import_cdm_csv_group_defaults_omitted() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"success": True})  # type: ignore[method-assign]
    client.import_cdm_csv(r"C:\temp\order.csv")
    client._call.assert_called_once_with(
        "cdm_import_csv",
        {"csv": r"C:\temp\order.csv", "has_header": False},
    )


def test_remote_session_import_cdm_preview_material_group_params() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"success": True})  # type: ignore[method-assign]
    client.import_cdm_preview(
        r"C:\temp\order.csv", material_group="MDF_18", include_offcuts=True, sheets="2:0"
    )
    client._call.assert_called_once_with(
        "cdm_import_preview",
        {
            "csv": r"C:\temp\order.csv",
            "has_header": False,
            "material_group": "MDF_18",
            "include_offcuts": True,
            "sheets": "2:0",
        },
    )


def test_remote_session_cdm_order_details_with_job() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"order_details": [], "job_name": "X"})  # type: ignore[method-assign]
    client.cdm_order_details(job_name="X")
    client._call.assert_called_once_with("cdm_order_details", {"job_name": "X"})


def test_remote_session_cdm_order_details_no_job() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"order_details": [], "job_name": None})  # type: ignore[method-assign]
    client.cdm_order_details()
    client._call.assert_called_once_with("cdm_order_details", {})


def test_remote_session_cdm_door_paths_with_type() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"door_paths": [], "type_name": "T1"})  # type: ignore[method-assign]
    client.cdm_door_paths(type_name="T1")
    client._call.assert_called_once_with("cdm_door_paths", {"type_name": "T1"})


def test_remote_session_cdm_configs_with_show() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"configs": [], "show": "all"})  # type: ignore[method-assign]
    client.cdm_configs(show="all")
    client._call.assert_called_once_with("cdm_configs", {"show": "all"})


def test_remote_session_cdm_materials_lookups_no_params() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"materials": [], "lookups": {}})  # type: ignore[method-assign]
    client.cdm_materials()
    client._call.assert_called_once_with("cdm_materials")
    client._call.reset_mock()
    client.cdm_lookups()
    client._call.assert_called_once_with("cdm_lookups")


def test_remote_session_create_cdm_job_skips_none_params() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"success": True})  # type: ignore[method-assign]
    client.create_cdm_job(job_name="J", material="M", due_date="2026-08-20")
    client._call.assert_called_once_with(
        "create_cdm_job",
        {"job_name": "J", "material": "M", "due_date": "2026-08-20"},
    )


def test_remote_session_create_cdm_job_all_params() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"success": True})  # type: ignore[method-assign]
    client.create_cdm_job(
        job_name="J",
        config="Fronty",
        material="M",
        customer="Klient A",
        po="PO-1",
        due_date="2026-08-20",
        description="opis",
    )
    client._call.assert_called_once_with(
        "create_cdm_job",
        {
            "job_name": "J",
            "config": "Fronty",
            "material": "M",
            "customer": "Klient A",
            "po": "PO-1",
            "due_date": "2026-08-20",
            "description": "opis",
        },
    )


def test_remote_session_create_cdm_job_material_group_params() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"success": True})  # type: ignore[method-assign]
    client.create_cdm_job(
        job_name="J",
        material_group="MDF_18",
        include_offcuts=True,
        prefer_offcuts=True,
        sheets="2:0,7:1",
        sheet_order="picked",
    )
    client._call.assert_called_once_with(
        "create_cdm_job",
        {
            "job_name": "J",
            "material_group": "MDF_18",
            "include_offcuts": True,
            "prefer_offcuts": True,
            "sheets": "2:0,7:1",
            "sheet_order": "picked",
        },
    )


def test_remote_session_create_cdm_job_group_defaults_omitted() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"success": True})  # type: ignore[method-assign]
    client.create_cdm_job(job_name="J")
    client._call.assert_called_once_with("create_cdm_job", {"job_name": "J"})


def test_remote_process_cdm_job() -> None:
    session = MagicMock()
    session.process_cdm_job.return_value = {
        "success": True,
        "job_name": "JOB-001",
        "processed": True,
    }
    app = RemoteApplication(session)
    result = app.process_cdm_job(job_name="JOB-001")
    assert result == {"success": True, "job_name": "JOB-001", "processed": True}
    session.process_cdm_job.assert_called_once_with(
        job_name="JOB-001",
        timeout_seconds=300,
        output_root=None,
    )


def test_remote_process_cdm_job_full_params() -> None:
    session = MagicMock()
    session.process_cdm_job.return_value = {
        "success": True,
        "job_name": "JOB-001",
        "processed": True,
    }
    app = RemoteApplication(session)
    result = app.process_cdm_job(
        job_name="JOB-001",
        timeout_seconds=600,
        output_root="C:/out",
    )
    assert result == {"success": True, "job_name": "JOB-001", "processed": True}
    session.process_cdm_job.assert_called_once_with(
        job_name="JOB-001",
        timeout_seconds=600,
        output_root="C:/out",
    )


def test_remote_session_process_cdm_job() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"success": True, "processed": True})  # type: ignore[method-assign]
    client.process_cdm_job(job_name="JOB-001")
    client._call.assert_called_once_with(
        "process_cdm_job",
        {"job_name": "JOB-001", "timeout_seconds": 300},
    )


def test_remote_session_process_cdm_job_full_params() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"success": True, "processed": True})  # type: ignore[method-assign]
    client.process_cdm_job(
        job_name="JOB-001",
        timeout_seconds=600,
        output_root="C:/out",
    )
    client._call.assert_called_once_with(
        "process_cdm_job",
        {
            "job_name": "JOB-001",
            "timeout_seconds": 600,
            "output_root": "C:/out",
        },
    )


def test_remote_session_process_cdm_job_extended_timeout() -> None:
    client = RemoteSession(timeout=30.0)
    sock = MagicMock()
    client._sock = sock
    client._call = MagicMock(return_value={"success": True})  # type: ignore[method-assign]
    client.process_cdm_job(job_name="JOB-001", timeout_seconds=600)
    sock.settimeout.assert_any_call(630.0)
    sock.settimeout.assert_called_with(30.0)


def test_remote_session_call_socket_timeout_wrapped() -> None:
    from alphacam_cli.gateway.client import RemoteConnectionError

    client = RemoteSession(timeout=30.0)
    sock = MagicMock()
    sock.recv_into.side_effect = TimeoutError("timed out")
    client._sock = sock
    with pytest.raises(RemoteConnectionError, match=r"request timed out after 30\.0s"):
        client._call("ping")
    sock.close.assert_called_once()
    assert client._sock is None


def test_remote_session_call_without_connect_reports_not_connected() -> None:
    client = RemoteSession()

    with pytest.raises(RemoteConnectionError, match="Not connected"):
        client._call("ping")


def test_call_send_oserror_closes_socket() -> None:
    session = RemoteSession()
    sock = MagicMock()
    sock.sendall.side_effect = OSError("broken pipe")
    session._sock = sock

    with pytest.raises(RemoteConnectionError, match="send failed"):
        session._call("ping")

    sock.close.assert_called_once()
    assert session._sock is None


def test_remote_session_health() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"ok": True, "version": "9.0.1"})  # type: ignore[method-assign]
    result = client.health()
    assert result == {"ok": True, "version": "9.0.1"}
    client._call.assert_called_once_with("health")


def test_remote_application_health() -> None:
    session = MagicMock()
    session.health.return_value = {"ok": True, "version": "9.0.1", "name": "AlphaCAM"}
    app = RemoteApplication(session)
    result = app.health()
    assert result == {"ok": True, "version": "9.0.1", "name": "AlphaCAM"}
    session.health.assert_called_once_with()


def test_remote_session_cdm_set_sheet_order() -> None:
    client = RemoteSession()
    client._call = MagicMock(return_value={"success": True})  # type: ignore[method-assign]
    client.cdm_set_sheet_order("Fronty", "picked")
    client._call.assert_called_once_with(
        "cdm_set_sheet_order", {"config_name": "Fronty", "order": "picked"}
    )


def test_remote_cdm_set_sheet_order_delegates() -> None:
    session = MagicMock()
    session.cdm_set_sheet_order.return_value = {
        "success": True,
        "config": "Fronty",
        "sheet_order": "picked",
        "value": 1,
    }
    app = RemoteApplication(session)
    result = app.cdm_set_sheet_order("Fronty", "picked")
    assert result == {
        "success": True,
        "config": "Fronty",
        "sheet_order": "picked",
        "value": 1,
    }
    session.cdm_set_sheet_order.assert_called_once_with("Fronty", "picked")


def test_call_rejects_response_id_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    session = RemoteSession()
    sock = MagicMock()
    session._sock = sock
    monkeypatch.setattr(client_module, "read_frame", lambda _sock: {"id": 999, "result": {}})

    with pytest.raises(RemoteConnectionError, match="response id mismatch"):
        session._call("ping")

    sock.close.assert_called_once()
    assert session._sock is None


def test_call_read_timeout_closes_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    session = RemoteSession()
    sock = MagicMock()
    session._sock = sock

    def raise_timeout(_sock: object) -> None:
        raise TimeoutError

    monkeypatch.setattr(client_module, "read_frame", raise_timeout)

    with pytest.raises(RemoteConnectionError, match="timed out"):
        session._call("ping")

    sock.close.assert_called_once()
    assert session._sock is None


def test_call_closed_connection_closes_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    session = RemoteSession()
    sock = MagicMock()
    session._sock = sock
    monkeypatch.setattr(client_module, "read_frame", lambda _sock: None)

    with pytest.raises(RemoteConnectionError, match="Connection closed"):
        session._call("ping")

    sock.close.assert_called_once()
    assert session._sock is None


def test_call_timeout_override_sets_and_restores_socket_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = RemoteSession(timeout=180.0)
    sock = MagicMock()
    session._sock = sock
    monkeypatch.setattr(
        client_module, "read_frame", lambda _sock: {"id": 1, "result": {"ok": True}}
    )

    assert session._call("ping", timeout=600.0) == {"ok": True}

    assert sock.settimeout.call_args_list[0].args == (600.0,)
    assert sock.settimeout.call_args_list[-1].args == (180.0,)


def test_call_timeout_override_can_shorten_socket_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = RemoteSession(timeout=180.0)
    sock = MagicMock()
    session._sock = sock
    monkeypatch.setattr(
        client_module, "read_frame", lambda _sock: {"id": 1, "result": {"ok": True}}
    )

    assert session._call("ping", timeout=45.0) == {"ok": True}

    assert sock.settimeout.call_args_list[0].args == (45.0,)
    assert sock.settimeout.call_args_list[-1].args == (180.0,)


def test_remote_connection_error_inherits_alphacam_connection_error() -> None:
    error = RemoteConnectionError("down")

    assert isinstance(error, AlphacamConnectionError)


def test_remote_com_error_inherits_alphacam_com_error_and_keeps_hresult() -> None:
    error = RemoteComError("boom", hresult=-32000)

    assert isinstance(error, AlphacamComError)
    assert error.hresult == -32000
    assert str(error) == "boom"


def test_remote_com_error_without_hresult() -> None:
    error = RemoteComError("internal")

    assert error.hresult is None


def test_call_com_error_maps_to_remote_com_error_with_hresult(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = RemoteSession()
    session._sock = MagicMock()
    monkeypatch.setattr(
        client_module,
        "read_frame",
        lambda _sock: {"id": 1, "error": {"code": -32000, "message": "COM failed"}},
    )

    with pytest.raises(RemoteComError) as exc_info:
        session._call("ping")

    assert exc_info.value.hresult == -32000
    assert str(exc_info.value) == "COM failed"


def test_call_internal_error_maps_to_remote_server_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = RemoteSession()
    session._sock = MagicMock()
    monkeypatch.setattr(
        client_module,
        "read_frame",
        lambda _sock: {"id": 1, "error": {"code": -32603, "message": "Internal error"}},
    )

    with pytest.raises(RemoteServerError) as exc_info:
        session._call("ping")

    assert str(exc_info.value) == "Internal error"
    assert not isinstance(exc_info.value, AlphacamComError)
    assert not isinstance(exc_info.value, AlphacamConnectionError)


def test_remote_server_error_is_exported_from_gateway_package() -> None:
    from alphacam_cli.gateway import RemoteServerError as Exported

    assert Exported is RemoteServerError


@pytest.mark.parametrize("code", [-32601, -32600, -32700, 12345])
def test_call_protocol_errors_map_to_remote_protocol_error(
    monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    session = RemoteSession()
    session._sock = MagicMock()
    monkeypatch.setattr(
        client_module,
        "read_frame",
        lambda _sock: {"id": 1, "error": {"code": code, "message": "bad request"}},
    )

    with pytest.raises(RemoteProtocolError, match=rf"JSON-RPC error \({code}\)"):
        session._call("ping")


def test_connect_socket_timeout_constant() -> None:
    from alphacam_cli.gateway.timeouts import CONNECT_SOCKET_TIMEOUT

    assert CONNECT_SOCKET_TIMEOUT == 10.0


def test_connect_filtered_port_raises_with_host_port_and_connect_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import socket as socket_module

    fake_sock = MagicMock()
    fake_sock.connect.side_effect = socket_module.timeout("timed out")  # noqa: UP041
    monkeypatch.setattr(client_module.socket, "socket", MagicMock(return_value=fake_sock))

    session = RemoteSession(host="192.168.100.60", port=9999)

    with pytest.raises(RemoteConnectionError) as exc_info:
        session.connect()

    message = str(exc_info.value)
    assert "192.168.100.60:9999" in message
    assert "10s" in message
    assert session._sock is None
    fake_sock.settimeout.assert_called_once_with(10.0)


def test_connect_success_restores_session_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_sock = MagicMock()
    monkeypatch.setattr(client_module.socket, "socket", MagicMock(return_value=fake_sock))

    session = RemoteSession(timeout=180.0)
    session.connect()

    assert session._sock is fake_sock
    assert fake_sock.settimeout.call_args_list == [call(10.0), call(180.0)]
