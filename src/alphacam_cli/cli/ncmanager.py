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

app = typer.Typer(help="NC output manager operations")
config_app = typer.Typer(help="NC output configurations")
app.add_typer(config_app, name="config")


@config_app.command("list")
@handle_com_errors
def config_list() -> None:
    """List NC output configurations (read-only, no dialogs)."""
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        result = ac.nc_configs()
        configs = list(result.get("configs", []))
        t = Table(title=f"NC Output Configurations ({result.get('count', len(configs))} found)")
        t.add_column("#", style="cyan")
        t.add_column("Name", style="green")
        for i, name in enumerate(configs, start=1):
            t.add_row(str(i), name)
        console.print(t)
