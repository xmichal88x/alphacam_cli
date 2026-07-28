from __future__ import annotations

import csv
import glob
import os
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

app = typer.Typer(help="Nesting operations")


@app.command()
@handle_com_errors
def run(
    csv_path: str = typer.Argument(..., help="CSV file with part definitions"),
    output_dir: str = typer.Option(
        "", "--output", "-o", help="Output directory for .anl and .ard files"
    ),
    sheet_width: float = typer.Option(2440, "--sheet-width", "-w", help="Sheet width"),
    sheet_height: float = typer.Option(1220, "--sheet-height", "-h", help="Sheet height"),
) -> None:
    """Run nesting from a CSV file with columns: filename, count."""
    require_platform()
    if not os.path.isfile(csv_path):
        console.print(f"[red]CSV file not found: {csv_path}[/red]")
        raise typer.Exit(code=1)

    out = output_dir or os.path.dirname(csv_path) or "."
    os.makedirs(out, exist_ok=True)

    # Read CSV with validation
    parts: list[dict[str, Any]] = []
    try:
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, 2):
                if not row or not any(row.values()):
                    continue
                try:
                    parts.append(
                        {
                            "name": str(row.get("filename", "")).strip(),
                            "count": int(row.get("count", 1)),
                        }
                    )
                except (ValueError, TypeError):
                    console.print(f"[yellow]Warning:[/yellow] Skipping row {row_num}: invalid data")
                    continue
    except csv.Error as e:
        console.print(f"[red]CSV error:[/red] {e}")
        raise typer.Exit(code=1) from e

    if not parts:
        console.print("[red]No valid parts in CSV[/red]")
        raise typer.Exit(code=1)

    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)

        # Create sheet geometry
        drw = ac.create_temp_drawing()
        if drw is None:
            console.print("[red]Failed to create drawing[/red]")
            raise typer.Exit(code=1)

        sheet_geo = drw.create_rectangle(0, 0, sheet_width, sheet_height)

        # Setup nesting
        nesting = ac.get_nesting()
        nesting.suppress_dialogs = True
        nl = nesting.new_nest_list(os.path.join(out, "nest.anl"))

        # Add each part type (create a drawing per part)
        for part in parts:
            np = nl.add_file(part["name"])
            np.required = part["count"]
        nl.save()

        # Setup sheet
        sl = nesting.new_sheet_list()
        ss = sl.add(sheet_geo)
        ss.thickness = 18.0
        ss.required = 1

        # Run nesting
        console.print(f"[yellow]Nesting {len(parts)} part types...[/yellow]")
        result = nesting.nest(nl, sl)
        console.print("[green]OK:[/green] Nesting completed")
        console.print(f"     Total parts: {sum(p['count'] for p in parts)}")
        console.print(f"     NestList parts: {result.count if result else 0}")


@app.command("list")
@handle_com_errors
def list_nests() -> None:
    """List available nest lists in the working directory."""
    files = sorted(glob.glob("*.anl"))
    if not files:
        console.print("[yellow]No .anl nest list files found in current directory[/yellow]")
        return

    t = Table(title="Nest Lists")
    t.add_column("File", style="cyan")
    for f in files:
        t.add_row(f)
    console.print(t)
