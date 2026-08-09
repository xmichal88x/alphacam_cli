from __future__ import annotations

from typing import Any

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
    separator: str | None = typer.Option(
        None, "--separator", help="CSV separator character (default: from import settings or ,)"
    ),
    header: bool = typer.Option(False, "--header", help="CSV has a header row"),
    material: str | None = typer.Option(
        None, "--material", help="Material name (AM_Materials) for the job; overrides CSV column 6"
    ),
    import_setting: str | None = typer.Option(
        None,
        "--import-setting",
        help="Import setting id or name from the database (defines column map, separator)",
    ),
    preview: bool = typer.Option(False, "--preview", help="Dry run preview without creating a job"),
) -> None:
    """Import a CSV door order into a single CDM job (headless, no dialogs)."""
    require_platform()
    import_setting_key: str | int | None = (
        int(import_setting)
        if import_setting is not None and import_setting.isdigit()
        else import_setting
    )
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        if preview:
            result = ac.import_cdm_preview(
                csv=csv,
                import_setting=import_setting_key,
                separator=separator,
                has_header=header,
                job=job,
                name=name,
                config=config,
                material=material,
            )
            _print_import_preview(result)
            return
        result = ac.import_cdm_csv(
            csv=csv,
            job=job,
            name=name,
            config=config,
            separator=separator,
            has_header=header,
            material=material,
            import_setting=import_setting_key,
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


import_settings_app = typer.Typer(help="CDM import settings")


@import_settings_app.command("list")
@handle_com_errors
def import_settings_list() -> None:
    """List CDM import settings from the database."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.cdm_import_settings()
        settings = result.get("settings", [])
        if not settings:
            console.print("[yellow]No CDM import settings found[/yellow]")
            return
        t = Table(title="CDM Import Settings")
        t.add_column("ID", style="cyan")
        t.add_column("Name", style="green")
        t.add_column("Selected")
        t.add_column("CreateJob")
        t.add_column("Delimiter")
        t.add_column("Kolumny")
        t.add_column("Count", justify="right")
        for setting in settings:
            t.add_row(
                str(setting.get("id", "")),
                str(setting.get("name", "")),
                "Yes" if setting.get("selected") else "No",
                "Yes" if setting.get("create_job") else "No",
                str(setting.get("delimiter_char", "") or ""),
                str(setting.get("fields", "") or ""),
                str(setting.get("fields_count", 0)),
            )
        console.print(t)


app.add_typer(import_settings_app, name="import-settings")


def _print_import_preview(result: dict[str, Any]) -> None:
    console.print("[cyan]PREVIEW (dry run, no changes)[/cyan]")
    setting = result.get("setting")
    if setting:
        console.print(
            f"Import settings: {setting.get('name')} "
            f"(id={setting.get('id')}, delimiter={setting.get('delimiter_char') or ''}, "
            f"create_job={setting.get('create_job') or False})"
        )
    field_map = result.get("field_map", [])
    if field_map:
        t = Table(title="Field mapping")
        t.add_column("Kol", style="cyan")
        t.add_column("Pole", style="green")
        t.add_column("Wymagane", style="yellow")
        for mapping in field_map:
            t.add_row(
                str(mapping.get("column", "")),
                str(mapping.get("field", "")),
                "Yes" if mapping.get("required") else "No",
            )
        console.print(t)
    console.print(f"Job: {result.get('job_name', '')}")
    console.print(f"Config: {result.get('config') or '-'}")
    console.print(f"Material: {result.get('material') or '-'}")
    console.print(f"Items: {result.get('items', 0)}")
    rows = result.get("rows", [])
    if rows:
        t = Table(title="Rows")
        t.add_column("Row", style="cyan")
        t.add_column("Style", style="green")
        t.add_column("Qty", justify="right")
        t.add_column("W x L", justify="right")
        t.add_column("Material")
        t.add_column("Klient")
        t.add_column("Nr zamowienia")
        t.add_column("Komentarz")
        t.add_column("Custom")
        t.add_column("JobName")
        for row in rows:
            custom = "; ".join(
                f"{key}={value}" for key, value in sorted((row.get("custom_fields") or {}).items())
            )
            job_ref = (
                row.get("job_name") or row.get("job_config_id") or row.get("job_material_id") or ""
            )
            t.add_row(
                str(row.get("row", "")),
                str(row.get("style", "") or ""),
                str(row.get("quantity", "") or ""),
                f"{row.get('width', '') or ''} x {row.get('length', '') or ''}",
                str(row.get("material", "") or ""),
                str(row.get("customer_name", "") or ""),
                str(row.get("order_number", "") or ""),
                str(row.get("production_comment", "") or ""),
                custom,
                str(job_ref),
            )
        console.print(t)
    for err in result.get("errors", []):
        console.print(f"[yellow]WARNING:[/yellow] {err}")
    if not result.get("success"):
        console.print("[red]ERROR:[/red] Preview failed")
        raise typer.Exit(code=1)
    if result.get("items", 0) == 0:
        console.print("[red]ERROR:[/red] No items to import")
        raise typer.Exit(code=1)
