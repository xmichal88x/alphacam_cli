from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from alphacam_cli.main import app

runner = CliRunner()


def test_cdm_create_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.run_cdm",
            return_value={
                "success": True,
                "job_name": "JOB-001",
                "type_name": "Typ Frontu 1",
                "width": 500.0,
                "length": 300.0,
                "quantity": 2,
            },
        ),
    ):
        result = runner.invoke(
            app,
            ["cdm", "create", "JOB-001", "Typ Frontu 1", "--width", "500", "--quantity", "2"],
        )
    assert result.exit_code == 0
    assert "CDM job created: JOB-001" in result.stderr
    assert "Typ Frontu 1" in result.stderr
    assert "500.0x300.0" in result.stderr


def test_cdm_create_process_message() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.run_cdm",
            return_value={
                "success": True,
                "job_name": "JOB-001",
                "type_name": "Typ Frontu 1",
                "width": 400.0,
                "length": 300.0,
                "quantity": 1,
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "create", "JOB-001", "Typ Frontu 1", "--process"])
    assert result.exit_code == 0
    assert "wymaga GUI (Session 2)" in result.stderr


def test_cdm_create_error() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.run_cdm",
            side_effect=RuntimeError("cdm: door type not found: XYZ"),
        ),
    ):
        result = runner.invoke(app, ["cdm", "create", "JOB-001", "XYZ"])
    assert result.exit_code == 1
    assert "door type not found" in result.stderr


def test_cdm_types_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_types",
            return_value={
                "types": [
                    {"id": 1, "name": "Typ Frontu 1"},
                    {"id": 2, "name": "L_B_10mm"},
                ]
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "types"])
    assert result.exit_code == 0
    assert "Typ Frontu 1" in result.stderr
    assert "L_B_10mm" in result.stderr


def test_cdm_types_empty() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_types",
            return_value={"types": [], "note": "no CDM jobs yet"},
        ),
    ):
        result = runner.invoke(app, ["cdm", "types"])
    assert result.exit_code == 0
    assert "No CDM door types found" in result.stderr
    assert "no CDM jobs yet" in result.stderr


def test_cdm_jobs_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_jobs",
            return_value={"jobs": [{"id": 1, "name": "JOB-001"}, {"id": 2, "name": "JOB-002"}]},
        ),
    ):
        result = runner.invoke(app, ["cdm", "jobs"])
    assert result.exit_code == 0
    assert "JOB-001" in result.stderr
    assert "JOB-002" in result.stderr


def test_cdm_jobs_empty() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_jobs",
            return_value={"jobs": []},
        ),
    ):
        result = runner.invoke(app, ["cdm", "jobs"])
    assert result.exit_code == 0
    assert "No CDM jobs found" in result.stderr


def test_cdm_import_command_requires_gui() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.import_cdm_csv",
            side_effect=RuntimeError("cdm: CSV import requires GUI (Session 2)"),
        ),
    ):
        result = runner.invoke(app, ["cdm", "import", r"C:\temp\order.csv"])
    assert result.exit_code == 1
    assert "requires GUI" in result.stderr


def test_cdm_delete_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.delete_cdm_job",
            return_value={"success": True, "job_name": "JOB-001"},
        ),
    ):
        result = runner.invoke(app, ["cdm", "delete", "JOB-001"])
    assert result.exit_code == 0
    assert "CDM job deleted: JOB-001" in result.stderr


def test_cdm_delete_command_error() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.delete_cdm_job",
            side_effect=RuntimeError("cdm: job not found: NOPE"),
        ),
    ):
        result = runner.invoke(app, ["cdm", "delete", "NOPE"])
    assert result.exit_code == 1
    assert "job not found" in result.stderr
