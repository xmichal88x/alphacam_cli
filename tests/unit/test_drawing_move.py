from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from alphacam_cli.core.drawing import CamPath, Drawing, MoveResult
from alphacam_cli.gateway.client import RemoteSession
from alphacam_cli.gateway.remote import _DrawingProxy
from alphacam_cli.gateway.server import COMError, GatewayServer
from alphacam_cli.main import app

runner = CliRunner()


def _drawing_with_paths(selected: list[bool]) -> tuple[Drawing, list[MagicMock]]:
    raw = MagicMock()
    paths: list[MagicMock] = []
    for flag in selected:
        path = MagicMock()
        path.Selected = flag
        paths.append(path)
    collection = MagicMock()
    collection.Count = len(paths)
    collection.Item.side_effect = lambda index: paths[index - 1]
    raw.Geometries = collection
    raw.ToolPaths.Count = 0
    raw.SetGeosSelected.side_effect = lambda value: [
        setattr(path, "Selected", value) for path in paths
    ]
    return Drawing(raw), paths


class _FakePath:
    def __init__(self, selected: bool) -> None:
        self._selected = selected
        self.moves: list[tuple[float, float, float]] = []
        self.move_error: str | None = None
        self.move_error_once: str | None = None
        self.fail_restore_on_error = False
        self.restore_error = False

    @property
    def Selected(self) -> bool:  # noqa: N802
        return self._selected

    @Selected.setter
    def Selected(self, value: bool) -> None:  # noqa: N802
        if self.restore_error and not value:
            raise RuntimeError("restore boom")  # noqa: TRY003
        self._selected = value

    def MoveG(self, dx: float, dy: float, dz: float) -> None:  # noqa: N802
        if self.move_error is not None:
            if self.fail_restore_on_error:
                self.restore_error = True
            raise RuntimeError(self.move_error)
        if self.move_error_once is not None:
            self.move_error_once = None
            raise RuntimeError("boom")  # noqa: TRY003
        self.moves.append((dx, dy, dz))


def _drawing_with_fake_paths(selected: list[bool]) -> tuple[Drawing, list[_FakePath]]:
    raw = MagicMock()
    paths = [_FakePath(flag) for flag in selected]
    collection = MagicMock()
    collection.Count = len(paths)
    collection.Item.side_effect = lambda index: paths[index - 1]
    raw.Geometries = collection
    raw.ToolPaths.Count = 0
    raw.SetGeosSelected.side_effect = lambda value: [
        setattr(path, "Selected", value) for path in paths
    ]
    return Drawing(raw), paths


class _StartElement:
    def __init__(self, path: _CoordFakePath) -> None:
        self._path = path

    @property
    def StartXG(self) -> float:  # noqa: N802
        return self._path.pos[0]

    @property
    def StartYG(self) -> float:  # noqa: N802
        return self._path.pos[1]

    @property
    def StartZG(self) -> float:  # noqa: N802
        return self._path.pos[2]


class _CoordFakePath:
    def __init__(self, selected: bool) -> None:
        self._selected = selected
        self.pos = (0.0, 0.0, 0.0)
        self.moves: list[tuple[float, float, float]] = []
        self.raise_before = False
        self.raise_after = False
        self.read_error = False
        self.calls = 0
        self.fail_calls: set[int] = set()

    @property
    def Selected(self) -> bool:  # noqa: N802
        return self._selected

    @Selected.setter
    def Selected(self, value: bool) -> None:  # noqa: N802
        self._selected = value

    def GetFirstElem(self) -> _StartElement:  # noqa: N802
        if self.read_error:
            raise RuntimeError("read boom")  # noqa: TRY003
        return _StartElement(self)

    def MoveG(self, dx: float, dy: float, dz: float) -> None:  # noqa: N802
        self.calls += 1
        if self.calls in self.fail_calls:
            raise RuntimeError("rollback boom")  # noqa: TRY003
        if self.raise_before:
            raise RuntimeError("boom")  # noqa: TRY003
        self.pos = (self.pos[0] + dx, self.pos[1] + dy, self.pos[2] + dz)
        self.moves.append((dx, dy, dz))
        if self.raise_after:
            self.raise_after = False
            raise RuntimeError("boom")  # noqa: TRY003


def _drawing_with_coord_paths(selected: list[bool]) -> tuple[Drawing, list[_CoordFakePath]]:
    raw = MagicMock()
    paths = [_CoordFakePath(flag) for flag in selected]
    collection = MagicMock()
    collection.Count = len(paths)
    collection.Item.side_effect = lambda index: paths[index - 1]
    raw.Geometries = collection
    raw.ToolPaths.Count = 0
    raw.SetGeosSelected.side_effect = lambda value: [
        setattr(path, "Selected", value) for path in paths
    ]
    return Drawing(raw), paths


def _make_app(drawing: Any = None) -> MagicMock:
    ac = MagicMock()
    if drawing is not None:
        with suppress(Exception):
            drawing.tool_paths_count = 0
    ac.get_active_drawing.return_value = drawing
    return ac


@contextmanager
def _context(*args: Any, **kwargs: Any) -> Iterator[object]:
    yield object()


def _invoke(ac: MagicMock, args: list[str]) -> Any:
    with (
        patch("alphacam_cli.cli.drawing.require_platform"),
        patch("alphacam_cli.cli.drawing.alphacam_context", _context),
        patch("alphacam_cli.cli.drawing.resolve_app", return_value=ac),
    ):
        return runner.invoke(app, ["drawing", "move", *args])


def test_drawing_move_moves_only_selected() -> None:
    drawing, paths = _drawing_with_paths([True, False, True])

    result = drawing.move(10, 5, 2)

    assert result.moved == 2
    assert isinstance(result, MoveResult)
    paths[0].MoveG.assert_called_once_with(10, 5, 2)
    paths[1].MoveG.assert_not_called()
    paths[2].MoveG.assert_called_once_with(10, 5, 2)


def test_drawing_move_warns_on_nonzero_dz() -> None:
    drawing, _ = _drawing_with_paths([True])

    result = drawing.move(1, 2, 3)

    assert any("dz != 0" in warning for warning in result.warnings)


def test_drawing_move_warns_when_toolpaths_exist() -> None:
    drawing, _ = _drawing_with_paths([True])
    drawing.raw_dispatch.ToolPaths.Count = 4

    result = drawing.move(1, 2)

    assert any("contains toolpaths" in warning for warning in result.warnings)


def test_drawing_move_warns_when_toolpath_count_unreadable() -> None:
    drawing, _ = _drawing_with_paths([True])
    drawing.raw_dispatch.ToolPaths.Count = "not-an-int"

    result = drawing.move(1, 2)

    assert any("cannot determine" in warning for warning in result.warnings)


def test_move_warnings_reports_toolpaths() -> None:
    drawing, _ = _drawing_with_paths([True])
    drawing.raw_dispatch.ToolPaths.Count = 2

    warnings = drawing._move_warnings(0.0)

    assert warnings == (
        "drawing contains toolpaths; moving geometry does not move existing toolpaths",
    )


def test_move_warnings_reports_unreadable_toolpaths() -> None:
    drawing, _ = _drawing_with_paths([True])
    drawing.raw_dispatch.ToolPaths.Count = "not-an-int"

    warnings = drawing._move_warnings(0.0)

    assert len(warnings) == 1
    assert "cannot determine" in warnings[0]


def test_move_warnings_reports_nonzero_dz() -> None:
    drawing, _ = _drawing_with_paths([True])

    assert drawing._move_warnings(1.5) == ("dz != 0: geometry moved off Z=0 plane",)


def test_cam_path_layer_preserves_empty_name() -> None:
    raw = MagicMock()
    raw.GetLayer.return_value.Name = ""

    assert CamPath(raw).layer == ""


def test_cam_path_layer_none_name_returns_none() -> None:
    raw = MagicMock()
    raw.GetLayer.return_value.Name = None

    assert CamPath(raw).layer is None


def test_drawing_move_without_selection_raises() -> None:
    drawing, _ = _drawing_with_paths([False, False])

    with pytest.raises(RuntimeError, match="No selected geometries"):
        drawing.move(1, 1)


def test_drawing_move_select_all_selects_and_moves_everything() -> None:
    drawing, paths = _drawing_with_paths([True, True])

    moved = drawing.move(1, 2, 3, select_all=True).moved

    assert moved == 2
    drawing.raw_dispatch.SetGeosSelected.assert_called_once_with(True)
    for path in paths:
        path.MoveG.assert_called_once_with(1, 2, 3)


def test_drawing_move_select_all_restores_selection() -> None:
    drawing, paths = _drawing_with_paths([False, True])

    moved = drawing.move(1, 0, select_all=True).moved

    assert moved == 2
    assert [path.Selected for path in paths] == [False, True]


def test_drawing_move_select_all_restores_selection_on_error() -> None:
    drawing, paths = _drawing_with_fake_paths([True, False])
    paths[1].move_error_once = "boom"

    with pytest.raises(RuntimeError, match="rolled back 2 path"):
        drawing.move(1, 0, select_all=True)

    assert [path.Selected for path in paths] == [True, False]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_drawing_move_rejects_non_finite(value: float) -> None:
    drawing, paths = _drawing_with_paths([True])

    with pytest.raises(ValueError, match="finite"):
        drawing.move(value, 0)

    paths[0].MoveG.assert_not_called()
    drawing.raw_dispatch.SetGeosSelected.assert_not_called()
    drawing.raw_dispatch.Geometries.Item.assert_not_called()


def test_drawing_move_rolls_back_on_midway_error() -> None:
    drawing, paths = _drawing_with_fake_paths([True, True, True])
    paths[1].move_error_once = "boom"

    with pytest.raises(RuntimeError, match="rolled back 2 path"):
        drawing.move(10, 5, 2)

    assert paths[0].moves == [(10, 5, 2), (-10, -5, -2)]
    assert paths[1].moves == [(-10, -5, -2)]
    assert paths[2].moves == []


def test_drawing_move_rolls_back_failed_path_first() -> None:
    drawing, paths = _drawing_with_fake_paths([True, True, True])
    paths[1].move_error_once = "boom"

    with pytest.raises(RuntimeError):
        drawing.move(1, 2, 3)

    assert paths[1].moves == [(-1, -2, -3)]
    assert paths[0].moves == [(1, 2, 3), (-1, -2, -3)]


def test_drawing_move_skips_rollback_when_position_unchanged() -> None:
    drawing, paths = _drawing_with_coord_paths([True])
    paths[0].raise_before = True

    with pytest.raises(RuntimeError, match="rolled back 0 path"):
        drawing.move(1, 2, 3)

    assert paths[0].moves == []
    assert paths[0].pos == (0.0, 0.0, 0.0)


def test_drawing_move_rolls_back_when_position_changed() -> None:
    drawing, paths = _drawing_with_coord_paths([True])
    paths[0].raise_after = True

    with pytest.raises(RuntimeError, match="rolled back 1 path"):
        drawing.move(1, 2, 3)

    assert paths[0].moves == [(1, 2, 3), (-1, -2, -3)]
    assert paths[0].pos == (0.0, 0.0, 0.0)


def test_drawing_move_marks_rollback_uncertain_when_start_unreadable() -> None:
    drawing, paths = _drawing_with_coord_paths([True, True])
    paths[0].read_error = True
    paths[1].raise_before = True

    with pytest.raises(RuntimeError, match="rollback uncertain for path 0"):
        drawing.move(1, 0)

    assert paths[0].moves == [(1, 0, 0), (-1, 0, 0)]
    assert paths[1].moves == []


def test_drawing_move_reports_rollback_failure() -> None:
    drawing, paths = _drawing_with_coord_paths([True, True])
    paths[0].fail_calls = {2}
    paths[1].raise_after = True
    paths[1].fail_calls = {2}

    with pytest.raises(RuntimeError, match=r"rollback_failed=2 \(path\(s\) 0, 1\)"):
        drawing.move(1, 1)


def test_drawing_move_rollback_failure_uses_drawing_indices() -> None:
    drawing, paths = _drawing_with_fake_paths([False, True, True, False])
    paths[2].move_error = "boom"

    with pytest.raises(RuntimeError, match=r"rollback_failed=1 \(path\(s\) 2\)"):
        drawing.move(1, 1)

    assert paths[1].moves == [(1, 1, 0), (-1, -1, 0)]


def test_drawing_move_restore_failure_does_not_mask_move_error() -> None:
    drawing, paths = _drawing_with_fake_paths([True, False, True])
    paths[1].move_error = "boom"
    paths[1].fail_restore_on_error = True

    with pytest.raises(RuntimeError) as excinfo:
        drawing.move(1, 2, 3, select_all=True)

    message = str(excinfo.value)
    assert "boom" in message
    assert "rollback_failed=1 (path(s) 1)" in message
    assert "selection restore failed for path(s) 1" in message
    assert isinstance(excinfo.value.__cause__, RuntimeError)
    assert str(excinfo.value.__cause__) == "boom"


def test_drawing_move_restore_failure_after_success_is_warning() -> None:
    drawing, paths = _drawing_with_fake_paths([True, False])
    paths[1].restore_error = True

    result = drawing.move(1, 0, select_all=True)

    assert result.moved == 2
    assert any("selection restore failed for path(s) 1" in warning for warning in result.warnings)


def test_cli_drawing_move_json() -> None:
    drawing = MagicMock()
    drawing.move.return_value = MoveResult(moved=2, warnings=())
    result = _invoke(_make_app(drawing), ["--dx", "10", "--dy", "5", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "success": True,
        "moved": 2,
        "dx": 10.0,
        "dy": 5.0,
        "dz": 0.0,
        "warnings": [],
    }
    drawing.move.assert_called_once_with(10.0, 5.0, 0.0, select_all=False)


def test_cli_drawing_move_json_long_payload_is_single_valid_line() -> None:
    warnings = tuple(
        f"selection restore failed for path(s) {index} " + " ".join(["detail"] * 20)
        for index in range(8)
    )
    drawing = MagicMock()
    drawing.move.return_value = MoveResult(moved=8, warnings=warnings)

    result = _invoke(_make_app(drawing), ["--dx", "1", "--dy", "2", "--json"])

    assert result.exit_code == 0
    expected = {
        "success": True,
        "moved": 8,
        "dx": 1.0,
        "dy": 2.0,
        "dz": 0.0,
        "warnings": list(warnings),
    }
    assert len(json.dumps(expected, sort_keys=True)) > 1000
    assert "\n" not in result.stdout.rstrip("\n")
    assert json.loads(result.stdout) == expected


def test_cli_drawing_move_json_includes_warnings() -> None:
    drawing = MagicMock()
    drawing.move.return_value = MoveResult(moved=1, warnings=("warn-a", "warn-b"))
    result = _invoke(_make_app(drawing), ["--dx", "1", "--dy", "2", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["warnings"] == ["warn-a", "warn-b"]


def test_cli_drawing_move_table() -> None:
    drawing = MagicMock()
    drawing.move.return_value = MoveResult(moved=3, warnings=())
    result = _invoke(_make_app(drawing), ["--dx", "1", "--dy", "2", "--dz", "3"])

    assert result.exit_code == 0
    assert "Geometry Moved" in result.stderr
    assert "Moved" in result.stderr
    assert "3" in result.stderr


def test_cli_drawing_move_rejects_non_finite_without_com() -> None:
    ac = _make_app(MagicMock())
    context = MagicMock()
    with (
        patch("alphacam_cli.cli.drawing.require_platform"),
        patch("alphacam_cli.cli.drawing.alphacam_context", context),
        patch("alphacam_cli.cli.drawing.resolve_app", return_value=ac),
    ):
        result = runner.invoke(app, ["drawing", "move", "--dx", "nan", "--dy", "1"])

    assert result.exit_code == 1
    assert "finite" in result.stderr
    context.assert_not_called()
    ac.get_active_drawing.assert_not_called()


def test_cli_drawing_move_prints_warnings_from_result() -> None:
    drawing = MagicMock()
    drawing.move.return_value = MoveResult(
        moved=1, warnings=("dz != 0: geometry moved off Z=0 plane",)
    )

    result = _invoke(_make_app(drawing), ["--dx", "1", "--dy", "2", "--dz", "3"])

    assert result.exit_code == 0
    assert result.stderr.count("Z=0") == 1


def test_cli_drawing_move_prints_toolpath_warning_once() -> None:
    drawing = MagicMock()
    drawing.move.return_value = MoveResult(
        moved=2,
        warnings=("drawing contains toolpaths; moving geometry does not move existing toolpaths",),
    )

    result = _invoke(_make_app(drawing), ["--dx", "1", "--dy", "2", "--all"])

    assert result.exit_code == 0
    assert result.stderr.lower().count("drawing contains toolpaths") == 1
    drawing.move.assert_called_once_with(1.0, 2.0, 0.0, select_all=True)


def test_cli_drawing_move_no_warnings_when_none() -> None:
    drawing = MagicMock()
    drawing.move.return_value = MoveResult(moved=1, warnings=())

    result = _invoke(_make_app(drawing), ["--dx", "1", "--dy", "2"])

    assert result.exit_code == 0
    assert "toolpaths" not in result.stderr.lower()


def test_cli_drawing_move_no_drawing() -> None:
    result = _invoke(_make_app(None), ["--dx", "1", "--dy", "2"])

    assert result.exit_code == 1
    assert "No active drawing" in result.stderr


def test_cli_drawing_move_no_selection() -> None:
    drawing = MagicMock()
    drawing.move.side_effect = RuntimeError("No selected geometries")
    result = _invoke(_make_app(drawing), ["--dx", "1", "--dy", "2"])

    assert result.exit_code == 1
    assert "No selected geometries" in result.stderr


@pytest.fixture
def server_app(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    import alphacam_cli.gateway.server as server_module

    fake = MagicMock()
    monkeypatch.setattr(server_module, "_app", fake)
    return fake


def test_handler_drawing_move_returns_payload(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.move.return_value = MoveResult(moved=4, warnings=("dz != 0: geometry moved off Z=0 plane",))
    drw.tool_paths_count = 0
    server_app.get_active_drawing.return_value = drw

    result = GatewayServer()._handler_drawing_move({"dx": 10, "dy": 5, "dz": 2, "all": True})

    assert result == {
        "success": True,
        "moved": 4,
        "dx": 10.0,
        "dy": 5.0,
        "dz": 2.0,
        "warnings": ["dz != 0: geometry moved off Z=0 plane"],
    }
    drw.move.assert_called_once_with(10.0, 5.0, 2.0, select_all=True)


def test_handler_drawing_move_warns_about_toolpaths(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.move.return_value = MoveResult(
        moved=1,
        warnings=("drawing contains toolpaths; moving geometry does not move existing toolpaths",),
    )
    drw.tool_paths_count = 3
    server_app.get_active_drawing.return_value = drw

    result = GatewayServer()._handler_drawing_move({"dx": 1, "dy": 2})

    assert any("toolpaths" in warning for warning in result["warnings"])


def test_handler_drawing_move_warns_when_toolpaths_unreadable(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.move.return_value = MoveResult(
        moved=1,
        warnings=(
            "cannot determine whether the drawing contains toolpaths; "
            "geometry may be moved without moving existing toolpaths",
        ),
    )
    drw.tool_paths_count = "not-an-int"
    server_app.get_active_drawing.return_value = drw

    result = GatewayServer()._handler_drawing_move({"dx": 1, "dy": 2})

    assert any("cannot determine" in warning for warning in result["warnings"])


def test_handler_drawing_move_warnings_are_not_duplicated(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.move.return_value = MoveResult(moved=1, warnings=("from-move-result",))
    drw.tool_paths_count = 99
    server_app.get_active_drawing.return_value = drw

    result = GatewayServer()._handler_drawing_move({"dx": 1, "dy": 2})

    assert result["warnings"] == ["from-move-result"]


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"dx": "abc", "dy": 1}, "dx must be a number"),
        ({"dx": 1, "dy": "abc"}, "dy must be a number"),
        ({"dx": 1, "dy": 1, "dz": "abc"}, "dz must be a number"),
        ({"dx": [1], "dy": 1}, "dx must be a number"),
    ],
)
def test_handler_drawing_move_rejects_non_numeric(
    server_app: MagicMock, params: dict[str, Any], message: str
) -> None:
    with pytest.raises(COMError, match=message):
        GatewayServer()._handler_drawing_move(params)

    server_app.get_active_drawing.assert_not_called()


@pytest.mark.parametrize("key", ["dx", "dy", "dz"])
def test_handler_drawing_move_rejects_non_finite(server_app: MagicMock, key: str) -> None:
    params: dict[str, Any] = {"dx": 0, "dy": 0, "dz": 0}
    params[key] = float("nan")

    with pytest.raises(COMError, match="finite"):
        GatewayServer()._handler_drawing_move(params)

    server_app.get_active_drawing.assert_not_called()


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"dy": 1}, "dx is required"),
        ({"dx": 1}, "dy is required"),
        ({"dx": None, "dy": 1}, "dx is required"),
        ({"dx": 1, "dy": None}, "dy is required"),
    ],
)
def test_handler_drawing_move_requires_dx_dy(
    server_app: MagicMock, params: dict[str, Any], message: str
) -> None:
    with pytest.raises(COMError, match=message):
        GatewayServer()._handler_drawing_move(params)

    server_app.get_active_drawing.assert_not_called()


def test_handler_drawing_move_no_drawing(server_app: MagicMock) -> None:
    server_app.get_active_drawing.return_value = None

    with pytest.raises(COMError, match="No active drawing"):
        GatewayServer()._handler_drawing_move({"dx": 1, "dy": 2})


def test_handler_drawing_move_wraps_error(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.move.side_effect = RuntimeError("No selected geometries")
    server_app.get_active_drawing.return_value = drw

    with pytest.raises(COMError, match="No selected geometries"):
        GatewayServer()._handler_drawing_move({"dx": 1, "dy": 2})


def test_remote_session_drawing_move_sends_params() -> None:
    session = RemoteSession()
    session._call = MagicMock(return_value={"success": True, "moved": 1})  # type: ignore[method-assign]

    session.drawing_move(10, 5, 2, select_all=True)

    session._call.assert_called_once_with(
        "drawing_move", {"dx": 10, "dy": 5, "dz": 2, "all": True}, timeout=45.0
    )


def test_remote_proxy_move_returns_count() -> None:
    session = MagicMock()
    session.drawing_move.return_value = {"success": True, "moved": 7, "warnings": []}
    proxy = _DrawingProxy(session, {})

    result = proxy.move(1, 2, 3, select_all=True)

    assert result.moved == 7
    assert isinstance(result, MoveResult)
    session.drawing_move.assert_called_once_with(1, 2, 3, True)


def test_remote_proxy_move_maps_warnings() -> None:
    session = MagicMock()
    session.drawing_move.return_value = {
        "success": True,
        "moved": 1,
        "warnings": ["dz != 0: geometry moved off Z=0 plane"],
    }
    proxy = _DrawingProxy(session, {})

    result = proxy.move(1, 2, 3)

    assert result.moved == 1
    assert result.warnings == ("dz != 0: geometry moved off Z=0 plane",)
    assert not hasattr(proxy, "last_move_warnings")


@pytest.mark.parametrize("missing", ["moved", "warnings"])
def test_remote_proxy_move_requires_contract_keys(missing: str) -> None:
    session = MagicMock()
    payload: dict[str, Any] = {"success": True, "moved": 1, "warnings": []}
    del payload[missing]
    session.drawing_move.return_value = payload
    proxy = _DrawingProxy(session, {})

    with pytest.raises(RuntimeError, match="contract"):
        proxy.move(1, 2)


class _FakeProxyDrawing:
    def move(self, dx: float, dy: float, dz: float = 0.0, select_all: bool = False) -> MoveResult:
        return MoveResult(moved=1, warnings=("handler warning",))


def test_cli_drawing_move_prints_warnings_from_move_result() -> None:
    proxy = _FakeProxyDrawing()

    result = _invoke(_make_app(proxy), ["--dx", "1", "--dy", "2", "--dz", "3"])

    assert result.exit_code == 0
    assert result.stderr.count("handler warning") == 1
