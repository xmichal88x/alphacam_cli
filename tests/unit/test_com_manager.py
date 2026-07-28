from __future__ import annotations

from alphacam_cli.com.constants import PROG_IDS


def test_prog_ids_defined():
    assert len(PROG_IDS) == 3
    assert "Ar5axaps.Application" in PROG_IDS
    assert "am5axaps.Application" in PROG_IDS
    assert "aroutaps.Application" in PROG_IDS


def test_module_constants():
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
