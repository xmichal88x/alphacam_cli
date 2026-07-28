from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from alphacam_cli.core.events import NcEventHandler


def test_drawing_creation(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.CreateTempDrawing())
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
            drw = Drawing(raw.CreateTempDrawing())
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
            drw = Drawing(raw.CreateTempDrawing())
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
            drw = Drawing(raw.CreateTempDrawing())
            raw_geo = MagicMock()
            drw._drw.Create2DGeometry.return_value = raw_geo
            geo = drw.create_2d_geometry(10, 20)
            assert isinstance(geo, Geo2D)
            drw._drw.Create2DGeometry.assert_called_once_with(10, 20)


def test_create_polygon(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import CamPath, Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.CreateTempDrawing())
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
            drw = Drawing(raw.CreateTempDrawing())
            drw.save_as("test.amd")
            drw._drw.SaveAs.assert_called_once_with("test.amd")


def test_output_nc(mock_com: MagicMock) -> None:
    from alphacam_cli.com.constants import ACAM_OUT_NC_FILE

    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.CreateTempDrawing())
            drw.output_nc("test.nc")
            drw._drw.OutputNC.assert_called_once_with("test.nc", ACAM_OUT_NC_FILE, False)


def test_clear(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.CreateTempDrawing())
            drw.clear()
            drw._drw.Clear.assert_called_once_with(
                True, False, True, False, False, False, False, False
            )


def test_select_all_geometries(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.CreateTempDrawing())
            geo1 = MagicMock()
            geo2 = MagicMock()
            geometries_mock = MagicMock()
            geometries_mock.Count = 2
            geometries_mock.Item.side_effect = lambda i: geo1 if i == 1 else geo2
            drw._drw.Geometries = geometries_mock

            drw.select_all_geometries()

            assert geo1.Selected is True
            assert geo2.Selected is True


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
            drw = Drawing(raw.CreateTempDrawing())
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
