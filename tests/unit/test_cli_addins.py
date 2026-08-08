from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from alphacam_cli.main import app

runner = CliRunner()


def test_reports_create_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.reports_create",
            return_value={"success": True, "job": "ok", "active_drawing": True},
        ),
    ):
        result = runner.invoke(app, ["reports", "create"])
    assert result.exit_code == 0
    assert "Reports created (job=ok)" in result.stderr
    assert "Active drawing" in result.stderr


def test_ncmanager_config_list_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.nc_configs",
            return_value={"count": 2, "configs": ["Alpha", "Beta"]},
        ),
    ):
        result = runner.invoke(app, ["ncmanager", "config", "list"])
    assert result.exit_code == 0
    assert "2 found" in result.stderr
    assert "Alpha" in result.stderr
    assert "Beta" in result.stderr


def test_autostyle_apply_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.auto_style_apply",
            return_value={"success": True, "file": r"C:\styles\auto.style"},
        ),
    ):
        result = runner.invoke(app, ["autostyle", "apply", r"C:\styles\auto.style"])
    assert result.exit_code == 0
    assert "Auto-style applied: C:\\styles\\auto.style" in result.stderr
