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
            return_value={
                "success": True,
                "job": "ok",
                "active_drawing": True,
                "settings_file": "raport_test.acreps",
            },
        ),
    ):
        result = runner.invoke(app, ["reports", "create", "--job", "Fronty"])
    assert result.exit_code == 0
    assert "Reports created (job=ok)" in result.stderr
    assert "Active drawing" in result.stderr
    assert "raport_test.acreps" in result.stderr


def test_reports_create_command_job_name_passed() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.reports_create",
            return_value={"success": True, "job": "ok", "active_drawing": True},
        ) as reports_create,
    ):
        result = runner.invoke(app, ["reports", "create", "--job", "Fronty"])
    assert result.exit_code == 0
    reports_create.assert_called_once_with(job_name="Fronty")


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


def test_autostyle_apply_rejects_pipeline_flags() -> None:
    from tests.unit.test_cli import _mock_com

    with _mock_com():
        result = runner.invoke(
            app,
            [
                "autostyle",
                "apply",
                r"C:\styles\auto.ara",
                "--agq",
                r"C:\ALPHACAM\LICOMDIR\Queries\Menadżer_Warstw_Fronty.agq",
            ],
        )
    assert result.exit_code == 2
    assert "No such option" in result.stderr
    assert "--agq" in result.stderr

    with _mock_com():
        result = runner.invoke(
            app,
            ["autostyle", "apply", r"C:\styles\auto.ara", "--layer-map", "KONTUR:1"],
        )
    assert result.exit_code == 2
    assert "No such option" in result.stderr
    assert "--layer-map" in result.stderr
