from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import win32com.client as win32  # type: ignore[import-untyped]

from alphacam_cli.core.drawing import CamPath


class Nesting:
    """Wrapper around AlphaCAM Nesting COM object.

    Accessed via acApp.Nesting — late binding through IDispatch.
    No separate makepy needed (import in example is commented out).
    """

    def __init__(self, dispatch: win32.CDispatch) -> None:
        self._n = dispatch

    def delete_all_nest_lists(self) -> None:
        self._n.DeleteAllNestLists()  # type: ignore[attr-defined]

    def new_nest_list(self, path: str) -> NestList:
        raw = self._n.NewNestList(path)  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to create nest list")  # noqa: TRY003
        return NestList(raw)

    def new_sheet_list(self) -> SheetList:
        raw = self._n.NewSheetList()  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to create sheet list")  # noqa: TRY003
        return SheetList(raw)

    def nest(self, nest_list: NestList, sheet_list: SheetList) -> NestList:
        raw = self._n.Nest(nest_list.raw_dispatch, sheet_list.raw_dispatch)  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Nesting operation returned None")  # noqa: TRY003
        return NestList(raw)

    def load_nest_list(self, filename: str) -> NestList:
        raw = self._n.LoadNestList(filename)  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to load nest list")  # noqa: TRY003
        return NestList(raw)

    @property
    def suppress_dialogs(self) -> bool:
        return bool(self._n.SuppressDialogs)  # type: ignore[attr-defined]

    @suppress_dialogs.setter
    def suppress_dialogs(self, value: bool) -> None:
        self._n.SuppressDialogs = value  # type: ignore[attr-defined]


class NestList:
    """Wrapper around INestList COM interface."""

    def __init__(self, dispatch: win32.CDispatch) -> None:
        self._nl = dispatch

    @property
    def raw_dispatch(self) -> Any:
        return self._nl

    @property
    def count(self) -> int:
        return int(self._nl.Count)  # type: ignore[attr-defined]

    @property
    def total_time(self) -> int:
        return int(self._nl.TotalTime)  # type: ignore[attr-defined]

    @total_time.setter
    def total_time(self, value: int) -> None:
        self._nl.TotalTime = value  # type: ignore[attr-defined]

    def add_file(self, filename: str) -> NestPart:
        raw = self._nl.AddFile(filename)  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to add file to nest list")  # noqa: TRY003
        return NestPart(raw)

    def save(self) -> None:
        self._nl.Save()  # type: ignore[attr-defined]

    def sort(self, method: int = 0) -> None:
        self._nl.Sort(method)  # type: ignore[attr-defined]


class NestPart:
    """Wrapper around INestPart COM interface."""

    def __init__(self, dispatch: win32.CDispatch) -> None:
        self._np = dispatch

    @property
    def required(self) -> int:
        return int(self._np.Required)  # type: ignore[attr-defined]

    @required.setter
    def required(self, value: int) -> None:
        self._np.Required = value  # type: ignore[attr-defined]

    @property
    def rotation_angle(self) -> float:
        return float(self._np.RotationAngle)  # type: ignore[attr-defined]

    @rotation_angle.setter
    def rotation_angle(self, value: float) -> None:
        self._np.RotationAngle = value  # type: ignore[attr-defined]


class SheetList:
    """Wrapper around ISheetList COM interface."""

    def __init__(self, dispatch: win32.CDispatch) -> None:
        self._sl = dispatch

    @property
    def raw_dispatch(self) -> Any:
        return self._sl

    @property
    def count(self) -> int:
        return int(self._sl.Count)  # type: ignore[attr-defined]

    def add(self, geometry: CamPath | Any) -> NestSheet:
        """Add a geometry (CamPath or raw COM object) as a sheet."""
        raw_geo = geometry.raw_dispatch if isinstance(geometry, CamPath) else geometry
        raw = self._sl.Add(raw_geo)  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to add sheet")  # noqa: TRY003
        return NestSheet(raw)


class NestSheet:
    """Wrapper around INestSheet COM interface."""

    def __init__(self, dispatch: win32.CDispatch) -> None:
        self._ns = dispatch

    @property
    def required(self) -> int:
        return int(self._ns.Required)  # type: ignore[attr-defined]

    @required.setter
    def required(self, value: int) -> None:
        self._ns.Required = value  # type: ignore[attr-defined]

    @property
    def thickness(self) -> float:
        return float(self._ns.Thickness)  # type: ignore[attr-defined]

    @thickness.setter
    def thickness(self, value: float) -> None:
        self._ns.Thickness = value  # type: ignore[attr-defined]
