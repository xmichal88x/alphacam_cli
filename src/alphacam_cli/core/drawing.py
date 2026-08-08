from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import win32com.client as win32  # type: ignore[import-untyped]

from alphacam_cli.com.constants import ACAM_OUT_NC_FILE


class Drawing:
    """Typed wrapper around AlphaCAM Drawing COM object."""

    def __init__(self, dispatch: win32.CDispatch) -> None:
        if dispatch is None:
            raise ValueError("dispatch cannot be None")  # noqa: TRY003
        self._drw = dispatch

    @property
    def geometries_count(self) -> int:
        return int(self._drw.Geometries.Count)  # type: ignore[attr-defined]

    @property
    def tool_paths_count(self) -> int:
        return int(self._drw.ToolPaths.Count)  # type: ignore[attr-defined]

    def create_rectangle(self, x1: float, y1: float, x2: float, y2: float) -> CamPath:
        raw = self._drw.CreateRectangle(x1, y1, x2, y2)  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to create rectangle")  # noqa: TRY003
        return CamPath(raw)

    def create_nest_data(self, file_name: str) -> Any:
        raw = self._drw.CreateNestData(file_name)  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to create nest data")  # noqa: TRY003
        return raw

    def create_circle(self, radius: float, cx: float, cy: float) -> CamPath:
        raw = self._drw.CreateCircle(radius, cx, cy)  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to create circle")  # noqa: TRY003
        return CamPath(raw)

    def create_text(self, text: str, x: float, y: float, height: float) -> Text:
        raw = self._drw.CreateText2(text, x, y, height)  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to create text")  # noqa: TRY003
        return Text(raw)

    def create_2d_geometry(self, x: float, y: float) -> Geo2D:
        raw = self._drw.Create2DGeometry(x, y)  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to create 2D geometry")  # noqa: TRY003
        return Geo2D(raw)

    def create_polygon(
        self, radius: float, sides: int, circumscribed: bool, cx: float, cy: float
    ) -> CamPath:
        raw = self._drw.CreatePolygon(radius, sides, circumscribed, cx, cy)  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to create polygon")  # noqa: TRY003
        return CamPath(raw)

    def zoom_all(self) -> None:
        self._drw.ZoomAll()  # type: ignore[attr-defined]

    def save_as(self, path: str) -> None:
        self._drw.SaveAs(path)  # type: ignore[attr-defined]

    def export(self, path: str, fmt: str) -> None:
        """Export the drawing to a CAD/graphics file (DXF, IGES, STL, EMF, WMF)."""
        from alphacam_cli.com.constants import (
            ACAM_STL_TYPE_STL,
            ACAM_UNITS_METRIC,
        )

        if fmt == "dxf":
            self._drw.SaveDxfFile(path, False, 2)  # type: ignore[attr-defined]
        elif fmt in ("igs", "iges"):
            self._drw.SaveIgesFile(path, False, ACAM_UNITS_METRIC)  # type: ignore[attr-defined]
        elif fmt == "stl":
            import pythoncom  # type: ignore[import-untyped]

            try:
                self._drw.SaveStlFile(path, ACAM_STL_TYPE_STL, 0.1)  # type: ignore[attr-defined]
            except pythoncom.com_error as e:
                raise ValueError(  # noqa: TRY003
                    "stl export requires 3D surfaces/solids in the drawing "
                    "(current drawing appears 2D)"
                ) from e
        elif fmt == "emf":
            self._drw.SaveEmfFile(path, False, False)  # type: ignore[attr-defined]
        elif fmt == "wmf":
            self._drw.SaveWmfFile(path, False, False)  # type: ignore[attr-defined]
        else:
            raise ValueError(f"Unsupported export format: {fmt}")  # noqa: TRY003

    def output_nc(self, path: str) -> None:
        self._drw.OutputNC(path, ACAM_OUT_NC_FILE, False)  # type: ignore[attr-defined]

    def output_nc_with_events(self, path: str, app_dispatch: Any) -> None:
        from win32com.client import DispatchWithEvents  # type: ignore[import-untyped]

        from alphacam_cli.core.events import NcEventHandler

        handler = DispatchWithEvents(app_dispatch, NcEventHandler)
        handler.nc_path = path
        self._drw.OutputNC(path, ACAM_OUT_NC_FILE, False)  # type: ignore[attr-defined]

    def clear(
        self,
        geometry: bool = True,
        construction: bool = False,
        toolpaths: bool = True,
        dimensions: bool = False,
        splines: bool = False,
        surfaces: bool = False,
        user_layers: bool = False,
        text: bool = False,
    ) -> None:
        self._drw.Clear(  # type: ignore[attr-defined]
            geometry,
            construction,
            toolpaths,
            dimensions,
            splines,
            surfaces,
            user_layers,
            text,
        )

    def geometries(self) -> list[CamPath]:
        coll = self._drw.Geometries  # type: ignore[attr-defined]
        count = int(coll.Count)
        return [CamPath(coll.Item(i)) for i in range(1, count + 1)]

    def select_all_geometries(self) -> None:
        self._drw.SetGeosSelected(True)  # type: ignore[attr-defined]

    def select_geometry(self, index: int = 1) -> None:
        coll = self._drw.Geometries  # type: ignore[attr-defined]
        count = int(coll.Count)
        if index < 1 or index > count:
            raise IndexError(f"Geometry index {index} out of range (1-{count})")  # noqa: TRY003
        coll.Item(index).Selected = True  # type: ignore[attr-defined]


class CamPath:
    def __init__(self, dispatch: win32.CDispatch) -> None:
        if dispatch is None:
            raise ValueError("dispatch cannot be None")  # noqa: TRY003
        self._path = dispatch

    @property
    def raw_dispatch(self) -> Any:
        return self._path

    @property
    def selected(self) -> bool:
        return bool(self._path.Selected)  # type: ignore[attr-defined]

    @selected.setter
    def selected(self, value: bool) -> None:
        self._path.Selected = value  # type: ignore[attr-defined]

    @property
    def tool_in_out(self) -> int:
        return int(self._path.ToolInOut)  # type: ignore[attr-defined]

    @tool_in_out.setter
    def tool_in_out(self, value: int) -> None:
        self._path.ToolInOut = value  # type: ignore[attr-defined]

    def fillet(self, radius: float) -> None:
        self._path.Fillet(radius)  # type: ignore[attr-defined]

    def set_start_point(self, x: float, y: float) -> None:
        self._path.SetStartPoint(x, y)  # type: ignore[attr-defined]


class Geo2D:
    def __init__(self, dispatch: win32.CDispatch) -> None:
        if dispatch is None:
            raise ValueError("dispatch cannot be None")  # noqa: TRY003
        self._geo = dispatch

    def add_line(self, x: float, y: float) -> None:
        self._geo.AddLine(x, y)  # type: ignore[attr-defined]

    def add_arc_2point(self, end_x: float, end_y: float, arc_x: float, arc_y: float) -> None:
        self._geo.AddArc2Point(end_x, end_y, arc_x, arc_y)  # type: ignore[attr-defined]

    def close_and_finish_line(self) -> CamPath:
        raw = self._geo.CloseAndFinishLine()  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to close and finish line")  # noqa: TRY003
        return CamPath(raw)

    def finish(self) -> CamPath:
        raw = self._geo.Finish()  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to finish geometry")  # noqa: TRY003
        return CamPath(raw)


class Text:
    def __init__(self, dispatch: win32.CDispatch) -> None:
        if dispatch is None:
            raise ValueError("dispatch cannot be None")  # noqa: TRY003
        self._text = dispatch

    @property
    def height(self) -> float:
        return float(self._text.Height)  # type: ignore[attr-defined]

    @height.setter
    def height(self, value: float) -> None:
        self._text.Height = value  # type: ignore[attr-defined]

    @property
    def text_string(self) -> str:
        return str(self._text.Text)  # type: ignore[attr-defined]

    @text_string.setter
    def text_string(self, value: str) -> None:
        self._text.Text = value  # type: ignore[attr-defined]

    @property
    def font_name(self) -> str:
        return str(self._text.FontName)  # type: ignore[attr-defined]

    @font_name.setter
    def font_name(self, value: str) -> None:
        self._text.FontName = value  # type: ignore[attr-defined]
