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


def test_cdm_import_command_success() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.import_cdm_csv",
            return_value={
                "success": True,
                "job_name": "order",
                "items": 2,
                "errors": [],
            },
        ) as mock_import,
    ):
        result = runner.invoke(app, ["cdm", "import", r"C:\temp\order.csv"])
    assert result.exit_code == 0
    assert "CDM job created: order (2 item(s))" in result.stderr
    assert "Imported:" in result.stderr
    mock_import.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        job=None,
        name=None,
        config=None,
        separator=",",
        has_header=False,
    )


def test_cdm_import_command_update_existing_job() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.import_cdm_csv",
            return_value={
                "success": True,
                "job_name": "JOB-001",
                "items": 3,
                "errors": [],
            },
        ) as mock_import,
    ):
        result = runner.invoke(app, ["cdm", "import", r"C:\temp\order.csv", "--job", "JOB-001"])
    assert result.exit_code == 0
    assert "CDM job updated: JOB-001 (3 item(s))" in result.stderr
    mock_import.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        job="JOB-001",
        name=None,
        config=None,
        separator=",",
        has_header=False,
    )


def test_cdm_import_command_name_and_config() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.import_cdm_csv",
            return_value={
                "success": True,
                "job_name": "Zadanie 132",
                "items": 1,
                "errors": [],
            },
        ) as mock_import,
    ):
        result = runner.invoke(
            app,
            [
                "cdm",
                "import",
                r"C:\temp\order.csv",
                "--name",
                "Zadanie 132",
                "--config",
                "Fronty",
            ],
        )
    assert result.exit_code == 0
    assert "CDM job created: Zadanie 132 (1 item(s))" in result.stderr
    mock_import.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        job=None,
        name="Zadanie 132",
        config="Fronty",
        separator=",",
        has_header=False,
    )


def test_cdm_import_command_header_flag() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.import_cdm_csv",
            return_value={
                "success": True,
                "job_name": "order",
                "items": 1,
                "errors": [],
            },
        ) as mock_import,
    ):
        result = runner.invoke(
            app, ["cdm", "import", r"C:\temp\order.csv", "--separator", ";", "--header"]
        )
    assert result.exit_code == 0
    assert "CDM job created: order (1 item(s))" in result.stderr
    mock_import.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        job=None,
        name=None,
        config=None,
        separator=";",
        has_header=True,
    )


def test_cdm_import_command_warnings() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.import_cdm_csv",
            return_value={
                "success": True,
                "job_name": "order",
                "items": 1,
                "errors": ["row 2: expected at least 5 columns, got 3"],
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "import", r"C:\temp\order.csv"])
    assert result.exit_code == 0
    assert "WARNING" in result.stderr
    assert "expected at least 5 columns" in result.stderr


def test_cdm_import_command_failure() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.import_cdm_csv",
            return_value={
                "success": False,
                "job_name": "order",
                "items": 0,
                "errors": ["row 1: door type not found: XYZ"],
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "import", r"C:\temp\order.csv"])
    assert result.exit_code == 1
    assert "ERROR" in result.stderr
    assert "door type not found" in result.stderr


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
