from __future__ import annotations

from typing import Any

import typer

from alphacam_cli.cli.common import (
    console,
    get_visible,
    handle_com_errors,
    path_basename,
    require_platform,
    resolve_app,
)
from alphacam_cli.com.constants import (
    ACAM_DRILL,
    ACAM_PECK,
    ACAM_POCKET_CONTOUR,
    ACAM_TAP,
    ACAM_TOOL_INSIDE,
    ACAM_TOOL_OUTSIDE,
)
from alphacam_cli.com.manager import alphacam_context
from alphacam_cli.core.logger import logger

app = typer.Typer(help="Milling operations")


def _validate_depth(depth: float) -> None:
    if depth >= 0:
        console.print(f"[red]Depth must be negative (got: {depth})[/red]")
        raise typer.Exit(code=2)


def _validate_speed(rpm: int) -> None:
    if rpm < 0 or rpm > 100000:
        console.print(f"[red]Spindle speed out of range: {rpm} (0-100000)[/red]")
        raise typer.Exit(code=2)


def _validate_feed(feed: float) -> None:
    if feed < 0:
        console.print(f"[red]Feed cannot be negative: {feed}[/red]")
        raise typer.Exit(code=2)


def _select_tool_by_name(ac: Any, name: str) -> None:
    files = ac.find_tool_files()
    name_norm = name.replace("\\", "/").lower()
    basename_lower = name.lower()
    exact_path = [f for f in files if f.replace("\\", "/").lower() == name_norm]
    exact = [f for f in files if f not in exact_path and path_basename(f).lower() == basename_lower]
    path_substring = []
    if "/" in name or "\\" in name:
        path_substring = [
            f
            for f in files
            if f not in exact_path and f not in exact and name_norm in f.replace("\\", "/").lower()
        ]
    prefix = [
        f
        for f in files
        if f not in exact_path
        and f not in exact
        and f not in path_substring
        and path_basename(f).lower().startswith(basename_lower)
    ]
    substring = [
        f
        for f in files
        if f not in exact_path
        and f not in exact
        and f not in path_substring
        and f not in prefix
        and basename_lower in path_basename(f).lower()
    ]
    matched = exact_path or exact or path_substring or prefix or substring
    if not matched:
        console.print(f"[red]No tool matching '{name}'[/red]")
        raise typer.Exit(code=1)
    if len(matched) > 1:
        console.print("[yellow]Multiple tools matched:[/yellow]")
        for m in matched:
            console.print(f"  {path_basename(m)}")
        console.print("[yellow]Please use a more specific name[/yellow]")
        raise typer.Exit(code=1)
    if ac.select_tool(matched[0]) is None:
        console.print(f"[red]Failed to select tool: {path_basename(matched[0])}[/red]")
        raise typer.Exit(code=1)


@app.command()
@handle_com_errors
def rough(
    depth: float = typer.Option(-10, "--depth", "-d", help="Final depth (negative)"),
    spindle: int = typer.Option(12000, "--spindle", "-s", help="Spindle speed RPM"),
    feed: float = typer.Option(3000, "--feed", "-f", help="Cut feed rate"),
    down_feed: float = typer.Option(2000, "--down-feed", help="Plunge feed rate"),
    rapid: float = typer.Option(10, "--rapid", "-r", help="Safe rapid level"),
    stock: float = typer.Option(0.5, "--stock", help="Stock allowance"),
    width_of_cut: float = typer.Option(5, "--width-of-cut", "-w", help="Width of cut"),
    max_depth_per_cut: float = typer.Option(2.5, "--max-depth", "-m", help="Max depth per pass"),
    material_top: float = typer.Option(0, "--material-top", help="Material top Z"),
    tool_side: str = typer.Option("outside", "--side", help="Tool side: outside/inside"),
    start_x: float = typer.Option(0.0, "--start-x", help="Start point X (direction)"),
    start_y: float = typer.Option(0.0, "--start-y", help="Start point Y (direction)"),
) -> None:
    """Rough/finish machining on selected geometries."""
    _validate_depth(depth)
    _validate_speed(spindle)
    _validate_feed(feed)
    _validate_feed(down_feed)
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        drw = ac.get_active_drawing()
        if drw is None:
            console.print("[red]No active drawing[/red]")
            raise typer.Exit(code=1)

        geo_count = drw.geometries_count
        if geo_count == 0:
            console.print("[yellow]No geometries to machine[/yellow]")
            raise typer.Exit(code=0)

        tool_side_lower = tool_side.lower()
        if tool_side_lower not in ("outside", "inside"):
            console.print(f"[red]Invalid tool side: '{tool_side}'. Use 'outside' or 'inside'[/red]")
            raise typer.Exit(code=2)
        side = ACAM_TOOL_OUTSIDE if tool_side_lower == "outside" else ACAM_TOOL_INSIDE
        for geo in drw.geometries():
            geo.tool_in_out = side
            geo.selected = True
            geo.set_start_point(start_x, start_y)

        md = ac.create_mill_data()
        md.safe_rapid_level = rapid
        md.rapid_down_to = 2
        md.material_top = material_top
        md.final_depth = depth
        md.spindle_speed = spindle
        md.down_feed = down_feed
        md.cut_feed = feed
        md.max_depth_per_cut = max_depth_per_cut
        md.width_of_cut = width_of_cut
        md.stock = stock
        md.xy_corners = 1
        md.start_x = start_x
        md.start_y = start_y

        # Fallback chain: RoughFinish -> process type 2
        console.print("[yellow]Executing RoughFinish...[/yellow]")
        try:
            md.rough_finish()
        except Exception:
            logger.warning("RoughFinish failed, trying fallback with process_type=2", exc_info=True)
            md.process_type = 2
            md.rough_finish()

        drw.zoom_all()
        console.print(f"[green]OK:[/green] ToolPaths: {drw.tool_paths_count}")


@app.command()
@handle_com_errors
def pocket(
    depth: float = typer.Option(-8, "--depth", "-d", help="Final depth"),
    width_of_cut: float = typer.Option(7.5, "--width-of-cut", "-w", help="Width of cut"),
    spindle: int = typer.Option(12000, "--spindle", "-s", help="Spindle speed RPM"),
    feed: float = typer.Option(3000, "--feed", "-f", help="Cut feed"),
) -> None:
    """Pocket machining on selected geometries."""
    _validate_depth(depth)
    _validate_speed(spindle)
    _validate_feed(feed)
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        drw = ac.get_active_drawing()
        if drw is None:
            console.print("[red]No active drawing[/red]")
            raise typer.Exit(code=1)

        drw.select_all_geometries()

        md = ac.create_mill_data()
        md.pocket_type = ACAM_POCKET_CONTOUR
        md.safe_rapid_level = 20
        md.rapid_down_to = 2
        md.final_depth = depth
        md.spindle_speed = spindle
        md.cut_feed = feed
        md.width_of_cut = width_of_cut
        md.stock = 1

        console.print("[yellow]Executing Pocket...[/yellow]")
        md.pocket()
        drw.zoom_all()
        console.print("[green]OK:[/green] Pocket done")


@app.command()
@handle_com_errors
def drill(
    depth: float = typer.Option(-15, "--depth", "-d", help="Bottom of hole"),
    drill_type: str = typer.Option("drill", "--type", "-t", help="drill/tap/peck"),
    spindle: int = typer.Option(12000, "--spindle", "-s", help="Spindle speed RPM"),
) -> None:
    """Drill/tap on selected circle geometries."""
    _validate_depth(depth)
    _validate_speed(spindle)

    drill_map = {"drill": ACAM_DRILL, "tap": ACAM_TAP, "peck": ACAM_PECK}
    d_type = drill_map.get(drill_type)
    if d_type is None:
        console.print(f"[red]Invalid drill type: {drill_type}. Use drill/tap/peck[/red]")
        raise typer.Exit(code=2)

    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        drw = ac.get_active_drawing()
        if drw is None:
            console.print("[red]No active drawing[/red]")
            raise typer.Exit(code=1)

        drw.select_all_geometries()

        md = ac.create_mill_data()
        md.drill_type = d_type
        md.safe_rapid_level = 20
        md.rapid_down_to = 2
        md.bottom_of_hole = depth
        md.spindle_speed = spindle

        console.print(f"[yellow]Executing Drill ({drill_type})...[/yellow]")
        md.drill_tap()
        drw.zoom_all()
        console.print("[green]OK:[/green] Drill done")


@app.command()
@handle_com_errors
def saw(
    depth: float = typer.Option(..., "--depth", "-d", help="Final depth (negative)"),
    spindle: int = typer.Option(12000, "--spindle", "-s", help="Spindle speed RPM"),
    feed: float = typer.Option(3000, "--feed", "-f", help="Cut feed rate"),
    down_feed: float = typer.Option(2000, "--down-feed", help="Plunge feed rate"),
    saw_angle: float = typer.Option(0, "--saw-angle", help="Saw angle (degrees)"),
    internal_corners: int = typer.Option(
        1, "--internal-corners", help="Internal corners mode (1=CUT_ON)"
    ),
    external_corners: int = typer.Option(
        1, "--external-corners", help="External corners mode (1=CUT_ON)"
    ),
    head_position: int = typer.Option(
        0, "--head-position", help="Saw head position (0=LEFT, 1=RIGHT)"
    ),
    tool: str | None = typer.Option(None, "--tool", help="Tool name or path (optional)"),
) -> None:
    """Saw cut on selected geometries."""
    _validate_depth(depth)
    _validate_speed(spindle)
    _validate_feed(feed)
    _validate_feed(down_feed)
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        drw = ac.get_active_drawing()
        if drw is None:
            console.print("[red]No active drawing[/red]")
            raise typer.Exit(code=1)

        if drw.geometries_count == 0:
            console.print("[yellow]No geometries to machine[/yellow]")
            raise typer.Exit(code=0)

        if tool:
            _select_tool_by_name(ac, tool)

        drw.select_all_geometries()

        md = ac.create_mill_data()
        md.safe_rapid_level = 20
        md.rapid_down_to = 2
        md.final_depth = depth
        md.spindle_speed = spindle
        md.down_feed = down_feed
        md.cut_feed = feed
        md.saw_angle = saw_angle
        md.saw_internal_corners = internal_corners
        md.saw_external_corners = external_corners
        md.saw_head_position = head_position

        console.print("[yellow]Executing Saw...[/yellow]")
        md.saw()
        drw.zoom_all()
        console.print(f"[green]OK:[/green] Saw done ({drw.tool_paths_count} tool paths)")


@app.command()
@handle_com_errors
def engrave(
    depth: float = typer.Option(..., "--depth", "-d", help="Engraving depth (negative)"),
    spindle: int = typer.Option(12000, "--spindle", "-s", help="Spindle speed RPM"),
    feed: float = typer.Option(3000, "--feed", "-f", help="Cut feed rate"),
    down_feed: float = typer.Option(2000, "--down-feed", help="Plunge feed rate"),
    engrave_type: int = typer.Option(
        0,
        "--engrave-type",
        help="Engrave type (0=GEOMETRIES, 1=GUIDE_LINES_APPROX, 2=GUIDE_LINES_EXACT)",
    ),
    step_length: float = typer.Option(0.1, "--step-length", help="Step length"),
    tool: str | None = typer.Option(None, "--tool", help="Tool name or path (optional)"),
) -> None:
    """Engrave on selected geometries."""
    _validate_depth(depth)
    _validate_speed(spindle)
    _validate_feed(feed)
    _validate_feed(down_feed)
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        drw = ac.get_active_drawing()
        if drw is None:
            console.print("[red]No active drawing[/red]")
            raise typer.Exit(code=1)

        if drw.geometries_count == 0:
            console.print("[yellow]No geometries to machine[/yellow]")
            raise typer.Exit(code=0)

        if tool:
            _select_tool_by_name(ac, tool)

        drw.select_all_geometries()

        md = ac.create_mill_data()
        md.safe_rapid_level = 20
        md.rapid_down_to = 2
        md.final_depth = depth
        md.spindle_speed = spindle
        md.down_feed = down_feed
        md.cut_feed = feed
        md.engrave_type = engrave_type
        md.step_length = step_length

        console.print("[yellow]Executing Engrave...[/yellow]")
        md.engrave()
        drw.zoom_all()
        console.print(f"[green]OK:[/green] Engrave done ({drw.tool_paths_count} tool paths)")


@app.command()
@handle_com_errors
def style(
    style_path: str = typer.Argument(..., help="Path to .ary machining style"),
) -> None:
    """Apply a .ary machining style to the active drawing (production pattern)."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        drw = ac.get_active_drawing()
        if drw is None:
            console.print("[red]No active drawing[/red]")
            raise typer.Exit(code=1)
        if drw.geometries_count == 0:
            console.print("[yellow]No geometries to machine[/yellow]")
            raise typer.Exit(code=0)
        if not style_path.lower().endswith(".ary"):
            console.print("[red]Style must be a .ary file[/red]")
            raise typer.Exit(code=2)
        ac.apply_mill_style(style_path)
        drw.zoom_all()
        fresh = ac.get_active_drawing()
        if fresh is not None:
            drw = fresh
        console.print(f"[green]OK:[/green] ToolPaths: {drw.tool_paths_count}")
