from __future__ import annotations

from alphacam_cli.core.machining import MillData


def test_mill_data_properties(mock_com):
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            md = MillData(raw.CreateMillData())
            assert md.safe_rapid_level == 10.0
            assert md.final_depth == -10.0
            assert md.spindle_speed == 12000
            assert md.cut_feed == 3000.0
            assert md.down_feed == 2000.0
            assert md.stock == 0.5
            assert md.width_of_cut == 5.0
            assert md.max_depth_per_cut == 2.5
            assert md.material_top == 0.0
            assert md.chord_error == 0.1
