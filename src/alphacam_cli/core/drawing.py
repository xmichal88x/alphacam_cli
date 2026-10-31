from __future__ import annotations

import contextlib
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import win32com.client as win32  # type: ignore[import-untyped]

    from alphacam_cli.core.nesting import NestInformation

from alphacam_cli.com.constants import ACAM_OUT_NC_FILE
from alphacam_cli.core.geolint import (
    FIXABLE_TYPES,
    REBUILD_TYPES,
    LintBudgetExceeded,
    PathInput,
    Segment,
    Thresholds,
    analyze_paths,
    path_has_arcs,
    rebuild_segments,
)


class UnreadableGeometryError(RuntimeError):
    pass


REMOVAL_TYPES = ("tiny", "spike")


def _skip_reason(types: list[str]) -> str | None:
    for name in ("unreadable", "empty", "layerUnreadable", "bigArc", "selfIntersect"):
        if name in types:
            return name
    if not set(types) & set(REBUILD_TYPES):
        return "no automatic fix"
    return None


def _fix_payload(
    *,
    units: str,
    fixed: dict[str, int],
    skipped: list[dict[str, Any]],
    failed: list[dict[str, Any]],
    deleted_paths: list[int],
    backup_path: str | None,
    remaining: dict[str, int],
    warnings: list[str],
    dry_run: bool,
    would_fix: dict[str, int] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "success": True,
        "units": units,
        "fixed": fixed,
        "skipped": skipped,
        "failed": failed,
        "deleted_paths": deleted_paths,
        "backup": backup_path,
        "remaining": remaining,
        "warnings": warnings,
    }
    if would_fix is not None:
        payload["would_fix"] = would_fix
    return payload


@dataclass(frozen=True)
class MoveResult:
    moved: int
    warnings: tuple[str, ...]


def _prop(obj: Any, name: str, default: Any) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return default


def _read_prop(obj: Any, name: str) -> Any:
    try:
        return getattr(obj, name)
    except Exception as exc:
        raise UnreadableGeometryError from exc


def _read_coord(obj: Any, name: str) -> float:
    try:
        return float(_read_prop(obj, name))
    except Exception as exc:
        raise UnreadableGeometryError from exc


class Drawing:
    """Typed wrapper around AlphaCAM Drawing COM object."""

    def __init__(self, dispatch: win32.CDispatch) -> None:
        if dispatch is None:
            raise ValueError("dispatch cannot be None")  # noqa: TRY003
        self._drw = dispatch

    @property
    def raw_dispatch(self) -> Any:
        """Return the raw COM dispatch object (for add-in automation)."""
        return self._drw

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

    def create_panel(
        self,
        width: float,
        height: float,
        offset: float = 50,
        fillet: float = 5,
    ) -> tuple[CamPath, CamPath]:
        """Create a parametric door/frame panel (official CreateDoor.py pattern).

        Returns (outer, inner): a filleted outer rectangle (tool outside)
        and an inner contour with a 2-point arc (tool inside).
        """
        outer = self.create_rectangle(0, 0, width, height)
        if fillet > 0:
            outer.fillet(fillet)
        outer.tool_in_out = -1  # Outside

        geo2d = self.create_2d_geometry(offset, offset)
        geo2d.add_line(width - offset, offset)
        geo2d.add_line(width - offset, height - 2 * offset)
        geo2d.add_arc_2point(width / 2, height - offset, offset, height - 2 * offset)
        inner = geo2d.close_and_finish_line()
        inner.tool_in_out = 1  # Inside

        return outer, inner

    def create_layer(self, name: str) -> Any:
        """Create (or return the existing) user layer with the given name.

        Returns the raw COM dispatch of the layer (must be passed to
        set_layer/SetLayer within the same process).
        """
        raw = self._drw.CreateLayer(name)  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to create layer")  # noqa: TRY003
        return raw

    def set_active_layer(self, layer: Any) -> None:
        """Set the active user layer."""
        self._drw.SetLayer(layer)  # type: ignore[attr-defined]

    def run_query(self, file_path: str) -> int:
        """Run a geometry query (.agq) on the drawing; returns applied rule count."""
        return int(self._drw.RunQuery(file_path))  # type: ignore[attr-defined]

    def get_nest_information(self) -> NestInformation:
        """Return the nesting results (sheets with part placements) for this drawing."""
        from alphacam_cli.core.nesting import NestInformation

        raw = self._drw.GetNestInformation()  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to get nest information")  # noqa: TRY003
        return NestInformation(raw)

    def zoom_all(self) -> None:
        self._drw.ZoomAll()  # type: ignore[attr-defined]

    def save_as(self, path: str) -> None:
        self._drw.SaveAs(path)  # type: ignore[attr-defined]

    def export(self, path: str, fmt: str) -> None:
        """Export the drawing to a CAD/graphics file (DXF, IGES, STL, EMF, WMF)."""
        from alphacam_cli.com.constants import (
            ACAM_STL_TYPE_SURFACES,
            ACAM_UNITS_METRIC,
        )

        if fmt == "dxf":
            self._drw.SaveDxfFile(path, False, 2)  # type: ignore[attr-defined]
        elif fmt in ("igs", "iges"):
            self._drw.SaveIgesFile(path, False, ACAM_UNITS_METRIC)  # type: ignore[attr-defined]
        elif fmt == "stl":
            import pythoncom  # type: ignore[import-untyped]

            self.select_all_geometries()
            try:
                self._drw.SaveStlFile(path, ACAM_STL_TYPE_SURFACES, 0.1)  # type: ignore[attr-defined]
            except pythoncom.com_error as e:
                raise ValueError(  # noqa: TRY003
                    "stl export failed: no facetable geometry in the drawing"
                ) from e
            with contextlib.suppress(pythoncom.com_error):
                self._drw.SetGeosSelected(False)  # type: ignore[attr-defined]
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

    def _restore_selection(self, paths: list[CamPath], previous: list[bool]) -> list[int]:
        failed: list[int] = []
        for index in range(min(len(paths), len(previous))):
            try:
                paths[index].selected = previous[index]
            except Exception:
                failed.append(index)
        return failed

    def move(self, dx: float, dy: float, dz: float = 0.0, select_all: bool = False) -> MoveResult:
        for name, value in (("dx", dx), ("dy", dy), ("dz", dz)):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")  # noqa: TRY003
        paths = self.geometries()
        previous: list[bool] | None = None
        moved_paths: list[tuple[int, CamPath]] = []
        error: Exception | None = None
        selected: list[tuple[int, CamPath]] = []
        start_points: dict[int, tuple[float, float, float] | None] = {}
        try:
            previous = [path.selected for path in paths] if select_all else None
            if select_all:
                self.select_all_geometries()
            selected = [(index, path) for index, path in enumerate(paths) if path.selected]
        except Exception as e:
            error = e
        if error is None and not selected:
            error = RuntimeError("No selected geometries")
        failed_path: tuple[int, CamPath] | None = None
        if error is None:
            for index, path in selected:
                start_points[index] = path.start_point()
                try:
                    path.move(dx, dy, dz)
                except Exception as e:
                    error = e
                    failed_path = (index, path)
                    break
                moved_paths.append((index, path))

        rolled_back = 0
        rollback_failed: list[int] = []
        rollback_uncertain: list[int] = []
        if error is not None:
            if failed_path is not None:
                index, path = failed_path
                outcome = self._rollback_path(
                    path, index, start_points.get(index), dx, dy, dz, rollback_uncertain
                )
                if outcome is None:
                    rollback_failed.append(index)
                elif outcome:
                    rolled_back += 1
            for index, path in reversed(moved_paths):
                outcome = self._rollback_path(
                    path, index, start_points.get(index), dx, dy, dz, rollback_uncertain
                )
                if outcome is None:
                    rollback_failed.append(index)
                elif outcome:
                    rolled_back += 1

        restore_failed = self._restore_selection(paths, previous) if previous is not None else []
        restore_message = (
            "selection restore failed for path(s) "
            + ", ".join(str(index) for index in restore_failed)
            if restore_failed
            else ""
        )

        if error is not None:
            details = [f"move failed: {error}"]
            if rollback_failed:
                failed_indices = ", ".join(str(index) for index in sorted(rollback_failed))
                details.append(f"rollback_failed={len(rollback_failed)} (path(s) {failed_indices})")
            else:
                details.append(f"rolled back {rolled_back} path(s)")
            for index in sorted(rollback_uncertain):
                details.append(f"rollback uncertain for path {index}")
            if restore_failed:
                details.append(restore_message)
            raise RuntimeError("; ".join(details)) from error
        warnings = list(self._move_warnings(dz))
        if restore_failed:
            warnings.append(restore_message)
        return MoveResult(moved=len(moved_paths), warnings=tuple(warnings))

    def _rollback_path(
        self,
        path: CamPath,
        index: int,
        before: tuple[float, float, float] | None,
        dx: float,
        dy: float,
        dz: float,
        uncertain: list[int],
    ) -> bool | None:
        after = path.start_point()
        if before is None or after is None:
            uncertain.append(index)
        elif after == before:
            return False
        try:
            path.move(-dx, -dy, -dz)
        except Exception:
            return None
        return True

    def _move_warnings(self, dz: float) -> tuple[str, ...]:
        warnings: list[str] = []
        if dz != 0.0:
            warnings.append("dz != 0: geometry moved off Z=0 plane")
        try:
            tool_paths = int(self.tool_paths_count)
        except Exception:
            warnings.append(
                "cannot determine whether the drawing contains toolpaths; "
                "geometry may be moved without moving existing toolpaths"
            )
        else:
            if tool_paths > 0:
                warnings.append(
                    "drawing contains toolpaths; moving geometry does not move existing toolpaths"
                )
        return tuple(warnings)

    def lint(self, select_all: bool = False, *, units: str) -> dict[str, Any]:
        thresholds = Thresholds().scaled(units)
        if select_all:
            count = int(self._drw.Geometries.Count)  # type: ignore[attr-defined]
            if count > thresholds.max_paths:
                raise LintBudgetExceeded(  # noqa: TRY003
                    f"lint budget exceeded: {count} paths "
                    f"(limit {thresholds.max_paths}); "
                    "narrow the scope (select fewer geometries and rerun without --all)"
                )
        paths = self.geometries()
        if select_all:
            selected = list(enumerate(paths))
        else:
            selected = [(index, path) for index, path in enumerate(paths) if path.selected]
            if not selected:
                raise RuntimeError("No selected geometries")  # noqa: TRY003
        if len(selected) > thresholds.max_paths:
            raise LintBudgetExceeded(  # noqa: TRY003
                f"lint budget exceeded: {len(selected)} paths "
                f"(limit {thresholds.max_paths}); "
                "narrow the scope (select fewer geometries and rerun without --all)"
            )
        total_elements = 0
        element_counts: dict[int, int] = {}
        unreadable: set[int] = set()
        for index, path in selected:
            try:
                count = path.element_count()
            except UnreadableGeometryError:
                unreadable.add(index)
                continue
            element_counts[index] = count
            total_elements += count
            if total_elements > thresholds.max_total_elements:
                raise LintBudgetExceeded(  # noqa: TRY003
                    f"lint budget exceeded: {total_elements} elements "
                    f"(limit {thresholds.max_total_elements}); "
                    "narrow the scope (select fewer geometries and rerun without --all)"
                )
        inputs: list[PathInput] = []
        for index, path in selected:
            layer: str | None
            layer_unreadable = False
            try:
                layer = path.layer
            except Exception:
                layer = None
                layer_unreadable = True
            if index in unreadable:
                inputs.append(
                    PathInput(
                        closed=None,
                        segments=[],
                        layer=layer,
                        unreadable=True,
                        layer_unreadable=layer_unreadable,
                        index=index,
                    )
                )
                continue
            try:
                closed = path.closed
                segments = path.segments(expected_count=element_counts.get(index))
            except UnreadableGeometryError:
                inputs.append(
                    PathInput(
                        closed=None,
                        segments=[],
                        layer=layer,
                        unreadable=True,
                        layer_unreadable=layer_unreadable,
                        index=index,
                    )
                )
                continue
            inputs.append(
                PathInput(
                    closed=closed,
                    segments=segments,
                    layer=layer,
                    layer_unreadable=layer_unreadable,
                    index=index,
                )
            )
        return analyze_paths(inputs, thresholds, units=units)

    def lint_fix(
        self,
        select_all: bool = False,
        *,
        units: str,
        dry_run: bool = False,
        backup: bool = True,
    ) -> dict[str, Any]:
        thresholds = Thresholds().scaled(units)
        paths = self.geometries()
        selected = (
            list(enumerate(paths))
            if select_all
            else [(index, path) for index, path in enumerate(paths) if path.selected]
        )
        if not selected:
            raise RuntimeError("No selected geometries")  # noqa: TRY003
        report = self.lint(select_all=select_all, units=units)
        issues_by_index = {
            int(entry["index"]): list(entry.get("issues", [])) for entry in report.get("paths", [])
        }
        closed_by_index = {
            int(entry["index"]): entry.get("closed") for entry in report.get("paths", [])
        }

        warnings = self._fix_warnings()
        fixed = {name: 0 for name in FIXABLE_TYPES}
        skipped: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        planned: list[tuple[int, CamPath, list[dict[str, Any]], list[Segment], bool]] = []
        delete_targets: list[tuple[int, CamPath, list[dict[str, Any]]]] = []
        duplicate_targets: list[tuple[int, CamPath, int]] = []

        for index, path in selected:
            issues = issues_by_index.get(index)
            if not issues:
                continue
            types = sorted({str(issue.get("type", "")) for issue in issues})
            duplicate_count = sum(1 for issue in issues if issue.get("type") == "duplicates")
            if duplicate_count:
                duplicate_targets.append((index, path, duplicate_count))
                continue
            reason = _skip_reason(types)
            segments: list[Segment] = []
            if reason is None:
                try:
                    segments = path.segments()
                except Exception:
                    reason = "unreadable"
                else:
                    if path_has_arcs(segments):
                        reason = "contains arcs"
            if reason is not None:
                skipped.append({"index": index, "types": types, "reason": reason})
                continue
            closed = bool(closed_by_index.get(index))
            rebuilt = rebuild_segments(segments, thresholds, closed=closed)
            if not rebuilt and set(types) <= set(REMOVAL_TYPES):
                delete_targets.append((index, path, issues))
                continue
            if (
                not closed
                and len(rebuilt) > 1
                and math.dist(
                    (rebuilt[0].start_x, rebuilt[0].start_y),
                    (rebuilt[-1].end_x, rebuilt[-1].end_y),
                )
                <= 1e-9
            ):
                closed = True
            planned.append((index, path, issues, rebuilt, closed))

        if dry_run:
            would_fix = {name: 0 for name in FIXABLE_TYPES}
            for _, _, issues, _, _ in planned:
                for issue in issues:
                    issue_type = str(issue.get("type", ""))
                    if issue_type in REBUILD_TYPES:
                        would_fix[issue_type] += 1
            for _, _, issues in delete_targets:
                for issue in issues:
                    issue_type = str(issue.get("type", ""))
                    if issue_type in REBUILD_TYPES:
                        would_fix[issue_type] += 1
            for _, _, count in duplicate_targets:
                would_fix["duplicates"] += count
            return _fix_payload(
                units=units,
                fixed=fixed,
                skipped=skipped,
                failed=failed,
                deleted_paths=[],
                backup_path=None,
                remaining=dict(report.get("issues_by_type", {})),
                warnings=warnings,
                dry_run=True,
                would_fix=would_fix,
            )

        backup_path: str | None = None
        if backup and (planned or delete_targets or duplicate_targets):
            backup_path = self._backup_drawing()

        for index, path, issues, rebuilt, closed in sorted(
            planned, key=lambda item: item[0], reverse=True
        ):
            reason = self._apply_rebuild(path, rebuilt, closed)
            if reason is None:
                for issue in issues:
                    issue_type = str(issue.get("type", ""))
                    if issue_type in fixed:
                        fixed[issue_type] += 1
            else:
                failed.append(
                    {
                        "index": index,
                        "types": sorted({str(issue.get("type", "")) for issue in issues}),
                        "reason": reason,
                    }
                )

        deleted_paths: list[int] = []
        for index, path, issues in sorted(delete_targets, key=lambda item: item[0], reverse=True):
            reason = self._remove_path(path)
            if reason is None:
                deleted_paths.append(index)
                for issue in issues:
                    issue_type = str(issue.get("type", ""))
                    if issue_type in fixed:
                        fixed[issue_type] += 1
            else:
                failed.append(
                    {
                        "index": index,
                        "types": sorted({str(issue.get("type", "")) for issue in issues}),
                        "reason": reason,
                    }
                )

        for index, path, count in sorted(duplicate_targets, key=lambda item: item[0], reverse=True):
            try:
                self._delete_geometry(path)
            except Exception as exc:
                failed.append(
                    {"index": index, "types": ["duplicates"], "reason": f"delete failed: {exc}"}
                )
            else:
                fixed["duplicates"] += count

        self._restore_scope_selection(select_all, [path for _, path in selected])
        try:
            remaining_report = self.lint(select_all=select_all, units=units)
            remaining = dict(remaining_report.get("issues_by_type", {}))
        except (RuntimeError, LintBudgetExceeded):
            remaining = {}

        skipped.sort(key=lambda entry: int(entry["index"]))
        failed.sort(key=lambda entry: int(entry["index"]))
        deleted_paths.sort()
        return _fix_payload(
            units=units,
            fixed=fixed,
            skipped=skipped,
            failed=failed,
            deleted_paths=deleted_paths,
            backup_path=backup_path,
            remaining=remaining,
            warnings=warnings,
            dry_run=False,
            would_fix=None,
        )

    def _fix_warnings(self) -> list[str]:
        try:
            tool_paths = int(self.tool_paths_count)
        except Exception:
            return [
                "cannot determine toolpath count; rebuilding geometry may orphan existing toolpaths"
            ]
        if tool_paths > 0:
            return [
                f"drawing contains {tool_paths} toolpath(s); "
                "rebuilding geometry may orphan existing toolpaths"
            ]
        return []

    def _backup_drawing(self) -> str:
        root = os.environ.get("TEMP") or tempfile.gettempdir()
        name = f"alphacam_lint_backup_{datetime.now().strftime('%Y%m%d-%H%M%S')}.dxf"
        target = os.path.join(root, name)
        try:
            self.export(target, "dxf")
        except Exception as exc:
            raise RuntimeError(f"backup failed: {exc}") from exc  # noqa: TRY003
        return target

    def _remove_path(self, path: CamPath) -> str | None:
        before = self.geometries_count
        try:
            self._delete_geometry(path)
        except Exception as exc:
            return f"delete failed: {exc}"
        if self.geometries_count >= before:
            return "delete failed: geometry count did not decrease"
        return None

    def _delete_geometry(self, path: CamPath) -> None:
        for candidate in self.geometries():
            with contextlib.suppress(Exception):
                candidate.selected = False
        path.selected = True
        self._drw.DeleteSelected()  # type: ignore[attr-defined]

    def _apply_rebuild(
        self, old_path: CamPath, segments: list[Segment], closed: bool
    ) -> str | None:
        if not segments:
            return "no segments left"
        points = [(segments[0].start_x, segments[0].start_y)]
        points.extend((segment.end_x, segment.end_y) for segment in segments)
        new_path: CamPath | None = None
        try:
            geo = self.create_2d_geometry(points[0][0], points[0][1])
            for x, y in points[1:]:
                geo.add_line(x, y)
            new_path = geo.close_and_finish_line() if closed else geo.finish()
        except Exception as exc:
            if new_path is not None:
                with contextlib.suppress(Exception):
                    self._delete_geometry(new_path)
            return f"rebuild failed: {exc}"
        reason = self._verify_rebuild(new_path, points)
        if reason is not None:
            with contextlib.suppress(Exception):
                self._delete_geometry(new_path)
            return reason
        try:
            self._delete_geometry(old_path)
        except Exception as exc:
            with contextlib.suppress(Exception):
                self._delete_geometry(new_path)
            return f"delete failed: {exc}"
        return None

    def _verify_rebuild(self, new_path: CamPath, points: list[tuple[float, float]]) -> str | None:
        try:
            segments = new_path.segments()
        except Exception as exc:
            return f"verify read failed: {exc}"
        expected_count = len(points) - 1
        if len(segments) != expected_count:
            return f"element count mismatch: {len(segments)} != {expected_count}"
        vertices = [(segment.start_x, segment.start_y) for segment in segments]
        vertices.extend((segment.end_x, segment.end_y) for segment in segments)
        actual_xs = [x for x, _ in vertices]
        actual_ys = [y for _, y in vertices]
        expected_xs = [x for x, _ in points]
        expected_ys = [y for _, y in points]
        if (
            abs(min(actual_xs) - min(expected_xs)) > 1e-6
            or abs(max(actual_xs) - max(expected_xs)) > 1e-6
            or abs(min(actual_ys) - min(expected_ys)) > 1e-6
            or abs(max(actual_ys) - max(expected_ys)) > 1e-6
        ):
            return "bbox mismatch"
        expected_length = sum(
            math.dist(points[position], points[position + 1]) for position in range(len(points) - 1)
        )
        actual_length = sum(
            math.dist((segment.start_x, segment.start_y), (segment.end_x, segment.end_y))
            for segment in segments
        )
        if abs(actual_length - expected_length) > 1e-6:
            return f"length mismatch: {actual_length} != {expected_length}"
        return None

    def _restore_scope_selection(self, select_all: bool, paths: list[CamPath]) -> None:
        if select_all:
            return
        with contextlib.suppress(Exception):
            self._drw.SetGeosSelected(False)  # type: ignore[attr-defined]
        for path in paths:
            with contextlib.suppress(Exception):
                path.selected = True


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

    def set_layer(self, layer: Any) -> None:
        """Assign this geometry to a user layer (raw dispatch from Drawing.create_layer)."""
        self._path.SetLayer(layer)  # type: ignore[attr-defined]

    def move(self, dx: float, dy: float, dz: float = 0.0) -> None:
        self._path.MoveG(dx, dy, dz)  # type: ignore[attr-defined]

    def start_point(self) -> tuple[float, float, float] | None:
        try:
            element = self._path.GetFirstElem()  # type: ignore[attr-defined]
            if element is None:
                return None
            return (
                float(element.StartXG),
                float(element.StartYG),
                float(element.StartZG),
            )
        except Exception:
            return None

    @property
    def closed(self) -> bool:
        return bool(_read_prop(self._path, "Closed"))

    @property
    def layer(self) -> str | None:
        layer = self._path.GetLayer()
        if layer is None:
            return None
        name = layer.Name
        if name is None:
            return None
        return str(name)

    def element_count(self) -> int:
        try:
            return int(self._path.GetElemCount())  # type: ignore[attr-defined]
        except Exception as exc:
            raise UnreadableGeometryError from exc

    def segments(self, expected_count: int | None = None) -> list[Segment]:
        count = self.element_count() if expected_count is None else expected_count
        if count == 0:
            return []
        try:
            element = self._path.GetFirstElem()  # type: ignore[attr-defined]
        except Exception as exc:
            raise UnreadableGeometryError from exc
        segments: list[Segment] = []
        for _ in range(count):
            if element is None:
                break
            is_arc = bool(_read_prop(element, "IsArc"))
            start_x = _read_coord(element, "StartXG")
            start_y = _read_coord(element, "StartYG")
            start_z = _read_coord(element, "StartZG")
            end_x = _read_coord(element, "EndXG")
            end_y = _read_coord(element, "EndYG")
            end_z = _read_coord(element, "EndZG")
            if is_arc:
                length = _read_coord(element, "Length")
                center_x = _read_coord(element, "CenterXG")
                center_y = _read_coord(element, "CenterYG")
                radius = _read_coord(element, "Radius")
                cw = bool(_read_prop(element, "CW"))
            else:
                length = self._line_length(element, start_x, start_y, end_x, end_y)
                center_x = 0.0
                center_y = 0.0
                radius = 0.0
                cw = False
            values = (
                start_x,
                start_y,
                start_z,
                end_x,
                end_y,
                end_z,
                length,
                center_x,
                center_y,
                radius,
            )
            if not all(math.isfinite(value) for value in values):
                raise UnreadableGeometryError("non-finite geometry value")  # noqa: TRY003
            segments.append(
                Segment(
                    is_arc=is_arc,
                    start_x=start_x,
                    start_y=start_y,
                    start_z=start_z,
                    end_x=end_x,
                    end_y=end_y,
                    end_z=end_z,
                    length=length,
                    center_x=center_x,
                    center_y=center_y,
                    radius=radius,
                    cw=cw,
                )
            )
            try:
                element = element.GetNext()
            except Exception as exc:
                raise UnreadableGeometryError from exc
        if len(segments) != count:
            detail = f"Read {len(segments)} of {count} path elements"
            raise UnreadableGeometryError(detail)
        return segments

    @staticmethod
    def _line_length(
        element: Any, start_x: float, start_y: float, end_x: float, end_y: float
    ) -> float:
        length_value = _prop(element, "Length", None)
        if length_value is not None:
            try:
                return float(length_value)
            except (TypeError, ValueError):
                pass
        return math.dist((start_x, start_y), (end_x, end_y))


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
