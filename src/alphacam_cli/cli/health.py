from __future__ import annotations

import json

import typer

from alphacam_cli.cli.common import require_platform
from alphacam_cli.com.manager import alphacam_context

app = typer.Typer(help="AlphaCAM health check (gateway + COM process)")


@app.command()
def health() -> None:
    """Zwraca JSON: ok=true gdy AlphaCAM żyje (COM); exit 0/1."""
    require_platform()
    with alphacam_context(visible=False) as raw:
        from alphacam_cli.core.application import Application
        from alphacam_cli.gateway.remote import RemoteApplication

        if isinstance(raw, RemoteApplication):
            result = raw.health()
        else:
            result = {"ok": True, "version": str(Application(raw).version)}
    print(json.dumps(result))
    if not result.get("ok"):
        raise typer.Exit(code=1)
