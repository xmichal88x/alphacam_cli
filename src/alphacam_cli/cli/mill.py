from __future__ import annotations

import typer

from alphacam_cli.cli.common import _visible, console, require_platform
from alphacam_cli.com.constants import (
    ACAM_DRILL,
    ACAM_PECK,
    ACAM_POCKET_CONTOUR,
    ACAM_TAP,
    ACAM_TOOL_INSIDE,
    ACAM_TOOL_OUTSIDE,
)
from alphacam_cli.com.manager import AlphacamConnectionError, alphacam_context
from alphacam_cli.core.application import Application

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


@app.command()
def rough(
    depth: float = typer.Option(-10, "--depth", "-d", help="Final depth (negative)"),
    spindle: int = typer.Option(12000, "--spindle", "-s", help="Spindle speed RPM"),
    feed: int = typer.Option(3000, "--feed", "-f", help="Cut feed rate"),
    down_feed: int = typer.Option(2000, "--down-feed", help="Plunge feed rate"),
    rapid: float = typer.Option(10, "--rapid", "-r", help="Safe rapid level"),
    stock: float = typer.Option(0.5, "--stock", help="Stock allowance"),
    width_of_cut: float = typer.Option(5, "--width-of-cut", "-w", help="Width of cut"),
    max_depth_per_cut: float = typer.Option(2.5, "--max-depth", "-m", help="Max depth per pass"),
    material_top: float = typer.Option(0, "--material-top", help="Material top Z"),
    tool_side: str = typer.Option("outside", "--side", help="Tool side: outside/inside"),
) -> None:
    """Rough/finish machining on selected geometries."""
    try:
        _validate_depth(depth)
        _validate_speed(spindle)
        _validate_feed(float(feed))
        _validate_feed(float(down_feed))

        require_platform()
        with alphacam_context(visible=_visible) as raw:
            ac = Application(raw)
            drw = ac.get_active_drawing()
            if drw is None:
                console.print("[red]No active drawing[/red]")
                raise typer.Exit(code=1)  # noqa: TRY301

            geo_count = drw.geometries_count
            if geo_count == 0:
                console.print("[yellow]No geometries to machine[/yellow]")
                raise typer.Exit(code=0)  # noqa: TRY301

            side = ACAM_TOOL_OUTSIDE if tool_side == "outside" else ACAM_TOOL_INSIDE
            for geo in drw.geometries():
                geo.tool_in_out = side
                geo.selected = True

            md = ac.create_mill_data()
            md.safe_rapid_level = rapid
            md.rapid_down_to = 2
            md.material_top = material_top
            md.final_depth = depth
            md.spindle_speed = spindle
            md.down_feed = float(down_feed)
            md.cut_feed = float(feed)
            md.max_depth_per_cut = max_depth_per_cut
            md.width_of_cut = width_of_cut
            md.stock = stock

            # Fallback chain: RoughFinish -> process type 2
            console.print("[yellow]Executing RoughFinish...[/yellow]")
            try:
                md.rough_finish()
            except Exception:
                console.print("[yellow]RoughFinish failed, trying fallback...[/yellow]")
                md.process_type = 2
                md.rough_finish()

            drw.zoom_all()
            console.print(f"[green]OK:[/green] ToolPaths: {drw.tool_paths_count}")

    except AlphacamConnectionError as e:
        console.print(f"[red]FAIL:[/red] {e}")
        raise typer.Exit(code=3) from e
    except Exception as e:
        console.print(f"[red]Machining error:[/red] {e}")
        raise typer.Exit(code=1) from e


@app.command()
def pocket(
    depth: float = typer.Option(-8, "--depth", "-d", help="Final depth"),
    width_of_cut: float = typer.Option(7.5, "--width-of-cut", "-w", help="Width of cut"),
    spindle: int = typer.Option(12000, "--spindle", "-s", help="Spindle speed RPM"),
    feed: int = typer.Option(3000, "--feed", "-f", help="Cut feed"),
) -> None:
    """Pocket machining on selected geometries."""
    try:
        _validate_depth(depth)
        _validate_speed(spindle)
        _validate_feed(float(feed))

        require_platform()
        with alphacam_context(visible=_visible) as raw:
            ac = Application(raw)
            drw = ac.get_active_drawing()
            if drw is None:
                console.print("[red]No active drawing[/red]")
                raise typer.Exit(code=1)  # noqa: TRY301

            drw.select_all_geometries()

            md = ac.create_mill_data()
            md.pocket_type = ACAM_POCKET_CONTOUR
            md.safe_rapid_level = 20
            md.rapid_down_to = 2
            md.final_depth = depth
            md.spindle_speed = spindle
            md.cut_feed = float(feed)
            md.width_of_cut = width_of_cut
            md.stock = 1

            console.print("[yellow]Executing Pocket...[/yellow]")
            md.pocket()
            drw.zoom_all()
            console.print("[green]OK:[/green] Pocket done")

    except AlphacamConnectionError as e:
        console.print(f"[red]FAIL:[/red] {e}")
        raise typer.Exit(code=3) from e
    except Exception as e:
        console.print(f"[red]Machining error:[/red] {e}")
        raise typer.Exit(code=1) from e


@app.command()
def drill(
    depth: float = typer.Option(-15, "--depth", "-d", help="Bottom of hole"),
    drill_type: str = typer.Option("drill", "--type", "-t", help="drill/tap/peck"),
    spindle: int = typer.Option(12000, "--spindle", "-s", help="Spindle speed RPM"),
) -> None:
    """Drill/tap on selected circle geometries."""
    try:
        _validate_depth(depth)
        _validate_speed(spindle)

        drill_map = {"drill": ACAM_DRILL, "tap": ACAM_TAP, "peck": ACAM_PECK}
        d_type = drill_map.get(drill_type)
        if d_type is None:
            console.print(f"[red]Invalid drill type: {drill_type}. Use drill/tap/peck[/red]")
            raise typer.Exit(code=2)  # noqa: TRY301

        require_platform()
        with alphacam_context(visible=_visible) as raw:
            ac = Application(raw)
            drw = ac.get_active_drawing()
            if drw is None:
                console.print("[red]No active drawing[/red]")
                raise typer.Exit(code=1)  # noqa: TRY301

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

    except AlphacamConnectionError as e:
        console.print(f"[red]FAIL:[/red] {e}")
        raise typer.Exit(code=3) from e
    except Exception as e:
        console.print(f"[red]Machining error:[/red] {e}")
        raise typer.Exit(code=1) from e
