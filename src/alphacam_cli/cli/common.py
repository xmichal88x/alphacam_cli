from __future__ import annotations

import sys

import typer
from rich.console import Console

console = Console(stderr=True)

# Global state set by main.py callback
_visible: bool = False


def require_platform() -> None:
    """Check we're on Windows before trying COM operations."""
    if sys.platform != "win32":
        console.print(
            "[red]Error:[/red] AlphaCAM CLI requires Windows + AlphaCAM software.\n"
            f"Detected platform: [yellow]{sys.platform}[/yellow]"
        )
        raise typer.Exit(code=1)
