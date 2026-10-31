from __future__ import annotations

import json
import math
import os
from typing import Any

import typer
from rich.table import Table

from alphacam_cli.cli.common import (
    console,
    get_visible,
    handle_com_errors,
    require_platform,
    resolve_app,
)
from alphacam_cli.com.manager import alphacam_context
from alphacam_cli.core.geolint import Thresholds

app = typer.Typer(help="Drawing operations")

_LINT_SEVERITY = {
    "unreadable": 0,
    "layerUnreadable": 1,
    "empty": 2,
    "selfIntersect": 3,
    "gap": 4,
    "spike": 5,
    "bigArc": 6,
    "nonZeroZ": 7,
    "nearlyClosed": 8,
    "duplicates": 9,
    "tiny": 10,
}


def _normalized_ratio(issue: dict[str, Any], thresholds: Thresholds) -> float:
    issue_type = str(issue.get("type", ""))
    value = float(issue.get("value", 0.0))
    if issue_type == "gap":
        return value / thresholds.gap_tol if thresholds.gap_tol > 0 else 0.0
    if issue_type == "nearlyClosed":
        return value / thresholds.nearly_closed_tol if thresholds.nearly_closed_tol > 0 else 0.0
    if issue_type == "bigArc":
        return value / thresholds.max_arc_radius if thresholds.max_arc_radius > 0 else 0.0
    if issue_type == "tiny":
        return thresholds.min_length / value if value > 0 else math.inf
    if issue_type == "spike":
        return value / thresholds.spike_turn_deg if thresholds.spike_turn_deg > 0 else 0.0
    if issue_type == "nonZeroZ":
        return value / thresholds.z_tol if thresholds.z_tol > 0 else 0.0
    return 0.0


def _lint_rows(
    result: dict[str, Any], thresholds: Thresholds
) -> list[tuple[int, float, int, dict[str, Any]]]:
    rows: list[tuple[int, float, int, dict[str, Any]]] = []
    for path in result.get("paths", []):
        index = int(path.get("index", 0))
        for issue in path.get("issues", []):
            severity = _LINT_SEVERITY.get(str(issue.get("type", "")), 99)
            rows.append((severity, _normalized_ratio(issue, thresholds), index, issue))
    rows.sort(
        key=lambda row: (
            row[0],
            -row[1],
            row[2],
            int(row[3].get("elem", 0)),
        )
    )
    return rows


def _fmt(value: Any) -> str:
    return f"{float(value):.6g}"


def _resolve_fmt(path: str, fmt: str) -> str:
    """Resolve 'auto' format from the file extension."""
    if fmt != "auto":
        return fmt
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    if not ext:
        console.print(
            "[red]Error:[/red] Cannot infer format from path without extension. Use --fmt."
        )
        raise typer.Exit(code=1)
    return ext


def _print_fix_result(result: dict[str, Any]) -> None:
    backup = result.get("backup")
    console.print(f"Backup: {backup}" if backup else "Backup: (none)")

    fixed: dict[str, Any] = result.get("fixed", {})
    repaired = Table(title="Fixed")
    repaired.add_column("Issue type", style="cyan")
    repaired.add_column("Count", style="green", justify="right")
    has_fixed = False
    for name, count in fixed.items():
        if int(count) > 0:
            repaired.add_row(str(name), str(count))
            has_fixed = True
    if not has_fixed:
        repaired.add_row("(none)", "0")
    console.print(repaired)

    would_fix: dict[str, Any] = result.get("would_fix", {})
    if would_fix:
        planned = Table(title="Would fix (dry run)")
        planned.add_column("Issue type", style="cyan")
        planned.add_column("Count", style="yellow", justify="right")
        for name, count in would_fix.items():
            if int(count) > 0:
                planned.add_row(str(name), str(count))
        console.print(planned)

    skipped: list[dict[str, Any]] = result.get("skipped", [])
    if skipped:
        skipped_table = Table(title="Skipped")
        skipped_table.add_column("Path", style="magenta", justify="right")
        skipped_table.add_column("Types", style="cyan")
        skipped_table.add_column("Reason", style="yellow")
        for entry in skipped:
            skipped_table.add_row(
                str(entry.get("index", "")),
                ", ".join(str(item) for item in entry.get("types", [])),
                str(entry.get("reason", "")),
            )
        console.print(skipped_table)

    failed: list[dict[str, Any]] = result.get("failed", [])
    if failed:
        failed_table = Table(title="Failed")
        failed_table.add_column("Path", style="magenta", justify="right")
        failed_table.add_column("Types", style="cyan")
        failed_table.add_column("Reason", style="red")
        for entry in failed:
            failed_table.add_row(
                str(entry.get("index", "")),
                ", ".join(str(item) for item in entry.get("types", [])),
                str(entry.get("reason", "")),
            )
        console.print(failed_table)

    remaining: dict[str, Any] = result.get("remaining", {})
    remaining_table = Table(title="Remaining issues")
    remaining_table.add_column("Issue type", style="cyan")
    remaining_table.add_column("Count", style="green", justify="right")
    if remaining:
        for name, count in remaining.items():
            remaining_table.add_row(str(name), str(count))
    else:
        remaining_table.add_row("(none)", "0")
    console.print(remaining_table)

    for warning in result.get("warnings", []):
        console.print(f"[yellow]Warning:[/yellow] {warning}")


@app.command()
@handle_com_errors
def create(
    width: float = typer.Option(100, "--width", "-w", help="Rectangle width"),
    height: float = typer.Option(50, "--height", "-h", help="Rectangle height"),
    fillet: float = typer.Option(0, "--fillet", "-f", help="Corner fillet radius"),
    text: str = typer.Option("", "--text", "-t", help="Text to add"),
) -> None:
    """Create a new drawing with a rectangle and optional fillet and text."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        drw = ac.new_drawing(width, height, fillet, text)
        if drw is None:
            console.print("[red]Failed to create drawing[/red]")
            raise typer.Exit(code=1)

        t = Table(title="Drawing Created")
        t.add_column("Property", style="cyan")
        t.add_column("Value", style="green")
        t.add_row("Width", str(width))
        t.add_row("Height", str(height))
        if fillet > 0:
            t.add_row("Fillet", str(fillet))
        t.add_row("Geometries", str(drw.geometries_count))
        console.print(t)


@app.command()
@handle_com_errors
def parametric(
    width: float = typer.Argument(..., help="Panel width"),
    height: float = typer.Argument(..., help="Panel height"),
    offset: float = typer.Option(50, "--offset", help="Inset of the inner contour"),
    fillet: float = typer.Option(5, "--fillet", "-f", help="Corner fillet radius"),
    depth: float | None = typer.Option(
        None, "--depth", "-d", help="DEPRECATED: ignored — use mill rough"
    ),
) -> None:
    """Create a parametric door/frame panel geometry.

    Outer filleted rectangle + inner arched contour.
    """
    if depth is not None:
        console.print(
            "[yellow]Warning:[/yellow] --depth is deprecated: machining is now a separate block "
            "(use 'alphacam mill rough')"
        )
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.drawing_parametric(
            width,
            height,
            offset=offset,
            fillet=fillet,
        )
        console.print(
            f"[green]OK:[/green] Panel {width:g}x{height:g} created "
            f"(offset={offset:g}, fillet={fillet:g})"
        )
        console.print(
            f"      Geometries: {result['geometries_count']}, "
            f"ToolPaths: {result['tool_paths_count']}"
        )


@app.command()
@handle_com_errors
def layer(name: str = typer.Argument(..., help="Layer name (max 31 characters)")) -> None:
    """Create a user layer on the active drawing (or return the existing one)."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        drw = ac.get_active_drawing()
        if drw is None:
            console.print("[red]No active drawing[/red]")
            raise typer.Exit(code=1)

        drw.create_layer(name)
        console.print(f"[green]OK:[/green] Layer created: {name}")


@app.command()
@handle_com_errors
def move(
    dx: float = typer.Option(..., "--dx", help="Move distance along global X"),
    dy: float = typer.Option(..., "--dy", help="Move distance along global Y"),
    dz: float = typer.Option(0.0, "--dz", help="Move distance along global Z"),
    all_: bool = typer.Option(False, "--all", help="Select all geometries before moving"),
    json_out: bool = typer.Option(False, "--json", help="Output deterministic JSON"),
) -> None:
    """Move selected geometry by a vector (dx, dy, dz)."""
    for name, value in (("dx", dx), ("dy", dy), ("dz", dz)):
        if not math.isfinite(value):
            console.print(f"[red]Error:[/red] --{name} must be a finite number")
            raise typer.Exit(code=1)
    require_platform()
    moved = 0
    failure: str | None = None
    warnings: list[str] = []
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        drw = ac.get_active_drawing()
        if drw is None:
            failure = "No active drawing"
        else:
            try:
                result = drw.move(dx, dy, dz, select_all=all_)
            except RuntimeError as e:
                failure = str(e)
            else:
                moved = result.moved
                warnings = list(result.warnings)

    if failure is not None:
        console.print(f"[red]Error:[/red] {failure}")
        raise typer.Exit(code=1)

    if json_out:
        payload = {
            "success": True,
            "moved": moved,
            "dx": dx,
            "dy": dy,
            "dz": dz,
            "warnings": warnings,
        }
        typer.echo(json.dumps(payload, sort_keys=True))
        return

    for warning in warnings:
        console.print(f"[yellow]Warning:[/yellow] {warning}")

    t = Table(title="Geometry Moved")
    t.add_column("Property", style="cyan")
    t.add_column("Value", style="green")
    t.add_row("dx", str(dx))
    t.add_row("dy", str(dy))
    t.add_row("dz", str(dz))
    t.add_row("Moved", str(moved))
    console.print(t)


@app.command()
@handle_com_errors
def lint(
    all_: bool = typer.Option(False, "--all", help="Scan all geometries instead of selection"),
    units: str = typer.Option(..., "--units", help="Required: mm|inch (threshold scaling)"),
    json_out: bool = typer.Option(False, "--json", help="Output deterministic JSON"),
    fix: bool = typer.Option(False, "--fix", help="Repair fixable defects in place"),
    dry_run: bool = typer.Option(False, "--dry-run", help="With --fix: plan only, no changes"),
    no_backup: bool = typer.Option(
        False, "--no-backup", help="With --fix: skip the DXF backup export"
    ),
) -> None:
    """Read-only geometry analysis for defects that break machining/NC."""
    require_platform()
    if units not in ("mm", "inch"):
        console.print("[red]Error:[/red] --units must be 'mm' or 'inch'")
        raise typer.Exit(code=1)

    result: dict[str, Any] | None = None
    failure: str | None = None
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        drw = ac.get_active_drawing()
        if drw is None:
            failure = "No active drawing"
        else:
            try:
                if fix:
                    result = drw.lint_fix(
                        select_all=all_,
                        units=units,
                        dry_run=dry_run,
                        backup=not no_backup,
                    )
                else:
                    result = drw.lint(select_all=all_, units=units)
            except RuntimeError as e:
                failure = str(e)

    if failure is not None:
        console.print(f"[red]Error:[/red] {failure}")
        raise typer.Exit(code=1)
    if result is None:
        console.print("[red]Error:[/red] lint produced no result")
        raise typer.Exit(code=1)

    if json_out:
        typer.echo(json.dumps(result, sort_keys=True))
        return

    if fix:
        _print_fix_result(result)
        return

    console.print(f"Scanned: {result.get('scanned', 0)} paths, flagged: {result.get('flagged', 0)}")
    skipped = int(result.get("intersect_skipped", 0))
    if skipped > 0:
        console.print(
            f"[yellow]Warning:[/yellow] intersection test skipped for {skipped} path(s) "
            "(segment or pair budget)"
        )

    summary = Table(title="Geometry Lint")
    summary.add_column("Issue type", style="cyan")
    summary.add_column("Count", style="green", justify="right")
    counts: dict[str, Any] = result.get("issues_by_type", {})
    if counts:
        for name, count in counts.items():
            summary.add_row(str(name), str(count))
    else:
        summary.add_row("(none)", "0")
    console.print(summary)

    rows = _lint_rows(result, Thresholds().scaled(units))
    if rows:
        worst = Table(title="Worst cases (max 20)")
        worst.add_column("Type", style="cyan")
        worst.add_column("Path", style="magenta", justify="right")
        worst.add_column("Elem", style="magenta", justify="right")
        worst.add_column("X", justify="right")
        worst.add_column("Y", justify="right")
        worst.add_column("Value", style="yellow", justify="right")
        for _, _, path_index, issue in rows[:20]:
            worst.add_row(
                str(issue.get("type", "")),
                str(path_index),
                str(issue.get("elem", "")),
                _fmt(issue.get("x", 0.0)),
                _fmt(issue.get("y", 0.0)),
                _fmt(issue.get("value", 0.0)),
            )
        console.print(worst)


@app.command()
@handle_com_errors
def query(
    file: str = typer.Argument(..., help="Path to the geometry query (.agq) file"),
) -> None:
    """Run a geometry query (.agq) on the active drawing."""
    require_platform()
    if not os.path.isfile(file):
        console.print(f"[red]Query file not found: {file}[/red]")
        raise typer.Exit(code=1)
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        drw = ac.get_active_drawing()
        if drw is None:
            console.print("[red]No active drawing[/red]")
            raise typer.Exit(code=1)

        count = drw.run_query(file)
        console.print(f"[green]OK:[/green] Query executed: {file}")
        console.print(f"      Matched: {count}")


@app.command()
@handle_com_errors
def save(
    path: str = typer.Argument(..., help="Output .amd file path"),
) -> None:
    """Save the active drawing to a file."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        drw = ac.get_active_drawing()
        if drw is None:
            console.print("[red]No active drawing[/red]")
            raise typer.Exit(code=1)

        drw.save_as(path)
        console.print(f"[green]OK:[/green] Saved to {path}")


@app.command()
@handle_com_errors
def open(
    path: str = typer.Argument(..., help="Path to .amd file"),
) -> None:
    """Open an existing drawing."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        drw = ac.open_drawing(path)
        if drw is None:
            console.print(f"[red]Failed to open: {path}[/red]")
            raise typer.Exit(code=1)

        drw.zoom_all()
        t = Table(title="Drawing Opened")
        t.add_column("Property", style="cyan")
        t.add_column("Value", style="green")
        t.add_row("Path", path)
        t.add_row("Geometries", str(drw.geometries_count))
        t.add_row("ToolPaths", str(drw.tool_paths_count))
        console.print(t)


@app.command("import")
@handle_com_errors
def import_file(
    path: str = typer.Argument(..., help="Path to CAD file (DXF/DWG, IGES, STEP, STL, VDA, CADL)"),
    fmt: str = typer.Option(
        "auto", "--fmt", "-f", help="dxf|dwg|iges|step|stl|vda|cadl (auto=from extension)"
    ),
    cabinets: bool = typer.Option(
        False, "--cabinets", help="Enable DXF cabinets input (DxfSpecial)"
    ),
) -> None:
    """Import a CAD file into the active drawing."""
    require_platform()
    fmt = _resolve_fmt(path, fmt)
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        if cabinets:
            ac.set_dxf_cabinets(True)
        drw = ac.open_cad_file(path, fmt)
        if drw is None:
            console.print(f"[red]Failed to import: {path}[/red]")
            raise typer.Exit(code=1)

        drw.zoom_all()
        t = Table(title="CAD File Imported")
        t.add_column("Property", style="cyan")
        t.add_column("Value", style="green")
        t.add_row("Path", path)
        t.add_row("Format", fmt.upper())
        t.add_row("Geometries", str(drw.geometries_count))
        t.add_row("ToolPaths", str(drw.tool_paths_count))
        console.print(t)


@app.command()
@handle_com_errors
def export(
    path: str = typer.Argument(..., help="Output CAD file path (DXF, IGES, STL, EMF, WMF)"),
    fmt: str = typer.Option(
        "auto", "--fmt", "-f", help="dxf|iges|stl|emf|wmf (auto=from extension)"
    ),
) -> None:
    """Export the active drawing to a CAD/graphics file."""
    require_platform()
    fmt = _resolve_fmt(path, fmt)
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        drw = ac.get_active_drawing()
        if drw is None:
            console.print("[red]No active drawing[/red]")
            raise typer.Exit(code=1)

        drw.export(path, fmt)
        console.print(f"[green]OK:[/green] Exported to {path} ({fmt.upper()})")


@app.command()
@handle_com_errors
def info() -> None:
    """Show active drawing info."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        drw = ac.get_active_drawing()
        if drw is None:
            console.print("[yellow]No active drawing[/yellow]")
            raise typer.Exit(code=0)

        t = Table(title="Active Drawing")
        t.add_column("Property", style="cyan")
        t.add_column("Value", style="green")
        t.add_row("Geometries", str(drw.geometries_count))
        t.add_row("ToolPaths", str(drw.tool_paths_count))
        console.print(t)
