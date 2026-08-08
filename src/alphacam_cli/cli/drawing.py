from __future__ import annotations

import os

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

app = typer.Typer(help="Drawing operations")


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
