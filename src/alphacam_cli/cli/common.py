from __future__ import annotations

import sys
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

import typer
from rich.console import Console

from alphacam_cli.com.manager import AlphacamComError, AlphacamConnectionError

console: Console = Console(stderr=True)

# Global state set by main.py callback
_visible: bool = False


def get_visible() -> bool:
    return _visible


def set_visible(value: bool) -> None:
    global _visible
    _visible = value


def require_platform() -> None:
    """Check we're on Windows before trying COM operations."""
    if sys.platform != "win32":
        console.print(
            "[red]Error:[/red] AlphaCAM CLI requires Windows + AlphaCAM software.\n"
            f"Detected platform: [yellow]{sys.platform}[/yellow]"
        )
        raise typer.Exit(code=1)


F = TypeVar("F", bound=Callable[..., Any])


def handle_com_errors(func: F) -> F:
    """Decorator that wraps CLI commands with standardized COM error handling.

    Exit codes:
    3 - COM connection error
    4 - COM runtime error (with HRESULT)
    1 - General error
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        try:
            func(*args, **kwargs)
        except AlphacamComError as e:
            console.print(f"[red]COM Error:[/red] {e}")
            if e.hresult:
                console.print(f"      HRESULT: [yellow]0x{e.hresult:08X}[/yellow]")
            console.print("      [dim]Try restarting AlphaCAM or check the connection.[/dim]")
            raise typer.Exit(code=4) from e
        except AlphacamConnectionError as e:
            console.print(f"[red]Connection Error:[/red] {e}")
            console.print("      [dim]Make sure AlphaCAM is installed and licensed.[/dim]")
            raise typer.Exit(code=3) from e
        except typer.Exit as e:
            if e.exit_code != 0:
                console.print(f"[dim]Exiting with code {e.exit_code}[/dim]")
            raise
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=1) from e

    return wrapper  # type: ignore[return-value]
