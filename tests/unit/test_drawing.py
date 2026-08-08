from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import pythoncom  # type: ignore[import-untyped]

from alphacam_cli.core.events import NcEventHandler


def test_drawing_creation(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            assert drw.geometries_count == 0
            assert drw.tool_paths_count == 0


def test_geometries_iteration(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import CamPath, Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            # Mock geometries collection
            geo = MagicMock()
            geo.Selected = False
            geo.ToolInOut = -1

            geometries_mock = MagicMock()
            geometries_mock.Count = 2
            geometries_mock.Item.side_effect = lambda i: geo
            drw._drw.Geometries = geometries_mock

            geos = drw.geometries()
            assert len(geos) == 2
            assert isinstance(geos[0], CamPath)


def test_rectangle_creation(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import CamPath

        rect_mock = MagicMock()
        with alphacam_context() as raw:
            raw.CreateRectangle.return_value = rect_mock
            p = CamPath(raw.CreateRectangle(0, 0, 100, 50))
            assert p is not None


def test_create_nest_data(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            nest_data = MagicMock()
            drw._drw.CreateNestData.return_value = nest_data
            result = drw.create_nest_data("nest.anl")
            assert result is nest_data
            drw._drw.CreateNestData.assert_called_once_with("nest.anl")


def test_create_nest_data_none(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            drw._drw.CreateNestData.return_value = None
            with pytest.raises(RuntimeError, match="Failed to create nest data"):
                drw.create_nest_data("nest.anl")


def test_output_nc_with_events(mock_com: MagicMock) -> None:
    with (
        mock_com,
        patch("win32com.client.DispatchWithEvents") as mock_dispatch_with_events,
    ):
        from alphacam_cli.core.drawing import Drawing

        drw = MagicMock()
        drawing = Drawing(drw)
        app_dispatch = MagicMock()

        drawing.output_nc_with_events("test.nc", app_dispatch)

        drw.OutputNC.assert_called_once_with("test.nc", 0, False)
        mock_dispatch_with_events.assert_called_once_with(app_dispatch, NcEventHandler)


def test_create_circle(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import CamPath, Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            path_mock = MagicMock()
            drw._drw.CreateCircle.return_value = path_mock
            path = drw.create_circle(50, 100, 100)
            assert isinstance(path, CamPath)
            drw._drw.CreateCircle.assert_called_once_with(50, 100, 100)


def test_create_text(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing, Text

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            text_mock = MagicMock()
            text_mock.Height = 10.0
            text_mock.Text = "Hello"
            text_mock.FontName = "Arial"
            drw._drw.CreateText2.return_value = text_mock
            txt = drw.create_text("Hello", 0, 0, 10)
            assert isinstance(txt, Text)
            assert txt.height == 10.0
            assert txt.text_string == "Hello"
            assert txt.font_name == "Arial"
            drw._drw.CreateText2.assert_called_once_with("Hello", 0, 0, 10)


def test_create_2d_geometry(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing, Geo2D

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            raw_geo = MagicMock()
            drw._drw.Create2DGeometry.return_value = raw_geo
            geo = drw.create_2d_geometry(10, 20)
            assert isinstance(geo, Geo2D)
            drw._drw.Create2DGeometry.assert_called_once_with(10, 20)


def test_create_panel(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import CamPath, Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            outer_raw = MagicMock()
            inner_raw = MagicMock()
            raw_geo = MagicMock()
            raw_geo.CloseAndFinishLine.return_value = inner_raw
            drw._drw.CreateRectangle.return_value = outer_raw
            drw._drw.Create2DGeometry.return_value = raw_geo

            outer, inner = drw.create_panel(800, 400, 50, 5)

            assert isinstance(outer, CamPath)
            assert isinstance(inner, CamPath)
            drw._drw.CreateRectangle.assert_called_once_with(0, 0, 800, 400)
            outer_raw.Fillet.assert_called_once_with(5.0)
            assert outer_raw.ToolInOut == -1
            drw._drw.Create2DGeometry.assert_called_once_with(50, 50)
            raw_geo.AddLine.assert_any_call(750, 50)
            raw_geo.AddLine.assert_any_call(750, 300)
            raw_geo.AddArc2Point.assert_called_once_with(400, 350, 50, 300)
            raw_geo.CloseAndFinishLine.assert_called_once()
            assert inner_raw.ToolInOut == 1


def test_create_panel_no_fillet(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            outer_raw = MagicMock()
            drw._drw.CreateRectangle.return_value = outer_raw
            outer, _ = drw.create_panel(800, 400, 50, 0)
            assert outer_raw.Fillet.call_count == 0


def test_create_polygon(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import CamPath, Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            path_mock = MagicMock()
            drw._drw.CreatePolygon.return_value = path_mock
            path = drw.create_polygon(50, 6, False, 100, 100)
            assert isinstance(path, CamPath)
            drw._drw.CreatePolygon.assert_called_once_with(50, 6, False, 100, 100)


def test_save_as(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            drw.save_as("test.amd")
            drw._drw.SaveAs.assert_called_once_with("test.amd")


def test_export_dxf(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            drw.export("test.dxf", "dxf")
            drw._drw.SaveDxfFile.assert_called_once_with("test.dxf", False, 2)


def test_export_iges(mock_com: MagicMock) -> None:
    from alphacam_cli.com.constants import ACAM_UNITS_METRIC

    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            drw.export("test.igs", "iges")
            drw._drw.SaveIgesFile.assert_called_once_with("test.igs", False, ACAM_UNITS_METRIC)


def test_export_stl(mock_com: MagicMock) -> None:
    from alphacam_cli.com.constants import ACAM_STL_TYPE_SURFACES

    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            drw.export("test.stl", "stl")
            drw._drw.SetGeosSelected.assert_any_call(True)
            drw._drw.SaveStlFile.assert_called_once_with("test.stl", ACAM_STL_TYPE_SURFACES, 0.1)


def test_export_stl_com_error_raises_value_error(mock_com: MagicMock) -> None:
    from alphacam_cli.com.constants import ACAM_STL_TYPE_SURFACES

    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            drw._drw.SaveStlFile.side_effect = pythoncom.com_error(-2147467259, "Unexpected error")
            with pytest.raises(ValueError, match="stl export failed"):
                drw.export("test.stl", "stl")
            drw._drw.SetGeosSelected.assert_any_call(True)
            drw._drw.SaveStlFile.assert_called_once_with("test.stl", ACAM_STL_TYPE_SURFACES, 0.1)


def test_export_emf(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            drw.export("test.emf", "emf")
            drw._drw.SaveEmfFile.assert_called_once_with("test.emf", False, False)


def test_export_wmf(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            drw.export("test.wmf", "wmf")
            drw._drw.SaveWmfFile.assert_called_once_with("test.wmf", False, False)


def test_export_unknown_format(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            with pytest.raises(ValueError, match="Unsupported export format: xyz"):
                drw.export("test.xyz", "xyz")


def test_output_nc(mock_com: MagicMock) -> None:
    from alphacam_cli.com.constants import ACAM_OUT_NC_FILE

    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            drw.output_nc("test.nc")
            drw._drw.OutputNC.assert_called_once_with("test.nc", ACAM_OUT_NC_FILE, False)


def test_clear(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            drw.clear()
            drw._drw.Clear.assert_called_once_with(
                True, False, True, False, False, False, False, False
            )


def test_select_all_geometries(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            drw.select_all_geometries()
            drw._drw.SetGeosSelected.assert_called_once_with(True)


def test_select_geometry(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            coll = drw._drw.Geometries
            coll.Count = 3

            drw.select_geometry(2)
            coll.Item.assert_called_once_with(2)
            item = coll.Item(2)
            assert item.Selected is True


def test_cam_path_properties(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.core.drawing import CamPath

        path_mock = MagicMock()
        cp = CamPath(path_mock)

        path_mock.Selected = False
        assert cp.selected is False

        cp.selected = True
        assert path_mock.Selected is True

        path_mock.ToolInOut = -1
        assert cp.tool_in_out == -1

        cp.tool_in_out = 1
        assert path_mock.ToolInOut == 1


def test_cam_path_fillet(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.core.drawing import CamPath

        path_mock = MagicMock()
        cp = CamPath(path_mock)
        cp.fillet(5.0)
        path_mock.Fillet.assert_called_once_with(5.0)


def test_cam_path_set_start_point(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.core.drawing import CamPath

        path_mock = MagicMock()
        cp = CamPath(path_mock)
        cp.set_start_point(10, 20)
        path_mock.SetStartPoint.assert_called_once_with(10, 20)


def test_geo2d_add_line_close(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import CamPath, Drawing, Geo2D

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            raw_geo = MagicMock()
            raw_path = MagicMock()
            raw_geo.CloseAndFinishLine.return_value = raw_path
            drw._drw.Create2DGeometry.return_value = raw_geo

            geo = drw.create_2d_geometry(0, 0)
            assert isinstance(geo, Geo2D)

            geo.add_line(100, 0)
            geo.add_line(100, 100)

            cp = geo.close_and_finish_line()
            assert isinstance(cp, CamPath)

            raw_geo.AddLine.assert_any_call(100, 0)
            raw_geo.AddLine.assert_any_call(100, 100)
            raw_geo.CloseAndFinishLine.assert_called_once()


def test_text_properties(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.core.drawing import Text

        text_mock = MagicMock()
        txt = Text(text_mock)

        text_mock.Height = 12.0
        assert txt.height == 12.0
        txt.height = 20.0
        assert text_mock.Height == 20.0

        text_mock.Text = "test"
        assert txt.text_string == "test"
        txt.text_string = "new"
        assert text_mock.Text == "new"

        text_mock.FontName = "Arial"
        assert txt.font_name == "Arial"
        txt.font_name = "Times"
        assert text_mock.FontName == "Times"


def test_drawing_init_none(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.core.drawing import Drawing

        with pytest.raises(ValueError, match="dispatch cannot be None"):
            Drawing(None)


def test_create_layer(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            layer_mock = MagicMock()
            drw._drw.CreateLayer.return_value = layer_mock
            result = drw.create_layer("KONTUR")
            assert result is layer_mock
            drw._drw.CreateLayer.assert_called_once_with("KONTUR")


def test_create_layer_none(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            drw._drw.CreateLayer.return_value = None
            with pytest.raises(RuntimeError, match="Failed to create layer"):
                drw.create_layer("KONTUR")


def test_set_active_layer(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            layer_mock = MagicMock()
            drw.set_active_layer(layer_mock)
            drw._drw.SetLayer.assert_called_once_with(layer_mock)


def test_run_query(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            drw._drw.RunQuery.return_value = 7
            result = drw.run_query(r"C:\ALPHACAM\LICOMDIR\Queries\test.agq")
            assert result == 7
            drw._drw.RunQuery.assert_called_once_with(r"C:\ALPHACAM\LICOMDIR\Queries\test.agq")


def test_cam_path_set_layer(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.core.drawing import CamPath

        path_mock = MagicMock()
        cp = CamPath(path_mock)
        layer_mock = MagicMock()
        cp.set_layer(layer_mock)
        path_mock.SetLayer.assert_called_once_with(layer_mock)
