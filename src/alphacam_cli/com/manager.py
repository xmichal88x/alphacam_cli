from __future__ import annotations

import contextlib
import threading
from collections.abc import Iterator
from typing import Any

from alphacam_cli.com.constants import PROG_IDS


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

    - Main thread: CoInitialize handled automatically by pythoncom (sys.coinit_flags)
    - Worker threads: would need explicit CoInitializeEx (future)
    - ALWAYS calls Quit() and clears COM references

    Yields the raw COM dispatch object.
    """
    import pythoncom  # type: ignore[import-untyped]
    import win32com.client as win32  # type: ignore[import-untyped]

    _needs_co_uninit = False
    ac_app = None

    if threading.current_thread() is not threading.main_thread():
        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        _needs_co_uninit = True

    try:
        ids = [prog_id] if prog_id else PROG_IDS
        last_error: Exception | None = None

        for pid in ids:
            try:
                ac_app = win32.gencache.EnsureDispatch(pid)  # type: ignore[attr-defined]
                break
            except Exception as e:
                last_error = e
                continue

        if ac_app is None:
            raise AlphacamConnectionError(  # noqa: TRY301, TRY003
                f"Cannot connect to AlphaCAM. Tried ProgIDs: {ids}\n"
                "Check: (1) AlphaCAM installed, (2) license active, "
                "(3) another process not blocking"
            ) from last_error

        ac_app.Visible = visible  # type: ignore[attr-defined]
        yield ac_app

    except AlphacamConnectionError:
        raise
    except pythoncom.com_error as e:  # type: ignore[attr-defined]
        hresult = e.hresult  # type: ignore[union-attr]
        raise AlphacamComError(f"COM error: {e.strerror}", hresult=hresult) from e  # noqa: TRY003  # type: ignore[attr-defined]
    except Exception as e:
        raise AlphacamComError(f"Unexpected COM error: {e}") from e  # noqa: TRY003
    finally:
        if ac_app is not None:
            with contextlib.suppress(Exception):
                ac_app.Quit()  # type: ignore[attr-defined]
            ac_app = None

        if _needs_co_uninit:
            with contextlib.suppress(Exception):
                pythoncom.CoUninitialize()  # type: ignore[attr-defined]
