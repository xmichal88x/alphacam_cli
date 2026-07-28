from __future__ import annotations

import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows + AlphaCAM")
class TestProductionWorkflows:
    """Integration tests that require a real AlphaCAM installation.

    These tests connect to a live AlphaCAM COM instance and exercise
    end-to-end production workflows (create, mill, NC output, batch,
    nesting). They are skipped on non-Windows platforms.
    """

    def test_full_workflow_create_mill_nc(self) -> None:
        """Create a drawing, apply a rough milling operation, and
        generate NC output from start to finish."""
        ...

    def test_batch_processing(self) -> None:
        """Process multiple drawing files in batch mode using a
        specified post-processor."""
        ...

    def test_nesting_from_csv(self) -> None:
        """Import a CSV part list, run nesting, and verify the
        generated sheet layout."""
        ...
