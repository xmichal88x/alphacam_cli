from __future__ import annotations

from unittest.mock import MagicMock, patch

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
