# ruff: noqa: N802
from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from alphacam_cli.core.drawing import Drawing
from alphacam_cli.gateway.client import RemoteSession
from alphacam_cli.gateway.remote import RemoteApplication, _DrawingProxy
from alphacam_cli.gateway.server import GatewayServer, RequestError
from alphacam_cli.main import app

runner = CliRunner()

_FIX_PAYLOAD: dict[str, Any] = {
    "success": True,
    "units": "mm",
    "fixed": {
        "duplicates": 0,
        "tiny": 1,
        "spike": 0,
        "gap": 0,
        "nearlyClosed": 0,
        "nonZeroZ": 0,
    },
    "skipped": [{"index": 3, "types": ["bigArc"], "reason": "bigArc"}],
    "failed": [],
    "backup": "C:\\Temp\\alphacam_lint_backup_20260101-000000.dxf",
    "remaining": {},
    "warnings": [],
}


class FakeLayer:
    def __init__(self, name: str) -> None:
        self.Name = name


class FakeElement:
    def __init__(
        self,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        *,
        start_z: float = 0.0,
        end_z: float = 0.0,
        is_arc: bool = False,
        center_x: float = 0.0,
        center_y: float = 0.0,
        radius: float = 0.0,
        length: float | None = None,
        cw: bool = False,
    ) -> None:
        self.StartXG = start_x
        self.StartYG = start_y
        self.StartZG = start_z
        self.EndXG = end_x
        self.EndYG = end_y
        self.EndZG = end_z
        self.IsArc = is_arc
        self.CenterXG = center_x
        self.CenterYG = center_y
        self.Radius = radius
        self.CW = cw
        self.Length = math.dist((start_x, start_y), (end_x, end_y)) if length is None else length
        self.GetNext: Callable[[], FakeElement | None] = lambda: None


def line(
    sx: float,
    sy: float,
    ex: float,
    ey: float,
    *,
    start_z: float = 0.0,
    end_z: float = 0.0,
) -> FakeElement:
    return FakeElement(sx, sy, ex, ey, start_z=start_z, end_z=end_z)


def arc(
    sx: float,
    sy: float,
    ex: float,
    ey: float,
    *,
    cx: float,
    cy: float,
    radius: float,
    length: float = 1000.0,
) -> FakeElement:
    return FakeElement(
        sx, sy, ex, ey, is_arc=True, center_x=cx, center_y=cy, radius=radius, length=length
    )


class FakePath:
    def __init__(
        self, elements: list[FakeElement], *, closed: bool = False, layer: str = "default"
    ) -> None:
        self.elements = elements
        self.Selected = False
        self.Closed = closed
        self.LayerName = layer
        self.tag: Any = None
        for current, following in zip(elements, elements[1:], strict=False):
            current.GetNext = lambda following=following: following
        if elements:
            elements[-1].GetNext = lambda: None

    def GetElemCount(self) -> int:
        return len(self.elements)

    def GetFirstElem(self) -> FakeElement | None:
        return self.elements[0] if self.elements else None

    def GetLayer(self) -> FakeLayer:
        return FakeLayer(self.LayerName)


class FakeCollection:
    def __init__(self, paths: list[FakePath]) -> None:
        self.items = paths

    @property
    def Count(self) -> int:
        return len(self.items)

    def Item(self, index: int) -> FakePath:
        return self.items[index - 1]


class FakeToolPaths:
    def __init__(self, count: int = 0) -> None:
        self.Count = count


class FakeGeo:
    def __init__(self, raw: FakeRaw, start: tuple[float, float]) -> None:
        self.raw = raw
        self.points = [start]

    def AddLine(self, x: float, y: float) -> None:
        self.points.append((x, y))

    def _create(self, closed: bool) -> FakePath:
        elements = [
            line(start[0], start[1], end[0], end[1])
            for start, end in zip(self.points, self.points[1:], strict=False)
        ]
        path = FakePath(elements, closed=closed)
        self.raw.geometries.items.append(path)
        return path

    def Finish(self) -> FakePath:
        return self._create(False)

    def CloseAndFinishLine(self) -> FakePath:
        return self._create(True)


class FakeRaw:
    def __init__(self, paths: list[FakePath], tool_paths: int = 0) -> None:
        self.Geometries = FakeCollection(paths)
        self.ToolPaths = FakeToolPaths(tool_paths)
        self.exported: list[str] = []
        self.deleted_order: list[Any] = []
        self.create_calls = 0
        self.delete_calls = 0
        self.select_calls = 0

    @property
    def geometries(self) -> FakeCollection:
        return self.Geometries

    def Create2DGeometry(self, x: float, y: float) -> FakeGeo:
        self.create_calls += 1
        return FakeGeo(self, (x, y))

    def SetGeosSelected(self, flag: bool) -> None:
        self.select_calls += 1
        for path in self.geometries.items:
            path.Selected = flag

    def DeleteSelected(self) -> None:
        self.delete_calls += 1
        removed = [path for path in self.geometries.items if path.Selected]
        self.deleted_order.extend(path.tag for path in removed)
        self.geometries.items[:] = [path for path in self.geometries.items if not path.Selected]

    def SaveDxfFile(self, path: str, *args: Any) -> None:
        self.exported.append(path)


def drawing_with(paths: list[FakePath], tool_paths: int = 0) -> tuple[Drawing, FakeRaw]:
    raw = FakeRaw(paths, tool_paths)
    return Drawing(raw), raw  # type: ignore[arg-type]


def test_lint_fix_removes_duplicate_via_delete_selected() -> None:
    original = FakePath([line(0, 0, 10, 0)])
    duplicate = FakePath([line(0, 0, 10, 0)])
    drawing, raw = drawing_with([original, duplicate])

    result = drawing.lint_fix(select_all=True, units="mm")

    assert result["success"] is True
    assert result["fixed"]["duplicates"] == 1
    assert raw.geometries.Count == 1
    assert raw.deleted_order == [duplicate.tag]
    assert result["backup"] == raw.exported[0]
    assert len(raw.exported) == 1


@pytest.mark.parametrize(
    ("name", "elements", "expect_end"),
    [
        ("tiny", [line(0, 0, 0.01, 0), line(0.01, 0, 10, 0)], (10.0, 0.0)),
        ("gap", [line(0, 0, 10, 0), line(10.1, 0, 20, 0)], (20.0, 0.0)),
        (
            "nearlyClosed",
            [line(0, 0, 10, 0), line(10, 0, 10, 10), line(10, 10, 0, 0.1)],
            (0.0, 0.0),
        ),
        ("nonZeroZ", [line(0, 0, 10, 0, start_z=5.0, end_z=5.0)], (10.0, 0.0)),
    ],
)
def test_lint_fix_rebuilds_linear_path(
    name: str, elements: list[FakeElement], expect_end: tuple[float, float]
) -> None:
    old = FakePath(elements)
    drawing, raw = drawing_with([old])

    result = drawing.lint_fix(select_all=True, units="mm")

    assert result["fixed"][name] == 1
    assert result["failed"] == []
    assert raw.geometries.Count == 1
    rebuilt = raw.geometries.items[0]
    assert rebuilt is not old
    assert math.dist(
        (rebuilt.elements[-1].EndXG, rebuilt.elements[-1].EndYG), expect_end
    ) == pytest.approx(0.0, abs=1e-6)
    assert all(element.IsArc is False for element in rebuilt.elements)
    assert all(element.StartZG == 0.0 and element.EndZG == 0.0 for element in rebuilt.elements)


def test_lint_fix_removes_spike_segment() -> None:
    old = FakePath([line(0, 0, 10, 0), line(10, 0, 9.9, 0)])
    drawing, raw = drawing_with([old])

    result = drawing.lint_fix(select_all=True, units="mm")

    assert result["fixed"]["spike"] == 1
    assert raw.geometries.Count == 1
    rebuilt = raw.geometries.items[0]
    assert len(rebuilt.elements) == 1
    assert rebuilt.elements[0].StartXG == pytest.approx(0.0)
    assert rebuilt.elements[0].EndXG == pytest.approx(10.0)


def test_lint_fix_deletes_path_left_empty_after_tiny_removal() -> None:
    old = FakePath([line(0, 0, 0.01, 0)])
    drawing, raw = drawing_with([old])

    result = drawing.lint_fix(select_all=True, units="mm")

    assert result["fixed"]["tiny"] == 1
    assert result["deleted_paths"] == [0]
    assert result["failed"] == []
    assert raw.geometries.Count == 0
    assert result["backup"] == raw.exported[0]


def test_lint_fix_deletes_path_left_empty_after_spike_removal() -> None:
    old = FakePath([line(0, 0, 0.01, 0)])
    drawing, raw = drawing_with([old])
    drawing.lint = MagicMock(  # type: ignore[method-assign]
        return_value={
            "paths": [{"index": 0, "closed": False, "issues": [{"type": "spike"}]}],
            "issues_by_type": {"spike": 1},
        }
    )

    result = drawing.lint_fix(select_all=True, units="mm")

    assert result["fixed"]["spike"] == 1
    assert result["deleted_paths"] == [0]
    assert result["failed"] == []
    assert raw.geometries.Count == 0


def test_lint_fix_keeps_path_when_delete_does_not_reduce_geometry() -> None:
    old = FakePath([line(0, 0, 0.01, 0)])
    drawing, raw = drawing_with([old])
    raw.DeleteSelected = MagicMock()  # type: ignore[method-assign, assignment]

    result = drawing.lint_fix(select_all=True, units="mm")

    assert result["fixed"]["tiny"] == 0
    assert result["deleted_paths"] == []
    assert result["failed"] == [
        {
            "index": 0,
            "types": ["tiny"],
            "reason": "delete failed: geometry count did not decrease",
        }
    ]
    assert raw.geometries.items == [old]


def test_lint_fix_skips_path_with_arcs() -> None:
    arc_path = FakePath([arc(0, 0, 1, 1, cx=0, cy=1, radius=1.0, length=0.01)])
    drawing, raw = drawing_with([arc_path])

    result = drawing.lint_fix(select_all=True, units="mm")

    assert result["skipped"] == [{"index": 0, "types": ["tiny"], "reason": "contains arcs"}]
    assert result["fixed"]["tiny"] == 0
    assert raw.geometries.items == [arc_path]
    assert raw.delete_calls == 0


def test_lint_fix_skips_big_arc() -> None:
    arc_path = FakePath([arc(0, 0, 0, 0, cx=0, cy=0, radius=5000.0)])
    drawing, raw = drawing_with([arc_path])

    result = drawing.lint_fix(select_all=True, units="mm")

    assert result["skipped"][0]["reason"] == "bigArc"
    assert raw.geometries.items == [arc_path]


def test_lint_fix_skips_self_intersect() -> None:
    old = FakePath([line(0, 0, 10, 10), line(5, 0, 5, 10)])
    drawing, raw = drawing_with([old])

    result = drawing.lint_fix(select_all=True, units="mm")

    assert result["skipped"][0]["reason"] == "selfIntersect"
    assert raw.geometries.items == [old]


def test_lint_fix_verification_failure_keeps_old_and_deletes_new() -> None:
    old = FakePath([line(0, 0, 0.01, 0), line(0.01, 0, 10, 0)])
    drawing, raw = drawing_with([old])
    drawing._verify_rebuild = MagicMock(return_value="bbox mismatch")  # type: ignore[method-assign]

    result = drawing.lint_fix(select_all=True, units="mm")

    assert result["failed"] == [{"index": 0, "types": ["tiny"], "reason": "bbox mismatch"}]
    assert result["fixed"]["tiny"] == 0
    assert raw.geometries.items == [old]
    assert raw.deleted_order == [None]


def test_lint_fix_dry_run_does_not_mutate() -> None:
    old = FakePath([line(0, 0, 0.01, 0), line(0.01, 0, 10, 0)])
    drawing, raw = drawing_with([old])

    result = drawing.lint_fix(select_all=True, units="mm", dry_run=True)

    assert result["would_fix"]["tiny"] == 1
    assert result["backup"] is None
    assert raw.create_calls == 0
    assert raw.delete_calls == 0
    assert raw.select_calls == 0
    assert raw.exported == []
    assert raw.geometries.items == [old]


def test_lint_fix_no_backup_skips_export() -> None:
    old = FakePath([line(0, 0, 0.01, 0), line(0.01, 0, 10, 0)])
    drawing, raw = drawing_with([old])

    result = drawing.lint_fix(select_all=True, units="mm", backup=False)

    assert result["backup"] is None
    assert raw.exported == []


def test_lint_fix_backup_failure_aborts_without_changes() -> None:
    old = FakePath([line(0, 0, 0.01, 0), line(0.01, 0, 10, 0)])
    drawing, raw = drawing_with([old])
    drawing.export = MagicMock(side_effect=RuntimeError("disk full"))  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="backup failed"):
        drawing.lint_fix(select_all=True, units="mm")

    assert raw.geometries.items == [old]
    assert raw.create_calls == 0
    assert raw.delete_calls == 0


def test_lint_fix_processes_paths_in_descending_index_order() -> None:
    paths = [
        FakePath(
            [
                line(0, 10.0 * index, 0.01, 10.0 * index),
                line(0.01, 10.0 * index, 10, 10.0 * index),
            ]
        )
        for index in range(3)
    ]
    for index, path in enumerate(paths):
        path.tag = index
    drawing, raw = drawing_with(paths)

    drawing.lint_fix(select_all=True, units="mm")

    assert raw.deleted_order == [2, 1, 0]


def test_lint_fix_warns_when_toolpaths_present() -> None:
    old = FakePath([line(0, 0, 0.01, 0), line(0.01, 0, 10, 0)])
    drawing, _ = drawing_with([old], tool_paths=2)

    result = drawing.lint_fix(select_all=True, units="mm")

    assert any("toolpath" in warning for warning in result["warnings"])


def test_lint_fix_reports_remaining_issues() -> None:
    old = FakePath([arc(0, 0, 1, 1, cx=0, cy=1, radius=1.0, length=0.01)])
    drawing, _ = drawing_with([old])

    result = drawing.lint_fix(select_all=True, units="mm")

    assert result["remaining"].get("tiny") == 1


def test_lint_fix_requires_selection() -> None:
    path = FakePath([line(0, 0, 10, 0)])
    drawing, _ = drawing_with([path])

    with pytest.raises(RuntimeError, match="No selected geometries"):
        drawing.lint_fix(units="mm")


@contextmanager
def _context(*args: Any, **kwargs: Any) -> Iterator[object]:
    yield object()


def _invoke(ac: Any, args: list[str]) -> Any:
    with (
        patch("alphacam_cli.cli.drawing.require_platform"),
        patch("alphacam_cli.cli.drawing.alphacam_context", _context),
        patch("alphacam_cli.cli.drawing.resolve_app", return_value=ac),
    ):
        return runner.invoke(app, ["drawing", "lint", *args])


def _make_app(drawing: Any) -> MagicMock:
    ac = MagicMock()
    ac.get_active_drawing.return_value = drawing
    return ac


def test_cli_lint_fix_json() -> None:
    drawing = MagicMock()
    drawing.lint_fix.return_value = _FIX_PAYLOAD

    result = _invoke(_make_app(drawing), ["--all", "--units", "mm", "--fix", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == _FIX_PAYLOAD
    drawing.lint_fix.assert_called_once_with(
        select_all=True, units="mm", dry_run=False, backup=True
    )
    drawing.lint.assert_not_called()


def test_cli_lint_fix_dry_run_no_backup_json() -> None:
    drawing = MagicMock()
    drawing.lint_fix.return_value = {**_FIX_PAYLOAD, "fixed": {}, "would_fix": {"tiny": 1}}

    result = _invoke(
        _make_app(drawing),
        ["--units", "mm", "--fix", "--dry-run", "--no-backup", "--json"],
    )

    assert result.exit_code == 0
    drawing.lint_fix.assert_called_once_with(
        select_all=False, units="mm", dry_run=True, backup=False
    )


def test_cli_lint_fix_table() -> None:
    drawing = MagicMock()
    drawing.lint_fix.return_value = _FIX_PAYLOAD

    result = _invoke(_make_app(drawing), ["--units", "mm", "--fix"])

    assert result.exit_code == 0
    assert "Fixed" in result.stderr
    assert "Skipped" in result.stderr
    assert "Remaining issues" in result.stderr
    assert "Backup:" in result.stderr


def test_cli_lint_without_fix_unchanged() -> None:
    drawing = MagicMock()
    drawing.lint.return_value = {"success": True, "units": "mm", "scanned": 0, "flagged": 0}

    result = _invoke(_make_app(drawing), ["--units", "mm", "--json"])

    assert result.exit_code == 0
    drawing.lint.assert_called_once_with(select_all=False, units="mm")
    drawing.lint_fix.assert_not_called()


def test_remote_session_drawing_lint_fix_sends_params() -> None:
    session = RemoteSession()
    session._call = MagicMock(return_value=_FIX_PAYLOAD)  # type: ignore[method-assign]

    result = session.drawing_lint_fix("mm", True, dry_run=True, backup=False)

    assert result == _FIX_PAYLOAD
    session._call.assert_called_once_with(
        "drawing_lint_fix",
        {"all": True, "units": "mm", "dry_run": True, "backup": False},
        timeout=150.0,
    )


def test_remote_proxy_lint_fix_returns_payload() -> None:
    session = MagicMock()
    session.drawing_lint_fix.return_value = _FIX_PAYLOAD
    proxy = _DrawingProxy(session, {})

    assert proxy.lint_fix(True, units="mm", dry_run=True, backup=False) == _FIX_PAYLOAD
    session.drawing_lint_fix.assert_called_once_with("mm", True, True, False)


def test_cli_lint_fix_remote_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock()
    session.drawing_lint_fix.return_value = _FIX_PAYLOAD
    session.get_active_drawing.return_value = {"geometries_count": 1}

    result = _invoke(RemoteApplication(session), ["--units", "mm", "--fix", "--json"])

    assert result.exit_code == 0
    session.drawing_lint_fix.assert_called_once_with("mm", False, False, True)


@pytest.fixture
def server_app(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    import alphacam_cli.gateway.server as server_module

    fake = MagicMock()
    monkeypatch.setattr(server_module, "_app", fake)
    return fake


def test_handler_drawing_lint_fix_returns_payload(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.lint_fix.return_value = _FIX_PAYLOAD
    server_app.get_active_drawing.return_value = drw
    gw = GatewayServer()
    watchdog = MagicMock()
    gw._watchdog_arm = MagicMock(return_value=watchdog)

    result = gw._handler_drawing_lint_fix(
        {"all": True, "units": "mm", "dry_run": True, "backup": False}
    )

    assert result == _FIX_PAYLOAD
    drw.lint_fix.assert_called_once_with(select_all=True, units="mm", dry_run=True, backup=False)
    gw._watchdog_arm.assert_called_once_with(180.0, "drawing_lint_fix")
    watchdog.cancel.assert_called_once()


def test_handler_drawing_lint_fix_requires_units(server_app: MagicMock) -> None:
    with pytest.raises(RequestError, match=r"units is required \(mm\|inch\)"):
        GatewayServer()._handler_drawing_lint_fix({})

    server_app.get_active_drawing.assert_not_called()


def test_handler_drawing_lint_fix_wraps_error(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.lint_fix.side_effect = RuntimeError("No selected geometries")
    server_app.get_active_drawing.return_value = drw

    with pytest.raises(RequestError, match="No selected geometries"):
        GatewayServer()._handler_drawing_lint_fix({"units": "mm"})
