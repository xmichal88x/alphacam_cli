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
    sheet_name: str = typer.Option(
        "", "--sheet-name", help="Sheet name from library (e.g. MDF_18); empty = draw rectangle"
    ),
    gap: float | None = typer.Option(
        None, "--gap", help="Gap between parts (mm); default from registry/.anl"
    ),
    edge_gap: float | None = typer.Option(
        None, "--edge-gap", help="Edge gap from sheet border (mm)"
    ),
    lead_gap: float | None = typer.Option(None, "--lead-gap", help="Lead-in/out gap (mm)"),
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

    # Write nest list (.anl) with parts from CSV
    anl_path = os.path.join(out, "nest.anl")
    lines = ["$SETUP", "1", "2", "0", "0", "0"]
    for part in parts:
        lines.extend(
            [
                "$ITEM",
                part["name"],
                str(part["count"]),
                "1",
                "90",
                "0",
            ]
        )
    with open(anl_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)

        # Create drawing and nest data from the nest list file
        drw = ac.create_temp_drawing()
        if drw is None:
            console.print("[red]Failed to create drawing[/red]")
            raise typer.Exit(code=1)

        nd = drw.create_nest_data(anl_path)

        if gap is not None:
            nd.Gap = gap  # type: ignore[attr-defined]
        if edge_gap is not None:
            nd.EdgeGap = edge_gap  # type: ignore[attr-defined]
        if lead_gap is not None:
            nd.LeadGap = lead_gap  # type: ignore[attr-defined]

        # Create sheet geometry (from library or rectangle) and run nesting
        console.print(f"[yellow]Nesting {len(parts)} part types...[/yellow]")
        if sheet_name:
            import win32com.client.gencache as gencache  # type: ignore[import-untyped]

            gencache.EnsureModule("{6702E3DF-142C-4627-8EA2-4C47EBC78441}", 0, 1, 3)
            app = gencache.EnsureDispatch("Ar5axaps.Application")
            try:
                sheet = app.Nesting.SheetDatabase.FindSheet(sheet_name)
            except Exception as e:
                console.print(f"[red]nest: sheet from library not found: {sheet_name}[/red]")
                raise typer.Exit(code=1) from e
            paths = sheet.InsertInActiveDrawingAtPoint(0.0, 0.0)
            try:
                thickness = sheet.Thickness.Thickness
            except Exception:
                thickness = 18.0
            nd.AddSheet(paths.Item(1), sheet.Material.Name, thickness, sheet.Quantity)
        else:
            sheet_geo = drw.create_rectangle(0, 0, sheet_width, sheet_height)
            nd.AddSheet(sheet_geo.raw_dispatch, "MDF", 18, 1)
        nd.DoNest()
        console.print("[green]OK:[/green] Nesting completed")
        console.print(f"     Total parts: {sum(p['count'] for p in parts)}")


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
