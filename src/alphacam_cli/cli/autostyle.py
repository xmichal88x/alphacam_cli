from __future__ import annotations

import typer

from alphacam_cli.cli.common import (
    console,
    get_visible,
    handle_com_errors,
    require_platform,
    resolve_app,
)
from alphacam_cli.com.manager import alphacam_context

app = typer.Typer(help="Auto-style operations (AutoStyles add-in)")


@app.command()
@handle_com_errors
def apply(
    file: str = typer.Argument(..., help="Path to the auto-style file"),
    agq: str | None = typer.Option(
        None, "--agq", help="Geometry query (.agq) to run before applying (pipeline mode)"
    ),
    layer_map: str | None = typer.Option(
        None,
        "--layer-map",
        help="Layer assignments 'NAME:1,2;NAME2:3' (1-based indices; pipeline mode)",
    ),
) -> None:
    """Apply an auto-style file to the active drawing (no dialogs).

    With --agq and/or --layer-map runs the full machining pipeline:
    create/assign layers, run the geometry query, then apply the auto-style.
    """
    require_platform()
    with alphacam_context(visible=get_visible()) as raw:
        ac = resolve_app(raw)
        if agq is not None or layer_map is not None:
            result = ac.machining_pipeline(agq=agq, ara=file, layer_map=layer_map)
            console.print(f"[green]OK:[/green] Auto-style applied: {file}")
            console.print(
                "      Geometries: "
                f"{result['geometries_count']}, ToolPaths: {result['tool_paths_count']}"
            )
            return
        result = ac.auto_style_apply(file)
        applied = str(result.get("file", file))
        console.print(f"[green]OK:[/green] Auto-style applied: {applied}")
