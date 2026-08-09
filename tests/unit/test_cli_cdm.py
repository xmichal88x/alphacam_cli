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
                "material": None,
            },
        ) as mock_run_cdm,
    ):
        result = runner.invoke(
            app,
            ["cdm", "create", "JOB-001", "Typ Frontu 1", "--width", "500", "--quantity", "2"],
        )
    assert result.exit_code == 0
    assert "CDM job created: JOB-001" in result.stderr
    assert "Typ Frontu 1" in result.stderr
    assert "500.0x300.0" in result.stderr
    mock_run_cdm.assert_called_once_with(
        job_name="JOB-001",
        type_name="Typ Frontu 1",
        width=500.0,
        length=300.0,
        quantity=2,
        bypass_nest=False,
        material=None,
    )


def test_cdm_create_command_material() -> None:
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
                "material": "MDF_18",
            },
        ) as mock_run_cdm,
    ):
        result = runner.invoke(
            app, ["cdm", "create", "JOB-001", "Typ Frontu 1", "--material", "MDF_18"]
        )
    assert result.exit_code == 0
    assert "Material: MDF_18" in result.stderr
    mock_run_cdm.assert_called_once_with(
        job_name="JOB-001",
        type_name="Typ Frontu 1",
        width=400.0,
        length=300.0,
        quantity=1,
        bypass_nest=False,
        material="MDF_18",
    )


def test_cdm_create_command_material_error() -> None:
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
                "material": "MDF_18",
                "material_error": "failed to set material",
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "create", "JOB-001", "Typ Frontu 1"])
    assert result.exit_code == 0
    assert "WARNING" in result.stderr
    assert "failed to set material" in result.stderr


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
        separator=None,
        has_header=False,
        material=None,
        import_setting=None,
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
        separator=None,
        has_header=False,
        material=None,
        import_setting=None,
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
        separator=None,
        has_header=False,
        material=None,
        import_setting=None,
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
        material=None,
        import_setting=None,
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


def test_cdm_import_command_material() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.import_cdm_csv",
            return_value={
                "success": True,
                "job_name": "order",
                "items": 1,
                "material": "MDF_18",
                "errors": [],
            },
        ) as mock_import,
    ):
        result = runner.invoke(app, ["cdm", "import", r"C:\temp\order.csv", "--material", "MDF_18"])
    assert result.exit_code == 0
    assert "CDM job created: order (1 item(s))" in result.stderr
    assert "Material: MDF_18" in result.stderr
    mock_import.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        job=None,
        name=None,
        config=None,
        separator=None,
        has_header=False,
        material="MDF_18",
        import_setting=None,
    )


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


def test_cdm_import_command_import_setting() -> None:
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
            app, ["cdm", "import", r"C:\temp\order.csv", "--import-setting", "3"]
        )
    assert result.exit_code == 0
    mock_import.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        job=None,
        name=None,
        config=None,
        separator=None,
        has_header=False,
        material=None,
        import_setting=3,
    )


def test_cdm_import_command_import_setting_name() -> None:
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
            app, ["cdm", "import", r"C:\temp\order.csv", "--import-setting", "sklep CSV"]
        )
    assert result.exit_code == 0
    mock_import.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        job=None,
        name=None,
        config=None,
        separator=None,
        has_header=False,
        material=None,
        import_setting="sklep CSV",
    )


def test_cdm_import_command_import_setting_separator_override() -> None:
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
            app,
            [
                "cdm",
                "import",
                r"C:\temp\order.csv",
                "--import-setting",
                "3",
                "--separator",
                ";",
            ],
        )
    assert result.exit_code == 0
    mock_import.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        job=None,
        name=None,
        config=None,
        separator=";",
        has_header=False,
        material=None,
        import_setting=3,
    )


def test_cdm_import_command_preview() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.import_cdm_preview",
            return_value={
                "success": True,
                "setting": {
                    "id": 3,
                    "name": "sklep CSV",
                    "delimiter_char": ";",
                    "create_job": True,
                    "selected": False,
                },
                "field_map": [
                    {"column": 1, "field": "door_type", "required": True},
                    {"column": 2, "field": "door_quantity", "required": True},
                    {"column": 3, "field": "door_width", "required": True},
                    {"column": 4, "field": "door_height", "required": True},
                ],
                "job_name": "order",
                "config": "Fronty",
                "material": "MDF_18",
                "items": 1,
                "rows": [
                    {
                        "row": 2,
                        "style": "Typ Frontu 1",
                        "quantity": 2,
                        "width": 500.0,
                        "length": 300.0,
                        "material": "MDF_18",
                        "customer_name": "Klient A",
                        "order_number": "Z-001",
                        "production_comment": "uwaga",
                        "custom_fields": {"1": "x", "2": "y"},
                        "job_name": "order",
                    }
                ],
                "errors": [],
                "job": None,
            },
        ) as mock_preview,
    ):
        result = runner.invoke(app, ["cdm", "import", r"C:\temp\order.csv", "--preview"])
    assert result.exit_code == 0
    assert "PREVIEW (dry run, no changes)" in result.stderr
    assert "Field mapping" in result.stderr
    assert "Import settings: sklep CSV" in result.stderr
    assert "Job: order" in result.stderr
    mock_preview.assert_called_once_with(
        csv=r"C:\temp\order.csv",
        import_setting=None,
        separator=None,
        has_header=False,
        job=None,
        name=None,
        config=None,
        material=None,
    )


def test_cdm_import_command_preview_failure() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.import_cdm_preview",
            return_value={
                "success": False,
                "setting": None,
                "field_map": [],
                "job_name": "order",
                "config": None,
                "material": None,
                "items": 0,
                "rows": [],
                "errors": ["row 1: door type not found: XYZ"],
                "job": None,
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "import", r"C:\temp\order.csv", "--preview"])
    assert result.exit_code == 1
    assert "ERROR" in result.stderr
    assert "door type not found" in result.stderr


def test_cdm_import_command_preview_no_items() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.import_cdm_preview",
            return_value={
                "success": True,
                "setting": None,
                "field_map": [],
                "job_name": "order",
                "config": None,
                "material": None,
                "items": 0,
                "rows": [],
                "errors": [],
                "job": None,
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "import", r"C:\temp\order.csv", "--preview"])
    assert result.exit_code == 1
    assert "No items to import" in result.stderr


def test_cdm_import_settings_list_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_import_settings",
            return_value={
                "settings": [
                    {
                        "id": 1,
                        "name": "Domyslny",
                        "selected": True,
                        "create_job": False,
                        "delimiter_char": ",",
                        "fields": "1→door_type, 2→door_quantity, 3→door_width",
                        "fields_count": 3,
                    },
                    {
                        "id": 3,
                        "name": "sklep CSV",
                        "selected": False,
                        "create_job": True,
                        "delimiter_char": ";",
                        "fields": "1→door_type, 2→door_quantity, 4→door_width",
                        "fields_count": 3,
                    },
                ]
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "import-settings", "list"])
    assert result.exit_code == 0
    assert "sklep CSV" in result.stderr
    assert "Import Settings" in result.stderr
    assert "Domyslny" in result.stderr


def test_cdm_import_settings_list_empty() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_import_settings",
            return_value={"settings": []},
        ),
    ):
        result = runner.invoke(app, ["cdm", "import-settings", "list"])
    assert result.exit_code == 0
    assert "No CDM import settings found" in result.stderr
