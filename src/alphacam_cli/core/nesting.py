from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import win32com.client as win32  # type: ignore[import-untyped]

from alphacam_cli.core.drawing import CamPath

logger = logging.getLogger(__name__)


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

    @property
    def name(self) -> str:
        return str(self._ns.Name)  # type: ignore[attr-defined]

    @property
    def material_name(self) -> str:
        return str(self._ns.MaterialName)  # type: ignore[attr-defined]

    @property
    def multiplicity(self) -> int:
        return int(self._ns.Multiplicity)  # type: ignore[attr-defined]

    def part_instances(self) -> list[NestPartInstance]:
        """Return the part instances placed on this sheet (1-based Item)."""
        try:
            coll = self._ns.Parts  # type: ignore[attr-defined]
            count = int(coll.Count)  # type: ignore[attr-defined]
        except Exception as e:
            logger.warning("nest sheet parts: accessing collection failed: %r", e)
            return []
        out: list[NestPartInstance] = []
        for i in range(1, count + 1):
            try:
                out.append(NestPartInstance(coll.Item(i)))
            except Exception as e:
                logger.warning("nest sheet parts: skipping item %s: %r", i, e)
        return out

    def to_dict(self) -> dict[str, Any]:
        name: str | None = None
        try:
            name = self.name
        except Exception as e:
            logger.warning("nest sheet to_dict: reading name failed: %r", e)
        material_name: str | None = None
        try:
            material_name = self.material_name
        except Exception as e:
            logger.warning("nest sheet to_dict: reading material_name failed: %r", e)
        thickness: float | None = None
        try:
            thickness = self.thickness
        except Exception as e:
            logger.warning("nest sheet to_dict: reading thickness failed: %r", e)
        required: int | None = None
        try:
            required = self.required
        except Exception as e:
            logger.warning("nest sheet to_dict: reading required failed: %r", e)
        multiplicity: int | None = None
        try:
            multiplicity = self.multiplicity
        except Exception as e:
            logger.warning("nest sheet to_dict: reading multiplicity failed: %r", e)
        return {
            "name": name,
            "material_name": material_name,
            "thickness": thickness,
            "required": required,
            "multiplicity": multiplicity,
            "parts": [p.to_dict() for p in self.part_instances()],
        }


class NestPartInstance:
    """Wrapper around INestPartInstance COM interface (a placed part on a sheet)."""

    def __init__(self, dispatch: win32.CDispatch) -> None:
        self._npi = dispatch

    @property
    def name(self) -> str:
        return str(self._npi.Name)  # type: ignore[attr-defined]

    @property
    def file_name(self) -> str:
        return str(self._npi.FileName)  # type: ignore[attr-defined]

    @property
    def rotation_angle(self) -> float:
        return float(self._npi.RotationAngle)  # type: ignore[attr-defined]

    @property
    def mirrored(self) -> bool:
        return bool(self._npi.Mirrored)  # type: ignore[attr-defined]

    @property
    def sheet(self) -> NestSheet:
        return NestSheet(self._npi.Sheet)  # type: ignore[attr-defined]

    def position(self) -> tuple[float | None, float | None]:
        """Global X/Y of the part's bounding box centre (resilient to COM byref quirks)."""
        try:
            paths = self._npi.Paths  # type: ignore[attr-defined]
        except Exception:
            return None, None
        calls: list[Any] = []
        if paths is not None:
            calls.append(lambda: paths.GetExtentXYG(0.0, 0.0, 0.0, 0.0))  # type: ignore[attr-defined]
            calls.append(lambda: paths.GetExtentXYG())  # type: ignore[attr-defined]
            try:
                path = paths.Item(1)
                calls.append(lambda: path.GetFeedExtentXYG(0.0, 0.0, 0.0, 0.0))  # type: ignore[attr-defined]
                calls.append(lambda: path.GetFeedExtentXYG())  # type: ignore[attr-defined]
            except Exception:
                pass
        for call in calls:
            try:
                result = call()
            except Exception:
                continue
            if not isinstance(result, (tuple, list)) or len(result) < 4:
                continue
            try:
                values = [float(v) for v in result[:4]]
            except (TypeError, ValueError):
                continue
            return (values[0] + values[2]) / 2.0, (values[1] + values[3]) / 2.0
        return None, None

    def to_dict(self) -> dict[str, Any]:
        px, py = self.position()
        name: str | None = None
        try:
            name = self.name
        except Exception as e:
            logger.warning("nest part to_dict: reading name failed: %r", e)
        file_name: str | None = None
        try:
            file_name = self.file_name
        except Exception as e:
            logger.warning("nest part to_dict: reading file_name failed: %r", e)
        rotation_angle: float | None = None
        try:
            rotation_angle = self.rotation_angle
        except Exception as e:
            logger.warning("nest part to_dict: reading rotation_angle failed: %r", e)
        mirrored: bool | None = None
        try:
            mirrored = self.mirrored
        except Exception as e:
            logger.warning("nest part to_dict: reading mirrored failed: %r", e)
        return {
            "name": name,
            "file_name": file_name,
            "rotation_angle": rotation_angle,
            "mirrored": mirrored,
            "position_x": px,
            "position_y": py,
        }


class NestInformation:
    """Wrapper around INestInformation COM interface (results of the current nest)."""

    def __init__(self, dispatch: win32.CDispatch) -> None:
        self._ni = dispatch

    def sheets(self) -> list[NestSheet]:
        """Return the nested sheets (1-based Item, individual failures skipped)."""
        try:
            coll = self._ni.Sheets  # type: ignore[attr-defined]
            count = int(coll.Count)  # type: ignore[attr-defined]
        except Exception as e:
            logger.warning("nest information: accessing sheets collection failed: %r", e)
            return []
        out: list[NestSheet] = []
        for i in range(1, count + 1):
            try:
                out.append(NestSheet(coll.Item(i)))
            except Exception as e:
                logger.warning("nest information: skipping sheet item %s: %r", i, e)
        return out

    def parts(self) -> list[dict[str, Any]]:
        """Return the nest parts from INestParts (Item → INestPart, only names exposed)."""
        try:
            coll = self._ni.Parts  # type: ignore[attr-defined]
            count = int(coll.Count)  # type: ignore[attr-defined]
        except Exception as e:
            logger.warning("nest information: accessing parts collection failed: %r", e)
            return []
        out: list[dict[str, Any]] = []
        for i in range(1, count + 1):
            try:
                raw = coll.Item(i)
                out.append({"name": str(raw.Name)})  # type: ignore[attr-defined]
            except Exception:
                continue
        return out

    def refresh(self) -> None:
        """Re-scan the drawing and update the nesting information."""
        self._ni.Refresh()  # type: ignore[attr-defined]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sheets": [s.to_dict() for s in self.sheets()],
            "parts": self.parts(),
        }
