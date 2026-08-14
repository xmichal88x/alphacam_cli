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

app = typer.Typer(help="Production reports (Reports add-in)")


@app.command()
@handle_com_errors
def create(
    job: str | None = typer.Option(
        None,
        "--job",
        help="CDM job name for the manifest filename (e.g. for cdm manifest)",
    ),
) -> None:
    """Create production reports for the active drawing (no dialogs)."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.reports_create(job_name=job)
        job_status = str(result.get("job", "ok"))
        console.print(f"[green]OK:[/green] Reports created (job={job_status})")
        t = Table(title="Reports Created")
        t.add_column("Property", style="cyan")
        t.add_column("Value", style="green")
        t.add_row("Job", job_status)
        t.add_row("Active drawing", "Yes" if result.get("active_drawing") else "No")
        t.add_row("Settings file", str(result.get("settings_file", "")))
        console.print(t)
