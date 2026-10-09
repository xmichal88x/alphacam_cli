from __future__ import annotations

import os
import pathlib
from typing import Any
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


def test_application_offcut_operations_delegate() -> None:
    raw = MagicMock()
    ac = Application(raw)
    create_result = {"success": False, "status": "blocked"}
    delete_result = {"success": False, "status": "not_found", "sheet_id": 123}
    with (
        patch("alphacam_cli.core.stock.stock_offcut_create", return_value=create_result) as create,
        patch("alphacam_cli.core.stock.stock_offcut_delete", return_value=delete_result) as delete,
    ):
        assert ac.stock_offcut_create("MDF", 18, 100, 200, 1, "offcut") == create_result
        assert ac.stock_offcut_delete(123) == delete_result
    create.assert_called_once_with(raw, "MDF", 18, 100, 200, 1, "offcut", raw.ActiveDrawing)
    delete.assert_called_once_with(raw, 123)


def test_application_version_readable_from_full_name(
    mock_com: MagicMock,
) -> None:
    """AlphacamVersion jako obiekt COM (nie string) -> wersja z FullName."""
    with mock_com:
        mock_com.return_value.AlphacamVersion = MagicMock()
        mock_com.return_value.FullName = r"C:\Program Files\Hexagon\ALPHACAM 2025\Acam.exe"
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            assert ac.version == "ALPHACAM 2025"


def test_application_version_com_object_no_year_fallback(
    mock_com: MagicMock,
) -> None:
    """FullName bez roku + AlphacamVersion obiekt COM -> fallback str()."""
    with mock_com:
        version_mock = MagicMock()
        version_mock.__str__ = MagicMock(return_value="<com object>")
        mock_com.return_value.AlphacamVersion = version_mock
        mock_com.return_value.FullName = r"C:\AlphaCAM\Acam.exe"
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            assert ac.version == "<com object>"


def test_application_version_plain_string_unchanged(mock_com: MagicMock) -> None:
    """AlphacamVersion to zwykly string -> zwrocony bez zmian."""
    with mock_com:
        mock_com.return_value.AlphacamVersion = "2024.1"
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            assert ac.version == "2024.1"


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


def test_manifest_list_adds_sheet_stats(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    monkeypatch.setattr(
        "alphacam_cli.core.application.acrepd._reports_data_dir",
        lambda licomdir_path, data_dir: str(tmp_path),
    )
    manifest = {
        "path": "C:/Reports/Data/Fronty - MDF_18.acrepd",
        "job_name": "Fronty",
        "material": "MDF_18",
        "size": 1234,
        "mtime": 1700000000.0,
    }
    monkeypatch.setattr(
        "alphacam_cli.core.application.acrepd.manifest_files",
        lambda data_dir: [manifest],
    )
    monkeypatch.setattr(
        "alphacam_cli.core.application.acrepd.sheet_count_light",
        lambda path: (2, 29),
    )
    result = Application(MagicMock()).manifest_list(None)
    assert result["manifests"] == [
        {
            "path": "C:/Reports/Data/Fronty - MDF_18.acrepd",
            "job_name": "Fronty",
            "material": "MDF_18",
            "size": 1234,
            "mtime": 1700000000.0,
            "sheet_count": 2,
            "first_utilization": 29,
        }
    ]


def test_manifest_list_sheet_stats_error_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    monkeypatch.setattr(
        "alphacam_cli.core.application.acrepd._reports_data_dir",
        lambda licomdir_path, data_dir: str(tmp_path),
    )
    monkeypatch.setattr(
        "alphacam_cli.core.application.acrepd.manifest_files",
        lambda data_dir: [
            {
                "path": "C:/Reports/Data/Fronty - MDF_18.acrepd",
                "job_name": "Fronty",
                "material": "MDF_18",
                "size": 1234,
                "mtime": 1700000000.0,
            }
        ],
    )
    monkeypatch.setattr(
        "alphacam_cli.core.application.acrepd.sheet_count_light",
        lambda path: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    result = Application(MagicMock()).manifest_list(None)
    assert result["manifests"][0]["sheet_count"] == 0
    assert result["manifests"][0]["first_utilization"] is None


# --- Application.import_cdm_csv: material group ---


def _new_job_app() -> tuple[Application, MagicMock]:
    am = MagicMock()
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    app = Application(MagicMock())
    app.get_cdm_automation_manager = lambda: am  # type: ignore[method-assign]
    return app, am


def _mock_group_import(
    monkeypatch: pytest.MonkeyPatch,
    group_sheets: list[dict[str, object]],
    *,
    material_groups: dict[str, list[dict[str, object]]] | None = None,
) -> dict[str, MagicMock]:
    setting: dict[str, object] = {
        "id": 3,
        "name": "sklep CSV",
        "selected": True,
        "create_job": True,
        "delimiter_char": ",",
        "sub_delimiter_char": ";",
        "ignore_header": False,
        "is_cdm_import": True,
    }
    detail = {"style": "PS_03", "row": 1, "width": 500.0, "length": 400.0, "quantity": 1}
    mocks = {
        "resolve": MagicMock(return_value=group_sheets),
        "set_selected": MagicMock(return_value=True),
        "set_job_material": MagicMock(return_value=True),
        "set_order_detail_material": MagicMock(return_value=True),
        "finalize": MagicMock(return_value=True),
        "set_sheet_order": MagicMock(return_value=True),
        "cleanup": MagicMock(return_value=(True, "")),
    }
    monkeypatch.setattr("alphacam_cli.core.application._resolve_import_setting", lambda _s: setting)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.field_map_from_setting", lambda _s: {})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.read_cdm_csv", lambda *_a, **_k: [["row"]])
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.parse_cdm_rows_mapped", lambda *_a, **_k: ([detail], [])
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.job_count", MagicMock(return_value=0))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.resolve_material_group", mocks["resolve"])
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.material_groups",
        lambda: (
            material_groups
            if material_groups is not None
            else {
                "MDF_18": [
                    {"id": 2, "name": "MDF_18", "offcut": False},
                    {"id": 7, "name": "MDF18", "offcut": False},
                ]
            }
        ),
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", mocks["set_job_material"])
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_selected_sheets", mocks["set_selected"])
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.set_order_detail_material", mocks["set_order_detail_material"]
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.finalize_cdm_job", mocks["finalize"])
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_sheet_order", mocks["set_sheet_order"])
    monkeypatch.setattr("alphacam_cli.core.cdm_db.cleanup_created_job", mocks["cleanup"])
    return mocks


def test_import_cdm_csv_group_validations(tmp_path: pathlib.Path) -> None:
    app = Application(MagicMock())
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="mutually exclusive"):
        app.import_cdm_csv(str(csv_file), material="MDF_18", material_group="MDF_18")
    with pytest.raises(RuntimeError, match="mutually exclusive"):
        app.import_cdm_csv(str(csv_file), material="MDF_18", sheets="2:0")
    with pytest.raises(RuntimeError, match="mutually exclusive"):
        app.import_cdm_csv(str(csv_file), material_group="MDF_18", sheets="2:0")
    with pytest.raises(RuntimeError, match="require --material-group"):
        app.import_cdm_csv(str(csv_file), prefer_offcuts=True)
    with pytest.raises(RuntimeError, match="require --material-group"):
        app.import_cdm_csv(str(csv_file), include_offcuts=True)
    with pytest.raises(RuntimeError, match="sheet-order"):
        app.import_cdm_csv(str(csv_file), material_group="MDF_18", sheet_order="fastest")
    with pytest.raises(RuntimeError, match="forces picked order"):
        app.import_cdm_csv(
            str(csv_file), material_group="MDF_18", prefer_offcuts=True, sheet_order="best"
        )


def test_import_cdm_csv_material_group(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    group = [
        {"id": 2, "name": "MDF_18", "offcut": False, "quantity": 0},
        {"id": 7, "name": "MDF18", "offcut": False, "quantity": 0},
    ]
    mocks = _mock_group_import(monkeypatch, group)
    app, _am = _new_job_app()
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    result = app.import_cdm_csv(str(csv_file), name="J1", config="Fronty", material_group="MDF_18")
    assert result["success"] is True
    assert result["errors"] == []
    mocks["resolve"].assert_called_once_with(
        "MDF_18", include_offcuts=False, offcuts_first=False, whole_quantity=0, offcut_quantity=1
    )
    mocks["set_job_material"].assert_called_once_with("J1", 0)
    mocks["set_selected"].assert_called_once_with("J1", group)
    mocks["finalize"].assert_called_once_with("J1")
    mocks["set_order_detail_material"].assert_not_called()
    mocks["set_sheet_order"].assert_not_called()
    assert result["material_group"] == "MDF_18 (group: MDF_18#2, MDF18#7)"
    assert result["material"] is None


def test_import_cdm_csv_material_group_call_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    group = [{"id": 2, "name": "MDF_18", "offcut": False, "quantity": 0}]
    mocks = _mock_group_import(monkeypatch, group)
    order: list[str] = []

    def _record(name: str) -> Any:
        def _fn(*_a: Any, **_k: Any) -> bool:
            order.append(name)
            return True

        return _fn

    mocks["set_job_material"].side_effect = _record("material")
    mocks["finalize"].side_effect = _record("finalize")
    mocks["set_selected"].side_effect = _record("sheets")
    app, _am = _new_job_app()
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    result = app.import_cdm_csv(str(csv_file), name="J1", config="Fronty", material_group="MDF_18")
    assert result["success"] is True
    assert order == ["material", "finalize", "sheets"]


def test_import_cdm_csv_group_new_job_sheets_fail_cleans_up(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    group = [{"id": 2, "name": "MDF_18", "offcut": False, "quantity": 0}]
    mocks = _mock_group_import(monkeypatch, group)
    mocks["set_selected"].return_value = False
    app, _am = _new_job_app()
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="failed to configure material group"):
        app.import_cdm_csv(str(csv_file), name="J1", config="Fronty", material_group="MDF_18")
    mocks["cleanup"].assert_called_once()


def test_import_cdm_csv_group_existing_job_fail_no_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    group = [{"id": 2, "name": "MDF_18", "offcut": False, "quantity": 0}]
    mocks = _mock_group_import(monkeypatch, group)
    mocks["set_selected"].return_value = False
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", lambda _am, _name: MagicMock())
    app, _am = _new_job_app()
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    result = app.import_cdm_csv(str(csv_file), job="J1", material_group="MDF_18")
    assert result["success"] is False
    assert any("failed to configure material group" in e for e in result["errors"])
    mocks["cleanup"].assert_not_called()
    assert result["items"] == 1


def test_import_cdm_csv_material_group_prefer_offcuts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    group = [
        {"id": 9, "name": "OFF", "offcut": True, "quantity": 1},
        {"id": 2, "name": "MDF_18", "offcut": False, "quantity": 0},
    ]
    mocks = _mock_group_import(monkeypatch, group)
    app, _am = _new_job_app()
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    result = app.import_cdm_csv(
        str(csv_file), name="J1", config="Fronty", material_group="MDF_18", prefer_offcuts=True
    )
    assert result["success"] is True
    mocks["resolve"].assert_called_once_with(
        "MDF_18", include_offcuts=True, offcuts_first=True, whole_quantity=0, offcut_quantity=1
    )
    mocks["set_sheet_order"].assert_called_once_with("Fronty", 1)
    assert result["material_group"] == "MDF_18 (group: OFF#9 (offcut), MDF_18#2)"
    assert result["material"] is None
    assert any(
        "sheet order set to picked globally for configuration 'Fronty'" in e
        for e in result["errors"]
    )


def test_import_cdm_csv_sheets_spec(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    mocks = _mock_group_import(monkeypatch, [{"id": 2, "quantity": 0}, {"id": 7, "quantity": 1}])
    app, _am = _new_job_app()
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    result = app.import_cdm_csv(str(csv_file), name="J1", config="Fronty", sheets="2:0, 7:1")
    assert result["success"] is True
    mocks["resolve"].assert_not_called()
    mocks["set_selected"].assert_called_once_with(
        "J1", [{"id": 2, "quantity": 0}, {"id": 7, "quantity": 1}]
    )
    assert result["material_group"] == "sheets: 2:0, 7:1"


def test_import_cdm_csv_sheets_unknown_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _mock_group_import(monkeypatch, [])
    app, _am = _new_job_app()
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="unknown sheet id"):
        app.import_cdm_csv(str(csv_file), name="J1", config="Fronty", sheets="2:0, 99:1")


def test_import_cdm_csv_sheet_order_best(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    group = [{"id": 2, "name": "MDF_18", "offcut": False, "quantity": 0}]
    mocks = _mock_group_import(monkeypatch, group)
    app, _am = _new_job_app()
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    result = app.import_cdm_csv(
        str(csv_file), name="J1", config="Fronty", material_group="MDF_18", sheet_order="best"
    )
    assert result["success"] is True
    mocks["set_sheet_order"].assert_called_once_with("Fronty", 0)


def test_import_cdm_preview_material_group(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    group = [
        {"id": 2, "name": "MDF_18", "offcut": False, "quantity": 0},
        {"id": 7, "name": "MDF18", "offcut": False, "quantity": 0},
    ]
    _mock_group_import(monkeypatch, group)
    app = Application(MagicMock())
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    result = app.import_cdm_preview(
        str(csv_file), name="J1", config="Fronty", material_group="MDF_18"
    )
    assert result["material_group"] == {"name": "MDF_18", "sheets": group}
    assert result["success"] is True


def test_import_cdm_preview_unknown_group_returns_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    mocks = _mock_group_import(monkeypatch, [])
    mocks["resolve"].side_effect = RuntimeError("cdm: material group not found: NOPE")
    app = Application(MagicMock())
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    result = app.import_cdm_preview(
        str(csv_file), name="J1", config="Fronty", material_group="NOPE"
    )
    assert result["success"] is False
    assert result["fatal_error"] is True
    assert any("material group not found" in e for e in result["errors"])


def test_import_cdm_preview_group_conflict(tmp_path: pathlib.Path) -> None:
    app = Application(MagicMock())
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="mutually exclusive"):
        app.import_cdm_preview(str(csv_file), material="MDF_18", material_group="MDF_18")


def test_import_cdm_preview_prefer_offcuts_requires_group(tmp_path: pathlib.Path) -> None:
    app = Application(MagicMock())
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="require --material-group"):
        app.import_cdm_preview(str(csv_file), prefer_offcuts=True)


def test_parse_sheets_spec_rejects_non_positive_id() -> None:
    from alphacam_cli.core.application import _parse_sheets_spec

    with pytest.raises(RuntimeError, match="invalid --sheets"):
        _parse_sheets_spec("0:1")


def test_parse_sheets_spec_rejects_negative_quantity() -> None:
    from alphacam_cli.core.application import _parse_sheets_spec

    with pytest.raises(RuntimeError, match="invalid --sheets"):
        _parse_sheets_spec("2:-1")


# --- Application.import_cdm_csv: "From Job" material resolution ---


def _mock_import(
    monkeypatch: pytest.MonkeyPatch,
    *,
    job_material: int | None = 2,
    default_material_id: int | None = 5,
    materials: dict[str, int] | None = None,
) -> tuple[Application, dict[str, MagicMock]]:
    setting: dict[str, object] = {
        "id": 3,
        "name": "sklep CSV",
        "selected": True,
        "create_job": True,
        "delimiter_char": ",",
        "sub_delimiter_char": ";",
        "ignore_header": False,
        "is_cdm_import": True,
    }
    detail = {"style": "PS_03", "row": 1, "width": 500.0, "length": 400.0, "quantity": 1}
    app, am = _new_job_app()
    job_obj = am.NewCDMJob.return_value
    mocks = {
        "job_material_id": MagicMock(return_value=job_material),
        "set_job_material": MagicMock(return_value=True),
        "set_order_detail_material": MagicMock(return_value=True),
        "set_selected_sheets": MagicMock(return_value=True),
    }
    monkeypatch.setattr("alphacam_cli.core.application._resolve_import_setting", lambda _s: setting)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.field_map_from_setting", lambda _s: {})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.read_cdm_csv", lambda *_a, **_k: [["row"]])
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.parse_cdm_rows_mapped", lambda *_a, **_k: ([detail], [])
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", lambda _am, _name: job_obj)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.job_count", MagicMock(return_value=0))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.sheet_materials",
        lambda: materials if materials is not None else {"MDF_18": 2, "DEFAULT": 5},
    )
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": default_material_id},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.job_material_id", mocks["job_material_id"])
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", mocks["set_job_material"])
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.set_order_detail_material", mocks["set_order_detail_material"]
    )
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.set_selected_sheets", mocks["set_selected_sheets"]
    )
    return app, mocks


def test_import_cdm_csv_job_keeps_job_material(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    app, mocks = _mock_import(monkeypatch, job_material=2)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    result = app.import_cdm_csv(str(csv_file), job="J1")
    assert result["success"] is True
    mocks["job_material_id"].assert_called_once_with("J1")
    mocks["set_order_detail_material"].assert_called_once_with("J1", 2)
    mocks["set_job_material"].assert_not_called()
    assert result["material_source"] == "job"
    assert result["material"] == "MDF_18"


def test_import_cdm_csv_job_group_material(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    app, mocks = _mock_import(monkeypatch, job_material=0)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    result = app.import_cdm_csv(str(csv_file), job="J1")
    assert result["success"] is True
    mocks["set_order_detail_material"].assert_called_once_with("J1", 0)
    mocks["set_job_material"].assert_not_called()
    mocks["set_selected_sheets"].assert_not_called()
    assert result["material_source"] == "job-group"
    assert result["material"] == "from job (group)"


def test_import_cdm_csv_job_material_read_failure_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    app, mocks = _mock_import(monkeypatch, job_material=None, default_material_id=5)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    result = app.import_cdm_csv(str(csv_file), job="J1")
    assert result["success"] is True
    mocks["set_job_material"].assert_called_once_with("J1", 5)
    mocks["set_order_detail_material"].assert_called_once_with("J1", 5)
    assert result["material_source"] == "database-default"
    assert any("failed to read job material; using database default" in e for e in result["errors"])


def test_import_cdm_csv_new_job_database_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    app, mocks = _mock_import(monkeypatch, default_material_id=5)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    result = app.import_cdm_csv(str(csv_file), name="J1", config="Fronty")
    assert result["success"] is True
    mocks["job_material_id"].assert_not_called()
    mocks["set_job_material"].assert_called_once_with("J1", 5)
    mocks["set_order_detail_material"].assert_called_once_with("J1", 5)
    assert result["material_source"] == "database-default"


def test_import_cdm_csv_explicit_material_overrides_job(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    app, mocks = _mock_import(monkeypatch, job_material=2)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("x", encoding="utf-8")
    result = app.import_cdm_csv(str(csv_file), job="J1", material="MDF_18")
    assert result["success"] is True
    mocks["job_material_id"].assert_not_called()
    mocks["set_job_material"].assert_called_once_with("J1", 2)
    mocks["set_order_detail_material"].assert_called_once_with("J1", 2)
    assert result["material_source"] == "explicit"


def _mock_create_group(
    monkeypatch: pytest.MonkeyPatch,
    group_sheets: list[dict[str, Any]],
    *,
    material_groups: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, MagicMock]:
    mocks: dict[str, MagicMock] = {
        "resolve": MagicMock(return_value=group_sheets),
        "set_selected": MagicMock(return_value=True),
        "set_job_material": MagicMock(return_value=True),
        "finalize": MagicMock(return_value=True),
        "set_sheet_order": MagicMock(return_value=True),
        "cleanup": MagicMock(return_value=(True, "")),
    }
    monkeypatch.setattr("alphacam_cli.core.cdm_db.job_count", MagicMock(return_value=0))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.resolve_material_group", mocks["resolve"])
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.material_groups",
        lambda: (
            material_groups
            if material_groups is not None
            else {
                "MDF_18": [
                    {"id": 2, "name": "MDF_18", "offcut": False},
                    {"id": 7, "name": "MDF18", "offcut": False},
                ]
            }
        ),
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", mocks["set_job_material"])
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_selected_sheets", mocks["set_selected"])
    monkeypatch.setattr("alphacam_cli.core.cdm_db.finalize_cdm_job", mocks["finalize"])
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_sheet_order", mocks["set_sheet_order"])
    monkeypatch.setattr("alphacam_cli.core.cdm_db.cleanup_created_job", mocks["cleanup"])
    return mocks


def test_create_cdm_job_material_group(monkeypatch: pytest.MonkeyPatch) -> None:
    group = [
        {"id": 2, "name": "MDF_18", "offcut": False, "quantity": 0},
        {"id": 7, "name": "MDF18", "offcut": False, "quantity": 0},
    ]
    mocks = _mock_create_group(monkeypatch, group)
    app, _am = _new_job_app()
    result = app.create_cdm_job("JOB-001", config="Fronty", material_group="MDF_18")
    assert result["success"] is True
    assert result["material_group"] == "MDF_18 (group: MDF_18#2, MDF18#7)"
    assert result["material"] == "MDF_18 (group: MDF_18#2, MDF18#7)"
    mocks["resolve"].assert_called_once_with(
        "MDF_18", include_offcuts=False, offcuts_first=False, whole_quantity=0, offcut_quantity=1
    )
    mocks["set_job_material"].assert_called_once_with("JOB-001", 0)
    mocks["finalize"].assert_called_once_with("JOB-001")
    mocks["set_selected"].assert_called_once_with("JOB-001", group)
    mocks["set_sheet_order"].assert_not_called()
    mocks["cleanup"].assert_not_called()


def test_create_cdm_job_material_group_prefer_offcuts(monkeypatch: pytest.MonkeyPatch) -> None:
    group = [
        {"id": 9, "name": "OFF", "offcut": True, "quantity": 1},
        {"id": 2, "name": "MDF_18", "offcut": False, "quantity": 0},
    ]
    mocks = _mock_create_group(monkeypatch, group)
    app, _am = _new_job_app()
    result = app.create_cdm_job(
        "JOB-001", config="Fronty", material_group="MDF_18", prefer_offcuts=True
    )
    mocks["resolve"].assert_called_once_with(
        "MDF_18", include_offcuts=True, offcuts_first=True, whole_quantity=0, offcut_quantity=1
    )
    mocks["set_sheet_order"].assert_called_once_with("Fronty", 1)
    assert any(
        "sheet order set to picked globally for configuration 'Fronty'" in w
        for w in result["warnings"]
    )
    assert "failed to set sheet order" not in " ".join(result["warnings"])


def test_create_cdm_job_group_validations(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_create_group(monkeypatch, [])
    app, am = _new_job_app()
    with pytest.raises(RuntimeError, match="mutually exclusive"):
        app.create_cdm_job("JOB-001", config="Fronty", material="MDF_18", material_group="MDF_18")
    with pytest.raises(RuntimeError, match="require --material-group"):
        app.create_cdm_job("JOB-001", config="Fronty", prefer_offcuts=True)
    with pytest.raises(RuntimeError, match="forces picked order"):
        app.create_cdm_job(
            "JOB-001",
            config="Fronty",
            material_group="MDF_18",
            prefer_offcuts=True,
            sheet_order="best",
        )
    with pytest.raises(RuntimeError, match="sheet-order"):
        app.create_cdm_job(
            "JOB-001", config="Fronty", material_group="MDF_18", sheet_order="fastest"
        )
    am.NewCDMJob.assert_not_called()


def test_create_cdm_job_sheets_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    mocks = _mock_create_group(monkeypatch, [])
    app, _am = _new_job_app()
    result = app.create_cdm_job("JOB-001", config="Fronty", sheets="2:0, 7:1")
    assert result["success"] is True
    mocks["resolve"].assert_not_called()
    mocks["set_selected"].assert_called_once_with(
        "JOB-001", [{"id": 2, "quantity": 0}, {"id": 7, "quantity": 1}]
    )
    assert result["material_group"] == "sheets: 2:0, 7:1"


def test_create_cdm_job_whitespace_material_with_group(monkeypatch: pytest.MonkeyPatch) -> None:
    group = [{"id": 2, "name": "MDF_18", "offcut": False, "quantity": 0}]
    mocks = _mock_create_group(monkeypatch, group)
    app, _am = _new_job_app()
    result = app.create_cdm_job("JOB-001", config="Fronty", material="   ", material_group="MDF_18")
    assert result["success"] is True
    mocks["set_job_material"].assert_called_once_with("JOB-001", 0)
    mocks["set_selected"].assert_called_once_with("JOB-001", group)


def test_create_cdm_job_sheets_unknown_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_create_group(monkeypatch, [])
    app, _am = _new_job_app()
    with pytest.raises(RuntimeError, match="unknown sheet id"):
        app.create_cdm_job("JOB-001", config="Fronty", sheets="2:0, 99:1")


def test_create_cdm_job_without_group_regression(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _am = _new_job_app()
    monkeypatch.setattr("alphacam_cli.core.cdm_db.job_count", MagicMock(return_value=0))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 2})
    set_job_material = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", set_job_material)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.finalize_cdm_job", lambda jn: True)
    set_selected = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_selected_sheets", set_selected)
    result = app.create_cdm_job("JOB-001", config="Fronty", material="MDF_18")
    assert result["material"] == "MDF_18"
    assert result["material_group"] is None
    set_job_material.assert_called_once_with("JOB-001", 2)
    set_selected.assert_not_called()
