from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from alphacam_cli.core.application import Application


def test_application_properties(mock_com: MagicMock) -> None:
    """Test Application wrapper properties."""
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            assert ac.name == "AlphaCAM"
            assert ac.version == "2024.1"
            assert ac.full_name == "C:\\AlphaCAM\\alphaCAM.exe"
            assert ac.program_level == 3
            assert ac.program_letter == 82
            assert ac.module_type == "R"
            assert ac.api_version == 20240315
            assert ac.licomdat_path == "C:\\Licomdat"
            assert ac.licomdir_path == "C:\\Licomdir"
            assert ac.post_file_name == "fanuc.pst"
            assert ac.is_router is True
            assert ac.is_mill is False


def test_application_visible_setter(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            ac.visible = True
            assert ac.visible is True
            ac.visible = False
            assert ac.visible is False


def test_get_active_drawing(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            drw = ac.get_active_drawing()
            assert drw is not None
            assert drw.geometries_count == 0


def test_new_drawing(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            drw = ac.new_drawing(200, 100, 5, "Hello")
            assert drw is not None
            raw.New.assert_called_once()
            raw.ActiveDrawing.CreateRectangle.assert_called_once_with(0, 0, 200, 100)
            raw.ActiveDrawing.CreateRectangle.return_value.Fillet.assert_called_once_with(5)
            raw.ActiveDrawing.CreateText2.assert_called_once_with("Hello", 5, 50, 4)
            raw.ActiveDrawing.ZoomAll.assert_called_once()


def test_new_drawing_no_geometry(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            drw = ac.new_drawing()
            assert drw is not None
            raw.New.assert_called_once()
            raw.ActiveDrawing.CreateRectangle.assert_called_once_with(0, 0, 100, 50)
            raw.ActiveDrawing.CreateRectangle.return_value.Fillet.assert_not_called()
            raw.ActiveDrawing.CreateText2.assert_not_called()
            raw.ActiveDrawing.ZoomAll.assert_called_once()


def test_new_drawing_none(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            raw.ActiveDrawing = None
            result = ac.new_drawing()
            assert result is None


def test_quit(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            ac.quit()
            raw.Quit.assert_called_once()


def test_select_tool(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            tool = ac.select_tool("flat_10mm.amt")
            assert tool is not None
            assert tool.name == "Flat - 10mm"
            raw.SelectTool.assert_called_once_with("flat_10mm.amt")


def test_get_current_tool(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            tool = ac.get_current_tool()
            assert tool is not None
            assert tool.name == "Flat - 10mm"


def test_find_tool_files(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            files = ac.find_tool_files()
            assert isinstance(files, list)


def test_find_drawing_files(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            files = ac.find_drawing_files()
            assert isinstance(files, list)


def test_get_nesting(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            nesting = ac.get_nesting()
            assert nesting is not None


def test_select_post(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            ac.select_post("fanuc")
            raw.SelectPost.assert_called_once_with("fanuc")


def test_open_drawing(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            drw = ac.open_drawing("test.amd")
            assert drw is not None
            raw.OpenDrawing.assert_called_once_with("test.amd")


def test_open_drawing_none(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            raw.OpenDrawing.return_value = None
            result = ac.open_drawing("missing.amd")
            assert result is None


def test_create_temp_drawing(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            drw = ac.create_temp_drawing()
            raw.New.assert_called_once()
            assert drw is not None


def test_create_temp_drawing_none(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            raw.ActiveDrawing = None
            result = ac.create_temp_drawing()
            assert result is None


def test_create_mill_data(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            md = ac.create_mill_data()
            assert md is not None


def test_apply_mill_style(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            ac.apply_mill_style(r"C:\ALPHACAM\LICOMDIR\Styles\Fronty\Edge_01.ary")
            style = raw.CreateMillStyle.return_value
            assert style.FileName == r"C:\ALPHACAM\LICOMDIR\Styles\Fronty\Edge_01.ary"
            style.Apply.assert_called_once()


def test_apply_mill_style_error(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            raw.CreateMillStyle.side_effect = Exception("style not found")
            with pytest.raises(RuntimeError, match="Failed to apply mill style"):
                ac.apply_mill_style(r"C:\ALPHACAM\LICOMDIR\Styles\Missing.ary")
