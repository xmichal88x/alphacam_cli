from __future__ import annotations

from alphacam_cli.core.events import NcEventHandler


def test_nc_event_handler_init() -> None:
    handler = NcEventHandler("/path/to/output.nc")
    assert handler.nc_path == "/path/to/output.nc"


def test_on_before_output_nc_dialog_box() -> None:
    handler = NcEventHandler("/path/to/output.nc")
    assert handler.OnBeforeOutputNcDialogBox() == 1


def test_on_before_create_nc() -> None:
    handler = NcEventHandler("/path/to/output.nc")
    assert handler.OnBeforeCreateNc() == ""


def test_on_before_output_nc() -> None:
    handler = NcEventHandler("/path/to/output.nc")
    assert handler.OnBeforeOutputNc() == "/path/to/output.nc"


def test_on_after_output_nc() -> None:
    handler = NcEventHandler("/path/to/output.nc")
    handler.OnAfterOutputNc("output.nc")  # should not raise
