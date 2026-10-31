from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from alphacam_cli.cli.common import handle_com_errors, path_basename
from alphacam_cli.com.manager import AlphacamComError, AlphacamConnectionError
from alphacam_cli.gateway.client import (
    RemoteComError,
    RemoteConnectionError,
    RemoteProtocolError,
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
