from __future__ import annotations

import os
import pathlib
from unittest.mock import MagicMock, patch

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


def test_module_dir(mock_com: MagicMock, tmp_path: pathlib.Path) -> None:
    licomdat = tmp_path / "licomdat"
    module = licomdat / "LICOMDAT" / "rtools.alp"
    module.mkdir(parents=True)
    (module / "x.art").write_bytes(b"art")
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            raw.LicomdatPath = str(licomdat)
            ac = Application(raw)
            assert ac._module_dir("rtools.alp") == str(module)


def test_module_dir_fallback(mock_com: MagicMock, tmp_path: pathlib.Path) -> None:
    licomdat = tmp_path / "licomdat"
    licomdat.mkdir()
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            raw.LicomdatPath = str(licomdat)
            ac = Application(raw)
            assert ac._module_dir("rtools.alp") == str(licomdat / "rtools.alp")


def test_find_tool_files_scoped_to_module_dir(mock_com: MagicMock, tmp_path: pathlib.Path) -> None:
    rtools = tmp_path / "LICOMDAT" / "rtools.alp"
    rtools.mkdir(parents=True)
    (rtools / "sub").mkdir()
    (rtools / "sub" / "tool_a.art").write_bytes(b"art")
    (rtools / "sub" / "tool_b.art").write_bytes(b"art")
    (tmp_path / "LICOMDAT" / "mtools.alp").mkdir()
    (tmp_path / "LICOMDAT" / "mtools.alp" / "mill_c.art").write_bytes(b"art")
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            raw.LicomdatPath = str(tmp_path)
            raw.ProgramLetter = 82  # 'R'
            ac = Application(raw)
            result = ac.find_tool_files("*.art")
    assert result == [
        str(tmp_path / "LICOMDAT" / "rtools.alp" / "sub" / "tool_a.art"),
        str(tmp_path / "LICOMDAT" / "rtools.alp" / "sub" / "tool_b.art"),
    ]


def test_find_drawing_files(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            files = ac.find_drawing_files()
            assert isinstance(files, list)


def test_glob_files(mock_com: MagicMock, tmp_path: pathlib.Path) -> None:
    (tmp_path / "b.amd").write_bytes(b"amd")
    (tmp_path / "a.amd").write_bytes(b"amd")
    (tmp_path / "skip.txt").write_bytes(b"txt")
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            result = ac.glob_files(str(tmp_path), "*.amd")
    assert result == [str(tmp_path / "a.amd"), str(tmp_path / "b.amd")]


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
            ac.select_post(r"C:\ALPHACAM\LICOMDAT\RPosts.Alp\fanuc.arp")
            raw.SelectPost.assert_called_once_with(r"C:\ALPHACAM\LICOMDAT\RPosts.Alp\fanuc.arp")


def test_find_post_files(mock_com: MagicMock) -> None:
    posts = [
        r"C:\Licomdat\RPosts.Alp\Alpha Reichenbacher.arp",
        r"C:\Licomdat\RPosts.Alp\fanuc.arp",
    ]
    with (
        mock_com,
        patch(
            "alphacam_cli.core.application.glob.glob",
            return_value=posts,
        ) as m_glob,
    ):
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            result = ac.find_post_files()
    assert result == posts
    m_glob.assert_called_once_with(os.path.join(r"C:\Licomdat", "RPosts.Alp", "*.arp"))


def test_find_post_files_fallback(mock_com: MagicMock) -> None:
    posts = [r"C:\Licomdat\posts_extra\fanuc.arp"]
    with (
        mock_com,
        patch(
            "alphacam_cli.core.application.glob.glob",
            side_effect=[[], posts],
        ) as m_glob,
    ):
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            result = ac.find_post_files()
    assert result == posts
    assert m_glob.call_args_list[1][0] == (
        os.path.join(r"C:\Licomdat", "RPosts.Alp", "**", "*.arp"),
    )
    assert m_glob.call_args_list[1].kwargs == {"recursive": True}


def test_select_post_by_name(mock_com: MagicMock) -> None:
    post_path = "C:/Licomdat/RPosts.Alp/fanuc.arp"
    with mock_com, patch("alphacam_cli.core.application.glob.glob", return_value=[post_path]):
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            ac.select_post("fanuc")
            raw.SelectPost.assert_called_once_with(post_path)


def test_select_post_by_name_not_found(mock_com: MagicMock) -> None:
    with mock_com, patch("alphacam_cli.core.application.glob.glob", return_value=[]):
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            with pytest.raises(RuntimeError, match="no matching post file"):
                ac.select_post("missing")


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


def _make_style(file_name: str) -> MagicMock:
    style = MagicMock()
    style.FileName = file_name
    return style


def test_apply_mill_style(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            style = _make_style(r"C:\ALPHACAM\LICOMDIR\Styles\Fronty\Edge_01.ary")
            raw.MillMachiningStyles = [style]
            ac = Application(raw)
            ac.apply_mill_style("C:/ALPHACAM/LICOMDIR/Styles/Fronty/Edge_01.ary")
            style.Apply.assert_called_once()


def test_apply_mill_style_by_basename(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            style = _make_style(r"C:\ALPHACAM\LICOMDIR\Styles\Fronty\Edge_01.ary")
            raw.MillMachiningStyles = [style]
            ac = Application(raw)
            ac.apply_mill_style("Edge_01.ary")
            style.Apply.assert_called_once()


def test_apply_mill_style_not_found(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            style = _make_style(r"C:\ALPHACAM\LICOMDIR\Styles\Edge.ary")
            raw.MillMachiningStyles = [style]
            ac = Application(raw)
            with pytest.raises(RuntimeError, match="Mill style not found: .*Edge_01.ary"):
                ac.apply_mill_style("Edge_01.ary")


def test_apply_mill_style_error(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            style = _make_style(r"C:\ALPHACAM\LICOMDIR\Styles\Edge.ary")
            raw.MillMachiningStyles = [style]
            style.Apply.side_effect = Exception("apply failed")
            ac = Application(raw)
            with pytest.raises(RuntimeError, match="Failed to apply mill style"):
                ac.apply_mill_style(r"C:\ALPHACAM\LICOMDIR\Styles\Edge.ary")
