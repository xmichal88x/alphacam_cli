from __future__ import annotations

import glob
import os
from typing import Any

import typer
from rich.progress import Progress

from alphacam_cli.cli.common import _visible, console, require_platform
from alphacam_cli.com.manager import AlphacamConnectionError, alphacam_context
from alphacam_cli.core.application import Application

app = typer.Typer(help="Batch processing")


@app.command()
def process(
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
    try:
        require_platform()
        files = sorted(glob.glob(os.path.join(input_dir, pattern)))
        if not files:
            console.print(f"[red]No files matching '{pattern}' in {input_dir}[/red]")
            raise typer.Exit(code=1)  # noqa: TRY301

        out = output_dir or input_dir
        os.makedirs(out, exist_ok=True)

        results: list[dict[str, Any]] = []
        with alphacam_context(visible=_visible) as raw:
            ac = Application(raw)
            if post:
                ac.select_post(post)
                console.print(f"[green]Post selected: {post}[/green]")

            with Progress() as progress:
                task = progress.add_task("Processing...", total=len(files))
                for f in files:
                    basename = os.path.splitext(os.path.basename(f))[0]
                    nc_path = os.path.join(out, f"{basename}.nc")
                    progress.update(task, description=f"Processing {basename}...")

                    try:
                        drw = ac.open_drawing(f)
                        if drw is None:
                            results.append(
                                {"file": f, "status": "FAIL", "error": "Could not open drawing"}
                            )
                            if not continue_on_error:
                                raise typer.Exit(code=1)  # noqa: TRY301
                            continue

                        drw.output_nc(nc_path)
                        drw.save_as(os.path.join(out, f"{basename}.amd"))
                        results.append({"file": f, "status": "OK", "error": ""})

                    except Exception as ex:
                        results.append({"file": f, "status": "FAIL", "error": str(ex)})
                        if not continue_on_error:
                            console.print(f"[red]FAIL:[/red] {f}: {ex}")
                            raise typer.Exit(code=1) from ex

                    progress.advance(task)

                ok_count = sum(1 for r in results if r["status"] == "OK")
                fail_count = sum(1 for r in results if r["status"] == "FAIL")
                console.print()
                console.print("[bold]Batch Summary[/bold]")
                console.print(f"  [green]OK:[/green] {ok_count}  [red]FAIL:[/red] {fail_count}")
                for r in results:
                    if r["error"]:
                        console.print(f"  [red]  {r['file']}: {r['error']}[/red]")
                console.print(f"[green]Done:[/green] {len(files)} files -> {out}")

    except AlphacamConnectionError as e:
        console.print(f"[red]FAIL:[/red] {e}")
        raise typer.Exit(code=3) from e
    except Exception as e:
        console.print(f"[red]Batch error:[/red] {e}")
        raise typer.Exit(code=1) from e
