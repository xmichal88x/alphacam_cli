from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from alphacam_cli.core.tool import Tool


def test_tool_properties(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            tool = Tool(raw.SelectTool("Flat - 10mm.amt"))
            assert tool.name == "Flat - 10mm"
            assert tool.diameter == 10.0
            assert tool.number == 1
            assert tool.tool_length == 50.0
            assert tool.tool_type == 0
            assert tool.feed_per_tooth == 0.1
            assert tool.file_name == "flat_10mm.amt"
            assert tool.units == 1
            assert tool.corner_radius == 0.0
            assert tool.note == ""
            assert tool.number_of_teeth == 2


def test_tool_init_none() -> None:
    with pytest.raises(ValueError, match="Tool dispatch object is None"):
        Tool(None)


def test_tool_empty_name() -> None:
    dispatch = MagicMock()
    dispatch.Name = ""
    tool = Tool(dispatch)
    assert tool.name == ""


def test_tool_zero_diameter() -> None:
    dispatch = MagicMock()
    dispatch.Diameter = 0.0
    tool = Tool(dispatch)
    assert tool.diameter == 0.0
