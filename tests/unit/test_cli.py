from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from unittest.mock import MagicMock, mock_open, patch

import pytest
from typer.testing import CliRunner

from alphacam_cli.main import app

runner = CliRunner()


def _make_app_mock() -> MagicMock:
    app = MagicMock()
    app.Visible = False
    app.AlphacamVersion = "2024.1"
    app.FullName = "C:\\AlphaCAM\\alphaCAM.exe"
    app.Name = "AlphaCAM"
    app.ProgramLevel = 3
    app.ProgramLetter = 82
    app.LicomdatPath = "C:\\Licomdat"
    app.LicomdirPath = "C:\\Licomdir"
    app.PostFileName = "fanuc.pst"
    app.ApiVersion = 20240315

    drw = MagicMock()
    drw.Geometries.Count = 0
    drw.ToolPaths.Count = 0
    app.ActiveDrawing = drw
    app.CreateTempDrawing.return_value = drw
    app.OpenDrawing.return_value = drw

    tool = MagicMock()
    tool.Diameter = 10.0
    tool.Name = "Flat - 10mm"
    tool.Number = 1
    tool.Length = 50.0
    tool.Type = 0
    app.SelectTool.return_value = tool
    app.GetCurrentTool.return_value = tool

    md = MagicMock()
    md.SafeRapidLevel = 10.0
    md.RapidDownTo = 2.0
    md.FinalDepth = -10.0
    md.SpindleSpeed = 12000
    md.DownFeed = 2000.0
    md.CutFeed = 3000.0
    md.MaterialTop = 0.0
    md.MaxDepthPerCut = 2.5
    md.WidthOfCut = 5.0
    md.Stock = 0.5
    md.PocketType = 0
    md.BottomOfHole = -15.0
    md.DrillType = 0
    app.CreateMillData.return_value = md

    return app


_MOCK_PATCHES = [
    ("alphacam_cli.cli.common", "require_platform"),
    ("alphacam_cli.cli.connect", "require_platform"),
    ("alphacam_cli.cli.connect", "alphacam_context"),
    ("alphacam_cli.cli.drawing", "require_platform"),
    ("alphacam_cli.cli.drawing", "alphacam_context"),
    ("alphacam_cli.cli.tool", "require_platform"),
    ("alphacam_cli.cli.tool", "alphacam_context"),
    ("alphacam_cli.cli.mill", "require_platform"),
    ("alphacam_cli.cli.mill", "alphacam_context"),
    ("alphacam_cli.cli.nc", "require_platform"),
    ("alphacam_cli.cli.nc", "alphacam_context"),
    ("alphacam_cli.cli.diagnose", "alphacam_context"),
    ("alphacam_cli.cli.post", "require_platform"),
    ("alphacam_cli.cli.post", "alphacam_context"),
    ("alphacam_cli.cli.nest", "require_platform"),
    ("alphacam_cli.cli.nest", "alphacam_context"),
    ("alphacam_cli.com.manager", "alphacam_context"),
]


@contextmanager
def _mock_com(app_mock: MagicMock | None = None) -> Iterator[MagicMock]:
    """Mock both require_platform and alphacam_context for CLI testing.

    Usage::

        with _mock_com() as app:
            result = runner.invoke(app, ["connect", "info"])
        assert result.exit_code == 0

    For tests that need custom mock config::

        with _mock_com() as app:
            app.ActiveDrawing.Geometries.Count = 5
            result = runner.invoke(app, ["mill", "rough", ...])
    """
    if app_mock is None:
        app_mock = _make_app_mock()

    @contextmanager
    def fake_context(visible: bool = False, prog_id: str | None = None) -> Iterator[MagicMock]:  # noqa: ARG001
        yield app_mock

    with ExitStack() as stack:
        for mod, attr in _MOCK_PATCHES:
            if attr == "alphacam_context":
                stack.enter_context(patch(f"{mod}.{attr}", fake_context))
            else:
                stack.enter_context(patch(f"{mod}.{attr}"))
        yield app_mock


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "alphacam-cli" in result.stdout


def test_help_shows_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "connect" in result.stdout
    assert "drawing" in result.stdout
    assert "tool" in result.stdout
    assert "mill" in result.stdout
    assert "nc" in result.stdout
    assert "batch" in result.stdout
    assert "nest" in result.stdout
    assert "post" in result.stdout


def test_connect_info_requires_windows() -> None:
    """Test that connect info fails on non-Windows platforms."""
    from unittest.mock import patch

    with patch("sys.platform", "linux"):
        result = runner.invoke(app, ["connect", "info"])
        assert result.exit_code == 1
        assert "requires Windows" in result.stderr


def test_drawing_create_requires_windows() -> None:
    with patch("sys.platform", "linux"):
        result = runner.invoke(app, ["drawing", "create"])
    assert result.exit_code == 1
    assert "AlphaCAM CLI requires Windows" in result.stderr


def test_tool_list_requires_windows() -> None:
    with patch("sys.platform", "linux"):
        result = runner.invoke(app, ["tool", "list"])
    assert result.exit_code == 1
    assert "AlphaCAM CLI requires Windows" in result.stderr


def test_mill_rough_requires_windows() -> None:
    with patch("sys.platform", "linux"):
        result = runner.invoke(app, ["mill", "rough"])
    assert result.exit_code == 1
    assert "AlphaCAM CLI requires Windows" in result.stderr


def test_nc_output_requires_windows() -> None:
    with patch("sys.platform", "linux"):
        result = runner.invoke(app, ["nc", "output", "test.nc"])
    assert result.exit_code == 1
    assert "AlphaCAM CLI requires Windows" in result.stderr


def test_batch_requires_windows() -> None:
    with patch("sys.platform", "linux"):
        result = runner.invoke(app, ["batch", "process", "."])
    assert result.exit_code == 1
    assert "AlphaCAM CLI requires Windows" in result.stderr


def test_nest_run_requires_windows() -> None:
    with patch("sys.platform", "linux"):
        result = runner.invoke(app, ["nest", "run", "test.csv"])
    assert result.exit_code == 1
    assert "AlphaCAM CLI requires Windows" in result.stderr


def test_post_list_requires_windows() -> None:
    with patch("sys.platform", "linux"):
        result = runner.invoke(app, ["post", "list"])
    assert result.exit_code == 1
    assert "AlphaCAM CLI requires Windows" in result.stderr


def test_diagnose_no_com() -> None:
    """Test that diagnose handles missing COM gracefully."""
    from alphacam_cli.cli.diagnose import app as diagnose_app

    runner = CliRunner()
    result = runner.invoke(diagnose_app, [])
    assert "Diagnostics" in result.stderr


def test_load_typer_import_error() -> None:
    from alphacam_cli.main import _load_typer

    with pytest.raises(ImportError):
        _load_typer("nonexistent.module")


def test_load_typer_missing_attribute() -> None:
    from alphacam_cli.main import _load_typer

    with patch("importlib.import_module") as mock_import:
        mock_import.return_value = object()
        with pytest.raises(AttributeError):
            _load_typer("some.module")


# =============================================================================
# Testy logiki CLI z mockowanym COM
# =============================================================================


def test_connect_info() -> None:
    with _mock_com():
        result = runner.invoke(app, ["connect", "info"])
    assert result.exit_code == 0
    assert "Name" in result.stderr
    assert "Version" in result.stderr
    assert "Module" in result.stderr


def test_connect_info_custom_prog_id() -> None:
    with _mock_com():
        result = runner.invoke(app, ["connect", "info", "--progid", "Custom.App"])
    assert result.exit_code == 0
    assert "Name" in result.stderr
    assert "AlphaCAM" in result.stderr


def test_drawing_create() -> None:
    with _mock_com():
        result = runner.invoke(app, ["drawing", "create", "-w", "200", "-h", "100"])
    assert result.exit_code == 0
    assert "200" in result.stderr
    assert "100" in result.stderr


def test_drawing_create_with_fillet_text() -> None:
    with _mock_com():
        result = runner.invoke(
            app, ["drawing", "create", "-w", "200", "-h", "100", "--fillet", "5", "--text", "Hello"]
        )
    assert result.exit_code == 0
    assert "Fillet" in result.stderr
    assert "5.0" in result.stderr


def test_drawing_save() -> None:
    with _mock_com():
        result = runner.invoke(app, ["drawing", "save", "output.amd"])
    assert result.exit_code == 0
    assert "Saved to" in result.stderr


def test_drawing_open() -> None:
    with _mock_com():
        result = runner.invoke(app, ["drawing", "open", "test.amd"])
    assert result.exit_code == 0
    assert "Geometries" in result.stderr
    assert "ToolPaths" in result.stderr


def test_drawing_info() -> None:
    with _mock_com():
        result = runner.invoke(app, ["drawing", "info"])
    assert result.exit_code == 0
    assert "Geometries" in result.stderr
    assert "ToolPaths" in result.stderr


def test_tool_list() -> None:
    paths = ["C:\\tools\\Flat-10mm.amt", "C:\\tools\\Ball-6mm.amt"]
    with (
        _mock_com(),
        patch("alphacam_cli.core.application.Application.find_tool_files", return_value=paths),
    ):
        result = runner.invoke(app, ["tool", "list"])
    assert result.exit_code == 0
    assert "Flat-10mm" in result.stderr
    assert "Ball-6mm" in result.stderr


def test_tool_list_empty() -> None:
    with _mock_com():
        result = runner.invoke(app, ["tool", "list"])
    assert result.exit_code == 0
    assert "No tools found" in result.stderr


def test_tool_select_by_name() -> None:
    paths = ["C:\\tools\\Flat-10mm.amt", "C:\\tools\\Ball-6mm.amt"]
    with (
        _mock_com(),
        patch("alphacam_cli.core.application.Application.find_tool_files", return_value=paths),
    ):
        result = runner.invoke(app, ["tool", "select", "Flat-10mm"])
    assert result.exit_code == 0
    assert "Flat" in result.stderr or "Diameter" in result.stderr


def test_tool_select_no_match() -> None:
    paths = ["C:\\tools\\Flat-10mm.amt", "C:\\tools\\Ball-6mm.amt"]
    with (
        _mock_com(),
        patch("alphacam_cli.core.application.Application.find_tool_files", return_value=paths),
    ):
        result = runner.invoke(app, ["tool", "select", "NotFound"])
    assert result.exit_code == 1
    assert "No tool matching" in result.stderr


def test_tool_current() -> None:
    with _mock_com():
        result = runner.invoke(app, ["tool", "current"])
    assert result.exit_code == 0
    assert "Flat" in result.stderr
    assert "Diameter" in result.stderr


def test_mill_rough() -> None:
    with _mock_com() as app_mock:
        app_mock.ActiveDrawing.Geometries.Count = 3
        result = runner.invoke(app, ["mill", "rough", "-d", "-10", "-s", "12000"])
    assert result.exit_code == 0
    assert "ToolPaths" in result.stderr


def test_mill_rough_no_geometries() -> None:
    with _mock_com():
        result = runner.invoke(app, ["mill", "rough", "-d", "-10", "-s", "12000"])
    assert result.exit_code == 0
    assert "No geometries" in result.stderr


def test_mill_pocket() -> None:
    with _mock_com() as app_mock:
        app_mock.ActiveDrawing.Geometries.Count = 2
        result = runner.invoke(app, ["mill", "pocket"])
    assert result.exit_code == 0
    assert "Pocket done" in result.stderr


def test_mill_drill() -> None:
    with _mock_com() as app_mock:
        app_mock.ActiveDrawing.Geometries.Count = 4
        result = runner.invoke(app, ["mill", "drill"])
    assert result.exit_code == 0
    assert "Drill done" in result.stderr


def test_mill_rough_invalid_depth() -> None:
    result = runner.invoke(app, ["mill", "rough", "--depth", "5"])
    assert result.exit_code == 2
    assert "Depth must be negative" in result.stderr


def test_mill_rough_invalid_speed() -> None:
    result = runner.invoke(app, ["mill", "rough", "--spindle", "200000"])
    assert result.exit_code == 2
    assert "Spindle speed out of range" in result.stderr


def test_mill_rough_invalid_feed() -> None:
    result = runner.invoke(app, ["mill", "rough", "--feed", "-1"])
    assert result.exit_code == 2
    assert "Feed cannot be negative" in result.stderr


def test_mill_rough_no_active_drawing() -> None:
    with _mock_com() as app_mock:
        app_mock.ActiveDrawing = None
        result = runner.invoke(app, ["mill", "rough", "-d", "-10"])
    assert result.exit_code == 1
    assert "No active drawing" in result.stderr


def test_mill_rough_fallback() -> None:
    with _mock_com() as app_mock:
        md = app_mock.CreateMillData.return_value
        md.RoughFinish.side_effect = [Exception("fail"), None]
        app_mock.ActiveDrawing.Geometries.Count = 3
        result = runner.invoke(app, ["mill", "rough", "-d", "-10"])
    assert result.exit_code == 0
    assert md.RoughFinish.call_count == 2
    assert md.ProcessType2 == 2


def test_mill_pocket_no_active_drawing() -> None:
    with _mock_com() as app_mock:
        app_mock.ActiveDrawing = None
        result = runner.invoke(app, ["mill", "pocket"])
    assert result.exit_code == 1
    assert "No active drawing" in result.stderr


def test_mill_drill_invalid_type() -> None:
    result = runner.invoke(app, ["mill", "drill", "--type", "invalid"])
    assert result.exit_code == 2
    assert "Invalid drill type" in result.stderr


def test_mill_drill_no_active_drawing() -> None:
    with _mock_com() as app_mock:
        app_mock.ActiveDrawing = None
        result = runner.invoke(app, ["mill", "drill"])
    assert result.exit_code == 1
    assert "No active drawing" in result.stderr


def test_nc_output() -> None:
    m = mock_open(read_data="N100 G0 X0 Y0\n")
    with _mock_com(), patch("os.path.exists", return_value=True), patch("builtins.open", m):
        result = runner.invoke(app, ["nc", "output", "test.nc"])
    assert result.exit_code == 0
    assert "NC output generated" in result.stderr


def test_nc_output_with_post() -> None:
    m = mock_open(read_data="N100 G0 X0 Y0\n")
    with (
        _mock_com() as app_mock,
        patch("os.path.exists", return_value=True),
        patch("builtins.open", m),
    ):
        result = runner.invoke(app, ["nc", "output", "test.nc", "--post", "fanuc"])
    assert result.exit_code == 0
    assert "Post selected" in result.stderr
    assert "fanuc" in result.stderr
    app_mock.SelectPost.assert_called_once_with("fanuc")


def test_nc_output_no_active_drawing() -> None:
    with _mock_com() as app_mock:
        app_mock.ActiveDrawing = None
        result = runner.invoke(app, ["nc", "output", "test.nc"])
    assert result.exit_code == 1
    assert "No active drawing" in result.stderr


def test_nc_output_file_not_created() -> None:
    with _mock_com():
        result = runner.invoke(app, ["nc", "output", "test.nc"])
    assert result.exit_code == 1
    assert "NC file not created" in result.stderr


def test_diagnose() -> None:
    with _mock_com():
        result = runner.invoke(app, ["diagnose", "diagnose"])
    assert result.exit_code == 0
    assert "AlphaCAM Diagnostics" in result.stderr
