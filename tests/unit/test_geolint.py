from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

import pytest

from alphacam_cli.core.geolint import (
    PathInput,
    Segment,
    Thresholds,
    analyze_paths,
)


def _line(
    sx: float,
    sy: float,
    ex: float,
    ey: float,
    length: float | None = None,
    start_z: float = 0.0,
    end_z: float = 0.0,
) -> Segment:
    return Segment(
        is_arc=False,
        start_x=sx,
        start_y=sy,
        end_x=ex,
        end_y=ey,
        length=math.dist((sx, sy), (ex, ey)) if length is None else length,
        start_z=start_z,
        end_z=end_z,
    )


def _arc(
    sx: float,
    sy: float,
    ex: float,
    ey: float,
    cx: float,
    cy: float,
    radius: float,
    cw: bool = False,
    length: float | None = None,
) -> Segment:
    if length is None:
        sweep = 2 * math.pi if (sx, sy) == (ex, ey) else math.pi
        length = radius * sweep
    return Segment(
        is_arc=True,
        start_x=sx,
        start_y=sy,
        end_x=ex,
        end_y=ey,
        length=length,
        center_x=cx,
        center_y=cy,
        radius=radius,
        cw=cw,
    )


def _rectangle(width: float = 10.0, height: float = 5.0) -> list[Segment]:
    return [
        _line(0, 0, width, 0),
        _line(width, 0, width, height),
        _line(width, height, 0, height),
        _line(0, height, 0, 0),
    ]


def test_clean_rectangle_has_no_issues() -> None:
    result = analyze_paths([PathInput(closed=True, segments=_rectangle())], units="inch")

    assert result["success"] is True
    assert result["scanned"] == 1
    assert result["flagged"] == 0
    assert result["issues_by_type"] == {}
    assert result["paths"] == []


def test_clean_full_circle_is_not_tiny() -> None:
    circle = _arc(10, 0, 10, 0, 0, 0, 10)

    result = analyze_paths([PathInput(closed=True, segments=[circle])], units="inch")

    assert result["flagged"] == 0
    assert result["issues_by_type"] == {}


def test_tiny_full_circle_is_flagged() -> None:
    circle = _arc(0.0001, 0, 0.0001, 0, 0, 0, 0.0001)

    result = analyze_paths([PathInput(closed=True, segments=[circle])], units="inch")

    assert result["issues_by_type"]["tiny"] == 1
    assert result["paths"][0]["issues"][0]["value"] == pytest.approx(2 * math.pi * 0.0001)


def test_full_circle_tiny_uses_effective_length() -> None:
    circle = _arc(0.0001, 0, 0.0001, 0, 0, 0, 0.0001, length=0.0)

    result = analyze_paths([PathInput(closed=True, segments=[circle])], units="inch")

    assert result["issues_by_type"]["tiny"] == 1
    assert result["paths"][0]["issues"][0]["value"] == pytest.approx(2 * math.pi * 0.0001)


def test_big_arc_is_flagged() -> None:
    arc = _arc(60000, 0, 0, 60000, 0, 0, 60000)

    result = analyze_paths([PathInput(closed=False, segments=[arc])], units="inch")

    assert result["issues_by_type"]["bigArc"] == 1
    issue = result["paths"][0]["issues"][0]
    assert issue["type"] == "bigArc"
    assert issue["elem"] == 0
    assert issue["value"] == pytest.approx(60000.0)
    assert issue["x"] == pytest.approx(60000.0)
    assert issue["y"] == pytest.approx(0.0)


def test_tiny_element_uses_mm_thresholds() -> None:
    segment = _line(0, 0, 10, 0, length=0.0013)

    result = analyze_paths(
        [PathInput(closed=False, segments=[segment])], Thresholds().scaled("mm"), units="mm"
    )

    assert result["issues_by_type"]["tiny"] == 1
    assert result["paths"][0]["issues"][0]["value"] == pytest.approx(0.0013)


def test_gap_between_elements_is_flagged() -> None:
    segments = [_line(0, 0, 10, 0), _line(10.0005, 0, 20, 0)]

    result = analyze_paths([PathInput(closed=False, segments=segments)], units="inch")

    assert result["issues_by_type"]["gap"] == 1
    issue = result["paths"][0]["issues"][0]
    assert issue["type"] == "gap"
    assert issue["value"] == pytest.approx(0.0005)


def test_spike_on_short_reversal_is_flagged() -> None:
    segments = [_line(0, 0, 0.005, 0), _line(0.005, 0, 0, 0)]

    result = analyze_paths([PathInput(closed=False, segments=segments)], units="inch")

    assert result["issues_by_type"]["spike"] == 1
    issue = result["paths"][0]["issues"][0]
    assert issue["type"] == "spike"
    assert issue["value"] == pytest.approx(180.0)


def test_self_intersection_is_flagged() -> None:
    segments = [
        _line(0, 0, 10, 10),
        _line(10, 10, 10, 0),
        _line(10, 0, 0, 10),
        _line(0, 10, 0, 0),
    ]

    result = analyze_paths([PathInput(closed=False, segments=segments)], units="inch")

    assert result["issues_by_type"]["selfIntersect"] == 1
    issue = result["paths"][0]["issues"][0]
    assert issue["type"] == "selfIntersect"
    assert issue["elem"] == 0
    assert issue["value"] == pytest.approx(0.0)
    assert issue["note"] == "elem 0 x elem 2"
    assert issue["x"] == pytest.approx(5.0)
    assert issue["y"] == pytest.approx(5.0)


def test_self_intersection_skipped_above_segment_limit() -> None:
    segments = [
        _line(0, 0, 10, 10),
        _line(10, 10, 10, 0),
        _line(10, 0, 0, 10),
        _line(0, 10, 0, 0),
    ]
    thresholds = replace(Thresholds(), max_segments_for_intersect=1)

    result = analyze_paths([PathInput(closed=False, segments=segments)], thresholds, units="inch")

    assert "selfIntersect" not in result["issues_by_type"]


def test_nearly_closed_open_path_is_flagged() -> None:
    segments = [_line(0, 0, 10, 0), _line(10, 0, 0.005, 0)]

    result = analyze_paths([PathInput(closed=False, segments=segments)], units="inch")

    assert result["issues_by_type"]["nearlyClosed"] == 1
    issue = result["paths"][0]["issues"][0]
    assert issue["type"] == "nearlyClosed"
    assert issue["value"] == pytest.approx(0.005)


def test_non_zero_z_is_flagged() -> None:
    segment = _line(0, 0, 10, 0, end_z=2.0)

    result = analyze_paths([PathInput(closed=False, segments=[segment])], units="inch")

    assert result["issues_by_type"]["nonZeroZ"] == 1
    issue = result["paths"][0]["issues"][0]
    assert issue["type"] == "nonZeroZ"
    assert issue["value"] == pytest.approx(2.0)


def test_non_zero_z_reported_once_per_path() -> None:
    segments = [_line(i * 10, 0, (i + 1) * 10, 0, start_z=5.0, end_z=5.0) for i in range(100)]

    result = analyze_paths([PathInput(closed=False, segments=segments)], units="inch")

    assert result["issues_by_type"]["nonZeroZ"] == 1
    issue = result["paths"][0]["issues"][0]
    assert issue["type"] == "nonZeroZ"
    assert issue["elem"] == -1
    assert issue["value"] == pytest.approx(5.0)
    assert issue["x"] == pytest.approx(0.0)
    assert issue["y"] == pytest.approx(0.0)


def test_single_element_path_is_not_nearly_closed() -> None:
    segment = _line(0, 0, 0.005, 0)

    result = analyze_paths([PathInput(closed=False, segments=[segment])], units="inch")

    assert "nearlyClosed" not in result["issues_by_type"]


def test_duplicate_paths_on_different_layers_are_not_flagged() -> None:
    paths = [
        PathInput(closed=True, segments=_rectangle(), layer="Cut"),
        PathInput(closed=True, segments=_rectangle(), layer="Engrave"),
    ]

    result = analyze_paths(paths, units="inch")

    assert "duplicates" not in result["issues_by_type"]
    assert result["flagged"] == 0


def test_duplicate_paths_on_same_layer_are_flagged() -> None:
    paths = [
        PathInput(closed=True, segments=_rectangle(), layer="Cut"),
        PathInput(closed=True, segments=_rectangle(), layer="Cut"),
    ]

    result = analyze_paths(paths, units="inch")

    assert result["issues_by_type"]["duplicates"] == 1
    assert result["paths"][0]["layer"] == "Cut"


def test_unreadable_path_reports_single_issue() -> None:
    result = analyze_paths(
        [PathInput(closed=True, segments=[], layer="Cut", unreadable=True)], units="inch"
    )

    assert result["scanned"] == 1
    assert result["flagged"] == 1
    assert result["issues_by_type"] == {"unreadable": 1}
    issue = result["paths"][0]["issues"][0]
    assert issue["type"] == "unreadable"
    assert issue["elem"] == -1


def test_flatten_stops_at_limit_quickly() -> None:
    arcs = [_arc(10, 0, 10, 0, 0, 0, 10) for _ in range(500)]

    result = analyze_paths([PathInput(closed=True, segments=arcs)], units="inch")

    assert result["intersect_skipped"] == 1
    assert "selfIntersect" not in result["issues_by_type"]


def test_result_reports_units() -> None:
    result = analyze_paths([PathInput(closed=False, segments=[_line(0, 0, 1, 0)])], units="mm")

    assert result["units"] == "mm"


def test_duplicate_paths_are_flagged() -> None:
    paths = [
        PathInput(closed=True, segments=_rectangle(), layer="Cut"),
        PathInput(closed=True, segments=_rectangle(), layer="Cut"),
    ]

    result = analyze_paths(paths, units="inch")

    assert result["scanned"] == 2
    assert result["flagged"] == 1
    assert result["issues_by_type"] == {"duplicates": 1}
    assert result["paths"][0]["index"] == 1
    issue = result["paths"][0]["issues"][0]
    assert issue["type"] == "duplicates"
    assert issue["elem"] == -1
    assert issue["value"] == pytest.approx(0.0)


def test_duplicate_paths_with_default_layer_are_flagged() -> None:
    paths = [
        PathInput(closed=True, segments=_rectangle(), layer=None),
        PathInput(closed=True, segments=_rectangle(), layer=None),
    ]

    result = analyze_paths(paths, units="inch")

    assert result["issues_by_type"]["duplicates"] == 1
    assert result["flagged"] == 1


def test_duplicate_paths_with_empty_layer_are_flagged() -> None:
    paths = [
        PathInput(closed=True, segments=_rectangle(), layer=""),
        PathInput(closed=True, segments=_rectangle(), layer=""),
    ]

    result = analyze_paths(paths, units="inch")

    assert result["issues_by_type"]["duplicates"] == 1
    assert result["flagged"] == 1


def test_empty_layer_differs_from_default_layer() -> None:
    paths = [
        PathInput(closed=True, segments=_rectangle(), layer=""),
        PathInput(closed=True, segments=_rectangle(), layer=None),
    ]

    result = analyze_paths(paths, units="inch")

    assert "duplicates" not in result["issues_by_type"]
    assert result["flagged"] == 0


def test_arc_cw_and_ccw_are_not_duplicates() -> None:
    ccw = _arc(1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, cw=False)
    cw = _arc(1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, cw=True)
    paths = [
        PathInput(closed=False, segments=[ccw], layer="Cut"),
        PathInput(closed=False, segments=[cw], layer="Cut"),
    ]

    result = analyze_paths(paths, units="inch")

    assert "duplicates" not in result["issues_by_type"]


def test_same_shape_on_different_z_is_not_duplicate() -> None:
    low = _line(0.0, 0.0, 10.0, 0.0, start_z=0.0, end_z=0.0)
    high = _line(0.0, 0.0, 10.0, 0.0, start_z=5.0, end_z=5.0)
    paths = [
        PathInput(closed=False, segments=[low], layer="Cut"),
        PathInput(closed=False, segments=[high], layer="Cut"),
    ]

    result = analyze_paths(paths, units="inch")

    assert "duplicates" not in result["issues_by_type"]


def test_same_shape_and_z_is_duplicate() -> None:
    first = _line(0.0, 0.0, 10.0, 0.0, start_z=2.0, end_z=2.0)
    second = _line(0.0, 0.0, 10.0, 0.0, start_z=2.0, end_z=2.0)
    paths = [
        PathInput(closed=False, segments=[first], layer="Cut"),
        PathInput(closed=False, segments=[second], layer="Cut"),
    ]

    result = analyze_paths(paths, units="inch")

    assert result["issues_by_type"]["duplicates"] == 1


def test_layer_unreadable_is_reported_and_excluded_from_duplicates() -> None:
    segment = _line(0.0, 0.0, 0.0001, 0.0)
    paths = [
        PathInput(closed=True, segments=[segment], layer="Cut", layer_unreadable=True),
        PathInput(closed=True, segments=[segment], layer="Cut", layer_unreadable=True),
    ]

    result = analyze_paths(paths, units="inch")

    assert result["issues_by_type"]["layerUnreadable"] == 2
    assert result["issues_by_type"]["tiny"] == 2
    assert "duplicates" not in result["issues_by_type"]
    assert all(
        issue["type"] == "layerUnreadable"
        for path in result["paths"]
        for issue in path["issues"][:1]
    )


def test_empty_path_is_flagged() -> None:
    result = analyze_paths([PathInput(closed=True, segments=[])], units="inch")

    assert result["flagged"] == 1
    assert result["issues_by_type"] == {"empty": 1}
    issue = result["paths"][0]["issues"][0]
    assert issue["type"] == "empty"
    assert issue["elem"] == -1


def test_closed_single_arc_with_gap_is_flagged() -> None:
    arc = _arc(1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0)

    result = analyze_paths([PathInput(closed=True, segments=[arc])], units="inch")

    assert result["issues_by_type"]["gap"] == 1
    assert result["paths"][0]["issues"][0]["value"] == pytest.approx(math.sqrt(2))


def test_closed_full_circle_has_no_gap() -> None:
    circle = _arc(10.0, 0.0, 10.0, 0.0, 0.0, 0.0, 10.0)

    result = analyze_paths([PathInput(closed=True, segments=[circle])], units="inch")

    assert "gap" not in result["issues_by_type"]


def test_unreadable_path_reports_closed_null() -> None:
    result = analyze_paths(
        [PathInput(closed=None, segments=[], layer="Cut", unreadable=True)], units="inch"
    )

    assert result["paths"][0]["closed"] is None


def test_empty_path_does_not_report_closed_null() -> None:
    result = analyze_paths([PathInput(closed=True, segments=[])], units="inch")

    assert result["paths"][0]["closed"] is True


def test_explicit_index_is_preserved() -> None:
    paths = [
        PathInput(closed=True, segments=[], index=7),
        PathInput(closed=True, segments=[], index=3),
    ]

    result = analyze_paths(paths, units="inch")

    assert [path["index"] for path in result["paths"]] == [7, 3]


def test_units_rejected_even_with_explicit_thresholds() -> None:
    with pytest.raises(ValueError, match="units must be"):
        analyze_paths(
            [PathInput(closed=False, segments=[_line(0, 0, 1, 0)])], Thresholds(), units="cm"
        )


def test_mirrored_paths_are_not_duplicates() -> None:
    mirrored = [_line(-seg.start_x, seg.start_y, -seg.end_x, seg.end_y) for seg in _rectangle()]
    paths = [
        PathInput(closed=True, segments=_rectangle(), layer="Cut"),
        PathInput(closed=True, segments=mirrored, layer="Cut"),
    ]

    result = analyze_paths(paths, units="inch")

    assert "duplicates" not in result["issues_by_type"]


def test_non_zero_z_points_to_element_with_max_abs_z() -> None:
    segments = [
        _line(0, 0, 10, 0, start_z=1.0, end_z=1.0),
        _line(10, 0, 20, 0, start_z=7.0, end_z=0.0),
    ]

    result = analyze_paths([PathInput(closed=False, segments=segments)], units="inch")

    issue = result["paths"][0]["issues"][0]
    assert issue["type"] == "nonZeroZ"
    assert issue["value"] == pytest.approx(7.0)
    assert issue["x"] == pytest.approx(10.0)
    assert issue["y"] == pytest.approx(0.0)


def test_intersect_skipped_counts_paths_that_exceed_limit() -> None:
    segments = [
        _line(0, 0, 10, 10),
        _line(10, 10, 10, 0),
        _line(10, 0, 0, 10),
        _line(0, 10, 0, 0),
    ]
    thresholds = replace(Thresholds(), max_segments_for_intersect=1)

    result = analyze_paths([PathInput(closed=False, segments=segments)], thresholds, units="inch")

    assert result["intersect_skipped"] == 1
    assert "selfIntersect" not in result["issues_by_type"]


def test_intersect_skipped_is_zero_for_checked_paths() -> None:
    result = analyze_paths([PathInput(closed=False, segments=[_line(0, 0, 1, 0)])], units="inch")

    assert result["intersect_skipped"] == 0


def test_thresholds_scale_to_mm() -> None:
    mm = Thresholds().scaled("mm")

    assert mm.max_arc_radius == pytest.approx(2540.0)
    assert mm.min_length == pytest.approx(0.0254)
    assert mm.gap_tol == pytest.approx(0.00254)
    assert mm.z_tol == pytest.approx(2.54e-5)
    assert mm.spike_turn_deg == pytest.approx(150.0)


def test_thresholds_inch_is_identity() -> None:
    base = Thresholds()

    assert base.scaled("inch") == base


def test_thresholds_reject_unknown_units() -> None:
    with pytest.raises(ValueError, match="units must be"):
        Thresholds().scaled("cm")


def test_analyze_paths_requires_units() -> None:
    fn: Any = analyze_paths

    with pytest.raises(TypeError):
        fn([PathInput(closed=False, segments=[_line(0, 0, 1, 0)])])


def test_non_zero_z_points_to_end_vertex_when_max_at_end() -> None:
    segment = _line(0.0, 0.0, 10.0, 20.0, start_z=1.0, end_z=7.0)

    result = analyze_paths([PathInput(closed=False, segments=[segment])], units="inch")

    issue = result["paths"][0]["issues"][0]
    assert issue["type"] == "nonZeroZ"
    assert issue["value"] == pytest.approx(7.0)
    assert issue["x"] == pytest.approx(10.0)
    assert issue["y"] == pytest.approx(20.0)


def test_non_zero_z_prefers_start_vertex_on_tie() -> None:
    segment = _line(0.0, 0.0, 10.0, 0.0, start_z=5.0, end_z=5.0)

    result = analyze_paths([PathInput(closed=False, segments=[segment])], units="inch")

    issue = result["paths"][0]["issues"][0]
    assert issue["x"] == pytest.approx(0.0)
    assert issue["y"] == pytest.approx(0.0)


def test_intersect_pair_limit_skips_many_segments_quickly() -> None:
    segments = [_line(float(i), 0.0, float(i + 1), 0.0) for i in range(2000)]

    result = analyze_paths([PathInput(closed=False, segments=segments)], units="inch")

    assert result["intersect_skipped"] == 1
    assert "selfIntersect" not in result["issues_by_type"]


def _crossing() -> list[Segment]:
    return [
        _line(0, 0, 10, 10),
        _line(10, 10, 10, 0),
        _line(10, 0, 0, 10),
        _line(0, 10, 0, 0),
    ]


def test_global_intersect_budget_skips_remaining_paths() -> None:
    thresholds = replace(Thresholds(), max_intersect_pairs_total=6)

    result = analyze_paths(
        [
            PathInput(closed=False, segments=_crossing()),
            PathInput(closed=False, segments=_crossing()),
        ],
        thresholds,
        units="inch",
    )

    assert result["intersect_skipped"] == 1
    assert result["issues_by_type"]["selfIntersect"] == 1


def test_global_intersect_budget_defaults() -> None:
    thresholds = Thresholds()

    assert thresholds.max_intersect_pairs_total == 2_000_000
    assert thresholds.max_total_elements == 5_000
    assert thresholds.max_paths == 2_000


def test_z_tol_scales_with_units() -> None:
    assert Thresholds().z_tol == pytest.approx(1e-6)
    assert Thresholds().scaled("mm").z_tol == pytest.approx(1e-6 * 25.4)
    assert Thresholds().scaled("inch").z_tol == pytest.approx(1e-6)


def test_intersect_budget_counts_only_cross_owner_pairs() -> None:
    arc = _arc(10, 0, 10, 0, 0, 0, 10)
    line = _line(100, 100, 101, 100)
    thresholds = replace(Thresholds(), flatten_tol=10.0, max_intersect_pairs_total=16)

    result = analyze_paths([PathInput(closed=True, segments=[arc, line])], thresholds, units="inch")

    assert result["intersect_skipped"] == 0


def test_intersect_pair_limit_is_independent_of_segment_limit() -> None:
    segments = [
        _line(0, 0, 10, 10),
        _line(10, 10, 10, 0),
        _line(10, 0, 0, 10),
        _line(0, 10, 0, 0),
    ]
    thresholds = replace(Thresholds(), max_intersect_pairs=1)

    result = analyze_paths([PathInput(closed=False, segments=segments)], thresholds, units="inch")

    assert result["intersect_skipped"] == 1
    assert "selfIntersect" not in result["issues_by_type"]
