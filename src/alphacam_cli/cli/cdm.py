from __future__ import annotations

import re
from datetime import datetime
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
from alphacam_cli.core.application import _validate_due_date, _validate_job_name

app = typer.Typer(help="Cabinet Door Manufacturing (CDM Automation Manager add-in)")


def _require_abs_windows_path(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    path = value.strip()
    if (
        not re.match(r"^[A-Za-z]:[\\/]", path)
        and not re.match(r"^\\\\", path)
        and not re.match(r"^//", path)
    ):
        console.print(f"[red]Error:[/red] {name} must be an absolute path")
        raise typer.Exit(code=2)
    return path


@app.command()
@handle_com_errors
def create(
    job_name: str = typer.Argument(..., help="CDM job name"),
    config: str | None = typer.Option(
        None, "--config", help="Configuration name (default: from database)"
    ),
    material: str | None = typer.Option(
        None, "--material", help="Material name (AM_Materials); default from database"
    ),
    customer: str | None = typer.Option(
        None, "--customer", help="Customer name (AM_CustomerDetails)"
    ),
    po: str | None = typer.Option(None, "--po", help="Purchase order number"),
    due_date: str | None = typer.Option(None, "--due-date", help="Due date (YYYY-MM-DD)"),
    description: str | None = typer.Option(None, "--description", help="Job description"),
) -> None:
    """Create an empty CDM job (no order details; add patterns via cdm import)."""
    require_platform()
    if due_date is not None:
        try:
            _validate_due_date(due_date)
        except RuntimeError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=2) from None
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.create_cdm_job(
            job_name=job_name,
            config=config,
            material=material,
            customer=customer,
            po=po,
            due_date=due_date,
            description=description,
        )
        if not result.get("success"):
            console.print(
                f"[red]Error:[/red] CDM job creation failed: {result.get('job_name') or job_name}"
            )
            for warning in result.get("warnings", []):
                console.print(f"[yellow]WARNING:[/yellow] {warning}")
            raise typer.Exit(code=1)
        console.print(f"[green]OK:[/green] CDM job created: {result.get('job_name') or job_name}")
        console.print(f"     Config: {result.get('config') or '-'}")
        console.print(f"     Material: {result.get('material') or '-'}")
        for warning in result.get("warnings", []):
            console.print(f"[yellow]WARNING:[/yellow] {warning}")


@app.command()
@handle_com_errors
def process(
    job_name: str = typer.Argument(..., help="CDM job name to process"),
    timeout: int = typer.Option(
        300,
        "--timeout",
        help="Processing timeout in seconds (client socket + server watchdog)",
    ),
    output_root: str | None = typer.Option(
        None,
        "--output-root",
        help="Override output root on the server (default: from the job's configuration)",
    ),
) -> None:
    """Process a CDM job headlessly.

    The ``ApplyMachiningAfterNesting.Events.HeadlessProcess`` macro runs
    in-proc on the gateway COM reference (no PsExec required).
    """
    require_platform()
    output_root = _require_abs_windows_path(output_root, "--output-root")
    kwargs: dict[str, Any] = {"job_name": job_name}
    if timeout != 300:
        kwargs["timeout_seconds"] = timeout
    if output_root is not None:
        kwargs["output_root"] = output_root
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        try:
            result = ac.process_cdm_job(**kwargs)
        except RuntimeError as exc:
            if "STALE_MACRO" in str(exc):
                console.print("[red]CDM processing blocked: previous macro invocation hung[/red]")
                console.print(f"[red]Detail:[/red] {exc}")
                console.print(
                    "[yellow]The AlphaCAM VBA host is hung — restart AlphaCAM "
                    "before retrying.[/yellow]"
                )
                raise typer.Exit(code=2) from exc
            raise
        if not result.get("success"):
            if result.get("status") == "stale_macro":
                console.print("[red]CDM processing blocked: previous macro invocation hung[/red]")
                detail = result.get("detail")
                if detail:
                    console.print(f"[red]Detail:[/red] {detail}")
                console.print(
                    "[yellow]The gateway is auto-restarting (~60s). "
                    "Retry the command afterwards.[/yellow]"
                )
                raise typer.Exit(code=2)
            job_display = result.get("job_name") or job_name
            console.print(f"[red]CDM job processing failed: {job_display}[/red]")
            status = result.get("status")
            if status:
                console.print(f"[red]Status: {status}[/red]")
            detail = result.get("detail")
            if detail:
                console.print(f"[red]Detail:[/red] {detail}")
            log = result.get("log")
            if log:
                console.print(f"[red]Log:[/red]\n{log}")
            raise typer.Exit(code=1)
        console.print(f"[green]OK:[/green] CDM job processed: {result.get('job_name') or job_name}")
        status = result.get("status")
        if status:
            console.print(f"[green]Status: {status}[/green]")
        report = result.get("report") or {}
        if report.get("success"):
            report_name = report.get("manifest_file") or "?"
            console.print(f"[green]Report: OK ({report_name})[/green]")
        elif report.get("skipped"):
            error = (
                report.get("error")
                or "reports disabled for job configuration (GenerateReports=False)"
            )
            console.print(f"[yellow]Report: NOT CREATED — {error}[/yellow]")
        elif report:
            console.print(
                f"[yellow]Report: NOT CREATED — {report.get('error') or 'unknown error'}[/yellow]"
            )
        for warning in result.get("warnings", []):
            console.print(f"[yellow]WARNING:[/yellow] {warning}")


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
        None,
        "--material",
        help="Material name (AM_Materials) for the job; overrides the mapped material column",
    ),
    import_setting: str | None = typer.Option(
        None,
        "--import-setting",
        help=(
            "Import setting id or name from the database "
            "(default: selected setting, AM_ImportSettings.Selected)"
        ),
    ),
    preview: bool = typer.Option(False, "--preview", help="Dry run preview without creating a job"),
) -> None:
    """Import a CSV door order into a single CDM job (headless, no dialogs)."""
    require_platform()
    job = (job or "").strip() or None
    if job and name:
        console.print("[red]Error:[/red] cdm: --name and --job are mutually exclusive")
        raise typer.Exit(code=2)
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
            errors = result.get("errors", [])
            if errors:
                for err in errors:
                    console.print(f"[red]ERROR:[/red] {err}")
            else:
                console.print("[red]ERROR:[/red] No rows imported (empty CSV or no valid rows)")
            raise typer.Exit(code=1)
        verb = "updated" if job else "created"
        job_display = result.get("job_name") or name or job or csv
        console.print(
            f"[green]OK:[/green] CDM job {verb}: {job_display} ({result.get('items', 0)} item(s))"
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
        if not result.get("success"):
            console.print(
                f"[red]Error:[/red] CDM job deletion failed: {result.get('job_name') or job_name}"
            )
            raise typer.Exit(code=1)
        console.print(f"[green]OK:[/green] CDM job deleted: {result.get('job_name') or job_name}")


@app.command("manifest")
@handle_com_errors
def manifest(
    job_name: str | None = typer.Argument(None, help="Job name (manifest list if omitted)"),
    material: str | None = typer.Option(
        None, "--material", "-m", help="Filter by material (sheet database name)"
    ),
    data_dir: str | None = typer.Option(
        None,
        "--dir",
        help="Override reports data directory (default: LICOMDIR\\Reports\\Data on server)",
    ),
    nc_root: str | None = typer.Option(
        None,
        "--nc-root",
        help="Override NC output root on the server (default: from job configuration)",
    ),
    show_all: bool = typer.Option(
        False, "--show-all", help="Show all custom fields (2-25) in the parts table"
    ),
    by_token: bool = typer.Option(
        False, "--by-token", help="Aggregate parts by project token (custom_field_1)"
    ),
    fill_threshold: int | None = typer.Option(
        None,
        "--fill-threshold",
        help="Sheet fill threshold percent (0-100) for fill classification (default: 70)",
    ),
    validate: bool = typer.Option(
        False, "--validate", help="Validate manifest consistency (token quantities and counts)"
    ),
    token_qty: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--token-qty",
        help="Expected quantity for a project token, repeatable (token=qty)",
    ),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Show nesting results manifests (.acrepd) for CDM jobs."""
    require_platform()
    if by_token and not job_name:
        console.print("[red]Error:[/red] --by-token requires a job name")
        raise typer.Exit(code=2)
    if validate and not job_name:
        console.print("[red]Error:[/red] --validate requires a job name")
        raise typer.Exit(code=2)
    if fill_threshold is not None and not 0 <= fill_threshold <= 100:
        console.print("[red]Error:[/red] --fill-threshold must be between 0 and 100")
        raise typer.Exit(code=2)
    data_dir = _require_abs_windows_path(data_dir, "--dir")
    if token_qty and not validate:
        console.print("[red]Error:[/red] --token-qty requires --validate")
        raise typer.Exit(code=2)
    token_qtys = _parse_token_qtys(token_qty or []) or None
    if job_name:
        nc_root = _require_abs_windows_path(nc_root, "--nc-root")
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        if job_name:
            exit_code = _print_manifest(
                ac,
                job_name,
                material,
                data_dir,
                json_out,
                nc_root,
                show_all,
                by_token,
                fill_threshold,
                validate,
                token_qtys,
            )
            if exit_code:
                raise typer.Exit(code=exit_code)
        else:
            ignored = []
            if material is not None:
                ignored.append("--material")
            if nc_root is not None:
                ignored.append("--nc-root")
            if show_all:
                ignored.append("--show-all")
            if by_token:
                ignored.append("--by-token")
            if fill_threshold is not None:
                ignored.append("--fill-threshold")
            if validate:
                ignored.append("--validate")
            if token_qty:
                ignored.append("--token-qty")
            if ignored:
                console.print(
                    f"[yellow]WARNING:[/yellow] {' '.join(ignored)} ignored without job name"
                )
            _print_manifest_list(ac, data_dir, json_out)


def _manifest_size_kb(size: Any) -> str:
    try:
        return f"{float(size) / 1024:.1f}"
    except (TypeError, ValueError):
        return str(size)


def _manifest_mtime(mtime: Any) -> str:
    try:
        return datetime.fromtimestamp(float(mtime)).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return str(mtime)


def _trunc(value: Any, n: int) -> str:
    text = str(value or "")
    if not text:
        return "-"
    if len(text) > n:
        return text[: max(n - 3, 1)] + "..."
    return text


def _parse_token_qtys(raw_items: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for raw in raw_items:
        token, sep, qty = raw.partition("=")
        token = token.strip()
        if not sep or not token:
            console.print(f'[red]Error:[/red] invalid --token-qty "{raw}" (expected token=qty)')
            raise typer.Exit(code=2)
        try:
            value = int(qty)
        except ValueError:
            console.print(f'[red]Error:[/red] invalid --token-qty "{raw}" (expected token=qty)')
            raise typer.Exit(code=2) from None
        if value < 0:
            console.print(f'[red]Error:[/red] invalid --token-qty "{raw}" (expected token=qty)')
            raise typer.Exit(code=2)
        if token in result:
            console.print(f'[red]Error:[/red] duplicate --token-qty for token "{token}"')
            raise typer.Exit(code=2)
        result[token] = value
    return result


def _print_manifest_list(ac: Any, data_dir: str | None, json_out: bool) -> None:
    data = ac.manifest_list(data_dir)
    if json_out:
        console.print_json(data=data)
        return
    manifests = data.get("manifests", [])
    if not manifests:
        console.print("[yellow]No manifests found[/yellow]")
        return
    t = Table(title="CDM Nesting Manifests")
    t.add_column("Job", style="green")
    t.add_column("Material")
    t.add_column("Arkusze", justify="right")
    t.add_column("Wypełn.", justify="right")
    t.add_column("Size (kB)", justify="right")
    t.add_column("Modified")
    t.add_column("Path", style="dim")
    for m in manifests:
        utilization = m.get("first_utilization")
        t.add_row(
            str(m.get("job_name", "") or ""),
            str(m.get("material", "") or ""),
            str(m.get("sheet_count", 0)),
            f"{utilization}%" if isinstance(utilization, (int, float)) else "-",
            _manifest_size_kb(m.get("size")),
            _manifest_mtime(m.get("mtime")),
            str(m.get("path", "") or ""),
        )
    console.print(t)


def _print_manifest(
    ac: Any,
    job_name: str,
    material: str | None,
    data_dir: str | None,
    json_out: bool,
    nc_root: str | None = None,
    show_all: bool = False,
    by_token: bool = False,
    fill_threshold: int | None = None,
    validate: bool = False,
    token_qty: dict[str, int] | None = None,
) -> int | None:
    data = ac.manifest_read(
        job_name=job_name,
        material=material,
        data_dir=data_dir,
        nc_root=nc_root,
        by_token=by_token,
        fill_threshold=fill_threshold,
        validate=validate,
        token_qty=token_qty,
    )
    if json_out:
        console.print_json(data=data)
        return None
    manifest = data.get("manifest", {})
    header = f"[cyan]Manifest:[/cyan] {manifest.get('job_name') or job_name}"
    if manifest.get("material"):
        header += f" [dim]({manifest.get('material')})[/dim]"
    console.print(header)
    console.print(f"     Total parts: {manifest.get('total_parts', 0)}")
    unmatched = manifest.get("unmatched_parts", [])
    console.print(
        f"     Unmatched parts: {len(unmatched) if isinstance(unmatched, list) else unmatched}"
    )
    for sheet in manifest.get("sheets", []):
        console.print(
            f"\n[bold]Arkusz {sheet.get('name', '')}[/bold] "
            f"{sheet.get('database_name', '') or ''} "
            f"{str(sheet.get('width', '') or '')}x{str(sheet.get('length', '') or '')}"
            f"x{str(sheet.get('thickness', '') or '')} mm, części: {sheet.get('part_count', 0)}"
        )
        if sheet.get("scrap") is not None or sheet.get("utilization") is not None:
            fill_label = sheet.get("fill_class") or "empty"
            console.print(
                f"     Wypełnienie: {sheet.get('utilization')}% (odpad: {sheet.get('scrap')}%) "
                f"[fill: {fill_label}]",
                markup=False,
            )
        nc_file = sheet.get("nc_filename")
        nc_label = str(nc_file) if nc_file else "BRAK"
        nc_source = sheet.get("nc_source")
        if isinstance(nc_source, str) and nc_source:
            nc_label += f" [{nc_source}]"
        console.print(f"     NC: {nc_label}", markup=False)
        parts = sheet.get("parts", [])
        if not parts:
            console.print("[dim]No parts on sheet[/dim]")
            continue
        t = Table()
        t.add_column("Część", style="green")
        t.add_column("Ilość", justify="right")
        t.add_column("X", justify="right")
        t.add_column("Y", justify="right")
        t.add_column("Rot", justify="right")
        t.add_column("WxL", justify="right")
        t.add_column("Klient")
        t.add_column("Zamówienie")
        t.add_column("Handle")
        t.add_column("CSV order/item")
        t.add_column("Token")
        t.add_column("Notes", overflow="fold")
        if show_all:
            for i in range(2, 26):
                t.add_column(f"CF{i}")
        for part in parts:
            csv_ref = ""
            if part.get("csv_order_number") or part.get("csv_item_number"):
                csv_ref = " / ".join(
                    str(part.get(k) or "")
                    for k in ("csv_order_number", "csv_item_number")
                    if part.get(k)
                )
            cols = [
                str(part.get("name", "") or ""),
                str(part.get("quantity_on_sheet", "") or ""),
                str(part.get("x", "") or ""),
                str(part.get("y", "") or ""),
                str(part.get("rotation", "") or ""),
                f"{str(part.get('width', '') or '')}x{str(part.get('length', '') or '')}",
                str(part.get("csv_customer_name") or ""),
                str(part.get("csv_order_number") or ""),
                str(part.get("handle_name", "") or ""),
                csv_ref,
                _trunc(part.get("custom_field_1"), 20),
                _trunc(part.get("production_comment"), 30),
            ]
            if show_all:
                for i in range(2, 26):
                    cols.append(_trunc(part.get(f"custom_field_{i}"), 20))
            t.add_row(*cols)
        console.print(t)
    nc_unmatched = manifest.get("nc_unmatched", [])
    if isinstance(nc_unmatched, list) and nc_unmatched:
        console.print("\n[cyan]NC unmatched:[/cyan]")
        for path in nc_unmatched:
            console.print(f"    {path}")
    nc_missing = manifest.get("nc_missing", [])
    if isinstance(nc_missing, list) and nc_missing:
        console.print("\n[cyan]NC missing:[/cyan]")
        for name in nc_missing:
            console.print(f"    {name}")
    nc_matched = manifest.get("nc_matched_by_order", [])
    if isinstance(nc_matched, list) and nc_matched:
        sheets = manifest.get("sheets", [])
        labels: list[str] = []
        for index in nc_matched:
            if (
                isinstance(index, int)
                and 0 <= index < len(sheets)
                and isinstance(sheets[index].get("name"), str)
            ):
                labels.append(sheets[index]["name"])
            else:
                labels.append(str(index))
        console.print(f"\n[cyan]NC matched by order:[/cyan] {', '.join(labels)}")
    if by_token:
        _print_manifest_by_token(data)
    if validate:
        _print_validation(data.get("validation") or {})
        return _validation_exit_code(data)
    return None


def _print_validation(validation: dict[str, Any]) -> None:
    console.print("\n[cyan]Validation:[/cyan]")
    for err in validation.get("errors", []):
        console.print(f"[red]ERROR:[/red] {err}")
    for warning in validation.get("warnings", []):
        console.print(f"[yellow]WARNING:[/yellow] {warning}")
    errors = validation.get("errors", [])
    if errors:
        console.print(f"[red]VALID: FAILED ({len(errors)} errors)[/red]")
    else:
        console.print("[green]VALID: OK[/green]")


def _validation_exit_code(data: dict[str, Any]) -> int:
    validation = data.get("validation") or {}
    errors = validation.get("errors", [])
    if errors:
        return 1
    if validation.get("warnings"):
        return 2
    return 0


def _print_manifest_by_token(data: dict[str, Any]) -> None:
    console.print("\n[cyan]By token:[/cyan]")
    for group in data.get("by_token", []):
        token = group.get("token")
        label = str(token) if token else "(no token)"
        order = group.get("csv_order_number") or "-"
        console.print(f"Token: {label}  Qty: {group.get('total_qty', 0)}  Order: {order}")
        for sheet in group.get("sheets", []):
            console.print(f"     Arkusz {sheet.get('sheet')}: {sheet.get('qty')}")


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
        t.add_column("Nr zamówienia")
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
    if not result.get("success"):
        for err in result.get("errors", []):
            console.print(f"[red]ERROR:[/red] {err}")
        console.print("[red]ERROR:[/red] Preview failed")
        raise typer.Exit(code=1)
    for err in result.get("errors", []):
        console.print(f"[yellow]WARNING:[/yellow] {err}")
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
    job_name: str | None = typer.Argument(None, help="CDM job name (default: all jobs)"),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """List CDM order details (all jobs when no job name given)."""
    require_platform()
    if job_name is not None:
        try:
            job_name = _validate_job_name(job_name)
        except RuntimeError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=2) from None
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.cdm_order_details(job_name=job_name)
        if json_out:
            console.print_json(data=result)
            return
        rows = result.get("order_details", [])
        if not rows:
            if job_name:
                console.print(f"[yellow]No CDM order details found for job {job_name}[/yellow]")
            else:
                console.print("[yellow]No CDM order details found[/yellow]")
            return
        title = f"CDM Order Details: {job_name}" if job_name else "CDM Order Details"
        t = Table(title=title)
        t.add_column("No", style="cyan", justify="right")
        if job_name is None:
            t.add_column("Job")
        t.add_column("Style", style="green")
        t.add_column("Ilość", justify="right")
        t.add_column("W x L", justify="right")
        t.add_column("Material")
        t.add_column("Klient")
        t.add_column("Nr zamówienia")
        t.add_column("Item")
        t.add_column("Komentarz")
        t.add_column("Custom")
        t.add_column("Obrót", justify="right")
        t.add_column("Priorytet", justify="right")
        t.add_column("Wiercenie")
        t.add_column("Mały element")
        t.add_column("Aktywny")
        for n, item in enumerate(rows, start=1):
            custom = "; ".join(
                f"{key}={value}" for key, value in sorted((item.get("custom_fields") or {}).items())
            )
            cols = [
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
            ]
            if job_name is None:
                cols.insert(1, str(item.get("job_name", "") or ""))
            t.add_row(*cols)
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
        t.add_column("Ziarno", justify="right")
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
    if not name or not name.strip():
        console.print("[red]ERROR:[/red] Configuration name is required")
        raise typer.Exit(code=1)
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
        t.add_column("Wybrany")
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
        t.add_column("Cecha")
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
