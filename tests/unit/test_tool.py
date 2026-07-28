from __future__ import annotations

from unittest.mock import MagicMock

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
