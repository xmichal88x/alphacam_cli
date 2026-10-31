from __future__ import annotations

import logging
import pathlib
import sys
import threading
import types
from typing import Any
from unittest.mock import MagicMock

import pytest

import alphacam_cli.gateway.server as server_module
import alphacam_cli.gateway.service as service_module
from alphacam_cli.gateway.server import GatewayServer


def _install_com(
    monkeypatch: pytest.MonkeyPatch,
    get_active: Any,
    launch_app: Any | None = None,
) -> Any:
    """Install fake pythoncom/win32com modules; returns the launched app."""
    app = launch_app if launch_app is not None else MagicMock()
    app.ActiveDrawing = None

    class FakeComError(Exception):
        hresult = 0

    pythoncom = types.ModuleType("pythoncom")
    pythoncom.COINIT_APARTMENTTHREADED = 2  # type: ignore[attr-defined]
    pythoncom.com_error = FakeComError  # type: ignore[attr-defined]
    pythoncom.CoInitializeEx = MagicMock()  # type: ignore[attr-defined]
    pythoncom.CoUninitialize = MagicMock()  # type: ignore[attr-defined]
    pythoncom.PumpWaitingMessages = MagicMock()  # type: ignore[attr-defined]

    gencache = MagicMock()
    gencache.EnsureDispatch.return_value = app
    client_mod = types.ModuleType("win32com.client")
    client_mod.GetActiveObject = get_active  # type: ignore[attr-defined]
    client_mod.gencache = gencache  # type: ignore[attr-defined]
    win32com = types.ModuleType("win32com")
    win32com.client = client_mod  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client_mod)
    monkeypatch.setitem(sys.modules, "win32com.client.gencache", gencache)
    return app


def _run_sta_once(server: GatewayServer) -> None:
    server._running.set()
    server._sta_loop()
    server._running.clear()
    assert server._sta_thread is not None
    server._sta_thread.join(timeout=2.0)
    assert not server._sta_thread.is_alive()


def _pids_sequence(monkeypatch: pytest.MonkeyPatch, *snapshots: list[int] | None) -> None:
    calls = iter(snapshots)
    monkeypatch.setattr(server_module, "_acam_processes", lambda: next(calls))


@pytest.fixture(autouse=True)
def _fast_quit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPHACAM_GATEWAY_QUIT_ON_STOP", raising=False)
    monkeypatch.setattr(server_module.time, "sleep", lambda _delay: None)


# --- A. persistent file log -------------------------------------------------


def test_add_file_handler_creates_dir_and_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    log_dir = tmp_path / "nested" / "logs"
    monkeypatch.setenv("ALPHACAM_GATEWAY_LOG_DIR", str(log_dir))
    logger = logging.getLogger("test.gateway.filelog")

    handler = service_module._add_file_handler(logger)

    try:
        assert handler is not None
        assert isinstance(handler, service_module.RotatingFileHandler)
        assert handler.maxBytes == 10 * 1024 * 1024
        assert handler.backupCount == 5
        assert log_dir.is_dir()
        assert service_module._log_file_path() == str(log_dir / "gateway.log")
        assert pathlib.Path(service_module._log_file_path()).exists()
        assert handler.formatter is not None
        assert handler.formatter._fmt == service_module._LOG_FORMAT
    finally:
        if handler is not None:
            logger.removeHandler(handler)
            handler.close()


def test_add_file_handler_failure_does_not_raise(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    monkeypatch.setenv("ALPHACAM_GATEWAY_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(service_module.os, "makedirs", MagicMock(side_effect=OSError("denied")))
    logger = logging.getLogger("test.gateway.filelog.fail")
    before = list(logger.handlers)

    assert service_module._add_file_handler(logger) is None
    assert logger.handlers == before


def test_main_wires_file_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    add_handler = MagicMock()
    monkeypatch.setattr(service_module, "_add_file_handler", add_handler)
    monkeypatch.setattr(service_module, "run_server", MagicMock())
    monkeypatch.setattr(sys, "argv", ["service", "127.0.0.1", "9999"])

    service_module.main()

    add_handler.assert_called_once_with(logging.getLogger())


# --- B. deterministic PID ownership ----------------------------------------


def test_attach_ok_with_no_process_before_is_owned_zombie_rot(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _pids_sequence(monkeypatch, [], [], [])
    _install_com(monkeypatch, get_active=MagicMock(return_value=object()))

    with caplog.at_level(logging.INFO, logger="alphacam.gateway"):
        gw = GatewayServer()
        _run_sta_once(gw)

    assert gw._owned is True
    assert gw._owned_pid is None
    assert "AlphaCAM ownership unknown (pid=None)" in caplog.text


def test_attach_ok_with_existing_pid_is_not_owned(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _pids_sequence(monkeypatch, [123], [123])
    _install_com(monkeypatch, get_active=MagicMock(return_value=object()))

    with caplog.at_level(logging.INFO, logger="alphacam.gateway"):
        gw = GatewayServer()
        _run_sta_once(gw)

    assert gw._owned is False
    assert gw._owned_pid is None
    assert "AlphaCAM attached existing (pid=123, owned=False)" in caplog.text


def test_attach_failure_launches_new_instance_and_records_pid(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _pids_sequence(monkeypatch, [], [456], [])
    _install_com(monkeypatch, get_active=MagicMock(side_effect=Exception("no ROT")))

    with caplog.at_level(logging.INFO, logger="alphacam.gateway"):
        gw = GatewayServer()
        _run_sta_once(gw)

    assert gw._owned is True
    assert gw._owned_pid == 456
    assert "AlphaCAM launched (pid=456, owned=True)" in caplog.text


def test_launch_with_ambiguous_owned_pid_is_unknown(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _pids_sequence(monkeypatch, [], [456, 789], [])
    _install_com(monkeypatch, get_active=MagicMock(side_effect=Exception("no ROT")))

    with caplog.at_level(logging.INFO, logger="alphacam.gateway"):
        gw = GatewayServer()
        _run_sta_once(gw)

    assert gw._owned is True
    assert gw._owned_pid is None
    assert "AlphaCAM ownership unknown (pid=None)" in caplog.text


def test_attach_with_dead_com_object_relaunches(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class DeadApp:
        @property
        def Name(self) -> str:  # noqa: N802
            raise RuntimeError

        def __setattr__(self, name: str, value: Any) -> None:
            object.__setattr__(self, name, value)

    dead_app = DeadApp()
    _pids_sequence(monkeypatch, [], [321], [])
    _install_com(
        monkeypatch,
        get_active=MagicMock(return_value=object()),
        launch_app=dead_app,
    )

    with caplog.at_level(logging.INFO, logger="alphacam.gateway"):
        gw = GatewayServer()
        _run_sta_once(gw)

    assert gw._owned is True
    assert gw._owned_pid == 321
    assert "AlphaCAM launched (pid=321, owned=True)" in caplog.text


# --- C. guaranteed cleanup of the owned instance ---------------------------


def test_stop_quit_exit_does_not_terminate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = MagicMock()
    app.ActiveDrawing = None
    terminate = MagicMock()
    monkeypatch.setattr(server_module, "_terminate_pid", terminate)
    monkeypatch.setattr(server_module, "_wait_for_pid_exit", MagicMock(return_value=True))
    logger = logging.getLogger("alphacam.gateway")

    server_module._release_ac_app(app, True, logger, 999)

    app.Quit.assert_called_once_with()
    terminate.assert_not_called()


def test_stop_timeout_terminates_only_owned_pid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = MagicMock()
    app.ActiveDrawing = None
    terminate = MagicMock(return_value=True)
    wait = MagicMock(return_value=False)
    monkeypatch.setattr(server_module, "_terminate_pid", terminate)
    monkeypatch.setattr(server_module, "_wait_for_pid_exit", wait)
    logger = logging.getLogger("alphacam.gateway")

    server_module._release_ac_app(app, True, logger, 777)

    wait.assert_called_once_with(777)
    terminate.assert_called_once_with(777, logger)
    app.Quit.assert_called_once_with()


def test_stop_unknown_pid_logs_critical_without_killing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    app = MagicMock()
    app.ActiveDrawing = None
    terminate = MagicMock()
    monkeypatch.setattr(server_module, "_terminate_pid", terminate)
    monkeypatch.setattr(server_module, "_acam_processes", lambda: [42])
    logger = logging.getLogger("alphacam.gateway")

    with caplog.at_level(logging.CRITICAL, logger="alphacam.gateway"):
        server_module._release_ac_app(app, True, logger, None)

    terminate.assert_not_called()
    assert "AlphaCAM orphan left (pid unknown)" in caplog.text


def test_sta_loop_passes_owned_pid_to_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pids_sequence(monkeypatch, [], [555], [])
    _install_com(monkeypatch, get_active=MagicMock(side_effect=Exception("no ROT")))
    release = MagicMock()
    monkeypatch.setattr(server_module, "_release_ac_app", release)

    gw = GatewayServer()
    _run_sta_once(gw)

    assert release.call_args.args[1] is True
    assert release.call_args.args[3] == 555


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.now += delay


def _install_fake_clock(monkeypatch: pytest.MonkeyPatch) -> _FakeClock:
    clock = _FakeClock()
    monkeypatch.setattr(server_module.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(server_module.time, "sleep", clock.sleep)
    return clock


def test_stop_pid_exits_before_timeout_no_terminate(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    clock = _install_fake_clock(monkeypatch)
    app = MagicMock()
    app.ActiveDrawing = None
    terminate = MagicMock()
    monkeypatch.setattr(server_module, "_terminate_pid", terminate)
    monkeypatch.setattr(server_module, "_acam_processes", lambda: [999] if clock.now < 0.3 else [])

    with caplog.at_level(logging.INFO, logger="alphacam.gateway"):
        server_module._release_ac_app(app, True, logging.getLogger("alphacam.gateway"), 999)

    terminate.assert_not_called()
    assert "AlphaCAM owned process pid=999 exited after Quit" in caplog.text
    assert clock.now <= 1.5
    assert clock.now == pytest.approx(0.3)
    assert clock.sleeps == [0.1] * 3


def test_stop_pid_persists_terminates_owned_pid_only(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    clock = _install_fake_clock(monkeypatch)
    app = MagicMock()
    app.ActiveDrawing = None
    terminate = MagicMock(return_value=True)
    monkeypatch.setattr(server_module, "_terminate_pid", terminate)
    monkeypatch.setattr(server_module, "_acam_processes", lambda: [777])

    with caplog.at_level(logging.WARNING, logger="alphacam.gateway"):
        server_module._release_ac_app(app, True, logging.getLogger("alphacam.gateway"), 777)

    terminate.assert_called_once_with(777, logging.getLogger("alphacam.gateway"))
    assert "AlphaCAM did not exit after Quit; terminated owned pid=777" in caplog.text
    assert clock.now <= 1.5
    assert clock.now == pytest.approx(0.5)
    assert clock.sleeps == [0.1] * 5


def test_stop_waits_for_sta_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    gw = GatewayServer()
    started = threading.Event()
    cleanup_done = threading.Event()

    def worker() -> None:
        started.set()
        threading.Event().wait(0.2)
        cleanup_done.set()

    thread = threading.Thread(target=worker, daemon=True)
    gw._sta_thread = thread
    thread.start()
    assert started.wait(1.0)

    gw.stop()

    assert cleanup_done.is_set()
    assert not thread.is_alive()
