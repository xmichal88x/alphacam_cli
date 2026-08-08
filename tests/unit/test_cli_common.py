from __future__ import annotations

import typer
from typer.testing import CliRunner

from alphacam_cli.cli.common import handle_com_errors, path_basename
from alphacam_cli.com.manager import AlphacamComError, AlphacamConnectionError

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

    return app
