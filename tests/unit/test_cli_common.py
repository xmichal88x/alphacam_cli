from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from alphacam_cli.cli.common import handle_com_errors, path_basename
from alphacam_cli.com.manager import AlphacamComError, AlphacamConnectionError
from alphacam_cli.gateway import client as client_module
from alphacam_cli.gateway.client import (
    RemoteComError,
    RemoteConnectionError,
    RemoteProtocolError,
    RemoteServerError,
    RemoteSession,
)
from alphacam_cli.main import app as main_app

runner = CliRunner()


def test_path_basename_windows() -> None:
    assert path_basename(r"C:\temp\parts\part1.amd") == "part1.amd"


def test_path_basename_forward_slash() -> None:
    assert path_basename("/temp/parts/part1.amd") == "part1.amd"


def test_path_basename_mixed() -> None:
    assert path_basename(r"C:\temp/parts\part1.amd") == "part1.amd"


def test_path_basename_bare_file() -> None:
    assert path_basename("part1.amd") == "part1.amd"


def test_handle_com_errors_success() -> None:
    app = _make_app(0)

    result = runner.invoke(app, [])
    assert result.exit_code == 0


def test_handle_com_errors_connection_error() -> None:
    app = _make_app(1)

    result = runner.invoke(app, [])
    assert result.exit_code == 3
    assert "Connection Error" in result.stderr


def test_handle_com_errors_com_error() -> None:
    app = _make_app(2)

    result = runner.invoke(app, [])
    assert result.exit_code == 4
    assert "COM Error" in result.stderr


def test_handle_com_errors_generic_error() -> None:
    app = _make_app(3)

    result = runner.invoke(app, [])
    assert result.exit_code == 1


def _make_app(error_type: int) -> typer.Typer:
    app = typer.Typer()

    @app.command()
    @handle_com_errors
    def cmd() -> None:
        if error_type == 1:
            raise AlphacamConnectionError("No connection")  # noqa: TRY003
        elif error_type == 2:
            raise AlphacamComError("COM failed", hresult=-2147221164)  # noqa: TRY003
        elif error_type == 3:
            raise ValueError("Something bad")  # noqa: TRY003
        elif error_type == 4:
            raise RemoteConnectionError("No remote connection")  # noqa: TRY003
        elif error_type == 5:
            raise RemoteComError("Remote COM failed", hresult=-32000)  # noqa: TRY003
        elif error_type == 6:
            raise RemoteProtocolError("Remote protocol failed")  # noqa: TRY003
        elif error_type == 7:
            raise RemoteServerError("Internal error")  # noqa: TRY003

    return app


def test_handle_com_errors_remote_connection_error() -> None:
    app = _make_app(4)

    result = runner.invoke(app, [])
    assert result.exit_code == 3
    assert "Connection Error" in result.stderr


def test_handle_com_errors_remote_com_error() -> None:
    app = _make_app(5)

    result = runner.invoke(app, [])
    assert result.exit_code == 4
    assert "COM Error" in result.stderr
    assert "HRESULT" in result.stderr


def test_handle_com_errors_remote_protocol_error() -> None:
    app = _make_app(6)

    result = runner.invoke(app, [])
    assert result.exit_code == 1


def test_handle_com_errors_remote_server_error_exits_1() -> None:
    app = _make_app(7)

    result = runner.invoke(app, [])
    assert result.exit_code == 1
    assert "COM Error" not in result.stderr


def test_cli_internal_error_code_32603_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    session = RemoteSession()
    session._sock = MagicMock()
    monkeypatch.setattr(
        client_module,
        "read_frame",
        lambda _sock: {"id": 1, "error": {"code": -32603, "message": "Internal error"}},
    )

    app = typer.Typer()

    @app.command()
    @handle_com_errors
    def cmd() -> None:
        session._call("ping")

    result = runner.invoke(app, [])

    assert result.exit_code == 1
    assert "Internal error" in result.stderr


@contextmanager
def _fake_alphacam_context(visible: bool = False, prog_id: str | None = None) -> Iterator[object]:
    _ = visible, prog_id
    yield object()


@pytest.mark.parametrize(
    ("error", "expected_exit"),
    [
        (RemoteConnectionError("down"), 3),
        (RemoteComError("COM failed", hresult=-32000), 4),
        (RemoteProtocolError("protocol failed"), 1),
        (RemoteServerError("internal failed"), 1),
    ],
)
def test_drawing_info_maps_remote_errors_to_exit_codes(
    error: Exception, expected_exit: int
) -> None:
    with (
        patch("alphacam_cli.cli.drawing.require_platform"),
        patch("alphacam_cli.cli.drawing.alphacam_context", _fake_alphacam_context),
        patch("alphacam_cli.cli.drawing.resolve_app", side_effect=error),
    ):
        result = runner.invoke(main_app, ["drawing", "info"])

    assert result.exit_code == expected_exit


@pytest.mark.parametrize(
    ("hresult", "rendered"),
    [
        (-32000, "0xFFFF8300"),
        (0x80004005, "0x80004005"),
    ],
)
def test_handle_com_errors_formats_hresult_as_unsigned_32bit(hresult: int, rendered: str) -> None:
    app = typer.Typer()

    @app.command()
    @handle_com_errors
    def cmd() -> None:
        raise AlphacamComError("COM failed", hresult=hresult)  # noqa: TRY003

    result = runner.invoke(app, [])

    assert result.exit_code == 4
    assert rendered in result.stderr
