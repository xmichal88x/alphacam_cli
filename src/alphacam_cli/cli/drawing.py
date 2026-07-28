from __future__ import annotations

import typer
from rich.table import Table

from alphacam_cli.cli.common import _visible, console, require_platform
from alphacam_cli.com.manager import AlphacamConnectionError, alphacam_context
from alphacam_cli.core.application import Application

app = typer.Typer(help="Drawing operations")


@app.command()
def create(
    width: float = typer.Option(100, "--width", "-w", help="Rectangle width"),
    height: float = typer.Option(50, "--height", "-h", help="Rectangle height"),
    fillet: float = typer.Option(0, "--fillet", "-f", help="Corner fillet radius"),
    text: str = typer.Option("", "--text", "-t", help="Text to add"),
) -> None:
    """Create a new drawing with a rectangle and optional fillet and text."""
    try:
        require_platform()
        with alphacam_context(visible=_visible) as raw:
            ac = Application(raw)
            drw = ac.create_temp_drawing()
            if drw is None:
                console.print("[red]Failed to create drawing[/red]")
                raise typer.Exit(code=1)  # noqa: TRY301

            rect = drw.create_rectangle(0, 0, width, height)
            if fillet > 0:
                rect.fillet(fillet)

            if text:
                drw.create_text(text, 5, height / 2, 4)

            drw.zoom_all()

            t = Table(title="Drawing Created")
            t.add_column("Property", style="cyan")
            t.add_column("Value", style="green")
            t.add_row("Width", str(width))
            t.add_row("Height", str(height))
            if fillet:
                t.add_row("Fillet", str(fillet))
            t.add_row("Geometries", str(drw.geometries_count))
            console.print(t)

    except AlphacamConnectionError as e:
        console.print(f"[red]FAIL:[/red] {e}")
        raise typer.Exit(code=3) from e
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e


@app.command()
def save(
    path: str = typer.Argument(..., help="Output .amd file path"),
) -> None:
    """Save the active drawing to a file."""
    try:
        require_platform()
        with alphacam_context(visible=_visible) as raw:
            ac = Application(raw)
            drw = ac.get_active_drawing()
            if drw is None:
                console.print("[red]No active drawing[/red]")
                raise typer.Exit(code=1)  # noqa: TRY301

            drw.save_as(path)
            console.print(f"[green]OK:[/green] Saved to {path}")

    except AlphacamConnectionError as e:
        console.print(f"[red]FAIL:[/red] {e}")
        raise typer.Exit(code=3) from e
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e


@app.command()
def open(
    path: str = typer.Argument(..., help="Path to .amd file"),
) -> None:
    """Open an existing drawing."""
    try:
        require_platform()
        with alphacam_context(visible=_visible) as raw:
            ac = Application(raw)
            drw = ac.open_drawing(path)
            if drw is None:
                console.print(f"[red]Failed to open: {path}[/red]")
                raise typer.Exit(code=1)  # noqa: TRY301

            drw.zoom_all()
            t = Table(title="Drawing Opened")
            t.add_column("Property", style="cyan")
            t.add_column("Value", style="green")
            t.add_row("Path", path)
            t.add_row("Geometries", str(drw.geometries_count))
            t.add_row("ToolPaths", str(drw.tool_paths_count))
            console.print(t)

    except AlphacamConnectionError as e:
        console.print(f"[red]FAIL:[/red] {e}")
        raise typer.Exit(code=3) from e
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e


@app.command()
def info() -> None:
    """Show active drawing info."""
    try:
        require_platform()
        with alphacam_context(visible=_visible) as raw:
            ac = Application(raw)
            drw = ac.get_active_drawing()
            if drw is None:
                console.print("[yellow]No active drawing[/yellow]")
                raise typer.Exit(code=0)  # noqa: TRY301

            t = Table(title="Active Drawing")
            t.add_column("Property", style="cyan")
            t.add_column("Value", style="green")
            t.add_row("Geometries", str(drw.geometries_count))
            t.add_row("ToolPaths", str(drw.tool_paths_count))
            console.print(t)

    except AlphacamConnectionError as e:
        console.print(f"[red]FAIL:[/red] {e}")
        raise typer.Exit(code=3) from e
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
