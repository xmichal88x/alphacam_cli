from __future__ import annotations

from typer.testing import CliRunner

from alphacam_cli.main import app

runner = CliRunner()


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
    result = runner.invoke(app, ["drawing", "create"])
    assert result.exit_code == 1
    assert "AlphaCAM CLI requires Windows" in result.stderr


def test_tool_list_requires_windows() -> None:
    result = runner.invoke(app, ["tool", "list"])
    assert result.exit_code == 1
    assert "AlphaCAM CLI requires Windows" in result.stderr


def test_mill_rough_requires_windows() -> None:
    result = runner.invoke(app, ["mill", "rough"])
    assert result.exit_code == 1
    assert "AlphaCAM CLI requires Windows" in result.stderr


def test_nc_output_requires_windows() -> None:
    result = runner.invoke(app, ["nc", "output", "test.nc"])
    assert result.exit_code == 1
    assert "AlphaCAM CLI requires Windows" in result.stderr


def test_batch_requires_windows() -> None:
    result = runner.invoke(app, ["batch", "process", "."])
    assert result.exit_code == 1
    assert "AlphaCAM CLI requires Windows" in result.stderr


def test_nest_run_requires_windows() -> None:
    result = runner.invoke(app, ["nest", "run", "test.csv"])
    assert result.exit_code == 1
    assert "AlphaCAM CLI requires Windows" in result.stderr


def test_post_list_requires_windows() -> None:
    result = runner.invoke(app, ["post", "list"])
    assert result.exit_code == 1
    assert "AlphaCAM CLI requires Windows" in result.stderr


def test_diagnose_no_com() -> None:
    """Test that diagnose handles missing COM gracefully."""
    from alphacam_cli.cli.diagnose import app as diagnose_app

    runner = CliRunner()
    result = runner.invoke(diagnose_app, [])
    assert result.exit_code in (0, 1)
