from __future__ import annotations

import contextlib
import logging
import queue
import sys
import threading
from collections.abc import Iterator
from typing import Any

from alphacam_cli.com.constants import PROG_IDS

CONNECT_TIMEOUT = 180
_RPC_E_CHANGED_MODE = -2147417850


class AlphacamConnectionError(Exception):
    """Cannot connect to AlphaCAM via COM."""


class AlphacamComError(Exception):
    """COM error during AlphaCAM operation."""

    def __init__(self, message: str, hresult: int | None = None) -> None:
        self.hresult = hresult
        super().__init__(message)


_REMOTE_MODE: bool = False
_REMOTE_HOST: str = "127.0.0.1"
_REMOTE_PORT: int = 8721


def set_remote_mode(host: str | None = None, port: int | None = None) -> None:
    global _REMOTE_MODE, _REMOTE_HOST, _REMOTE_PORT
    _REMOTE_MODE = True
    if host is not None:
        _REMOTE_HOST = host
    if port is not None:
        _REMOTE_PORT = port


def clear_remote_mode() -> None:
    global _REMOTE_MODE
    _REMOTE_MODE = False


def is_remote() -> bool:
    return _REMOTE_MODE


@contextlib.contextmanager
def alphacam_context(
    visible: bool = False,
    prog_id: str | None = None,
    keep_alive: bool = False,
) -> Iterator[Any]:
    if is_remote():
        from alphacam_cli.gateway.client import RemoteSession
        from alphacam_cli.gateway.remote import RemoteApplication

        session = RemoteSession(_REMOTE_HOST, _REMOTE_PORT)
        try:
            session.connect()
            yield RemoteApplication(session)
        finally:
            session.close()
        return

    import pythoncom  # type: ignore[import-untyped]
    import win32com.client as win32  # type: ignore[import-untyped]

    logger = logging.getLogger("alphacam")

    result_queue: queue.Queue[Any] = queue.Queue(maxsize=2)
    stop_event = threading.Event()

    def sta_worker() -> None:
        try:
            com_initialized = False
            ac_app = None
            owned = False
            try:
                pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
                com_initialized = True
            except pythoncom.com_error as e:
                if e.hresult != _RPC_E_CHANGED_MODE:
                    result_queue.put(("error", e))
                    return

            try:
                ids = [prog_id] if prog_id else PROG_IDS
                last_error: Exception | None = None
                for pid in ids:
                    try:
                        ac_app = win32.GetActiveObject(pid)
                        break
                    except Exception:
                        try:
                            ac_app = win32.Dispatch(pid)
                            owned = True
                            break
                        except Exception as e:
                            last_error = e

                if ac_app is None:
                    exc = AlphacamConnectionError(
                        f"Cannot connect to AlphaCAM. Tried ProgIDs: {ids}\n"
                        "Check: (1) AlphaCAM installed, (2) license active, "
                        "(3) another process not blocking"
                    )
                    if last_error is not None:
                        exc.__cause__ = last_error
                    result_queue.put(("error", exc))
                    return

                with contextlib.suppress(Exception):
                    ac_app.Visible = visible  # type: ignore[attr-defined]

                if sys.platform == "win32":
                    try:
                        stream = pythoncom.CoMarshalInterThreadInterfaceInStream(
                            pythoncom.IID_IDispatch,
                            ac_app,  # type: ignore[arg-type]
                        )
                    except (TypeError, ValueError, pythoncom.com_error):
                        result_queue.put(("simple", ac_app, owned))
                    else:
                        result_queue.put(("marshaled", stream, owned))
                else:
                    result_queue.put(("simple", ac_app, owned))

                while not stop_event.is_set():
                    pythoncom.PumpWaitingMessages()
                    stop_event.wait(0.05)

            finally:
                if owned and not keep_alive and ac_app is not None:
                    with contextlib.suppress(Exception):
                        ac_app.Quit()  # type: ignore[attr-defined]
                if com_initialized:
                    pythoncom.CoUninitialize()  # type: ignore[attr-defined]
        except Exception as exc:
            try:
                result_queue.put_nowait(("error", exc))
                logger.warning("STA worker error: %r", exc)
            except queue.Full:
                logger.warning("STA worker error after result delivered: %r", exc)

    thread = threading.Thread(target=sta_worker, daemon=True)
    thread.start()

    try:
        result = result_queue.get(timeout=CONNECT_TIMEOUT)
    except queue.Empty:
        stop_event.set()
        thread.join(timeout=5)
        raise AlphacamConnectionError(  # noqa: TRY003
            f"Timed out after {CONNECT_TIMEOUT}s connecting to AlphaCAM.\n"
            "Check: (1) AlphaCAM is not hung, "
            "(2) license server is responding"
        ) from None

    status = result[0]
    if status == "error":
        stop_event.set()
        thread.join(timeout=5)
        raise result[1]  # type: ignore[arg-type]

    ac_app = result[1]
    if status == "marshaled":
        try:
            raw = pythoncom.CoGetInterfaceAndReleaseStream(result[1], pythoncom.IID_IDispatch)
            ac_app = win32.Dispatch(raw)
        except Exception:
            with contextlib.suppress(Exception):
                pythoncom.CoReleaseMarshalData(result[1])
            stop_event.set()
            thread.join(timeout=5)
            raise

    try:
        yield ac_app

    except AlphacamConnectionError:
        raise
    except pythoncom.com_error as e:  # type: ignore[attr-defined]
        raise AlphacamComError(  # noqa: TRY003
            f"COM error: {e.strerror}", hresult=e.hresult
        ) from e
    except Exception as e:
        raise AlphacamComError(f"Unexpected COM error: {e}") from e  # noqa: TRY003
    finally:
        stop_event.set()
        thread.join(timeout=5)
        with contextlib.suppress(queue.Empty):
            while True:
                late = result_queue.get_nowait()
                if late[0] == "error":
                    logger.error("STA thread: late error after yield", exc_info=late[1])
