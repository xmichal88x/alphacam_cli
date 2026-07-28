from __future__ import annotations

import typer
from rich.table import Table

from alphacam_cli.cli.common import console, get_visible, handle_com_errors, require_platform
from alphacam_cli.com.manager import alphacam_context
from alphacam_cli.core.application import Application

app = typer.Typer(help="Test and manage AlphaCAM connection")


@app.command()
@handle_com_errors
def info(
    prog_id: str = typer.Option("", "--progid", help="Specific COM ProgID to use"),
    visible: bool = typer.Option(False, "--visible", "-v", help="Show AlphaCAM window"),
) -> None:
    """Test COM connection and display AlphaCAM version info."""
    require_platform()
    pid = prog_id or None
    with alphacam_context(visible=visible or get_visible(), prog_id=pid) as raw:
        ac = Application(raw)

        table = Table(title="AlphaCAM Connection Info", title_style="bold cyan")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Name", ac.name)
        table.add_row("Version", ac.version)
        table.add_row("Module", ac.module_type)
        table.add_row("Level", str(ac.program_level))
        table.add_row("API Version", str(ac.api_version))
        table.add_row("Full Name", ac.full_name)
        table.add_row("Licomdat", ac.licomdat_path)
        table.add_row("Licomdir", ac.licomdir_path)
        table.add_row("Post File", ac.post_file_name)

        console.print(table)
