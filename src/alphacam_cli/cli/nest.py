from __future__ import annotations

import csv
import glob
import os
from contextlib import suppress
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
    advanced: bool = typer.Option(
        False, "--advanced", help="Use full NestList API (NewNestList/AddFile/Nest)"
    ),
    total_time: float | None = typer.Option(None, "--total-time", help="Nest time limit (seconds)"),
    optimise_level: int | None = typer.Option(
        None, "--optimise-level", help="Nest optimisation level (0/1)"
    ),
    part_gap: float | None = typer.Option(
        None, "--part-gap", help="Gap between parts in advanced mode (mm)"
    ),
    cut_width: float | None = typer.Option(None, "--cut-width", help="Cut width compensation (mm)"),
    nesting_method: int | None = typer.Option(
        None,
        "--nesting-method",
        help="0=TrueShape, 1=Original, 2=Rectangular, 3=Manual",
    ),
    optimise_for_cuts: int | None = typer.Option(
        None, "--optimise-for-cuts", help="0=ForSpace, 1=ForCuts"
    ),
    cut_direction: int | None = typer.Option(None, "--cut-direction", help="0=X, 1=Y, 2=Auto"),
    resolution: float | None = typer.Option(None, "--resolution", help="Nest resolution"),
    select_best_sheet: int | None = typer.Option(
        None, "--select-best-sheet", help="Select best sheet (0/1)"
    ),
    no_aperture_nesting: bool = typer.Option(
        False, "--no-aperture-nesting", help="Prevent aperture nesting (advanced mode)"
    ),
    order_by_part: bool = typer.Option(
        False, "--order-by-part", help="Order parts by part (advanced mode)"
    ),
    no_subroutines: bool = typer.Option(
        False, "--no-subroutines", help="Do not use subroutines (advanced mode)"
    ),
    minimise_tool_changes: bool = typer.Option(
        False, "--minimise-tool-changes", help="Minimise tool changes (advanced mode)"
    ),
    strict_priorities: bool = typer.Option(
        False, "--strict-priorities", help="Strict part priorities (advanced mode)"
    ),
    inner_first: bool = typer.Option(
        False, "--inner-first", help="Nest inner parts first (advanced mode)"
    ),
    preserve_sheet_edge: bool = typer.Option(
        False, "--preserve-sheet-edge", help="Preserve sheet edge (advanced mode)"
    ),
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

        # Create sheet geometry (from library or rectangle) and run nesting
        console.print(f"[yellow]Nesting {len(parts)} part types...[/yellow]")
        if advanced:
            nesting = raw.Nesting
            nesting.SuppressDialogs = True
            nl = nesting.NewNestList(anl_path)
            for part in parts:
                nest_part = nl.AddFile(str(part["name"]))
                nest_part.Required = int(part["count"])
            if total_time is not None:
                nl.TotalTime = float(total_time)
            if optimise_level is not None:
                nl.OptimiseLevel = int(optimise_level)
            if part_gap is not None:
                nl.PartGap = float(part_gap)
            if cut_width is not None:
                nl.CutWidth = float(cut_width)
            if nesting_method is not None:
                nl.NestingMethod = int(nesting_method)
            if optimise_for_cuts is not None:
                nl.OptimiseForCuts = int(optimise_for_cuts)
            if cut_direction is not None:
                nl.CutDirection = int(cut_direction)
            if resolution is not None:
                nl.Resolution = float(resolution)
            if select_best_sheet is not None:
                nl.SelectBestSheet = int(select_best_sheet)
            if no_aperture_nesting:
                nl.PreventApertureNest = True
            if order_by_part:
                nl.OrderByPart = True
            if no_subroutines:
                nl.UseSubroutines = False
            if minimise_tool_changes:
                nl.MinimiseToolChanges = True
            if strict_priorities:
                nl.StrictPriorities = True
            if inner_first:
                nl.InnerFirst = True
            if preserve_sheet_edge:
                nl.PreserveSheetEdge = True
            if gap is not None and part_gap is None:
                nl.PartGap = float(gap)
            if edge_gap is not None:
                nl.EdgeGap = float(edge_gap)
            if lead_gap is not None:
                nl.LeadInGap = float(lead_gap)

            sl = nesting.NewSheetList()
            if sheet_name:
                try:
                    sheet = nesting.SheetDatabase.FindSheet(sheet_name)
                except Exception as e:
                    console.print(f"[red]nest: sheet from library not found: {sheet_name}[/red]")
                    raise typer.Exit(code=1) from e
                paths = sheet.InsertInActiveDrawingAtPoint(0.0, 0.0)
                nest_sheet = sl.Add(paths.Item(1))
                try:
                    nest_sheet.Thickness = float(sheet.Thickness.Thickness)
                except Exception:
                    nest_sheet.Thickness = 18.0
            else:
                sheet_geo = drw.create_rectangle(0, 0, sheet_width, sheet_height)
                nest_sheet = sl.Add(sheet_geo.raw_dispatch)
                nest_sheet.Thickness = 18.0
            nest_sheet.Required = 1
            try:
                result = nesting.Nest(nl, sl)
                try:
                    count = int(result.Count)
                except (TypeError, AttributeError, ValueError):
                    count = 0
            finally:
                with suppress(Exception):
                    nesting.DeleteAllNestLists()
            console.print("[green]OK:[/green] Nesting completed")
            console.print(f"     Total parts: {sum(p['count'] for p in parts)}")
            console.print(f"     Un-nested parts: {count}")
            return

        if gap is not None:
            nd.Gap = gap  # type: ignore[attr-defined]
        if edge_gap is not None:
            nd.EdgeGap = edge_gap  # type: ignore[attr-defined]
        if lead_gap is not None:
            nd.LeadGap = lead_gap  # type: ignore[attr-defined]

        if sheet_name:
            nesting = raw.Nesting
            try:
                sheet = nesting.SheetDatabase.FindSheet(sheet_name)
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
