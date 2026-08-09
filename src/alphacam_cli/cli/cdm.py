from __future__ import annotations

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

app = typer.Typer(help="Cabinet Door Manufacturing (CDM Automation Manager add-in)")


@app.command()
@handle_com_errors
def create(
    job_name: str = typer.Argument(..., help="CDM job name"),
    type_name: str = typer.Argument(..., help="Door type name (e.g. 'Typ Frontu 1')"),
    width: float = typer.Option(400, "--width", "-w", help="Door width (mm)"),
    length: float = typer.Option(300, "--length", "-l", help="Door length (mm)"),
    quantity: int = typer.Option(1, "--quantity", "-q", help="Door quantity"),
    bypass_nest: bool = typer.Option(False, "--bypass-nest", help="Bypass nesting"),
    process: bool = typer.Option(False, "--process", help="Request processing (requires GUI)"),
) -> None:
    """Create a CDM job with a single order detail (headless, no dialogs)."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.run_cdm(
            job_name=job_name,
            type_name=type_name,
            width=width,
            length=length,
            quantity=quantity,
            bypass_nest=bypass_nest,
        )
        console.print(f"[green]OK:[/green] CDM job created: {result['job_name']}")
        console.print(f"     Door type: {result['type_name']}")
        console.print(
            f"     Size: {result['width']}x{result['length']}, quantity: {result['quantity']}"
        )
        if process:
            console.print(
                "[yellow]cdm: Process() wymaga GUI (Session 2) — job zapisany w bazie[/yellow]"
            )


@app.command("types")
@handle_com_errors
def list_types() -> None:
    """List CDM door types seen in existing jobs."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.cdm_types()
        types = result.get("types", [])
        if not types:
            console.print("[yellow]No CDM door types found[/yellow]")
            note = result.get("note")
            if note:
                console.print(f"[dim]{note}[/dim]")
            return
        t = Table(title="CDM Door Types")
        t.add_column("ID", style="cyan")
        t.add_column("Name", style="green")
        for item in types:
            t.add_row(str(item["id"]), str(item["name"]))
        console.print(t)
        note = result.get("note")
        if note:
            console.print(f"[dim]{note}[/dim]")


@app.command("jobs")
@handle_com_errors
def list_jobs() -> None:
    """List existing CDM jobs."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.cdm_jobs()
        jobs = result.get("jobs", [])
        if not jobs:
            console.print("[yellow]No CDM jobs found[/yellow]")
            return
        t = Table(title="CDM Jobs")
        t.add_column("ID", style="cyan")
        t.add_column("Name", style="green")
        for item in jobs:
            t.add_row(str(item["id"]), str(item["name"]))
        console.print(t)
