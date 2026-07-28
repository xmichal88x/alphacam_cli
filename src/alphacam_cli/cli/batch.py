from __future__ import annotations

import glob
import os
from datetime import datetime
from typing import Any

import typer
from rich.progress import Progress

from alphacam_cli.cli.common import console, get_visible, handle_com_errors, require_platform
from alphacam_cli.com.manager import alphacam_context
from alphacam_cli.core.application import Application

STATUS_OK = "OK"
STATUS_FAIL = "FAIL"

app = typer.Typer(help="Batch processing")


def _process_file(
    ac: Application,
    file_path: str,
    output_dir: str,
) -> dict[str, Any]:
    basename = os.path.splitext(os.path.basename(file_path))[0]
    result: dict[str, Any] = {"file": file_path, "status": STATUS_OK, "error": ""}

    try:
        drw = ac.open_drawing(file_path)
    except Exception as ex:
        return {**result, "status": STATUS_FAIL, "error": f"Failed to open drawing: {ex}"}

    if drw is None:
        return {**result, "status": STATUS_FAIL, "error": "Could not open drawing"}

    nc_path = os.path.join(output_dir, f"{basename}.nc")
    try:
        drw.output_nc(nc_path)
    except Exception as ex:
        return {**result, "status": STATUS_FAIL, "error": f"NC output failed: {ex}"}

    try:
        drw.save_as(os.path.join(output_dir, f"{basename}.amd"))
    except Exception as ex:
        result["error"] = f"Drawing save failed (NC generated): {ex}"

    return result


@app.command()
@handle_com_errors
def process(
    ctx: typer.Context,
    input_dir: str = typer.Argument(..., help="Directory with .amd files"),
    output_dir: str = typer.Option(
        "", "--output", "-o", help="Output directory (default: same as input)"
    ),
    post: str = typer.Option("", "--post", "-p", help="Post-processor name"),
    pattern: str = typer.Option("*.amd", "--pattern", help="Input file pattern"),
    continue_on_error: bool = typer.Option(
        False, "--continue-on-error", help="Continue on individual file failure"
    ),
) -> None:
    """Batch process multiple .amd files to generate NC code."""
    require_platform()
    files = sorted(glob.glob(os.path.join(input_dir, pattern)))
    if not files:
        console.print(f"[red]No files matching '{pattern}' in {input_dir}[/red]")
        raise typer.Exit(code=1)

    out = output_dir or input_dir
    os.makedirs(out, exist_ok=True)

    results: list[dict[str, Any]] = []
    with alphacam_context(visible=get_visible()) as raw:
        ac = Application(raw)
        if post:
            ac.select_post(post)
            console.print(f"[green]Post selected: {post}[/green]")

        with Progress() as progress:
            task = progress.add_task("Processing...", total=len(files))
            for f in files:
                basename = os.path.splitext(os.path.basename(f))[0]
                progress.update(task, description=f"Processing {basename}...")
                result = _process_file(ac, f, out)
                results.append(result)
                progress.advance(task)

                if result["status"] == "FAIL" and not continue_on_error:
                    break

    ok_count = sum(1 for r in results if r["status"] == "OK")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    console.print()
    console.print("[bold]Batch Summary[/bold]")
    console.print(f"  [green]OK:[/green] {ok_count}  [red]FAIL:[/red] {fail_count}")
    for r in results:
        if r["error"]:
            console.print(f"  [red]  {r['file']}: {r['error']}[/red]")
    console.print(f"[green]Done:[/green] {len(results)} files -> {out}")

    if fail_count:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(out, f"batch-errors-{timestamp}.log")
        with open(log_path, "w") as log_f:
            for r in results:
                if r["error"]:
                    log_f.write(f"{r['file']}: {r['error']}\n")
        console.print(f"  [yellow]Errors logged: {log_path}[/yellow]")

    if fail_count:
        ctx.exit(1)
