from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from alphacam_cli.cli.health import app
from alphacam_cli.gateway.client import RemoteComError, RemoteConnectionError
from alphacam_cli.gateway.remote import RemoteApplication

runner = CliRunner()


@contextmanager
def _remote_context() -> Iterator[MagicMock]:
    raw = MagicMock(spec=RemoteApplication)
    raw.health.return_value = {"ok": True, "version": "9.0.1"}

    @contextmanager
    def fake_context(visible: bool = False) -> Iterator[MagicMock]:
        yield raw

    with (
        patch("alphacam_cli.cli.health.require_platform"),
        patch("alphacam_cli.cli.health.alphacam_context", fake_context),
    ):
        yield raw


def _json_stdout(output: str) -> dict[str, object]:
    return json.loads(output)


def _assert_no_traceback(result: object) -> None:
    output = getattr(result, "output", "")
    stderr = getattr(result, "stderr", "")
    assert "Traceback" not in output
    assert "Traceback" not in stderr


def test_health_success_returns_json_exit_0() -> None:
    with _remote_context():
        result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert _json_stdout(result.stdout) == {"ok": True, "version": "9.0.1"}
    _assert_no_traceback(result)


def test_health_not_ok_returns_json_exit_1() -> None:
    with _remote_context() as raw:
        raw.health.return_value = {"ok": False, "error": "AlphaCAM not attached"}
        result = runner.invoke(app, [])
    assert result.exit_code == 1
    payload = _json_stdout(result.stdout)
    assert payload["ok"] is False
    assert payload["error"] == "AlphaCAM not attached"
    _assert_no_traceback(result)


def test_health_connection_error_returns_json_exit_3() -> None:
    @contextmanager
    def failing_context(visible: bool = False) -> Iterator[MagicMock]:
        raise RemoteConnectionError("cannot connect to 192.168.100.60:9999")  # noqa: TRY003
        yield MagicMock()  # pragma: no cover - unreachable

    with (
        patch("alphacam_cli.cli.health.require_platform"),
        patch("alphacam_cli.cli.health.alphacam_context", failing_context),
    ):
        result = runner.invoke(app, [])

    assert result.exit_code == 3
    payload = _json_stdout(result.stdout)
    assert payload == {"ok": False, "error": "cannot connect to 192.168.100.60:9999"}
    _assert_no_traceback(result)


def test_health_com_error_returns_json_with_hresult_exit_4() -> None:
    with _remote_context() as raw:
        raw.health.side_effect = RemoteComError("COM failure", hresult=-2147467259)
        result = runner.invoke(app, [])

    assert result.exit_code == 4
    payload = _json_stdout(result.stdout)
    assert payload == {"ok": False, "error": "COM failure", "hresult": -2147467259}
    _assert_no_traceback(result)


def test_health_com_error_without_hresult_returns_null() -> None:
    with _remote_context() as raw:
        raw.health.side_effect = RemoteComError("COM failure")
        result = runner.invoke(app, [])

    assert result.exit_code == 4
    payload = _json_stdout(result.stdout)
    assert payload == {"ok": False, "error": "COM failure", "hresult": None}
    _assert_no_traceback(result)


def test_health_unexpected_error_returns_json_exit_1() -> None:
    @contextmanager
    def failing_context(visible: bool = False) -> Iterator[MagicMock]:
        raise RuntimeError("unexpected")
        yield MagicMock()  # pragma: no cover - unreachable

    with (
        patch("alphacam_cli.cli.health.require_platform"),
        patch("alphacam_cli.cli.health.alphacam_context", failing_context),
    ):
        result = runner.invoke(app, [])

    assert result.exit_code == 1
    assert _json_stdout(result.stdout) == {"ok": False, "error": "unexpected"}
    _assert_no_traceback(result)
