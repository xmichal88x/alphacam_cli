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


def test_remote_reports_create() -> None:
    session = MagicMock()
    session.reports_create.return_value = {"success": True, "job": "ok", "active_drawing": True}
    app = RemoteApplication(session)
    result = app.reports_create()
    assert result == {"success": True, "job": "ok", "active_drawing": True}
    session.reports_create.assert_called_once_with()


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


def test_remote_machining_pipeline() -> None:
    session = MagicMock()
    session.machining_pipeline.return_value = {
        "success": True,
        "geometries_count": 2,
        "tool_paths_count": 4,
    }
    app = RemoteApplication(session)
    result = app.machining_pipeline(agq=r"C:\q.agq", ara=r"C:\a.ara", layer_map="KONTUR:1")
    assert result["tool_paths_count"] == 4
    session.machining_pipeline.assert_called_once_with(
        agq=r"C:\q.agq", ara=r"C:\a.ara", layer_map="KONTUR:1"
    )


def test_remote_machining_pipeline_defaults() -> None:
    session = MagicMock()
    session.machining_pipeline.return_value = {"success": True}
    app = RemoteApplication(session)
    result = app.machining_pipeline()
    assert result == {"success": True}
    session.machining_pipeline.assert_called_once_with(agq=None, ara=None, layer_map=None)


def test_remote_run_cdm() -> None:
    session = MagicMock()
    session.run_cdm.return_value = {
        "success": True,
        "job_name": "JOB-001",
        "type_name": "Typ Frontu 1",
        "width": 500.0,
        "length": 300.0,
        "quantity": 2,
    }
    app = RemoteApplication(session)
    result = app.run_cdm(
        job_name="JOB-001",
        type_name="Typ Frontu 1",
        width=500,
        length=300,
        quantity=2,
        bypass_nest=True,
    )
    assert result["success"] is True
    assert result["job_name"] == "JOB-001"
    session.run_cdm.assert_called_once_with(
        job_name="JOB-001",
        type_name="Typ Frontu 1",
        width=500,
        length=300,
        quantity=2,
        bypass_nest=True,
    )


def test_remote_run_cdm_defaults() -> None:
    session = MagicMock()
    session.run_cdm.return_value = {"success": True}
    app = RemoteApplication(session)
    app.run_cdm(job_name="JOB-001", type_name="Typ Frontu 1")
    session.run_cdm.assert_called_once_with(
        job_name="JOB-001",
        type_name="Typ Frontu 1",
        width=400,
        length=300,
        quantity=1,
        bypass_nest=False,
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
        "csv": r"C:\temp\order.csv",
        "created": False,
    }
    app = RemoteApplication(session)
    result = app.import_cdm_csv(r"C:\temp\order.csv", job_name="JOB-001")
    assert result["success"] is True
    assert result["job_name"] == "JOB-001"
    assert result["created"] is False
    session.import_cdm_csv.assert_called_once_with(
        csv=r"C:\temp\order.csv", job_name="JOB-001", separator=",", has_header=False
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
        "csv": "x.csv",
        "created": True,
    }
    app = RemoteApplication(session)
    result = app.import_cdm_csv("x.csv")
    assert result["created"] is True
    session.import_cdm_csv.assert_called_once_with(
        csv="x.csv", job_name=None, separator=",", has_header=False
    )
