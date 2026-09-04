from __future__ import annotations

import typer

from alphacam_cli.cli.common import (
    console,
    get_visible,
    handle_com_errors,
    require_platform,
    resolve_app,
)
from alphacam_cli.com.manager import alphacam_context

app = typer.Typer(help="Auto-style and VBA macro operations")


@app.command()
@handle_com_errors
def apply(
    file: str = typer.Argument(..., help="Path to the auto-style file"),
) -> None:
    """Apply an auto-style file to the active drawing (no dialogs)."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.auto_style_apply(file)
        applied = str(result.get("file", file))
        console.print(f"[green]OK:[/green] Auto-style applied: {applied}")


@app.command("open")
@handle_com_errors
def open_vba_project(
    file: str = typer.Argument(..., help="Path to the VBA project file (.arb)"),
) -> None:
    """Open a VBA project for editing (shows VBA IDE)."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.open_vba_project(file)
        opened = str(result.get("file", file))
        console.print(f"[green]OK:[/green] VBA project opened: {opened}")
