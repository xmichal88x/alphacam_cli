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
    material: str | None = typer.Option(
        None, "--material", help="Material name (AM_Materials) for the job; default from database"
    ),
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
            material=material,
        )
        console.print(f"[green]OK:[/green] CDM job created: {result['job_name']}")
        console.print(f"     Door type: {result['type_name']}")
        console.print(
            f"     Size: {result['width']}x{result['length']}, quantity: {result['quantity']}"
        )
        if result.get("material"):
            console.print(f"     Material: {result['material']}")
        if result.get("material_error"):
            console.print(f"[yellow]WARNING:[/yellow] {result['material_error']}")


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


@app.command("import")
@handle_com_errors
def import_csv(
    csv: str = typer.Argument(..., help="CSV file path (Windows path on the server)"),
    name: str | None = typer.Option(
        None, "--name", help="Job name for a new CDM job (default: CSV basename)"
    ),
    config: str | None = typer.Option(
        None, "--config", help="Configuration name for a new CDM job (default: from database)"
    ),
    job: str | None = typer.Option(None, "--job", help="Import into an existing CDM job by name"),
    separator: str = typer.Option(",", "--separator", help="CSV separator character"),
    header: bool = typer.Option(False, "--header", help="CSV has a header row"),
    material: str | None = typer.Option(
        None, "--material", help="Material name (AM_Materials) for the job; overrides CSV column 6"
    ),
) -> None:
    """Import a CSV door order into a single CDM job (headless, no dialogs)."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.import_cdm_csv(
            csv=csv,
            job=job,
            name=name,
            config=config,
            separator=separator,
            has_header=header,
            material=material,
        )
        if not result.get("success"):
            for err in result.get("errors", []):
                console.print(f"[red]ERROR:[/red] {err}")
            raise typer.Exit(code=1)
        verb = "updated" if job else "created"
        console.print(
            f"[green]OK:[/green] CDM job {verb}: {result['job_name']} ({result['items']} item(s))"
        )
        console.print(f"     Imported: {csv}")
        if result.get("material"):
            console.print(f"     Material: {result['material']}")
        for err in result.get("errors", []):
            console.print(f"[yellow]WARNING:[/yellow] {err}")


@app.command("delete")
@handle_com_errors
def delete_job(
    job_name: str = typer.Argument(..., help="CDM job name"),
) -> None:
    """Delete a CDM job from the database (headless, no dialogs)."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.delete_cdm_job(job_name=job_name)
        console.print(f"[green]OK:[/green] CDM job deleted: {result['job_name']}")
