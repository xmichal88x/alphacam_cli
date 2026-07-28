from __future__ import annotations

import glob
import os

import typer
from rich.table import Table

from alphacam_cli.cli.common import _visible, console, require_platform
from alphacam_cli.com.manager import AlphacamConnectionError, alphacam_context
from alphacam_cli.core.application import Application

app = typer.Typer(help="Post-processor operations")


@app.command()
def list() -> None:
    """List available post-processors in the AlphaCAM posts directory."""
    try:
        require_platform()
        with alphacam_context(visible=_visible) as raw:
            ac = Application(raw)
            posts_dir = os.path.join(ac.licomdir_path, "posts")

            if not os.path.isdir(posts_dir):
                console.print(f"[red]Posts directory not found: {posts_dir}[/red]")
                raise typer.Exit(code=1)  # noqa: TRY301

            # Post files can be .vba or .dll
            files = sorted(
                glob.glob(os.path.join(posts_dir, "*.vba"))
                + glob.glob(os.path.join(posts_dir, "*.dll"))
            )
            # Also try licomdat/posts
            posts_dir2 = os.path.join(ac.licomdat_path, "licomdat", "posts")
            if os.path.isdir(posts_dir2):
                files.extend(
                    glob.glob(os.path.join(posts_dir2, "*.vba"))
                    + glob.glob(os.path.join(posts_dir2, "*.dll"))
                )
            files = sorted(set(files))

            if not files:
                console.print("[yellow]No post-processors found[/yellow]")
                raise typer.Exit(code=0)  # noqa: TRY301

            t = Table(title=f"Post-Processors ({len(files)} found)")
            t.add_column("Name", style="cyan")
            t.add_column("Path", style="green")
            for f in files:
                t.add_row(os.path.basename(f), f)
            console.print(t)

    except AlphacamConnectionError as e:
        console.print(f"[red]FAIL:[/red] {e}")
        raise typer.Exit(code=3) from e
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
