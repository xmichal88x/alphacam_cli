from __future__ import annotations

from typing import Any

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
        t.add_column("Pola")
        t.add_column("Liczba pól", justify="right")
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
    if result.get("job"):
        console.print("[dim](job existence not verified - dry run)[/dim]")
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


def _yes_no(value: Any) -> str:
    return "Yes" if value else "No"


def _basename(value: Any) -> str:
    return path_basename(str(value or ""))


def _config_value(value: Any) -> str:
    if isinstance(value, bool):
        return _yes_no(value)
    if value is None or str(value) == "":
        return "-"
    return str(value)


def _print_config_section(title: str, pairs: list[tuple[str, Any]]) -> None:
    t = Table(title=title)
    t.add_column("Pole", style="green")
    t.add_column("Wartość")
    for field, value in pairs:
        t.add_row(field, _config_value(value))
    console.print(t)


order_details_app = typer.Typer(help="CDM order details")


@order_details_app.command("list")
@handle_com_errors
def order_details_list(
    job_name: str = typer.Argument(..., help="CDM job name"),
) -> None:
    """List CDM order details for a job."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.cdm_order_details(job_name=job_name)
        rows = result.get("order_details", [])
        if not rows:
            console.print(f"[yellow]No CDM order details found for job {job_name}[/yellow]")
            return
        t = Table(title=f"CDM Order Details: {job_name}")
        t.add_column("No", style="cyan", justify="right")
        t.add_column("Style", style="green")
        t.add_column("Qty", justify="right")
        t.add_column("W x L", justify="right")
        t.add_column("Material")
        t.add_column("Klient")
        t.add_column("Nr zam")
        t.add_column("Item")
        t.add_column("Komentarz")
        t.add_column("Custom")
        t.add_column("Rotation", justify="right")
        t.add_column("NestPri", justify="right")
        t.add_column("Drilling")
        t.add_column("SmallNest")
        t.add_column("Active")
        for n, item in enumerate(rows, start=1):
            custom = "; ".join(
                f"{key}={value}" for key, value in sorted((item.get("custom_fields") or {}).items())
            )
            t.add_row(
                str(n),
                str(item.get("style_name", "") or ""),
                str(item.get("quantity", "") or ""),
                f"{item.get('width', '') or ''} x {item.get('length', '') or ''}",
                str(item.get("material_id", "") or ""),
                str(item.get("csv_customer_name", "") or ""),
                str(item.get("csv_order_number", "") or ""),
                str(item.get("csv_item_number", "") or ""),
                str(item.get("production_comment", "") or ""),
                custom,
                str(item.get("rotation_method", "") or ""),
                str(item.get("nesting_priority", "") or ""),
                _yes_no(item.get("has_drilling")),
                _yes_no(item.get("small_nest_part")),
                _yes_no(item.get("active_in_process")),
            )
        console.print(t)


door_paths_app = typer.Typer(help="CDM door paths")


@door_paths_app.command("list")
@handle_com_errors
def door_paths_list(
    type_name: str | None = typer.Argument(None, help="Door type name filter (e.g. L_B_10mm)"),
) -> None:
    """List CDM door paths from the database."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.cdm_door_paths(type_name=type_name)
        rows = result.get("door_paths", [])
        if not rows:
            if type_name:
                console.print(f"[yellow]No door paths found for type {type_name}[/yellow]")
            else:
                console.print("[yellow]No door paths found[/yellow]")
            return
        t = Table(title="CDM Door Paths")
        t.add_column("Path", style="green")
        t.add_column("Type")
        t.add_column("Tool")
        t.add_column("ToolNo", justify="right")
        t.add_column("Method")
        t.add_column("SafeRapid", justify="right")
        t.add_column("RapidTo", justify="right")
        t.add_column("Depth", justify="right")
        t.add_column("Spindle", justify="right")
        t.add_column("DownFeed", justify="right")
        t.add_column("CutFeed", justify="right")
        t.add_column("LeadIn", justify="right")
        t.add_column("LeadOut", justify="right")
        t.add_column("SlopeIn")
        t.add_column("SlopeOut")
        t.add_column("Stock", justify="right")
        t.add_column("InOut")
        t.add_column("Side")
        for item in rows:
            t.add_row(
                str(item.get("path_name", "") or ""),
                str(item.get("door_type", "") or ""),
                str(item.get("tool_name", "") or ""),
                str(item.get("tool_number", "") or ""),
                str(item.get("machining_method", "") or ""),
                str(item.get("safe_rapid", "") or ""),
                str(item.get("rapid_down_to", "") or ""),
                str(item.get("final_depth", "") or ""),
                str(item.get("spindle_speed", "") or ""),
                str(item.get("down_feed", "") or ""),
                str(item.get("cut_feed", "") or ""),
                str(item.get("lead_in", "") or ""),
                str(item.get("lead_out", "") or ""),
                _yes_no(item.get("slope_in")),
                _yes_no(item.get("slope_out")),
                str(item.get("stock", "") or ""),
                str(item.get("tool_in_out", "") or ""),
                str(item.get("tool_side", "") or ""),
            )
        console.print(t)


materials_app = typer.Typer(help="CDM materials")


@materials_app.command("list")
@handle_com_errors
def materials_list() -> None:
    """List CDM materials from the database."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.cdm_materials()
        rows = result.get("materials", [])
        if not rows:
            console.print("[yellow]No materials found[/yellow]")
            return
        t = Table(title="CDM Materials")
        t.add_column("ID", style="cyan", justify="right")
        t.add_column("Name", style="green")
        t.add_column("Width", justify="right")
        t.add_column("Length", justify="right")
        t.add_column("Thickness", justify="right")
        t.add_column("Grain", justify="right")
        for item in rows:
            t.add_row(
                str(item.get("id", "") or ""),
                str(item.get("name", "") or ""),
                str(item.get("width", "") or ""),
                str(item.get("length", "") or ""),
                str(item.get("thickness", "") or ""),
                str(item.get("grain_restriction", "") or ""),
            )
        console.print(t)


config_app = typer.Typer(help="CDM job configurations")


@config_app.command("list")
@handle_com_errors
def config_list() -> None:
    """List CDM job configurations from the database."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.cdm_configs()
        rows = result.get("configs", [])
        if not rows:
            console.print("[yellow]No configurations found[/yellow]")
            return
        t = Table(title="CDM Configurations")
        t.add_column("ID", style="cyan", justify="right")
        t.add_column("Name", style="green")
        t.add_column("Post")
        t.add_column("NC Ext")
        t.add_column("GenNC")
        t.add_column("GenReports")
        t.add_column("NestMethod", justify="right")
        t.add_column("PackTo", justify="right")
        for item in rows:
            t.add_row(
                str(item.get("id", "") or ""),
                str(item.get("name", "") or ""),
                _basename(item.get("post_processor")),
                str(item.get("nc_extension", "") or ""),
                _yes_no(item.get("generate_nc")),
                _yes_no(item.get("generate_reports")),
                str(item.get("nesting_method", "") or ""),
                str(item.get("nesting_pack_to", "") or ""),
            )
        console.print(t)


@config_app.command("show")
@handle_com_errors
def config_show(
    name: str = typer.Argument(..., help="Configuration name"),
) -> None:
    """Show a single CDM configuration (basic, nesting and CDM settings)."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.cdm_configs(show=name)
        rows = result.get("configs", [])
        if not rows:
            console.print(f"[red]Configuration not found: {name}[/red]")
            raise typer.Exit(code=1)
        cfg = rows[0]
        cdm = cfg.get("cdm") or {}
        display_name = str(cfg.get("name", "") or name)
        _print_config_section(
            f"Config: {display_name} — Podstawowe",
            [
                ("Name", cfg.get("name")),
                ("Post processor", cfg.get("post_processor")),
                ("Drawing output", cfg.get("drawing_output_location")),
                ("NC output", cfg.get("nc_output_location")),
                ("Report output", cfg.get("report_output_location")),
                ("NC extension", cfg.get("nc_extension")),
                ("Generate NC", cfg.get("generate_nc")),
                ("Generate reports", cfg.get("generate_reports")),
                ("Replace space with underscore", cfg.get("replace_space_with_underscore")),
                ("Clear output folders", cfg.get("clear_output_folders")),
                ("Custom VBA macro", cfg.get("custom_vba_macro")),
                ("Compiled file name", cfg.get("compiled_file_name")),
            ],
        )
        _print_config_section(
            f"Config: {display_name} — Nesting",
            [
                ("Method", cfg.get("nesting_method")),
                ("Pack to", cfg.get("nesting_pack_to")),
                ("Gap between paths", cfg.get("nesting_gap_between_paths")),
                ("Gap at sheet edge", cfg.get("nesting_gap_at_sheet_edge")),
                ("Extra gap at lead start", cfg.get("nesting_extra_gap_at_lead_start")),
                ("Time per sheet", cfg.get("nesting_time_per_sheet")),
                ("Optimisation level", cfg.get("nesting_optimisation_level")),
                ("Search resolution", cfg.get("nesting_search_resolution")),
                ("Minimise tool changes", cfg.get("nesting_minimise_tool_changes")),
                ("Use bridged", cfg.get("nesting_use_bridged")),
                ("Use onion skin", cfg.get("nesting_use_onion_skin")),
                ("Prevent nesting in apertures", cfg.get("nesting_prevent_nesting_in_apertures")),
                ("Force strict priorities", cfg.get("nesting_force_strict_priorities")),
                ("Common line cutting", cfg.get("nesting_common_line_cutting")),
                ("Total time", cfg.get("nesting_total_time")),
                ("Sheet order type", cfg.get("nesting_sheet_order_type")),
                ("Sheet alignment", cfg.get("nesting_sheet_alignment")),
                ("Inactivity timeout", cfg.get("nesting_inactivity_timeout")),
            ],
        )
        _print_config_section(
            f"Config: {display_name} — CDM",
            [
                ("Disable nesting", cdm.get("disable_nesting")),
                ("Disable nesting oversize X", cdm.get("disable_nesting_oversize_x")),
                ("Disable nesting oversize Y", cdm.get("disable_nesting_oversize_y")),
                ("Use default press", cdm.get("use_default_press")),
                (
                    "Press group by material thickness",
                    cdm.get("press_group_by_material_thickness"),
                ),
                ("Generate NC for parts", cdm.get("generate_nc_for_parts")),
                ("Capture nested part positions", cdm.get("capture_nested_part_positions")),
                ("Part recovery X", cdm.get("part_recovery_x")),
                ("Part recovery Y", cdm.get("part_recovery_y")),
                ("Z depth tolerance", cdm.get("z_depth_tolerance")),
                ("Preview material thickness", cdm.get("preview_material_thickness")),
                ("Custom macro", cdm.get("custom_macro")),
            ],
        )


setups_app = typer.Typer(help="CDM setups")


@setups_app.command("list")
@handle_com_errors
def setups_list() -> None:
    """List CDM setups from the database."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.cdm_lookups()
        rows = result.get("lookups", {}).get("setups", [])
        if not rows:
            console.print("[yellow]No setups found[/yellow]")
            return
        t = Table(title="CDM Setups")
        t.add_column("ID", style="cyan", justify="right")
        t.add_column("Name", style="green")
        t.add_column("WhatToExtract", justify="right")
        t.add_column("PanelAlign")
        t.add_column("ZLevelStep", justify="right")
        t.add_column("StepLength", justify="right")
        t.add_column("GeometryQuery")
        for item in rows:
            t.add_row(
                str(item.get("id", "") or ""),
                str(item.get("name", "") or ""),
                str(item.get("fe_what_to_extract", "") or ""),
                _yes_no(item.get("fe_use_panel_alignment")),
                str(item.get("fe_z_level_step", "") or ""),
                str(item.get("imp_step_length", "") or ""),
                str(item.get("geometry_query", "") or ""),
            )
        console.print(t)


customers_app = typer.Typer(help="CDM customers")


@customers_app.command("list")
@handle_com_errors
def customers_list() -> None:
    """List CDM customers from the database."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.cdm_lookups()
        rows = result.get("lookups", {}).get("customers", [])
        if not rows:
            console.print("[yellow]No customers found[/yellow]")
            return
        t = Table(title="CDM Customers")
        t.add_column("ID", style="cyan", justify="right")
        t.add_column("Name", style="green")
        t.add_column("Address")
        t.add_column("City")
        t.add_column("Contact")
        t.add_column("Phone")
        t.add_column("Email")
        for item in rows:
            t.add_row(
                str(item.get("id", "") or ""),
                str(item.get("name", "") or ""),
                str(item.get("address_line_1", "") or ""),
                str(item.get("city", "") or ""),
                str(item.get("contact_name", "") or ""),
                str(item.get("telephone_number", "") or ""),
                str(item.get("email_address", "") or ""),
            )
        console.print(t)


machining_orders_app = typer.Typer(help="CDM machining orders")


@machining_orders_app.command("list")
@handle_com_errors
def machining_orders_list() -> None:
    """List CDM machining orders from the database."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.cdm_lookups()
        rows = result.get("lookups", {}).get("machining_orders", [])
        if not rows:
            console.print("[yellow]No machining orders found[/yellow]")
            return
        t = Table(title="CDM Machining Orders")
        t.add_column("Seq", style="cyan", justify="right")
        t.add_column("List", style="green")
        t.add_column("Style")
        t.add_column("Layer")
        t.add_column("Multidrill")
        for item in rows:
            t.add_row(
                str(item.get("seq_num", "") or ""),
                str(item.get("list_name", "") or ""),
                str(item.get("machining_style_name", "") or ""),
                str(item.get("layer_name", "") or ""),
                _yes_no(item.get("is_multidrill")),
            )
        console.print(t)


doorstyles_app = typer.Typer(help="CDM door styles")


@doorstyles_app.command("list")
@handle_com_errors
def doorstyles_list() -> None:
    """List CDM door styles from the database."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.cdm_lookups()
        rows = result.get("lookups", {}).get("doorstyles", [])
        if not rows:
            console.print("[yellow]No door styles found[/yellow]")
            return
        t = Table(title="CDM Door Styles")
        t.add_column("ID", style="cyan", justify="right")
        t.add_column("File", style="green")
        t.add_column("Project")
        for item in rows:
            t.add_row(
                str(item.get("id", "") or ""),
                _basename(item.get("full_file_name")),
                str(item.get("vba_project_name", "") or ""),
            )
        console.print(t)


multidrill_app = typer.Typer(help="CDM multidrill heads")


@multidrill_app.command("list")
@handle_com_errors
def multidrill_list() -> None:
    """List CDM multidrill heads from the database."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.cdm_lookups()
        rows = result.get("lookups", {}).get("multidrill", [])
        if not rows:
            console.print("[yellow]No multidrill heads found[/yellow]")
            return
        t = Table(title="CDM Multidrill Heads")
        t.add_column("ID", style="cyan", justify="right")
        t.add_column("Name", style="green")
        t.add_column("Selected")
        t.add_column("Feed", justify="right")
        t.add_column("Spindle", justify="right")
        t.add_column("Rapid", justify="right")
        t.add_column("Bottom", justify="right")
        for item in rows:
            t.add_row(
                str(item.get("id", "") or ""),
                str(item.get("name", "") or ""),
                _yes_no(item.get("selected")),
                str(item.get("feed_rate", "") or ""),
                str(item.get("spindle_speed", "") or ""),
                str(item.get("safe_rapid_distance", "") or ""),
                str(item.get("bottom_of_hole", "") or ""),
            )
        console.print(t)


fittings_app = typer.Typer(help="CDM fittings")


@fittings_app.command("list")
@handle_com_errors
def fittings_list() -> None:
    """List CDM fittings from the database."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.cdm_lookups()
        rows = result.get("lookups", {}).get("fittings", [])
        if not rows:
            console.print("[yellow]No fittings found[/yellow]")
            return
        t = Table(title="CDM Fittings")
        t.add_column("ID", style="cyan", justify="right")
        t.add_column("JobFile", justify="right")
        t.add_column("Type", style="green")
        t.add_column("File")
        for item in rows:
            t.add_row(
                str(item.get("id", "") or ""),
                str(item.get("fk_job_file_id", "") or ""),
                str(item.get("fitting_type", "") or ""),
                str(item.get("fitting_file", "") or ""),
            )
        console.print(t)


layers_mapping_app = typer.Typer(help="CDM layer mappings")


@layers_mapping_app.command("list")
@handle_com_errors
def layers_mapping_list() -> None:
    """List CDM layer mappings from the database."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.cdm_lookups()
        rows = result.get("lookups", {}).get("layers_mapping", [])
        if not rows:
            console.print("[yellow]No layer mappings found[/yellow]")
            return
        t = Table(title="CDM Layer Mappings")
        t.add_column("Setup", style="green")
        t.add_column("Layer")
        t.add_column("Style")
        t.add_column("Order", justify="right")
        t.add_column("Feature")
        t.add_column("SideClosed", justify="right")
        t.add_column("DirClosed", justify="right")
        t.add_column("Start", justify="right")
        for item in rows:
            t.add_row(
                str(item.get("setup_name", "") or ""),
                str(item.get("layer_name", "") or ""),
                str(item.get("machining_style_name", "") or ""),
                str(item.get("machining_order", "") or ""),
                _yes_no(item.get("is_feature_layer")),
                str(item.get("tool_side_closed_geo", "") or ""),
                str(item.get("tool_direction_closed_geo", "") or ""),
                str(item.get("start_point", "") or ""),
            )
        console.print(t)


app.add_typer(order_details_app, name="order-details")
app.add_typer(door_paths_app, name="doorpaths")
app.add_typer(materials_app, name="materials")
app.add_typer(config_app, name="config")
app.add_typer(setups_app, name="setups")
app.add_typer(customers_app, name="customers")
app.add_typer(machining_orders_app, name="machining-orders")
app.add_typer(doorstyles_app, name="doorstyles")
app.add_typer(multidrill_app, name="multidrill")
app.add_typer(fittings_app, name="fittings")
app.add_typer(layers_mapping_app, name="layers-mapping")
