from __future__ import annotations

import platform as _platform
import sys

import typer

try:
    import win32com  # type: ignore[import-untyped]
except ImportError:
    win32com = None  # type: ignore[assignment]

from alphacam_cli.cli.common import console, get_visible
from alphacam_cli.com.constants import PROG_IDS
from alphacam_cli.com.manager import alphacam_context
from alphacam_cli.core.application import Application

app = typer.Typer(help="System diagnostics for AlphaCAM")


@app.command()
def diagnose() -> None:
    """Run system diagnostics for AlphaCAM connectivity."""
    console.print("[bold cyan]AlphaCAM Diagnostics[/bold cyan]")

    # 1. Platform info
    console.print(f"\\[INFO] Platform: {_platform.platform()}")
    console.print(f"\\[INFO] Python: {sys.version.split()[0]}")

    if win32com is None:
        pywin32_ver = "NOT INSTALLED"
    else:
        pywin32_ver = getattr(win32com, "__version__", "unknown")
    console.print(f"\\[INFO] pywin32: {pywin32_ver}")

    # 2. Try COM connection through all known ProgIDs
    for prog_id in PROG_IDS:
        try:
            with alphacam_context(visible=get_visible(), prog_id=prog_id) as raw:
                ac = Application(raw)
                console.print(f"\\[OK]   COM connection: {prog_id}")
                console.print(f"\\[INFO] AlphaCAM: {ac.version} ({ac.module_type})")

                # 3. Drawing test
                drw = ac.create_temp_drawing()
                if drw is not None:
                    console.print("\\[OK]   Drawing: CreateTempDrawing OK")
                else:
                    console.print("\\[WARN] Drawing: CreateTempDrawing returned None")

                # 4. Tool library
                files = ac.find_tool_files()
                console.print(f"\\[OK]   Tool library: {len(files)} tools found")

                # 5. MillData
                try:
                    ac.create_mill_data()
                    console.print("\\[OK]   MillData: OK")
                except Exception:
                    console.print(
                        "\\[WARN] MillData: create failed (no active drawing or other error)"
                    )

                return  # Success with first ProgID

        except Exception:
            console.print(f"\\[FAIL] COM connection: {prog_id}")
            continue

    console.print("[red]FAIL:[/red] No AlphaCAM COM connection available")
    raise typer.Exit(code=1)
