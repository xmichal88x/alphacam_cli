from __future__ import annotations

import contextlib
import queue
import sys
import threading
from collections.abc import Iterator
from typing import Any

from alphacam_cli.com.constants import PROG_IDS

CONNECT_TIMEOUT = 30
_RPC_E_CHANGED_MODE = -2147417850


class AlphacamConnectionError(Exception):
    """Cannot connect to AlphaCAM via COM."""


class AlphacamComError(Exception):
    """COM error during AlphaCAM operation."""

    def __init__(self, message: str, hresult: int | None = None) -> None:
        self.hresult = hresult
        super().__init__(message)


@contextlib.contextmanager
def alphacam_context(
    visible: bool = False,
    prog_id: str | None = None,
) -> Iterator[Any]:
    """
    Context manager for AlphaCAM COM connection.

    Uses a dedicated STA thread with message pump for COM apartment correctness.
    The COM dispatch is created in a long-lived STA thread and marshaled to the
    caller's thread via CoMarshalInterThreadInterfaceInStream. The STA thread
    stays alive (pumping COM messages) until the context exits.

    Yields the raw COM dispatch object.
    """
    import pythoncom  # type: ignore[import-untyped]
    import win32com.client as win32  # type: ignore[import-untyped]

    result_queue: queue.Queue[Any] = queue.Queue()
    stop_event = threading.Event()

    def sta_worker() -> None:
        result_sent = False
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

                # Marshal for cross-thread COM access
                # On Windows with real COM: CoMarshalInterThreadInterfaceInStream
                # On non-Windows or mock dispatch: pass directly
                if sys.platform == "win32":
                    try:
                        stream = pythoncom.CoMarshalInterThreadInterfaceInStream(
                            pythoncom.IID_IDispatch,
                            ac_app,  # type: ignore[arg-type]
                        )
                    except (TypeError, pythoncom.com_error):
                        result_queue.put(("simple", ac_app, owned))
                        result_sent = True
                    else:
                        result_queue.put(("marshaled", stream, owned))
                        result_sent = True
                else:
                    result_queue.put(("simple", ac_app, owned))
                    result_sent = True

                # Message pump — keep STA apartment alive for cross-thread COM
                while not stop_event.is_set():
                    pythoncom.PumpWaitingMessages()
                    stop_event.wait(0.05)

            finally:
                if owned and ac_app is not None:
                    with contextlib.suppress(Exception):
                        ac_app.Quit()  # type: ignore[attr-defined]
                if com_initialized:
                    pythoncom.CoUninitialize()  # type: ignore[attr-defined]
        except Exception as exc:
            import logging

            logger = logging.getLogger("alphacam")
            logger.exception("STA thread in alphacam_context() failed unexpectedly")
            if not result_sent:
                with contextlib.suppress(Exception):
                    result_queue.put(("error", exc))

    thread = threading.Thread(target=sta_worker, daemon=True)
    thread.start()

    try:
        result = result_queue.get(timeout=CONNECT_TIMEOUT)
    except queue.Empty:
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
        ac_app = pythoncom.CoGetInterfaceAndReleaseStream(result[1], pythoncom.IID_IDispatch)

    try:
        ac_app.Visible = visible  # type: ignore[attr-defined]
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
