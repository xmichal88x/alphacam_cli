from __future__ import annotations

import os

import typer

from alphacam_cli.cli.common import console, get_visible, handle_com_errors, require_platform
from alphacam_cli.com.manager import alphacam_context
from alphacam_cli.core.application import Application

app = typer.Typer(help="NC output operations")


@app.command()
@handle_com_errors
def output(
    path: str = typer.Argument(..., help="Output .nc file path"),
    post: str = typer.Option("", "--post", "-p", help="Post-processor to select"),
) -> None:
    """Generate NC code from active drawing."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = Application(raw)
        if post:
            ac.select_post(post)
            console.print(f"[green]Post selected: {post}[/green]")

        drw = ac.get_active_drawing()
        if drw is None:
            console.print("[red]No active drawing[/red]")
            raise typer.Exit(code=1)

        drw.output_nc(path)

        if os.path.exists(path):
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            console.print("[green]OK:[/green] NC output generated")
            console.print(f"     Path: {path}")
            console.print(f"     Lines: {len(lines)}")
            for line in lines[:5]:
                console.print(f"     {line.rstrip()}")
        else:
            console.print(f"[red]NC file not created: {path}[/red]")
            raise typer.Exit(code=1)
