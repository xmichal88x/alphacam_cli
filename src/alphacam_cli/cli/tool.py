from __future__ import annotations

import os

import typer
from rich.table import Table

from alphacam_cli.cli.common import _visible, console, require_platform
from alphacam_cli.com.manager import AlphacamConnectionError, alphacam_context
from alphacam_cli.core.application import Application

app = typer.Typer(help="Tool operations")


@app.command()
def list(
    pattern: str = typer.Option("*.amt", "--pattern", "-p", help="Tool file pattern"),
) -> None:
    """List available tools from the AlphaCAM tool library."""
    try:
        require_platform()
        with alphacam_context(visible=_visible) as raw:
            ac = Application(raw)
            files = ac.find_tool_files(pattern)

            if not files:
                console.print("[yellow]No tools found.[/yellow]")
                raise typer.Exit(code=0)  # noqa: TRY301

            t = Table(title=f"Tools ({len(files)} found)")
            t.add_column("#", style="dim")
            t.add_column("Name", style="cyan")
            t.add_column("Path", style="green")

            for i, f in enumerate(files, 1):
                t.add_row(str(i), os.path.basename(f), f)
            console.print(t)

    except AlphacamConnectionError as e:
        console.print(f"[red]FAIL:[/red] {e}")
        raise typer.Exit(code=3) from e
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e


@app.command()
def select(
    name: str = typer.Argument(..., help="Tool name (partial match)"),
) -> None:
    """Select a tool by name (partial match against library)."""
    try:
        require_platform()
        with alphacam_context(visible=_visible) as raw:
            ac = Application(raw)
            files = ac.find_tool_files()

            basename_lower = name.lower()
            exact = [f for f in files if os.path.basename(f).lower() == basename_lower]
            prefix = [
                f
                for f in files
                if f not in exact and os.path.basename(f).lower().startswith(basename_lower)
            ]
            substring = [
                f
                for f in files
                if f not in exact
                and f not in prefix
                and basename_lower in os.path.basename(f).lower()
            ]
            matched = exact or prefix or substring
            if not matched:
                console.print(f"[red]No tool matching '{name}'[/red]")
                raise typer.Exit(code=1)  # noqa: TRY301

            tool_path = matched[0]
            tool = ac.select_tool(tool_path)
            if tool is None:
                console.print(f"[red]Failed to select tool: {os.path.basename(tool_path)}[/red]")
                raise typer.Exit(code=1)  # noqa: TRY301

            t = Table(title="Tool Selected")
            t.add_column("Property", style="cyan")
            t.add_column("Value", style="green")
            t.add_row("Name", tool.name)
            t.add_row("Diameter", f"{tool.diameter:.2f}")
            t.add_row("Number", str(tool.number))
            t.add_row("Length", f"{tool.tool_length:.2f}")
            t.add_row("Type", str(tool.tool_type))
            console.print(t)

    except AlphacamConnectionError as e:
        console.print(f"[red]FAIL:[/red] {e}")
        raise typer.Exit(code=3) from e
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e


@app.command()
def current() -> None:
    """Show currently selected tool."""
    try:
        require_platform()
        with alphacam_context(visible=_visible) as raw:
            ac = Application(raw)
            tool = ac.get_current_tool()
            if tool is None:
                console.print("[yellow]No tool selected.[/yellow]")
                raise typer.Exit(code=0)  # noqa: TRY301

            t = Table(title="Current Tool")
            t.add_column("Property", style="cyan")
            t.add_column("Value", style="green")
            t.add_row("Name", tool.name)
            t.add_row("Diameter", f"{tool.diameter:.2f}")
            t.add_row("Number", str(tool.number))
            t.add_row("Length", f"{tool.tool_length:.2f}")
            console.print(t)

    except AlphacamConnectionError as e:
        console.print(f"[red]FAIL:[/red] {e}")
        raise typer.Exit(code=3) from e
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
