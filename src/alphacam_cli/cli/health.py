from __future__ import annotations

import json
from typing import Any, NoReturn

import typer

from alphacam_cli.cli.common import require_platform
from alphacam_cli.com.manager import AlphacamComError, AlphacamConnectionError, alphacam_context

app = typer.Typer(help="AlphaCAM health check (gateway + COM process)")


def _emit_error(
    error: str, *, code: int, hresult: int | None = None, include_hresult: bool = False
) -> NoReturn:
    payload: dict[str, Any] = {"ok": False, "error": error}
    if include_hresult:
        payload["hresult"] = hresult
    typer.echo(json.dumps(payload))
    raise typer.Exit(code=code)


@app.command()
def health() -> None:
    """Zwraca JSON: ok=true gdy AlphaCAM żyje (COM); exit 0/1/3/4."""
    try:
        require_platform()
        with alphacam_context(visible=False) as raw:
            from alphacam_cli.core.application import Application
            from alphacam_cli.gateway.remote import RemoteApplication

            if isinstance(raw, RemoteApplication):
                result = raw.health()
            else:
                result = {"ok": True, "version": str(Application(raw).version)}
    except AlphacamConnectionError as e:
        _emit_error(str(e), code=3)
    except AlphacamComError as e:
        _emit_error(str(e), code=4, hresult=e.hresult, include_hresult=True)
    except typer.Exit as e:
        if e.exit_code:
            _emit_error("platform check failed", code=e.exit_code)
        raise
    except Exception as e:
        _emit_error(str(e), code=1)

    typer.echo(json.dumps(result))
    if not result.get("ok"):
        raise typer.Exit(code=1)
