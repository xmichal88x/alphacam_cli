from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

INCH_TO_MM = 25.4
ISSUE_TYPES = (
    "bigArc",
    "tiny",
    "gap",
    "spike",
    "selfIntersect",
    "nearlyClosed",
    "nonZeroZ",
    "duplicates",
    "unreadable",
    "layerUnreadable",
    "empty",
)
_MAX_FLATTEN_PER_ARC = 512
_ARC_EPS = 1e-9
_INTERSECT_EPS = 1e-9


class LintBudgetExceeded(RuntimeError):  # noqa: N818
    pass


@dataclass(frozen=True)
class Segment:
    is_arc: bool
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    length: float
    start_z: float = 0.0
    end_z: float = 0.0
    center_x: float = 0.0
    center_y: float = 0.0
    radius: float = 0.0
    cw: bool = False


@dataclass(frozen=True)
class Thresholds:
    max_arc_radius: float = 100.0
    min_length: float = 0.001
    gap_tol: float = 1e-4
    spike_turn_deg: float = 150.0
    spike_max_length: float = 0.01
    nearly_closed_tol: float = 0.01
    flatten_tol: float = 0.001
    max_segments_for_intersect: int = 4000
    max_intersect_pairs: int = 1_000_000
    max_intersect_pairs_total: int = 2_000_000
    max_total_elements: int = 5_000
    max_paths: int = 2_000
    z_tol: float = 1e-6

    def scaled(self, units: str) -> Thresholds:
        if units == "inch":
            return self
        if units != "mm":
            raise ValueError("units must be 'mm' or 'inch'")  # noqa: TRY003
        k = INCH_TO_MM
        return replace(
            self,
            max_arc_radius=self.max_arc_radius * k,
            min_length=self.min_length * k,
            gap_tol=self.gap_tol * k,
            spike_max_length=self.spike_max_length * k,
            nearly_closed_tol=self.nearly_closed_tol * k,
            flatten_tol=self.flatten_tol * k,
            z_tol=self.z_tol * k,
        )


@dataclass(frozen=True)
class PathInput:
    closed: bool | None
    segments: Sequence[Segment]
    layer: str | None = None
    unreadable: bool = False
    layer_unreadable: bool = False
    index: int | None = None


@dataclass(frozen=True)
class Issue:
    type: str
    elem: int
    x: float
    y: float
    value: float
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type,
            "elem": self.elem,
            "x": self.x,
            "y": self.y,
            "value": self.value,
        }
        if self.note:
            payload["note"] = self.note
        return payload


@dataclass
class PathReport:
    index: int
    closed: bool | None
    issues: list[Issue] = field(default_factory=list)
    intersect_skipped: bool = False
    pairs_used: int = 0


def analyze_paths(
    paths: Sequence[PathInput],
    thresholds: Thresholds | None = None,
    *,
    units: str,
) -> dict[str, Any]:
    if units not in ("mm", "inch"):
        raise ValueError("units must be 'mm' or 'inch'")  # noqa: TRY003
    th = thresholds if thresholds is not None else Thresholds().scaled(units)
    remaining_pairs = th.max_intersect_pairs_total
    reports: list[PathReport] = []
    for position, path in enumerate(paths):
        report = analyze_path(
            path.index if path.index is not None else position,
            path.closed,
            path.segments,
            th,
            unreadable=path.unreadable,
            layer_unreadable=path.layer_unreadable,
            intersect_budget=remaining_pairs,
        )
        remaining_pairs = max(0, remaining_pairs - report.pairs_used)
        reports.append(report)
    _mark_duplicates(paths, reports)

    flagged = [report for report in reports if report.issues]
    counts: dict[str, int] = {}
    for report in flagged:
        for issue in report.issues:
            counts[issue.type] = counts.get(issue.type, 0) + 1

    intersect_skipped = sum(1 for report in reports if report.intersect_skipped)

    return {
        "success": True,
        "units": units,
        "scanned": len(reports),
        "flagged": len(flagged),
        "intersect_skipped": intersect_skipped,
        "issues_by_type": {name: counts[name] for name in ISSUE_TYPES if name in counts},
        "paths": [
            {
                "index": report.index,
                "closed": report.closed,
                "layer": path.layer,
                "issues": [issue.to_dict() for issue in report.issues],
            }
            for path, report in zip(paths, reports, strict=True)
            if report.issues
        ],
    }


def analyze_path(
    index: int,
    closed: bool | None,
    segments: Sequence[Segment],
    thresholds: Thresholds,
    *,
    unreadable: bool = False,
    layer_unreadable: bool = False,
    intersect_budget: int | None = None,
) -> PathReport:
    th = thresholds
    report = PathReport(index=index, closed=closed)
    if unreadable:
        report.issues.append(Issue("unreadable", -1, 0.0, 0.0, 0.0))
        if layer_unreadable:
            report.issues.append(Issue("layerUnreadable", -1, 0.0, 0.0, 0.0))
        return report
    if layer_unreadable:
        report.issues.append(Issue("layerUnreadable", -1, 0.0, 0.0, 0.0))

    count = len(segments)
    if count == 0:
        report.issues.append(Issue("empty", -1, 0.0, 0.0, 0.0))
        return report

    is_full_circle = (
        count == 1
        and segments[0].is_arc
        and _same_point(
            segments[0].start_x,
            segments[0].start_y,
            segments[0].end_x,
            segments[0].end_y,
        )
    )

    for elem, seg in enumerate(segments):
        if seg.is_arc and seg.radius > th.max_arc_radius:
            report.issues.append(Issue("bigArc", elem, seg.start_x, seg.start_y, seg.radius))
        length = seg.length
        if is_full_circle:
            length = max(length, 2 * math.pi * seg.radius)
        if length < th.min_length:
            report.issues.append(Issue("tiny", elem, seg.start_x, seg.start_y, length))

    max_z = 0.0
    max_z_x = 0.0
    max_z_y = 0.0
    for seg in segments:
        start_abs = abs(seg.start_z)
        end_abs = abs(seg.end_z)
        z = max(start_abs, end_abs)
        if z > max_z:
            max_z = z
            if end_abs > start_abs:
                max_z_x, max_z_y = seg.end_x, seg.end_y
            else:
                max_z_x, max_z_y = seg.start_x, seg.start_y
    if max_z > th.z_tol:
        report.issues.append(Issue("nonZeroZ", -1, max_z_x, max_z_y, max_z))

    junctions = [(i, i + 1) for i in range(count - 1)]
    if closed and count > 1:
        junctions.append((count - 1, 0))
    elif closed and count == 1 and not is_full_circle:
        junctions.append((0, 0))

    for first_idx, second_idx in junctions:
        a = segments[first_idx]
        b = segments[second_idx]
        distance = math.dist((a.end_x, a.end_y), (b.start_x, b.start_y))
        if distance > th.gap_tol:
            report.issues.append(Issue("gap", first_idx, a.end_x, a.end_y, distance))
        if min(a.length, b.length) < th.spike_max_length:
            turn = _turn_angle(a, b)
            if turn > th.spike_turn_deg:
                report.issues.append(Issue("spike", first_idx, a.end_x, a.end_y, turn))

    budget = th.max_intersect_pairs_total if intersect_budget is None else intersect_budget
    issues, skipped, pairs_used = _self_intersections(segments, th, budget)
    report.issues.extend(issues)
    report.intersect_skipped = skipped
    report.pairs_used = pairs_used

    if not closed and count > 1:
        last = segments[-1]
        distance = math.dist((segments[0].start_x, segments[0].start_y), (last.end_x, last.end_y))
        if distance < th.nearly_closed_tol:
            report.issues.append(Issue("nearlyClosed", count - 1, last.end_x, last.end_y, distance))

    return report


def _same_point(x1: float, y1: float, x2: float, y2: float) -> bool:
    return math.hypot(x2 - x1, y2 - y1) <= _ARC_EPS


def _sweep(seg: Segment) -> float:
    if not seg.is_arc or seg.radius <= 0:
        return 0.0
    if _same_point(seg.start_x, seg.start_y, seg.end_x, seg.end_y):
        return -2 * math.pi if seg.cw else 2 * math.pi
    start = math.atan2(seg.start_y - seg.center_y, seg.start_x - seg.center_x)
    end = math.atan2(seg.end_y - seg.center_y, seg.end_x - seg.center_x)
    if seg.cw:
        return -((start - end) % (2 * math.pi))
    return (end - start) % (2 * math.pi)


def _tangent(seg: Segment, at_end: bool) -> tuple[float, float]:
    px = seg.end_x if at_end else seg.start_x
    py = seg.end_y if at_end else seg.start_y
    if seg.is_arc and seg.radius > 0:
        angle = math.atan2(py - seg.center_y, px - seg.center_x)
        angle += -math.pi / 2 if seg.cw else math.pi / 2
        return math.cos(angle), math.sin(angle)
    dx = seg.end_x - seg.start_x
    dy = seg.end_y - seg.start_y
    norm = math.hypot(dx, dy)
    if norm <= 0:
        return 0.0, 0.0
    return dx / norm, dy / norm


def _turn_angle(a: Segment, b: Segment) -> float:
    ax, ay = _tangent(a, at_end=True)
    bx, by = _tangent(b, at_end=False)
    if math.hypot(ax, ay) == 0 or math.hypot(bx, by) == 0:
        return 0.0
    dot = max(-1.0, min(1.0, ax * bx + ay * by))
    return math.degrees(math.acos(dot))


def _flatten(
    segments: Sequence[Segment], tolerance: float, limit: int
) -> tuple[list[tuple[float, float, float, float]], list[int], bool]:
    flat: list[tuple[float, float, float, float]] = []
    owners: list[int] = []
    for owner, seg in enumerate(segments):
        if not seg.is_arc or seg.radius <= 0:
            flat.append((seg.start_x, seg.start_y, seg.end_x, seg.end_y))
            owners.append(owner)
            if len(flat) > limit:
                return flat, owners, True
            continue
        sweep = _sweep(seg)
        if tolerance <= 0 or tolerance >= seg.radius:
            step = math.pi / 8
        else:
            step = 2 * math.acos(max(-1.0, min(1.0, 1 - tolerance / seg.radius)))
        if step <= 0:
            step = math.pi / 8
        pieces = max(1, min(_MAX_FLATTEN_PER_ARC, int(math.ceil(abs(sweep) / step))))
        start_angle = math.atan2(seg.start_y - seg.center_y, seg.start_x - seg.center_x)
        prev_x, prev_y = seg.start_x, seg.start_y
        for k in range(1, pieces + 1):
            angle = start_angle + sweep * k / pieces
            x = seg.center_x + seg.radius * math.cos(angle)
            y = seg.center_y + seg.radius * math.sin(angle)
            flat.append((prev_x, prev_y, x, y))
            owners.append(owner)
            prev_x, prev_y = x, y
            if len(flat) > limit:
                return flat, owners, True
    return flat, owners, False


def _self_intersections(
    segments: Sequence[Segment], th: Thresholds, budget: int
) -> tuple[list[Issue], bool, int]:
    flat, owners, exceeded = _flatten(segments, th.flatten_tol, th.max_segments_for_intersect)
    if exceeded:
        return [], True, 0
    owner_counts: dict[int, int] = {}
    for owner in owners:
        owner_counts[owner] = owner_counts.get(owner, 0) + 1
    total_pairs = len(flat) * (len(flat) - 1) // 2
    same_owner_pairs = sum(count * (count - 1) // 2 for count in owner_counts.values())
    pair_count = total_pairs - same_owner_pairs
    if pair_count > min(th.max_intersect_pairs, budget):
        return [], True, 0
    issues: list[Issue] = []
    for i in range(len(flat)):
        x1, y1, x2, y2 = flat[i]
        min_x = min(x1, x2)
        max_x = max(x1, x2)
        min_y = min(y1, y2)
        max_y = max(y1, y2)
        for j in range(i + 1, len(flat)):
            if owners[i] == owners[j]:
                continue
            x3, y3, x4, y4 = flat[j]
            if (
                max_x < min(x3, x4) - _INTERSECT_EPS
                or max(x3, x4) < min_x - _INTERSECT_EPS
                or max_y < min(y3, y4) - _INTERSECT_EPS
                or max(y3, y4) < min_y - _INTERSECT_EPS
            ):
                continue
            point = _proper_intersection((x1, y1, x2, y2), (x3, y3, x4, y4))
            if point is not None:
                issues.append(
                    Issue(
                        "selfIntersect",
                        owners[i],
                        point[0],
                        point[1],
                        0.0,
                        note=f"elem {owners[i]} x elem {owners[j]}",
                    )
                )
    return issues, False, pair_count


def _proper_intersection(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> tuple[float, float] | None:
    x1, y1, x2, y2 = a
    x3, y3, x4, y4 = b
    denom = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if abs(denom) <= _INTERSECT_EPS:
        return None
    t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / denom
    u = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / denom
    if _INTERSECT_EPS < t < 1 - _INTERSECT_EPS and _INTERSECT_EPS < u < 1 - _INTERSECT_EPS:
        return x1 + t * (x2 - x1), y1 + t * (y2 - y1)
    return None


def _signature(path: PathInput) -> tuple[Any, ...] | None:
    if path.layer_unreadable or not path.segments:
        return None
    layer: Any = path.layer if path.layer is not None else ("__default__",)
    return (
        layer,
        tuple(
            (
                seg.is_arc,
                round(seg.start_x, 6),
                round(seg.start_y, 6),
                round(seg.end_x, 6),
                round(seg.end_y, 6),
                round(seg.radius, 6),
                seg.cw,
                round(seg.center_x, 6),
                round(seg.center_y, 6),
                round(seg.start_z, 6),
                round(seg.end_z, 6),
            )
            for seg in path.segments
        ),
    )


def _mark_duplicates(paths: Sequence[PathInput], reports: Sequence[PathReport]) -> None:
    seen: dict[tuple[Any, ...], int] = {}
    for path, report in zip(paths, reports, strict=True):
        signature = _signature(path)
        if signature is None:
            continue
        original = seen.get(signature)
        if original is None:
            seen[signature] = report.index
        else:
            head = path.segments[0]
            report.issues.append(
                Issue("duplicates", -1, head.start_x, head.start_y, float(original))
            )
