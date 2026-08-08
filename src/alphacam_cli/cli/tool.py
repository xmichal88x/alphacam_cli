from __future__ import annotations

import typer
from rich.table import Table

from alphacam_cli.cli.common import (
    console,
    get_visible,
    handle_com_errors,
    path_basename,
    require_platform,
    resolve_app,
)
from alphacam_cli.com.manager import alphacam_context

app = typer.Typer(help="Tool operations")


@app.command()
@handle_com_errors
def list(
    pattern: str = typer.Option("*.amt", "--pattern", "-p", help="Tool file pattern"),
) -> None:
    """List available tools from the AlphaCAM tool library."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        files = ac.find_tool_files(pattern)

        if not files:
            console.print("[yellow]No tools found.[/yellow]")
            raise typer.Exit(code=0)

        t = Table(title=f"Tools ({len(files)} found)")
        t.add_column("#", style="dim")
        t.add_column("Name", style="cyan")
        t.add_column("Path", style="green")

        for i, f in enumerate(files, 1):
            t.add_row(str(i), path_basename(f), f)
        console.print(t)


@app.command()
@handle_com_errors
def select(
    name: str = typer.Argument(..., help="Tool name (partial match)"),
) -> None:
    """Select a tool by name (partial match against library)."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        files = ac.find_tool_files()

        basename_lower = name.lower()
        exact = [f for f in files if path_basename(f).lower() == basename_lower]
        prefix = [
            f
            for f in files
            if f not in exact and path_basename(f).lower().startswith(basename_lower)
        ]
        substring = [
            f
            for f in files
            if f not in exact and f not in prefix and basename_lower in path_basename(f).lower()
        ]
        matched = exact or prefix or substring
        if not matched:
            console.print(f"[red]No tool matching '{name}'[/red]")
            raise typer.Exit(code=1)

        if len(matched) > 1:
            console.print("[yellow]Multiple tools matched:[/yellow]")
            for m in matched:
                console.print(f"  {path_basename(m)}")
            console.print("[yellow]Please use a more specific name[/yellow]")
            raise typer.Exit(code=1)

        tool_path = matched[0]
        tool = ac.select_tool(tool_path)
        if tool is None:
            console.print(f"[red]Failed to select tool: {path_basename(tool_path)}[/red]")
            raise typer.Exit(code=1)

        t = Table(title="Tool Selected")
        t.add_column("Property", style="cyan")
        t.add_column("Value", style="green")
        t.add_row("Name", tool.name)
        t.add_row("Diameter", f"{tool.diameter:.2f}")
        t.add_row("Number", str(tool.number))
        t.add_row("Length", f"{tool.tool_length:.2f}")
        t.add_row("Type", str(tool.tool_type))
        console.print(t)


@app.command()
@handle_com_errors
def current() -> None:
    """Show currently selected tool."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        tool = ac.get_current_tool()
        if tool is None:
            console.print("[yellow]No tool selected.[/yellow]")
            raise typer.Exit(code=0)

        t = Table(title="Current Tool")
        t.add_column("Property", style="cyan")
        t.add_column("Value", style="green")
        t.add_row("Name", tool.name)
        t.add_row("Diameter", f"{tool.diameter:.2f}")
        t.add_row("Number", str(tool.number))
        t.add_row("Length", f"{tool.tool_length:.2f}")
        console.print(t)
