from __future__ import annotations

import contextlib
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any

from alphacam_cli.com.constants import PROG_IDS

CONNECT_TIMEOUT = 30  # seconds — max time to wait for COM connection


class AlphacamConnectionError(Exception):
    """Cannot connect to AlphaCAM via COM."""


class AlphacamComError(Exception):
    """COM error during AlphaCAM operation."""

    def __init__(self, message: str, hresult: int | None = None) -> None:
        self.hresult = hresult
        super().__init__(message)


_dispatch_lock = threading.Lock()


@contextlib.contextmanager
def alphacam_context(
    visible: bool = False,
    prog_id: str | None = None,
) -> Iterator[Any]:
    """
    Context manager for AlphaCAM COM connection.

    - Main thread: CoInitialize handled automatically by pythoncom (sys.coinit_flags)
    - Worker threads: CoInitializeEx is called automatically (non-main thread detection)
    - Only calls Quit() if WE created the instance (not when attaching to a running one)
    - The yielded dispatch object is ONLY valid inside the with block

    Yields the raw COM dispatch object.
    """
    import pythoncom  # type: ignore[import-untyped]
    import win32com.client as win32  # type: ignore[import-untyped]

    _needs_co_uninit = False
    ac_app = None
    _owned = False

    if threading.current_thread() is not threading.main_thread():
        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
            _needs_co_uninit = True
        except pythoncom.com_error as e:  # type: ignore[attr-defined]
            if e.hresult == -2147417830:  # RPC_E_CHANGED_MODE
                _needs_co_uninit = False
            else:
                raise

    try:
        ids = [prog_id] if prog_id else PROG_IDS

        def _connect() -> tuple[Any, bool]:
            needs_uninit = False
            try:
                pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
                needs_uninit = True
            except pythoncom.com_error as e:  # type: ignore[attr-defined]
                if e.hresult != -2147417830:  # RPC_E_CHANGED_MODE
                    raise

            try:
                last_error: Exception | None = None
                for pid in ids:
                    try:
                        with _dispatch_lock:
                            ac_app = win32.GetActiveObject(pid)
                        return ac_app, False  # noqa: TRY300
                    except Exception:
                        try:
                            with _dispatch_lock:
                                ac_app = win32.Dispatch(pid)
                            return ac_app, True  # noqa: TRY300
                        except Exception as e:
                            last_error = e
                            continue
                raise AlphacamConnectionError(  # noqa: TRY301, TRY003
                    f"Cannot connect to AlphaCAM. Tried ProgIDs: {ids}\n"
                    "Check: (1) AlphaCAM installed, (2) license active, "
                    "(3) another process not blocking"
                ) from last_error
            finally:
                if needs_uninit:
                    with contextlib.suppress(Exception):
                        pythoncom.CoUninitialize()  # type: ignore[attr-defined]

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_connect)
            try:
                ac_app, _owned = future.result(timeout=CONNECT_TIMEOUT)
            except FutureTimeoutError:
                raise AlphacamConnectionError(  # noqa: TRY003
                    f"Timed out after {CONNECT_TIMEOUT}s connecting to AlphaCAM.\n"
                    "Check: (1) AlphaCAM is not hung, "
                    "(2) license server is responding"
                ) from None

        ac_app.Visible = visible  # type: ignore[attr-defined]
        yield ac_app

    except AlphacamConnectionError:
        raise
    except pythoncom.com_error as e:  # type: ignore[attr-defined]
        raise AlphacamComError(f"COM error: {e.strerror}", hresult=e.hresult) from e  # noqa: TRY003
    except Exception as e:
        raise AlphacamComError(f"Unexpected COM error: {e}") from e  # noqa: TRY003
    finally:
        if ac_app is not None and _owned:
            with contextlib.suppress(Exception):
                ac_app.Quit()  # type: ignore[attr-defined]
        if _needs_co_uninit:
            with contextlib.suppress(Exception):
                pythoncom.CoUninitialize()  # type: ignore[attr-defined]
