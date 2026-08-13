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


def test_drawing_parametric_creates_panel(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            result = ac.drawing_parametric(800, 400)
            assert result["success"] is True
            assert result["outer"] == {"tool_in_out": -1}
            assert result["inner"] == {"tool_in_out": 1}
            raw.New.assert_called_once()
            raw.ActiveDrawing.CreateRectangle.assert_called_once_with(0, 0, 800, 400)
            raw.ActiveDrawing.CreateRectangle.return_value.Fillet.assert_called_once_with(5)
            raw.ActiveDrawing.Create2DGeometry.assert_called_once_with(50, 50)
            raw.ActiveDrawing.ZoomAll.assert_called_once()
            raw.CreateMillData.assert_not_called()


def test_drawing_parametric_geometry_only(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            result = ac.drawing_parametric(800, 400, offset=60, fillet=3)
            assert result["success"] is True
            raw.SelectTool.assert_not_called()
            raw.CreateMillData.assert_not_called()
            md = raw.CreateMillData.return_value
            assert md.RoughFinish.call_count == 0


def test_drawing_parametric_no_machining(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            ac.drawing_parametric(800, 400)
            raw.SelectTool.assert_not_called()
            raw.CreateMillData.assert_not_called()


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
    (rtools / "top_a.art").write_bytes(b"art")
    (rtools / "sub").mkdir()
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
        str(tmp_path / "LICOMDAT" / "rtools.alp" / "sub" / "tool_b.art"),
        str(tmp_path / "LICOMDAT" / "rtools.alp" / "top_a.art"),
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


def test_get_nesting_fallback(mock_com: MagicMock) -> None:
    """App.Nesting raises -> fallback to Dispatch('AcamNest.Nesting')."""
    ac = Application(_RaiseOnNesting())
    nesting = ac.get_nesting()
    assert nesting is not None
    mock_com.assert_any_call("AcamNest.Nesting")


def test_get_nesting_both_failed(mock_com: MagicMock) -> None:
    """App.Nesting and Dispatch('AcamNest.Nesting') both fail -> RuntimeError."""
    mock_com.side_effect = Exception("dispatch failed")
    ac = Application(_RaiseOnNesting())
    with pytest.raises(
        RuntimeError,
        match=(
            r"Failed to get nesting \(App\.Nesting and AcamNest\.Nesting failed\)"
            r": dispatch failed"
        ),
    ):
        ac.get_nesting()


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
            side_effect=[posts, []],
        ) as m_glob,
    ):
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            result = ac.find_post_files()
    assert result == posts
    assert m_glob.call_args_list[0][0] == (os.path.join(r"C:\Licomdat", "RPosts.Alp", "*.arp"),)
    assert m_glob.call_args_list[1][0] == (
        os.path.join(r"C:\Licomdat", "RPosts.Alp", "**", "*.arp"),
    )


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


def test_find_style_files(mock_com: MagicMock, tmp_path: pathlib.Path) -> None:
    styles = tmp_path / "Styles"
    styles.mkdir(parents=True)
    (styles / "Edge.ary").write_bytes(b"a" * 10)
    (styles / "Fronty_AutoStyl.ara").write_bytes(b"b" * 20)
    (styles / "Fronty").mkdir()
    (styles / "Fronty" / "Ball_06.ary").write_bytes(b"c" * 30)
    (styles / "notes.txt").write_text("ignore", encoding="utf-8")
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            raw.LicomdirPath = str(tmp_path)
            ac = Application(raw)
            result = ac.find_style_files()
    assert result == [
        str(styles / "Edge.ary"),
        str(styles / "Fronty" / "Ball_06.ary"),
        str(styles / "Fronty_AutoStyl.ara"),
    ]


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


def test_open_cad_file_dxf(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            drw = ac.open_cad_file(r"C:\parts\panel.dxf", "dxf")
            assert drw is not None
            raw.OpenDxfFile.assert_called_once_with(r"C:\parts\panel.dxf", False)


def test_open_cad_file_dwg_clear(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            ac.open_cad_file(r"C:\parts\panel.dwg", "dwg", clear=True)
            raw.OpenDxfFile.assert_called_once_with(r"C:\parts\panel.dwg", True)


def test_open_cad_file_iges(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            ac.open_cad_file(r"C:\parts\panel.igs", "iges")
            raw.OpenIgesFile.assert_called_once_with(r"C:\parts\panel.igs", False, 0)


def test_open_cad_file_step(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            ac.open_cad_file(r"C:\parts\panel.step", "step")
            raw.OpenStepFileEx.assert_called_once_with(r"C:\parts\panel.step", False, 0)


def test_open_cad_file_step_fallback(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            raw.OpenStepFileEx.side_effect = AttributeError("no OpenStepFileEx")
            ac = Application(raw)
            ac.open_cad_file(r"C:\parts\panel.stp", "stp")
            raw.OpenStepFile.assert_called_once_with(r"C:\parts\panel.stp", False)


def test_open_cad_file_stl(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            ac.open_cad_file(r"C:\parts\panel.stl", "stl")
            raw.OpenStlFile.assert_called_once_with(r"C:\parts\panel.stl", False)


def test_open_cad_file_unknown_format(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            with pytest.raises(ValueError, match="Unsupported CAD format: xyz"):
                ac.open_cad_file(r"C:\parts\panel.xyz", "xyz")


def test_open_cad_file_com_error(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            raw.OpenDxfFile.side_effect = RuntimeError("com failed")
            ac = Application(raw)
            with pytest.raises(RuntimeError, match=r"Failed to open CAD file .*dxf.*: com failed"):
                ac.open_cad_file(r"C:\parts\panel.dxf", "dxf")


def test_set_dxf_cabinets(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            ac.set_dxf_cabinets(True)
            assert raw.CadInputSettings.DxfSpecial == 1
            ac.set_dxf_cabinets(False)
            assert raw.CadInputSettings.DxfSpecial == 0


def test_set_dxf_cabinets_error(mock_com: MagicMock) -> None:
    class _RaiseOnSet:
        def __setattr__(self, name: str, value: int) -> None:
            raise RuntimeError("no settings")  # noqa: TRY003

    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            raw.CadInputSettings = _RaiseOnSet()
            ac = Application(raw)
            with pytest.raises(RuntimeError, match="Failed to set DXF cabinets input"):
                ac.set_dxf_cabinets(True)


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


class _RaiseOnNesting(MagicMock):
    """MagicMock whose attribute access to 'Nesting' raises a COM-style error."""

    def __getattr__(self, name: str) -> MagicMock:
        if name == "Nesting":
            raise RuntimeError("COMError -2147467259")  # noqa: TRY003
        return super().__getattr__(name)  # type: ignore[no-any-return]


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
