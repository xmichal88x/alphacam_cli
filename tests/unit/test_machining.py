from __future__ import annotations

from unittest.mock import MagicMock

from alphacam_cli.core.machining import MillData


def _make_md(mock_com: MagicMock) -> MillData:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            return MillData(raw.CreateMillData())


def test_mill_data_properties(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
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


def test_mill_data_safe_rapid_level(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.safe_rapid_level = 25.0
    assert md.safe_rapid_level == 25.0


def test_mill_data_rapid_down_to(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.rapid_down_to = 5.0
    assert md.rapid_down_to == 5.0


def test_mill_data_final_depth(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.final_depth = -15.0
    assert md.final_depth == -15.0


def test_mill_data_spindle_speed(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.spindle_speed = 18000
    assert md.spindle_speed == 18000


def test_mill_data_down_feed(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.down_feed = 1500.0
    assert md.down_feed == 1500.0


def test_mill_data_cut_feed(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.cut_feed = 4000.0
    assert md.cut_feed == 4000.0


def test_mill_data_max_depth_per_cut(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.max_depth_per_cut = 1.0
    assert md.max_depth_per_cut == 1.0


def test_mill_data_stock(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.stock = 1.0
    assert md.stock == 1.0


def test_mill_data_xy_corners(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.xy_corners = 1
    assert md.xy_corners == 1


def test_mill_data_saw_angle(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.saw_angle = 15.0
    assert md.saw_angle == 15.0


def test_mill_data_saw_internal_corners(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.saw_internal_corners = 1
    assert md.saw_internal_corners == 1


def test_mill_data_saw_external_corners(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.saw_external_corners = 2
    assert md.saw_external_corners == 2


def test_mill_data_saw_open_ends(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.saw_open_ends = 1
    assert md.saw_open_ends == 1


def test_mill_data_saw_head_position(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.saw_head_position = 1
    assert md.saw_head_position == 1


def test_mill_data_engrave_type(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.engrave_type = 1
    assert md.engrave_type == 1


def test_mill_data_step_length(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.step_length = 0.05
    assert md.step_length == 0.05


def test_mill_data_engrave_corner_angle_limit(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.engrave_corner_angle_limit = 45.0
    assert md.engrave_corner_angle_limit == 45.0


def test_mill_data_rough_finish(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.rough_finish()
    md._md.RoughFinish.assert_called_once_with()


def test_mill_data_pocket(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.pocket()
    md._md.Pocket.assert_called_once_with()


def test_mill_data_drill_tap(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.drill_tap()
    md._md.DrillTap.assert_called_once_with()


def test_mill_data_engrave(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.engrave()
    md._md.Engrave.assert_called_once_with()


def test_mill_data_saw(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.saw()
    md._md.Saw.assert_called_once_with()


def test_mill_data_machine_surfaces(mock_com: MagicMock) -> None:
    md = _make_md(mock_com)
    md.machine_surfaces()
    md._md.MachineSurfaces.assert_called_once_with()
