from __future__ import annotations

import queue
import time
from unittest.mock import MagicMock, patch

import pytest

from alphacam_cli.com.constants import PROG_IDS


def test_prog_ids_defined() -> None:
    assert len(PROG_IDS) == 3
    assert "Ar5axaps.Application" in PROG_IDS
    assert "am5axaps.Application" in PROG_IDS
    assert "aroutaps.Application" in PROG_IDS


def test_module_constants() -> None:
    from alphacam_cli.com.constants import (
        ACAM_OUT_NC_FILE,
        ACAM_POCKET_CONTOUR,
        ACAM_TOOL_BALL,
        ACAM_TOOL_DRILL,
        ACAM_TOOL_SQUARE,
        MODULE_MILL,
        MODULE_ROUTER,
    )

    assert ACAM_TOOL_SQUARE == 0
    assert ACAM_TOOL_BALL == 2
    assert ACAM_TOOL_DRILL == 3
    assert ACAM_POCKET_CONTOUR == 0
    assert ACAM_OUT_NC_FILE == 0
    assert MODULE_MILL == 77
    assert MODULE_ROUTER == 82


def test_alphacam_context_success(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            assert raw is not None


def test_alphacam_context_visible_set(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context(visible=True) as raw:
            assert raw.Visible is True


def test_alphacam_context_custom_prog_id(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context(prog_id="Custom.App") as raw:
            assert raw is not None


def test_alphacam_context_timeout() -> None:
    from alphacam_cli.com.manager import AlphacamConnectionError, alphacam_context

    with patch("alphacam_cli.com.manager.queue.Queue") as mock_queue_cls:
        mock_q = MagicMock()
        mock_q.get.side_effect = queue.Empty
        mock_queue_cls.return_value = mock_q

        with pytest.raises(AlphacamConnectionError, match="Timed out"), alphacam_context():
            pass


def test_alphacam_context_all_prog_ids_fail(mock_com: MagicMock) -> None:
    from alphacam_cli.com.manager import AlphacamConnectionError, alphacam_context

    with mock_com, patch("win32com.client.GetActiveObject") as mock_get:
        mock_get.side_effect = Exception("No active")
        with patch("win32com.client.Dispatch") as mock_dispatch:
            mock_dispatch.side_effect = Exception("Cannot create")

            with pytest.raises(AlphacamConnectionError, match="Cannot connect"), alphacam_context():
                pass


def test_alphacam_context_yields_raw_dispatch(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            raw.Name = "TestApp"
            assert raw.Name == "TestApp"


def test_alphacam_context_owned_true_calls_quit(mock_com: MagicMock) -> None:
    with mock_com:
        from win32com.client import Dispatch

        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context():
            pass
        # _owned=True means Quit was called on the app
        app = Dispatch.return_value
        app.Quit.assert_called_once()


def test_alphacam_context_keep_alive_prevents_quit(mock_com: MagicMock) -> None:
    """When keep_alive=True and owned=True, Quit should NOT be called."""
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context(keep_alive=True):
            pass

        mock_com.return_value.Quit.assert_not_called()


def test_alphacam_context_marshal_failure_cleanup(mock_com: MagicMock) -> None:
    """When CoGetInterfaceAndReleaseStream fails, marshal data is released."""
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        fake_stream = MagicMock()
        with (
            patch("sys.platform", "win32"),
            patch("pythoncom.CoMarshalInterThreadInterfaceInStream", return_value=fake_stream),
            patch(
                "pythoncom.CoGetInterfaceAndReleaseStream",
                side_effect=Exception("Unmarshal failed"),
            ),
            patch("pythoncom.CoReleaseMarshalData") as mock_release,
            pytest.raises(Exception, match="Unmarshal failed"),
            alphacam_context(),
        ):
            pass

        mock_release.assert_called_once_with(fake_stream)


def test_alphacam_context_owned_false_skips_quit(mock_com: MagicMock) -> None:
    with patch("win32com.client.GetActiveObject") as mock_get:
        app = MagicMock()
        app.Visible = False
        mock_get.return_value = app
        with patch("win32com.client.Dispatch") as mock_dispatch:
            from alphacam_cli.com.manager import alphacam_context

            with alphacam_context():
                pass
            mock_dispatch.return_value.Quit.assert_not_called()


def test_alphacam_context_error_message_contains_prog_ids(mock_com: MagicMock) -> None:
    from alphacam_cli.com.constants import PROG_IDS
    from alphacam_cli.com.manager import AlphacamConnectionError, alphacam_context

    with mock_com, patch("win32com.client.GetActiveObject") as mock_get:
        mock_get.side_effect = Exception("No active")
        with patch("win32com.client.Dispatch") as mock_dispatch:
            mock_dispatch.side_effect = Exception("Cannot create")

            with pytest.raises(AlphacamConnectionError) as exc_info, alphacam_context():
                pass
            msg = str(exc_info.value)
            for pid in PROG_IDS:
                assert pid in msg


def test_alphacam_com_error_hresult() -> None:
    from alphacam_cli.com.manager import AlphacamComError

    err = AlphacamComError("Test error", hresult=-2147221164)
    assert err.hresult == -2147221164
    assert "Test error" in str(err)


def test_alphacam_com_error_no_hresult() -> None:
    from alphacam_cli.com.manager import AlphacamComError

    err = AlphacamComError("Test error")
    assert err.hresult is None


def test_alphacam_connection_error() -> None:
    from alphacam_cli.com.manager import AlphacamConnectionError

    err = AlphacamConnectionError("Connection failed")
    assert "Connection failed" in str(err)


def test_co_uninitialize_not_called_on_init_failure(mock_com: MagicMock) -> None:
    from alphacam_cli.com.manager import alphacam_context

    with mock_com:
        import pythoncom

        with (
            patch("pythoncom.CoInitializeEx") as mock_init,
            patch("pythoncom.CoUninitialize") as mock_uninit,
        ):
            mock_init.side_effect = pythoncom.com_error(
                -2147221005,
                0,
                None,
                "CoInitializeEx failed",
            )

            with pytest.raises(pythoncom.com_error), alphacam_context():
                pass

            mock_uninit.assert_not_called()


def test_sta_worker_late_error_handled(mock_com: MagicMock) -> None:
    """When STA worker crashes after result delivery, context exits cleanly."""
    from alphacam_cli.com.manager import alphacam_context

    with mock_com:
        call_count = 0

        def failing_pump() -> None:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise RuntimeError

        with (
            patch("pythoncom.PumpWaitingMessages", side_effect=failing_pump),
            alphacam_context(keep_alive=True),
        ):
            time.sleep(0.15)

        assert call_count > 1, "Pump should have been called multiple times"
