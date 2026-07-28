from __future__ import annotations

from unittest.mock import MagicMock


def test_drawing_creation(mock_com):
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing

        with alphacam_context() as raw:
            drw = Drawing(raw.CreateTempDrawing())
            assert drw.geometries_count == 0
            assert drw.tool_paths_count == 0


def test_geometries_iteration(mock_com):
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing, Path

        with alphacam_context() as raw:
            drw = Drawing(raw.ActiveDrawing)
            # Mock geometries collection
            geo = MagicMock()
            geo.Selected = False
            geo.ToolInOut = -1

            geometries_mock = MagicMock()
            geometries_mock.Count = 2
            geometries_mock.side_effect = lambda i: geo
            drw._drw.Geometries = geometries_mock

            geos = drw.geometries()
            assert len(geos) == 2
            assert isinstance(geos[0], Path)


def test_rectangle_creation(mock_com):
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Path

        rect_mock = MagicMock()
        with alphacam_context() as raw:
            raw.CreateRectangle.return_value = rect_mock
            p = Path(raw.CreateRectangle(0, 0, 100, 50))
            assert p is not None
