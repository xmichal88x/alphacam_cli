from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from alphacam_cli.core.nesting import Nesting, NestList, NestPart, NestSheet, SheetList


def test_nesting_properties(mock_com: MagicMock) -> None:
    """Test Nesting wrapper properties."""
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            assert n.suppress_dialogs is False
            n.suppress_dialogs = True
            assert n.suppress_dialogs is True


def test_nesting_new_nest_list(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            nl = n.new_nest_list("test.nst")
            assert isinstance(nl, NestList)
            assert nl.count == 0


def test_nesting_new_nest_list_none_error(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            n._n.NewNestList.return_value = None
            with pytest.raises(RuntimeError, match="Failed to create nest list"):
                n.new_nest_list("test.nst")


def test_nesting_new_sheet_list(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            sl = n.new_sheet_list()
            assert isinstance(sl, SheetList)


def test_nesting_new_sheet_list_none_error(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            n._n.NewSheetList.return_value = None
            with pytest.raises(RuntimeError, match="Failed to create sheet list"):
                n.new_sheet_list()


def test_nesting_delete_all_nest_lists(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            n.delete_all_nest_lists()
            n._n.DeleteAllNestLists.assert_called_once_with()


def test_nesting_load_nest_list(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            nl = n.load_nest_list("existing.nst")
            assert isinstance(nl, NestList)
            n._n.LoadNestList.assert_called_once_with("existing.nst")


def test_nesting_load_nest_list_none_error(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            n._n.LoadNestList.return_value = None
            with pytest.raises(RuntimeError, match="Failed to load nest list"):
                n.load_nest_list("gone.nst")


def test_nesting_nest(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            nl = n.new_nest_list("parts.nst")
            sl = n.new_sheet_list()
            result = n.nest(nl, sl)
            assert isinstance(result, NestList)
            n._n.Nest.assert_called_once_with(nl._nl, sl._sl)


def test_nest_list_properties(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            nl = n.new_nest_list("test.nst")
            assert nl.count == 0
            assert nl.total_time == 0


def test_nest_list_total_time_setter(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            nl = n.new_nest_list("test.nst")
            nl.total_time = 10
            assert nl._nl.TotalTime == 10


def test_nest_list_raw_dispatch(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            nl = n.new_nest_list("test.nst")
            assert nl.raw_dispatch is nl._nl


def test_nest_list_add_file(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            nl = n.new_nest_list("test.nst")
            np = nl.add_file("part.amd")
            assert isinstance(np, NestPart)
            nl._nl.AddFile.assert_called_once_with("part.amd")


def test_nest_list_add_file_none_error(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            nl = n.new_nest_list("test.nst")
            nl._nl.AddFile.return_value = None
            with pytest.raises(RuntimeError, match="Failed to add file to nest list"):
                nl.add_file("bad.amd")


def test_nest_list_sort(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            nl = n.new_nest_list("test.nst")
            nl.sort(1)
            nl._nl.Sort.assert_called_once_with(1)


def test_nest_list_sort_default(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            nl = n.new_nest_list("test.nst")
            nl.sort()
            nl._nl.Sort.assert_called_once_with(0)


def test_nest_list_save(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            nl = n.new_nest_list("test.nst")
            nl.save()
            nl._nl.Save.assert_called_once_with()


def test_nest_list_save_no_filename(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            nl = n.new_nest_list("test.nst")
            nl.save()
            nl._nl.Save.assert_called_once_with()


def test_nest_part_properties(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            nl = n.new_nest_list("test.nst")
            np = nl.add_file("part.amd")
            np._np.Required = 5
            assert np.required == 5
            np._np.RotationAngle = 45.0
            assert np.rotation_angle == 45.0


def test_nest_part_required_setter(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            nl = n.new_nest_list("test.nst")
            np = nl.add_file("part.amd")
            np.required = 3
            assert np._np.Required == 3


def test_nest_part_rotation_angle_setter(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            nl = n.new_nest_list("test.nst")
            np = nl.add_file("part.amd")
            np.rotation_angle = 90.0
            assert np._np.RotationAngle == 90.0


def test_sheet_list_properties(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            sl = n.new_sheet_list()
            assert sl.count == 0
            assert sl.raw_dispatch is sl._sl


def test_sheet_list_add(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            sl = n.new_sheet_list()
            raw_geo = MagicMock()
            ns = sl.add(raw_geo)
            assert isinstance(ns, NestSheet)
            sl._sl.Add.assert_called_once_with(raw_geo)


def test_sheet_list_add_none_error(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            sl = n.new_sheet_list()
            sl._sl.Add.return_value = None
            with pytest.raises(RuntimeError, match="Failed to add sheet"):
                sl.add(MagicMock())


def test_nest_sheet_properties(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            sl = n.new_sheet_list()
            ns = sl.add(MagicMock())
            ns._ns.Required = 3
            assert ns.required == 3
            ns._ns.Thickness = 2.5
            assert ns.thickness == 2.5


def test_nest_sheet_required_setter(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            sl = n.new_sheet_list()
            ns = sl.add(MagicMock())
            ns.required = 10
            assert ns._ns.Required == 10


def test_nest_sheet_thickness_setter(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            n = Nesting(raw.Nesting)
            sl = n.new_sheet_list()
            ns = sl.add(MagicMock())
            ns.thickness = 18.0
            assert ns._ns.Thickness == 18.0
