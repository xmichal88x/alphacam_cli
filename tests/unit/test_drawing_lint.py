from __future__ import annotations

import json
import math
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from alphacam_cli.cli.drawing import _lint_rows
from alphacam_cli.core.drawing import CamPath, Drawing
from alphacam_cli.core.geolint import LintBudgetExceeded, Thresholds
from alphacam_cli.gateway.client import RemoteProtocolError, RemoteSession
from alphacam_cli.gateway.remote import RemoteApplication, _DrawingProxy
from alphacam_cli.gateway.server import GatewayServer, RequestError
from alphacam_cli.main import app

runner = CliRunner()

_PAYLOAD: dict[str, Any] = {
    "success": True,
    "scanned": 3,
    "flagged": 1,
    "issues_by_type": {"bigArc": 1},
    "paths": [
        {
            "index": 0,
            "closed": True,
            "issues": [{"type": "bigArc", "elem": 2, "x": 1.0, "y": 2.0, "value": 60000.0}],
        }
    ],
}


def _line_element(
    sx: float, sy: float, ex: float, ey: float, length: float | None = None
) -> MagicMock:
    element = MagicMock()
    element.IsArc = False
    element.StartXG = sx
    element.StartYG = sy
    element.StartZG = 0.0
    element.EndXG = ex
    element.EndYG = ey
    element.EndZG = 0.0
    element.Length = math.dist((sx, sy), (ex, ey)) if length is None else length
    return element


def _arc_element(
    sx: float,
    sy: float,
    ex: float,
    ey: float,
    cx: float,
    cy: float,
    radius: float,
    length: float = 1000.0,
    cw: bool = False,
) -> MagicMock:
    element = MagicMock()
    element.IsArc = True
    element.StartXG = sx
    element.StartYG = sy
    element.StartZG = 0.0
    element.EndXG = ex
    element.EndYG = ey
    element.EndZG = 0.0
    element.Length = length
    element.CenterXG = cx
    element.CenterYG = cy
    element.Radius = radius
    element.CW = cw
    return element


def _drawing_with_paths(
    specs: list[tuple[bool, list[Any]]],
) -> tuple[Drawing, list[MagicMock]]:
    raw = MagicMock()
    paths: list[MagicMock] = []
    for selected, elements in specs:
        path = MagicMock()
        path.Selected = selected
        path.Closed = False
        path.GetLayer.return_value.Name = "default"
        path.GetElemCount.return_value = len(elements)
        path.GetFirstElem.return_value = elements[0]
        for current, following in zip(elements, elements[1:], strict=False):
            current.GetNext.return_value = following
        elements[-1].GetNext.return_value = elements[0]
        paths.append(path)
    collection = MagicMock()
    collection.Count = len(paths)
    collection.Item.side_effect = lambda index: paths[index - 1]
    raw.Geometries = collection
    return Drawing(raw), paths


def _make_app(drawing: Any = None) -> MagicMock:
    ac = MagicMock()
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
        return runner.invoke(app, ["drawing", "lint", *args])


def test_segments_respects_element_count_when_getnext_wraps() -> None:
    elements = [
        _line_element(0, 0, 10, 0),
        _line_element(10, 0, 10, 5),
        _line_element(10, 5, 0, 5),
    ]
    drawing, _ = _drawing_with_paths([(True, elements)])

    segments = drawing.geometries()[0].segments()

    assert len(segments) == 3
    assert segments[0].start_x == pytest.approx(0.0)
    assert segments[2].end_x == pytest.approx(0.0)


class _LengthRaises:
    IsArc = False
    StartXG = 0.0
    StartYG = 0.0
    StartZG = 0.0
    EndXG = 3.0
    EndYG = 4.0
    EndZG = 0.0

    def __init__(self) -> None:
        self.GetNext = MagicMock(return_value=self)

    @property
    def Length(self) -> float:  # noqa: N802
        raise RuntimeError("boom")


def test_segments_length_falls_back_to_endpoint_distance() -> None:
    drawing, _ = _drawing_with_paths([(True, [_LengthRaises()])])

    segments = drawing.geometries()[0].segments()

    assert segments[0].length == pytest.approx(5.0)


def _drawing_with_path(path: MagicMock) -> Drawing:
    raw = MagicMock()
    collection = MagicMock()
    collection.Count = 1
    collection.Item.return_value = path
    raw.Geometries = collection
    return Drawing(raw)


def _path(elements: list[Any], count: int) -> MagicMock:
    path = MagicMock()
    path.Selected = True
    path.Closed = False
    path.GetLayer.return_value.Name = "default"
    path.GetElemCount.return_value = count
    path.GetFirstElem.return_value = elements[0] if elements else None
    for current, following in zip(elements, elements[1:], strict=False):
        current.GetNext.return_value = following
    if elements:
        elements[-1].GetNext.return_value = None
    return path


def test_lint_marks_truncated_element_chain_unreadable() -> None:
    elements = [_line_element(0, 0, 10, 0), _line_element(10, 0, 10, 5)]
    drawing = _drawing_with_path(_path(elements, count=5))

    result = drawing.lint(select_all=True, units="mm")

    assert result["scanned"] == 1
    assert result["flagged"] == 1
    assert result["issues_by_type"] == {"unreadable": 1}
    assert result["paths"][0]["issues"] == [
        {"type": "unreadable", "elem": -1, "x": 0.0, "y": 0.0, "value": 0.0}
    ]


def test_lint_empty_path_is_flagged_empty() -> None:
    drawing = _drawing_with_path(_path([], count=0))

    result = drawing.lint(select_all=True, units="mm")

    assert result["scanned"] == 1
    assert result["flagged"] == 1
    assert result["issues_by_type"] == {"empty": 1}
    assert result["paths"][0]["issues"] == [
        {"type": "empty", "elem": -1, "x": 0.0, "y": 0.0, "value": 0.0}
    ]
    assert result["paths"][0]["closed"] is False


def test_segments_empty_path_returns_empty_list() -> None:
    path = _path([], count=0)

    assert CamPath(path).segments() == []


def test_lint_scans_only_selected_paths() -> None:
    drawing, _ = _drawing_with_paths(
        [
            (True, [_arc_element(60000, 0, 0, 60000, 0, 0, 60000)]),
            (False, [_line_element(0, 0, 10, 0)]),
        ]
    )

    result = drawing.lint(units="mm")

    assert result["scanned"] == 1
    assert result["flagged"] == 1
    assert result["issues_by_type"] == {"bigArc": 1}


def test_lint_all_scans_every_path() -> None:
    drawing, _ = _drawing_with_paths(
        [
            (False, [_line_element(0, 0, 10, 0)]),
            (False, [_line_element(0, 5, 10, 5)]),
        ]
    )

    result = drawing.lint(select_all=True, units="mm")

    assert result["scanned"] == 2
    assert result["units"] == "mm"
    assert result["paths"] == []


class _UnreadableX:
    IsArc = False
    StartYG = 0.0
    StartZG = 0.0
    EndXG = 3.0
    EndYG = 4.0
    EndZG = 0.0
    Length = 5.0

    def __init__(self) -> None:
        self.GetNext = MagicMock(return_value=self)

    @property
    def StartXG(self) -> float:  # noqa: N802
        raise RuntimeError("boom")


def test_lint_marks_unreadable_path_and_continues() -> None:
    drawing, _ = _drawing_with_paths(
        [
            (True, [_UnreadableX()]),
            (True, [_line_element(0, 0, 10, 0)]),
        ]
    )

    result = drawing.lint(select_all=True, units="mm")

    assert result["scanned"] == 2
    assert result["flagged"] == 1
    assert result["issues_by_type"] == {"unreadable": 1}
    issue = result["paths"][0]["issues"][0]
    assert issue["type"] == "unreadable"
    assert issue["elem"] == -1
    assert result["paths"][0]["layer"] == "default"


def test_lint_raises_when_element_budget_exceeded() -> None:
    path = _path([_line_element(0, 0, 10, 0)], count=5001)
    drawing = _drawing_with_path(path)

    with pytest.raises(LintBudgetExceeded, match="5001"):
        drawing.lint(select_all=True, units="mm")

    path.GetElemCount.assert_called_once()
    path.GetFirstElem.assert_not_called()


def test_lint_element_budget_counts_all_selected_paths() -> None:
    raw = MagicMock()
    paths = [_path([_line_element(0, 0, 10, 0)], count=3000) for _ in range(2)]
    collection = MagicMock()
    collection.Count = len(paths)
    collection.Item.side_effect = lambda index: paths[index - 1]
    raw.Geometries = collection
    drawing = Drawing(raw)

    with pytest.raises(LintBudgetExceeded, match="6000"):
        drawing.lint(select_all=True, units="mm")

    for path in paths:
        path.GetFirstElem.assert_not_called()


def test_lint_raises_when_path_budget_exceeded_without_reading_elements() -> None:
    raw = MagicMock()
    paths = [_path([], count=0) for _ in range(2001)]
    collection = MagicMock()
    collection.Count = len(paths)
    collection.Item.side_effect = lambda index: paths[index - 1]
    raw.Geometries = collection
    drawing = Drawing(raw)

    with pytest.raises(LintBudgetExceeded, match="2001 paths"):
        drawing.lint(select_all=True, units="mm")

    paths[0].GetElemCount.assert_not_called()
    paths[0].GetFirstElem.assert_not_called()
    paths[0].GetLayer.assert_not_called()


def test_lint_path_budget_checks_count_before_wrapping_geometries() -> None:
    raw = MagicMock()
    collection = MagicMock()
    collection.Count = 2001
    raw.Geometries = collection
    drawing = Drawing(raw)

    with pytest.raises(LintBudgetExceeded, match="2001 paths"):
        drawing.lint(select_all=True, units="mm")

    collection.Item.assert_not_called()


def test_lint_without_selection_raises() -> None:
    drawing, _ = _drawing_with_paths([(False, [_line_element(0, 0, 10, 0)])])

    with pytest.raises(RuntimeError, match="No selected geometries"):
        drawing.lint(units="mm")


def test_lint_rejects_unknown_units_before_selection() -> None:
    drawing, paths = _drawing_with_paths([(False, [_line_element(0, 0, 10, 0)])])

    with pytest.raises(ValueError, match="units must be"):
        drawing.lint(units="cm")

    drawing.raw_dispatch.Geometries.Item.assert_not_called()
    assert paths[0].Selected is False


class _UnreadableIsArc:
    StartXG = 0.0
    StartYG = 0.0
    StartZG = 0.0
    EndXG = 3.0
    EndYG = 4.0
    EndZG = 0.0
    Length = 5.0

    def __init__(self) -> None:
        self.GetNext = MagicMock(return_value=self)

    @property
    def IsArc(self) -> bool:  # noqa: N802
        raise RuntimeError("boom")


class _UnreadableStartZ:
    IsArc = False
    StartXG = 0.0
    StartYG = 0.0
    EndXG = 3.0
    EndYG = 4.0
    EndZG = 0.0
    Length = 5.0

    def __init__(self) -> None:
        self.GetNext = MagicMock(return_value=self)

    @property
    def StartZG(self) -> float:  # noqa: N802
        raise RuntimeError("boom")


class _UnreadableEndZ:
    IsArc = False
    StartXG = 0.0
    StartYG = 0.0
    StartZG = 0.0
    EndXG = 3.0
    EndYG = 4.0
    Length = 5.0

    def __init__(self) -> None:
        self.GetNext = MagicMock(return_value=self)

    @property
    def EndZG(self) -> float:  # noqa: N802
        raise RuntimeError("boom")


class _UnreadableArcLength:
    IsArc = True
    StartXG = 10.0
    StartYG = 0.0
    StartZG = 0.0
    EndXG = 0.0
    EndYG = 10.0
    EndZG = 0.0
    CenterXG = 0.0
    CenterYG = 0.0
    Radius = 10.0
    CW = False

    def __init__(self) -> None:
        self.GetNext = MagicMock(return_value=self)

    @property
    def Length(self) -> float:  # noqa: N802
        raise RuntimeError("boom")


class _UnreadableArcRadius:
    IsArc = True
    StartXG = 10.0
    StartYG = 0.0
    StartZG = 0.0
    EndXG = 0.0
    EndYG = 10.0
    EndZG = 0.0
    Length = 15.7
    CenterXG = 0.0
    CenterYG = 0.0
    CW = False

    def __init__(self) -> None:
        self.GetNext = MagicMock(return_value=self)

    @property
    def Radius(self) -> float:  # noqa: N802
        raise RuntimeError("boom")


@pytest.mark.parametrize(
    "factory",
    [
        _UnreadableIsArc,
        _UnreadableStartZ,
        _UnreadableEndZ,
        _UnreadableArcLength,
        _UnreadableArcRadius,
    ],
)
def test_lint_marks_hard_read_failures_unreadable(factory: type) -> None:
    drawing, _ = _drawing_with_paths([(True, [factory()])])

    result = drawing.lint(units="mm")

    assert result["issues_by_type"] == {"unreadable": 1}
    assert result["paths"][0]["issues"][0]["elem"] == -1


def test_lint_marks_unreadable_closed_as_unreadable_only() -> None:
    drawing, paths = _drawing_with_paths([(True, [_line_element(0, 0, 10, 0)])])

    with patch.object(
        type(paths[0]), "Closed", new_callable=PropertyMock, create=True
    ) as closed_mock:
        closed_mock.side_effect = RuntimeError("boom")
        result = drawing.lint(select_all=True, units="mm")

    assert result["issues_by_type"] == {"unreadable": 1}
    assert result["paths"][0]["issues"] == [
        {"type": "unreadable", "elem": -1, "x": 0.0, "y": 0.0, "value": 0.0}
    ]


def test_lint_marks_get_elem_count_failure_unreadable() -> None:
    path = _path([_line_element(0, 0, 10, 0)], count=1)
    path.GetElemCount.side_effect = RuntimeError("boom")
    drawing = _drawing_with_path(path)

    result = drawing.lint(select_all=True, units="mm")

    assert result["issues_by_type"] == {"unreadable": 1}
    assert result["paths"][0]["issues"][0]["type"] == "unreadable"


def test_lint_reads_get_elem_count_once_per_path() -> None:
    drawing, paths = _drawing_with_paths([(True, [_line_element(0, 0, 10, 0)])])

    drawing.lint(select_all=True, units="mm")

    paths[0].GetElemCount.assert_called_once()


def test_segments_uses_expected_count_without_com_read() -> None:
    path = _path([_line_element(0, 0, 10, 0)], count=1)

    segments = CamPath(path).segments(expected_count=1)

    assert len(segments) == 1
    path.GetElemCount.assert_not_called()


def test_lint_marks_get_first_elem_failure_unreadable() -> None:
    path = _path([_line_element(0, 0, 10, 0)], count=1)
    path.GetFirstElem.side_effect = RuntimeError("boom")
    drawing = _drawing_with_path(path)

    result = drawing.lint(select_all=True, units="mm")

    assert result["issues_by_type"] == {"unreadable": 1}
    assert result["paths"][0]["issues"][0]["type"] == "unreadable"


def test_lint_marks_get_next_failure_unreadable() -> None:
    elements = [_line_element(0, 0, 10, 0), _line_element(10, 0, 10, 5)]
    path = _path(elements, count=2)
    elements[0].GetNext.side_effect = RuntimeError("boom")
    drawing = _drawing_with_path(path)

    result = drawing.lint(select_all=True, units="mm")

    assert result["issues_by_type"] == {"unreadable": 1}
    assert result["paths"][0]["issues"][0]["type"] == "unreadable"


def test_lint_requires_units() -> None:
    drawing, _ = _drawing_with_paths([(True, [_line_element(0, 0, 10, 0)])])
    lint_fn: Any = drawing.lint

    with pytest.raises(TypeError):
        lint_fn(select_all=True)


def test_lint_unreadable_layer_is_reported_and_excluded_from_duplicates() -> None:
    arc = _arc_element(60000, 0, 0, 60000, 0, 0, 60000)
    drawing, paths = _drawing_with_paths(
        [(True, [arc]), (True, [_arc_element(60000, 0, 0, 60000, 0, 0, 60000)])]
    )
    for path in paths:
        path.GetLayer.side_effect = RuntimeError("boom")

    result = drawing.lint(select_all=True, units="mm")

    assert "duplicates" not in result["issues_by_type"]
    assert result["issues_by_type"] == {"bigArc": 2, "layerUnreadable": 2}
    assert [path["layer"] for path in result["paths"]] == [None, None]
    assert all(path["issues"][0]["type"] == "layerUnreadable" for path in result["paths"])


def test_lint_reports_closed_null_for_unreadable_path() -> None:
    drawing, _ = _drawing_with_paths([(True, [_UnreadableX()])])

    result = drawing.lint(select_all=True, units="mm")

    assert result["paths"][0]["closed"] is None


def test_lint_path_index_reflects_drawing_order_for_selection() -> None:
    drawing, _ = _drawing_with_paths(
        [
            (False, [_line_element(0, 0, 10, 0)]),
            (True, [_arc_element(60000, 0, 0, 60000, 0, 0, 60000)]),
            (False, [_line_element(0, 5, 10, 5)]),
            (True, [_arc_element(60000, 0, 0, 60000, 0, 0, 60000)]),
        ]
    )

    result = drawing.lint(units="mm")

    assert [path["index"] for path in result["paths"]] == [1, 3]


def test_lint_duplicate_arcs_reversed_are_not_duplicates() -> None:
    drawing, _ = _drawing_with_paths(
        [
            (True, [_arc_element(1, 0, 0, 1, 0, 0, 1, cw=False)]),
            (True, [_arc_element(1, 0, 0, 1, 0, 0, 1, cw=True)]),
        ]
    )

    result = drawing.lint(select_all=True, units="mm")

    assert "duplicates" not in result["issues_by_type"]


@pytest.mark.parametrize(
    "element",
    [
        _line_element(float("nan"), 0, 10, 0),
        _line_element(0, 0, float("inf"), 0),
        _line_element(0, 0, 10, 0, length=float("nan")),
        _arc_element(10, 0, 0, 10, 0, 0, float("inf")),
    ],
)
def test_lint_marks_non_finite_values_unreadable(element: MagicMock) -> None:
    drawing, _ = _drawing_with_paths([(True, [element])])

    result = drawing.lint(select_all=True, units="mm")

    assert result["issues_by_type"] == {"unreadable": 1}
    assert result["paths"][0]["issues"][0]["elem"] == -1


def test_cli_lint_json() -> None:
    drawing = MagicMock()
    drawing.lint.return_value = _PAYLOAD

    result = _invoke(_make_app(drawing), ["--all", "--units", "inch", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == _PAYLOAD
    drawing.lint.assert_called_once_with(select_all=True, units="inch")


def test_cli_lint_json_long_payload_is_single_valid_line() -> None:
    payload: dict[str, Any] = {
        "success": True,
        "scanned": 7,
        "flagged": 7,
        "issues_by_type": {"selfIntersect": 7},
        "paths": [
            {
                "index": index,
                "closed": True,
                "layer": f"LONG LAYER NAME {index} " + " ".join(["segment"] * 12),
                "issues": [
                    {"type": "selfIntersect", "elem": index, "x": 1.0, "y": 2.0, "value": 3.0}
                ],
            }
            for index in range(7)
        ],
    }
    drawing = MagicMock()
    drawing.lint.return_value = payload

    result = _invoke(_make_app(drawing), ["--all", "--units", "mm", "--json"])

    assert result.exit_code == 0
    assert len(json.dumps(payload, sort_keys=True)) > 1000
    assert "\n" not in result.stdout.rstrip("\n")
    assert json.loads(result.stdout) == payload


def test_cli_lint_table() -> None:
    drawing = MagicMock()
    drawing.lint.return_value = _PAYLOAD

    result = _invoke(_make_app(drawing), ["--units", "mm"])

    assert result.exit_code == 0
    assert "Geometry Lint" in result.stderr
    assert "bigArc" in result.stderr
    assert "Worst cases" in result.stderr


def test_cli_lint_budget_exceeded_exits_cleanly() -> None:
    drawing = MagicMock()
    drawing.lint.side_effect = LintBudgetExceeded(
        "lint budget exceeded: 6000 elements (limit 5000); narrow the scope"
    )

    result = _invoke(_make_app(drawing), ["--units", "mm"])

    assert result.exit_code == 1
    assert "lint budget exceeded: 6000 elements" in result.stderr
    assert "Traceback" not in result.stderr


def test_lint_rows_sorts_by_severity_then_normalized_ratio() -> None:
    thresholds = Thresholds().scaled("mm")
    result = {
        "paths": [
            {
                "index": 0,
                "issues": [
                    {
                        "type": "tiny",
                        "elem": 1,
                        "x": 0.0,
                        "y": 0.0,
                        "value": thresholds.min_length / 3,
                    },
                    {"type": "gap", "elem": 2, "x": 0.0, "y": 0.0, "value": thresholds.gap_tol * 2},
                    {
                        "type": "bigArc",
                        "elem": 3,
                        "x": 0.0,
                        "y": 0.0,
                        "value": thresholds.max_arc_radius * 1.5,
                    },
                    {
                        "type": "spike",
                        "elem": 4,
                        "x": 0.0,
                        "y": 0.0,
                        "value": thresholds.spike_turn_deg * 1.2,
                    },
                    {
                        "type": "gap",
                        "elem": 5,
                        "x": 0.0,
                        "y": 0.0,
                        "value": thresholds.gap_tol * 5,
                    },
                    {
                        "type": "tiny",
                        "elem": 6,
                        "x": 0.0,
                        "y": 0.0,
                        "value": thresholds.min_length / 10,
                    },
                ],
            }
        ]
    }

    rows = _lint_rows(result, thresholds)

    assert [row[3]["type"] for row in rows] == [
        "gap",
        "gap",
        "spike",
        "bigArc",
        "tiny",
        "tiny",
    ]
    assert [row[3]["elem"] for row in rows[:2]] == [5, 2]
    assert [row[3]["elem"] for row in rows[-2:]] == [6, 1]


def test_lint_rows_puts_unreadable_types_first() -> None:
    thresholds = Thresholds().scaled("mm")
    result = {
        "paths": [
            {
                "index": 0,
                "issues": [
                    {"type": "duplicates", "elem": 0, "x": 0.0, "y": 0.0, "value": 0.0},
                    {"type": "empty", "elem": -1, "x": 0.0, "y": 0.0, "value": 0.0},
                    {"type": "layerUnreadable", "elem": -1, "x": 0.0, "y": 0.0, "value": 0.0},
                    {"type": "unreadable", "elem": -1, "x": 0.0, "y": 0.0, "value": 0.0},
                    {"type": "selfIntersect", "elem": 1, "x": 0.0, "y": 0.0, "value": 0.0},
                ],
            }
        ]
    }

    rows = _lint_rows(result, thresholds)

    assert [row[3]["type"] for row in rows] == [
        "unreadable",
        "layerUnreadable",
        "empty",
        "selfIntersect",
        "duplicates",
    ]


def test_cli_lint_table_warns_when_intersection_skipped() -> None:
    drawing = MagicMock()
    drawing.lint.return_value = {**_PAYLOAD, "intersect_skipped": 2}

    result = _invoke(_make_app(drawing), ["--units", "mm"])

    assert result.exit_code == 0
    assert "intersection test skipped for 2 path(s)" in result.stderr


def test_cli_lint_requires_units() -> None:
    drawing = MagicMock()

    result = _invoke(_make_app(drawing), [])

    assert result.exit_code != 0
    drawing.lint.assert_not_called()


def test_cli_lint_no_drawing() -> None:
    result = _invoke(_make_app(None), ["--units", "mm"])

    assert result.exit_code == 1
    assert "No active drawing" in result.stderr


def test_cli_lint_no_selection() -> None:
    drawing = MagicMock()
    drawing.lint.side_effect = RuntimeError("No selected geometries")

    result = _invoke(_make_app(drawing), ["--units", "mm"])

    assert result.exit_code == 1
    assert "No selected geometries" in result.stderr


def test_cli_lint_rejects_unknown_units() -> None:
    drawing = MagicMock()

    result = _invoke(_make_app(drawing), ["--units", "cm"])

    assert result.exit_code == 1
    assert "units must be" in result.stderr
    drawing.lint.assert_not_called()


@pytest.fixture
def server_app(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    import alphacam_cli.gateway.server as server_module

    fake = MagicMock()
    monkeypatch.setattr(server_module, "_app", fake)
    return fake


def test_handler_drawing_lint_returns_payload(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.lint.return_value = _PAYLOAD
    server_app.get_active_drawing.return_value = drw

    result = GatewayServer()._handler_drawing_lint({"all": True, "units": "inch"})

    assert result == _PAYLOAD
    drw.lint.assert_called_once_with(select_all=True, units="inch")


def test_handler_drawing_lint_no_drawing(server_app: MagicMock) -> None:
    server_app.get_active_drawing.return_value = None

    with pytest.raises(RequestError, match="No active drawing"):
        GatewayServer()._handler_drawing_lint({"all": False, "units": "mm"})


@pytest.mark.parametrize("params", [{}, {"units": None}, {"units": ""}, {"units": 1}])
def test_handler_drawing_lint_requires_units(server_app: MagicMock, params: dict[str, Any]) -> None:
    with pytest.raises(RequestError, match=r"units is required \(mm\|inch\)"):
        GatewayServer()._handler_drawing_lint(params)

    server_app.get_active_drawing.assert_not_called()


def test_handler_drawing_lint_rejects_unknown_units(server_app: MagicMock) -> None:
    with pytest.raises(RequestError, match="units must be"):
        GatewayServer()._handler_drawing_lint({"units": "cm"})

    server_app.get_active_drawing.assert_not_called()


def test_handler_drawing_lint_wraps_error(server_app: MagicMock) -> None:
    drw = MagicMock()
    drw.lint.side_effect = RuntimeError("No selected geometries")
    server_app.get_active_drawing.return_value = drw

    with pytest.raises(RequestError, match="No selected geometries"):
        GatewayServer()._handler_drawing_lint({"all": False, "units": "mm"})


def test_remote_session_drawing_lint_sends_params() -> None:
    session = RemoteSession()
    session._call = MagicMock(return_value=_PAYLOAD)  # type: ignore[method-assign]

    result = session.drawing_lint(select_all=True, units="inch")

    assert result == _PAYLOAD
    session._call.assert_called_once_with(
        "drawing_lint", {"all": True, "units": "inch"}, timeout=150.0
    )


def test_remote_proxy_lint_returns_payload() -> None:
    session = MagicMock()
    session.drawing_lint.return_value = _PAYLOAD
    proxy = _DrawingProxy(session, {})

    assert proxy.lint(True, units="inch") == _PAYLOAD
    session.drawing_lint.assert_called_once_with("inch", True)


def test_cli_drawing_lint_remote_request_error_exits_1() -> None:
    session = RemoteSession()

    def fake_call(method: str, params: Any = None, timeout: float | None = None) -> Any:
        if method == "drawing_lint":
            raise RemoteProtocolError(  # noqa: TRY003
                "JSON-RPC error (-32600): No selected geometries"
            )
        return {"geometries_count": 0, "tool_paths_count": 0}

    session._call = MagicMock(side_effect=fake_call)  # type: ignore[method-assign]

    result = _invoke(RemoteApplication(session), ["--units", "mm"])

    assert result.exit_code == 1
    assert "No selected geometries" in result.stderr
