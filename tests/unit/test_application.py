from __future__ import annotations

from alphacam_cli.core.application import Application


def test_application_properties(mock_com):
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


def test_application_visible_setter(mock_com):
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            ac.visible = True
            assert ac.visible is True
            ac.visible = False
            assert ac.visible is False


def test_get_active_drawing(mock_com):
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context() as raw:
            ac = Application(raw)
            drw = ac.get_active_drawing()
            assert drw is not None
            assert drw.geometries_count == 0
