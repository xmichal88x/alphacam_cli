from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from alphacam_cli.cli.common import console
from alphacam_cli.main import app

runner = CliRunner()


@contextmanager
def _wide_console(width: int = 200) -> Iterator[None]:
    original = console.width
    console.width = width
    try:
        yield
    finally:
        console.width = original


def test_cdm_create_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.create_cdm_job",
            return_value={
                "success": True,
                "job_name": "JOB-001",
                "config": "Fronty",
                "material": "MDF_18",
                "warnings": [],
            },
        ) as mock_create,
    ):
        result = runner.invoke(app, ["cdm", "create", "JOB-001"])
    assert result.exit_code == 0
    assert "CDM job created: JOB-001" in result.stderr
    assert "Config: Fronty" in result.stderr
    assert "Material: MDF_18" in result.stderr
    mock_create.assert_called_once_with(
        job_name="JOB-001",
        config=None,
        material=None,
        customer=None,
        po=None,
        due_date=None,
        description=None,
    )


def test_cdm_create_command_config_material() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.create_cdm_job",
            return_value={
                "success": True,
                "job_name": "JOB-001",
                "config": "Fronty",
                "material": "MDF_18",
                "warnings": [],
            },
        ) as mock_create,
    ):
        result = runner.invoke(
            app, ["cdm", "create", "JOB-001", "--config", "Fronty", "--material", "MDF_18"]
        )
    assert result.exit_code == 0
    assert "CDM job created: JOB-001" in result.stderr
    mock_create.assert_called_once_with(
        job_name="JOB-001",
        config="Fronty",
        material="MDF_18",
        customer=None,
        po=None,
        due_date=None,
        description=None,
    )


def test_cdm_create_command_metadata() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.create_cdm_job",
            return_value={
                "success": True,
                "job_name": "JOB-001",
                "config": "Fronty",
                "material": "MDF_18",
                "warnings": [],
            },
        ) as mock_create,
    ):
        result = runner.invoke(
            app,
            [
                "cdm",
                "create",
                "JOB-001",
                "--customer",
                "Klient A",
                "--po",
                "PO-1",
                "--due-date",
                "2026-08-10",
                "--description",
                "opis",
            ],
        )
    assert result.exit_code == 0
    mock_create.assert_called_once_with(
        job_name="JOB-001",
        config=None,
        material=None,
        customer="Klient A",
        po="PO-1",
        due_date="2026-08-10",
        description="opis",
    )


def test_cdm_create_command_warnings() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.create_cdm_job",
            return_value={
                "success": True,
                "job_name": "JOB-001",
                "config": "Fronty",
                "material": "MDF_18",
                "warnings": ["failed to set customer", "cdm: customer not found: X"],
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "create", "JOB-001"])
    assert result.exit_code == 0
    assert "WARNING" in result.stderr
    assert "failed to set customer" in result.stderr
    assert "cdm: customer not found: X" in result.stderr


def test_cdm_create_command_failure() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.create_cdm_job",
            return_value={
                "success": False,
                "job_name": "JOB-001",
                "warnings": ["cdm: customer not found: X"],
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "create", "JOB-001"])
    assert result.exit_code == 1
    assert "CDM job creation failed: JOB-001" in result.stderr
    assert "WARNING" in result.stderr
    assert "cdm: customer not found: X" in result.stderr


def test_cdm_create_command_invalid_due_date() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.create_cdm_job",
        ) as mock_create,
    ):
        result = runner.invoke(app, ["cdm", "create", "JOB-001", "--due-date", "2026-13-40"])
    assert result.exit_code == 2
    assert "invalid due date" in result.stderr
    mock_create.assert_not_called()


def test_cdm_create_command_old_flags_removed() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.create_cdm_job",
            return_value={
                "success": True,
                "job_name": "JOB-001",
                "config": "Fronty",
                "material": None,
                "warnings": [],
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "create", "JOB-001", "Typ Frontu 1"])
    assert result.exit_code != 0
    assert "Got unexpected extra argument" in result.stderr


def test_cdm_create_error() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.create_cdm_job",
            side_effect=RuntimeError("cdm: config not found: Fronty"),
        ),
    ):
        result = runner.invoke(app, ["cdm", "create", "JOB-001"])
    assert result.exit_code == 1
    assert "config not found" in result.stderr


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


def test_cdm_import_command_name_job_conflict() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.import_cdm_csv",
        ) as mock_import,
    ):
        result = runner.invoke(
            app,
            ["cdm", "import", r"C:\temp\order.csv", "--name", "Zadanie 132", "--job", "JOB-001"],
        )
    assert result.exit_code == 2
    assert "mutually exclusive" in result.stderr
    mock_import.assert_not_called()


def test_cdm_import_command_empty_csv() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.import_cdm_csv",
            return_value={
                "success": False,
                "job_name": "order",
                "items": 0,
                "errors": [],
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "import", r"C:\temp\empty.csv"])
    assert result.exit_code == 1
    assert "No rows imported" in result.stderr
    assert "empty CSV or no valid rows" in result.stderr


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


def test_cdm_delete_command_failure() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.delete_cdm_job",
            return_value={"success": False, "job_name": "JOB-001"},
        ),
    ):
        result = runner.invoke(app, ["cdm", "delete", "JOB-001"])
    assert result.exit_code == 1
    assert "CDM job deletion failed: JOB-001" in result.stderr


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


def test_cdm_import_command_preview_no_setting() -> None:
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
                "items": 1,
                "rows": [
                    {"row": 1, "style": "P003", "quantity": 1, "width": 500.0, "length": 500.0}
                ],
                "errors": [],
                "job": None,
            },
        ) as mock_preview,
    ):
        result = runner.invoke(app, ["cdm", "import", r"C:\temp\order.csv", "--preview"])
    assert result.exit_code == 0
    assert "PREVIEW" in result.stderr
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


def test_cdm_order_details_list_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.cdm_order_details",
            return_value={
                "order_details": [
                    {
                        "style_name": "Typ Frontu 1",
                        "quantity": 2,
                        "width": 500.0,
                        "length": 300.0,
                        "material_id": 3,
                        "csv_customer_name": "Klient A",
                        "csv_order_number": "Z-001",
                        "csv_item_number": "I-1",
                        "production_comment": "uwaga",
                        "custom_fields": {"1": "x", "2": "y"},
                        "rotation_method": 1,
                        "nesting_priority": 2,
                        "has_drilling": True,
                        "small_nest_part": False,
                        "active_in_process": True,
                    }
                ],
                "job_name": "JOB-001",
            },
        ) as mock_details,
    ):
        result = runner.invoke(app, ["cdm", "order-details", "list", "JOB-001"])
    assert result.exit_code == 0
    assert "Typ Frontu 1" in result.stderr
    assert "Z-001" in result.stderr
    assert "1=x; 2=y" in result.stderr
    assert "Yes" in result.stderr
    mock_details.assert_called_once_with(job_name="JOB-001")


def test_cdm_order_details_list_json() -> None:
    from tests.unit.test_cli import _mock_com

    payload = {
        "order_details": [
            {
                "style_name": "Typ Frontu 1",
                "quantity": 2,
                "width": 500.0,
                "length": 300.0,
                "material_id": 3,
                "csv_customer_name": "Klient A",
                "csv_order_number": "Z-001",
                "csv_item_number": "I-1",
                "production_comment": "uwaga",
                "custom_fields": {"1": "x", "2": "y"},
                "rotation_method": 1,
                "nesting_priority": 2,
                "has_drilling": True,
                "small_nest_part": False,
                "active_in_process": True,
            }
        ],
        "job_name": "JOB-001",
    }
    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_order_details",
            return_value=payload,
        ) as mock_details,
    ):
        result = runner.invoke(app, ["cdm", "order-details", "list", "JOB-001", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stderr)
    assert data == payload
    mock_details.assert_called_once_with(job_name="JOB-001")


def test_cdm_order_details_list_json_empty() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_order_details",
            return_value={"order_details": [], "job_name": "JOB-001"},
        ),
    ):
        result = runner.invoke(app, ["cdm", "order-details", "list", "JOB-001", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stderr)
    assert data == {"order_details": [], "job_name": "JOB-001"}


def test_cdm_order_details_list_empty() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_order_details",
            return_value={"order_details": [], "job_name": "JOB-001"},
        ),
    ):
        result = runner.invoke(app, ["cdm", "order-details", "list", "JOB-001"])
    assert result.exit_code == 0
    assert "No CDM order details found for job JOB-001" in result.stderr


def test_cdm_order_details_list_without_job() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.cdm_order_details",
            return_value={
                "order_details": [
                    {
                        "style_name": "Typ Frontu 1",
                        "quantity": 2,
                        "width": 500.0,
                        "length": 300.0,
                        "material_id": 3,
                        "csv_customer_name": "Klient A",
                        "csv_order_number": "Z-001",
                        "csv_item_number": "I-1",
                        "production_comment": "uwaga",
                        "custom_fields": {"1": "x"},
                        "rotation_method": 1,
                        "nesting_priority": 2,
                        "has_drilling": True,
                        "small_nest_part": False,
                        "active_in_process": True,
                        "job_name": "JOB-001",
                    },
                    {
                        "style_name": "Typ Frontu 2",
                        "quantity": 1,
                        "width": 400.0,
                        "length": 200.0,
                        "material_id": 4,
                        "csv_customer_name": "Klient B",
                        "csv_order_number": "Z-002",
                        "csv_item_number": "I-2",
                        "production_comment": "",
                        "custom_fields": {},
                        "rotation_method": 0,
                        "nesting_priority": 1,
                        "has_drilling": False,
                        "small_nest_part": True,
                        "active_in_process": False,
                        "job_name": "JOB-002",
                    },
                ],
                "job_name": None,
            },
        ) as mock_details,
    ):
        result = runner.invoke(app, ["cdm", "order-details", "list"])
    assert result.exit_code == 0
    assert "Typ Frontu 1" in result.stderr
    assert "Typ Frontu 2" in result.stderr
    assert "JOB-001" in result.stderr
    assert "JOB-002" in result.stderr
    mock_details.assert_called_once_with(job_name=None)


def test_cdm_order_details_list_no_job_all() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_order_details",
            return_value={"order_details": [], "job_name": None},
        ),
    ):
        result = runner.invoke(app, ["cdm", "order-details", "list"])
    assert result.exit_code == 0
    assert "No CDM order details found" in result.stderr
    assert "for job" not in result.stderr


def test_cdm_door_paths_list_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.cdm_door_paths",
            return_value={
                "door_paths": [
                    {
                        "path_name": "Path 1",
                        "door_type": "L_B_10mm",
                        "tool_name": "Flat - 10mm",
                        "tool_number": 1,
                        "machining_method": "Pocket",
                        "safe_rapid": 5.0,
                        "rapid_down_to": 1.0,
                        "final_depth": -10.0,
                        "spindle_speed": 12000,
                        "down_feed": 2000.0,
                        "cut_feed": 4000.0,
                        "lead_in": 1.0,
                        "lead_out": 1.0,
                        "slope_in": True,
                        "slope_out": False,
                        "stock": 0.5,
                        "tool_in_out": 1,
                        "tool_side": 2,
                    }
                ],
                "type_name": None,
            },
        ) as mock_paths,
    ):
        result = runner.invoke(app, ["cdm", "doorpaths", "list"])
    assert result.exit_code == 0
    assert "Path 1" in result.stderr
    assert "L_B_10mm" in result.stderr
    assert "Flat - 10mm" in result.stderr
    mock_paths.assert_called_once_with(type_name=None)


def test_cdm_door_paths_list_command_filtered() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_door_paths",
            return_value={"door_paths": [], "type_name": "L_B_10mm"},
        ),
    ):
        result = runner.invoke(app, ["cdm", "doorpaths", "list", "L_B_10mm"])
    assert result.exit_code == 0
    assert "No door paths found for type L_B_10mm" in result.stderr


def test_cdm_materials_list_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_materials",
            return_value={
                "materials": [
                    {
                        "id": 1,
                        "name": "MDF 18mm",
                        "width": 2800.0,
                        "length": 2070.0,
                        "thickness": 18.0,
                        "grain_restriction": 1,
                    }
                ]
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "materials", "list"])
    assert result.exit_code == 0
    assert "MDF 18mm" in result.stderr


def test_cdm_materials_list_empty() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_materials",
            return_value={"materials": []},
        ),
    ):
        result = runner.invoke(app, ["cdm", "materials", "list"])
    assert result.exit_code == 0
    assert "No materials found" in result.stderr


def test_cdm_config_list_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.cdm_configs",
            return_value={
                "configs": [
                    {
                        "id": 1,
                        "name": "Fronty",
                        "post_processor": r"C:\Post\Alpha Reichenbacher.arp",
                        "nc_extension": "nc",
                        "generate_nc": True,
                        "generate_reports": False,
                        "nesting_method": 1,
                        "nesting_pack_to": 2,
                    }
                ],
                "show": None,
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "config", "list"])
    assert result.exit_code == 0
    assert "Fronty" in result.stderr
    assert "Alpha Reichenbacher.arp" in result.stderr
    assert "Yes" in result.stderr


def test_cdm_config_show_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_configs",
            return_value={
                "configs": [
                    {
                        "id": 1,
                        "name": "Fronty",
                        "post_processor": "Alpha Reichenbacher.arp",
                        "drawing_output_location": r"C:\out\draw",
                        "nc_output_location": r"C:\out\nc",
                        "report_output_location": r"C:\out\rep",
                        "nc_extension": "nc",
                        "generate_nc": True,
                        "generate_reports": False,
                        "replace_space_with_underscore": True,
                        "clear_output_folders": False,
                        "custom_vba_macro": "Macro.vbs",
                        "compiled_file_name": "Fronty.pgm",
                        "nesting_method": 1,
                        "nesting_pack_to": 2,
                        "nesting_gap_between_paths": 4.0,
                        "nesting_gap_at_sheet_edge": 10.0,
                        "nesting_extra_gap_at_lead_start": 0.0,
                        "nesting_time_per_sheet": 60,
                        "nesting_optimisation_level": 3,
                        "nesting_search_resolution": 0.5,
                        "nesting_minimise_tool_changes": True,
                        "nesting_use_bridged": True,
                        "nesting_use_onion_skin": False,
                        "nesting_prevent_nesting_in_apertures": True,
                        "nesting_force_strict_priorities": False,
                        "nesting_common_line_cutting": True,
                        "nesting_total_time": 120,
                        "nesting_sheet_order_type": 1,
                        "nesting_sheet_alignment": 0,
                        "nesting_inactivity_timeout": 30,
                        "cdm": {
                            "disable_nesting": False,
                            "disable_nesting_oversize_x": 0.0,
                            "disable_nesting_oversize_y": 0.0,
                            "use_default_press": True,
                            "press_group_by_material_thickness": True,
                            "generate_nc_for_parts": True,
                            "capture_nested_part_positions": False,
                            "part_recovery_x": 5.0,
                            "part_recovery_y": 5.0,
                            "z_depth_tolerance": 0.1,
                            "preview_material_thickness": 18.0,
                            "custom_macro": "CDM_Macro.vbs",
                        },
                    }
                ],
                "show": "Fronty",
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "config", "show", "Fronty"])
    assert result.exit_code == 0
    assert "Podstawowe" in result.stderr
    assert "Nesting" in result.stderr
    assert "CDM" in result.stderr
    assert "Macro.vbs" in result.stderr
    assert "CDM_Macro.vbs" in result.stderr
    assert "Yes" in result.stderr


def test_cdm_config_show_not_found() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_configs",
            return_value={"configs": [], "show": "NOPE"},
        ),
    ):
        result = runner.invoke(app, ["cdm", "config", "show", "NOPE"])
    assert result.exit_code == 1
    assert "Configuration not found: NOPE" in result.stderr


def test_cdm_config_show_empty_name() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_configs",
            return_value={"configs": [], "show": ""},
        ) as mock_configs,
    ):
        result = runner.invoke(app, ["cdm", "config", "show", ""])
    assert result.exit_code == 1
    assert "Configuration name is required" in result.stderr
    mock_configs.assert_not_called()


def test_cdm_setups_list_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_lookups",
            return_value={
                "lookups": {
                    "setups": [
                        {
                            "id": 1,
                            "name": "Setup 1",
                            "fe_what_to_extract": 2,
                            "fe_use_panel_alignment": True,
                            "fe_z_level_step": 2.0,
                            "imp_step_length": 5.0,
                            "geometry_query": "q1",
                        }
                    ]
                }
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "setups", "list"])
    assert result.exit_code == 0
    assert "Setup 1" in result.stderr


def test_cdm_customers_list_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.cdm_lookups",
            return_value={
                "lookups": {
                    "customers": [
                        {
                            "id": 1,
                            "name": "Klient A",
                            "address_line_1": "ul. Testowa 1",
                            "city": "Warszawa",
                            "contact_name": "Jan Kowalski",
                            "telephone_number": "123456789",
                            "email_address": "jan@example.com",
                        }
                    ]
                }
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "customers", "list"])
    assert result.exit_code == 0
    assert "Klient A" in result.stderr
    assert "jan@example.com" in result.stderr


def test_cdm_machining_orders_list_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_lookups",
            return_value={
                "lookups": {
                    "machining_orders": [
                        {
                            "seq_num": 1,
                            "list_name": "Lista 1",
                            "machining_style_name": "Frezy 6mm",
                            "layer_name": "Warstwa 1",
                            "is_multidrill": True,
                        }
                    ]
                }
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "machining-orders", "list"])
    assert result.exit_code == 0
    assert "Frezy 6mm" in result.stderr
    assert "Yes" in result.stderr


def test_cdm_doorstyles_list_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_lookups",
            return_value={
                "lookups": {
                    "doorstyles": [
                        {
                            "id": 1,
                            "full_file_name": r"C:\Styles\Front1.vbs",
                            "vba_project_name": "Fronty",
                        }
                    ]
                }
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "doorstyles", "list"])
    assert result.exit_code == 0
    assert "Front1.vbs" in result.stderr
    assert "Fronty" in result.stderr


def test_cdm_multidrill_list_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_lookups",
            return_value={
                "lookups": {
                    "multidrill": [
                        {
                            "id": 1,
                            "name": "MD 2x2",
                            "selected": True,
                            "feed_rate": 3000.0,
                            "spindle_speed": 12000,
                            "safe_rapid_distance": 5.0,
                            "bottom_of_hole": -18.0,
                        }
                    ]
                }
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "multidrill", "list"])
    assert result.exit_code == 0
    assert "MD 2x2" in result.stderr


def test_cdm_fittings_list_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.cdm_lookups",
            return_value={
                "lookups": {
                    "fittings": [
                        {
                            "id": 1,
                            "fk_job_file_id": 7,
                            "fitting_type": "Zawias",
                            "fitting_file": r"C:\Fittings\h1.vbs",
                        }
                    ]
                }
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "fittings", "list"])
    assert result.exit_code == 0
    assert "Zawias" in result.stderr


def test_cdm_layers_mapping_list_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.cdm_lookups",
            return_value={
                "lookups": {
                    "layers_mapping": [
                        {
                            "setup_name": "Setup 1",
                            "layer_name": "Warstwa 1",
                            "machining_style_name": "Frezy 6mm",
                            "machining_order": 3,
                            "is_feature_layer": True,
                            "tool_side_closed_geo": 1,
                            "tool_direction_closed_geo": 0,
                            "start_point": 2,
                        }
                    ]
                }
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "layers-mapping", "list"])
    assert result.exit_code == 0
    assert "Warstwa 1" in result.stderr
    assert "Yes" in result.stderr


_MANIFEST_LIST_DATA = {
    "success": True,
    "directory": r"C:\x",
    "manifests": [
        {
            "path": r"C:\x\Fronty - MDF_18.acrepd",
            "job_name": "Fronty",
            "material": "MDF_18",
            "size": 1000,
            "mtime": 1700000000.0,
            "sheet_count": 2,
            "first_utilization": 29,
        }
    ],
}

_MANIFEST_READ_DATA = {
    "success": True,
    "manifest": {
        "job_name": "Fronty",
        "material": "MDF_18",
        "job": {},
        "drawings": [],
        "sheets": [
            {
                "id": 1,
                "name": "Arkusz A1",
                "database_name": "MDF_18",
                "width": 2800.0,
                "length": 2070.0,
                "thickness": 18.0,
                "part_count": 1,
                "unique_part_count": 1,
                "quantity": 1,
                "scrap": 71,
                "utilization": 29,
                "fill_class": "partial",
                "nest_nc_filename": "x.nc",
                "press_name": None,
                "has_image": False,
                "parts": [
                    {
                        "id": 1,
                        "sheet_id": 1,
                        "name": "PF-002Small_4",
                        "drawing_file_name": "a.amd",
                        "item_number": "1",
                        "quantity": 1,
                        "quantity_on_sheet": 7,
                        "x": 79.0,
                        "y": 613.0,
                        "rotation": 90,
                        "width": 500.0,
                        "length": 600.0,
                        "thickness": 18.0,
                        "material": "MDF_18",
                        "nest_kit_number": "3",
                        "handle_name": None,
                        "csv_customer_name": "Klient Test",
                        "csv_order_number": "ZAM-001",
                        "csv_item_number": None,
                        "press_sheet_name": None,
                        "has_image": False,
                    }
                ],
            }
        ],
        "total_parts": 1,
        "unmatched_parts": [],
        "path": r"C:\x\Fronty - MDF_18.acrepd",
    },
}


def test_cdm_manifest_list_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_list",
            return_value=_MANIFEST_LIST_DATA,
        ) as mock_manifest_list,
    ):
        result = runner.invoke(app, ["cdm", "manifest"])
    assert result.exit_code == 0
    assert "Fronty" in result.stderr
    assert "MDF_18" in result.stderr
    mock_manifest_list.assert_called_once_with(None)


def test_cdm_manifest_list_empty() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_list",
            return_value={"success": True, "manifests": []},
        ) as mock_manifest_list,
    ):
        result = runner.invoke(app, ["cdm", "manifest"])
    assert result.exit_code == 0
    assert "No manifests found" in result.stderr
    mock_manifest_list.assert_called_once_with(None)


def test_cdm_manifest_list_sheet_columns() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_list",
            return_value=_MANIFEST_LIST_DATA,
        ) as mock_manifest_list,
    ):
        result = runner.invoke(app, ["cdm", "manifest"])
    assert result.exit_code == 0
    assert "Arkusze" in result.stderr
    assert "Wypełn." in result.stderr
    assert "29%" in result.stderr
    mock_manifest_list.assert_called_once_with(None)


def test_cdm_manifest_list_sheet_columns_no_utilization() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_list",
            return_value={
                **_MANIFEST_LIST_DATA,
                "manifests": [
                    {
                        **_MANIFEST_LIST_DATA["manifests"][0],
                        "first_utilization": None,
                    }
                ],
            },
        ) as mock_manifest_list,
    ):
        result = runner.invoke(app, ["cdm", "manifest"])
    assert result.exit_code == 0
    assert "Arkusze" in result.stderr
    assert "Wypełn." in result.stderr
    assert "-" in result.stderr
    mock_manifest_list.assert_called_once_with(None)


def test_cdm_manifest_list_json_unchanged() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_list",
            return_value=_MANIFEST_LIST_DATA,
        ) as mock_manifest_list,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stderr)
    assert set(data["manifests"][0]) == {
        "path",
        "job_name",
        "material",
        "size",
        "mtime",
        "sheet_count",
        "first_utilization",
    }
    mock_manifest_list.assert_called_once_with(None)


def test_cdm_manifest_list_ignored_options_warning() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_list",
            return_value=_MANIFEST_LIST_DATA,
        ) as mock_manifest_list,
    ):
        result = runner.invoke(
            app,
            [
                "cdm",
                "manifest",
                "--material",
                "MDF_18",
                "--nc-root",
                r"C:\NC\Out",
                "--show-all",
                "--fill-threshold",
                "50",
            ],
        )
    assert result.exit_code == 0
    assert (
        "--material --nc-root --show-all --fill-threshold ignored without job name" in result.stderr
    )
    mock_manifest_list.assert_called_once_with(None)


def test_cdm_manifest_list_dir_and_json_not_ignored() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_list",
            return_value=_MANIFEST_LIST_DATA,
        ) as mock_manifest_list,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "--json", "--dir", r"C:\Reports\Data"])
    assert result.exit_code == 0
    assert "ignored without job name" not in result.stderr
    data = json.loads(result.stderr)
    assert data["manifests"][0]["job_name"] == "Fronty"
    mock_manifest_list.assert_called_once_with(r"C:\Reports\Data")


def test_cdm_manifest_read_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_MANIFEST_READ_DATA,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB"])
    assert result.exit_code == 0
    assert "Arkusz A1" in result.stderr
    assert "Wypełnienie: 29% (odpad: 71%)" in result.stderr
    assert "[fill: partial]" in result.stderr
    assert "PF-002Small_4" in result.stderr
    assert "Klient Test" in result.stderr
    assert "ZAM-001" in result.stderr
    assert "Total parts: 1" in result.stderr
    assert "NC unmatched:" not in result.stderr
    assert "NC missing:" not in result.stderr
    assert "NC matched by order:" not in result.stderr
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_cdm_manifest_read_nc_sections_text() -> None:
    from tests.unit.test_cli import _mock_com

    data = copy.deepcopy(_MANIFEST_READ_DATA)
    data["manifest"]["nc_unmatched"] = [r"C:\nc\A.nc", r"C:\nc\B.nc"]
    data["manifest"]["nc_missing"] = ["Arkusz A3"]
    data["manifest"]["nc_matched_by_order"] = [0, 4]
    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=data,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB"])
    assert result.exit_code == 0
    assert "NC unmatched:" in result.stderr
    assert r"C:\nc\A.nc" in result.stderr
    assert r"C:\nc\B.nc" in result.stderr
    assert "NC missing:" in result.stderr
    assert "Arkusz A3" in result.stderr
    assert "NC matched by order:" in result.stderr
    assert "Arkusz A1, 4" in result.stderr
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_cdm_manifest_read_json() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_MANIFEST_READ_DATA,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stderr)
    assert data["manifest"]["job_name"] == "Fronty"
    assert data["manifest"]["sheets"][0]["name"] == "Arkusz A1"
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_cdm_manifest_not_found() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            side_effect=RuntimeError("manifest: not found: BRAK"),
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "BRAK"])
    assert result.exit_code == 1
    assert "manifest: not found" in result.stderr
    mock_manifest_read.assert_called_once_with(
        job_name="BRAK",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def _manifest_read_data_with(part_updates: dict[str, Any]) -> dict[str, Any]:
    data = copy.deepcopy(_MANIFEST_READ_DATA)
    data["manifest"]["sheets"][0]["parts"][0].update(part_updates)
    return data


def test_cdm_manifest_read_token_notes_columns() -> None:
    from tests.unit.test_cli import _mock_com

    long_comment = "komentarz" + "x" * 40
    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_manifest_read_data_with(
                {"custom_field_1": "ABC", "production_comment": long_comment}
            ),
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB"])
    assert result.exit_code == 0
    assert "Token" in result.stderr
    assert "Notes" in result.stderr
    assert "ABC" in result.stderr
    assert long_comment[:27] + "..." in result.stderr
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_cdm_manifest_read_token_notes_empty_dash() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_manifest_read_data_with(
                {"custom_field_1": None, "production_comment": None}
            ),
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB"])
    assert result.exit_code == 0
    assert "Token" in result.stderr
    assert "Notes" in result.stderr
    assert "-" in result.stderr
    assert "ABC" not in result.stderr
    assert "None" not in result.stderr
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_cdm_manifest_read_show_all_custom_fields() -> None:
    from tests.unit.test_cli import _mock_com

    updates = {
        "custom_field_2": "CF2VAL",
        "custom_field_10": "CF10VAL",
        "custom_field_25": "CF25VAL",
    }
    with (
        _mock_com(),
        _wide_console(400),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_manifest_read_data_with(updates),
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--show-all"])
    assert result.exit_code == 0
    assert "CF2" in result.stderr
    assert "CF10" in result.stderr
    assert "CF25" in result.stderr
    assert "CF2VAL" in result.stderr
    assert "CF10VAL" in result.stderr
    assert "CF25VAL" in result.stderr
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_cdm_manifest_read_nc_filename_header() -> None:
    from tests.unit.test_cli import _mock_com

    data = copy.deepcopy(_MANIFEST_READ_DATA)
    data["manifest"]["sheets"][0]["nc_filename"] = "Arkusz_A1.nc"
    data["manifest"]["sheets"][0]["nc_source"] = "report"
    data["manifest"]["sheets"].append(
        {
            "name": "Arkusz A2",
            "database_name": "MDF_18",
            "width": 2800.0,
            "length": 2070.0,
            "thickness": 18.0,
            "part_count": 0,
            "scrap": None,
            "utilization": None,
            "nc_filename": "Arkusz_A2.nc",
            "nc_source": "disk",
            "parts": [],
        }
    )
    data["manifest"]["sheets"].append(
        {
            "name": "Arkusz A3",
            "database_name": "MDF_18",
            "width": 2800.0,
            "length": 2070.0,
            "thickness": 18.0,
            "part_count": 0,
            "scrap": None,
            "utilization": None,
            "nc_filename": None,
            "nc_source": None,
            "parts": [],
        }
    )
    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=data,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB"])
    assert result.exit_code == 0
    assert "NC: Arkusz_A1.nc [report]" in result.stderr
    assert "NC: Arkusz_A2.nc [disk]" in result.stderr
    assert "NC: BRAK" in result.stderr
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_cdm_manifest_read_nc_root_override() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_MANIFEST_READ_DATA,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--nc-root", r"C:\NC\Out"])
    assert result.exit_code == 0
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root=r"C:\NC\Out",
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_cdm_manifest_relative_nc_root_exit2() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_MANIFEST_READ_DATA,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--nc-root", "nc/out"])
    assert result.exit_code == 2
    assert "--nc-root must be an absolute path" in result.stderr
    mock_manifest_read.assert_not_called()


def test_cdm_manifest_list_relative_nc_root_warning() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_list",
            return_value=_MANIFEST_LIST_DATA,
        ) as mock_manifest_list,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "--nc-root", "nc/out"])
    assert result.exit_code == 0
    assert "--nc-root ignored without job name" in result.stderr
    assert "--nc-root must be an absolute path" not in result.stderr
    mock_manifest_list.assert_called_once_with(None)


def test_cdm_manifest_relative_dir_exit2() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_list",
            return_value=_MANIFEST_LIST_DATA,
        ) as mock_manifest_list,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "--dir", "reports/data"])
    assert result.exit_code == 2
    assert "--dir must be an absolute path" in result.stderr
    mock_manifest_list.assert_not_called()


def test_cdm_manifest_unc_nc_root_ok() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_MANIFEST_READ_DATA,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--nc-root", r"\\server\share\Out"])
    assert result.exit_code == 0
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root=r"\\server\share\Out",
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_cdm_manifest_unc_forward_slash_nc_root_ok() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_MANIFEST_READ_DATA,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--nc-root", "//server/share/Out"])
    assert result.exit_code == 0
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root="//server/share/Out",
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def _manifest_read_data_by_token() -> dict[str, Any]:
    data = copy.deepcopy(_MANIFEST_READ_DATA)
    data["manifest"]["sheets"][0]["parts"][0].update({"custom_field_1": "ABC"})
    data["by_token"] = [
        {
            "token": "ABC",
            "total_qty": 9,
            "sheets": [{"sheet": "Arkusz A1", "qty": 4}, {"sheet": "Arkusz A2", "qty": 5}],
            "csv_order_number": "ZAM-001",
        },
        {
            "token": None,
            "total_qty": 2,
            "sheets": [{"sheet": "?", "qty": 2}],
            "csv_order_number": None,
        },
    ]
    return data


def test_cdm_manifest_read_by_token_flag_passed() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_manifest_read_data_by_token(),
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--by-token"])
    assert result.exit_code == 0
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=True,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_cdm_manifest_read_by_token_requires_job_name() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_manifest_read_data_by_token(),
        ),
    ):
        result = runner.invoke(app, ["cdm", "manifest", "--by-token"])
    assert result.exit_code == 2
    assert "--by-token requires a job name" in result.stderr


def test_cdm_manifest_read_by_token_text_section() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_manifest_read_data_by_token(),
        ),
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--by-token"])
    assert result.exit_code == 0
    assert "By token:" in result.stderr
    assert "Token: ABC  Qty: 9  Order: ZAM-001" in result.stderr
    assert "Token: (no token)  Qty: 2  Order: -" in result.stderr
    assert "Arkusz A1: 4" in result.stderr
    assert "Arkusz A2: 5" in result.stderr
    assert "Arkusz ?: 2" in result.stderr


def test_cdm_manifest_read_by_token_json() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_manifest_read_data_by_token(),
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--by-token", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stderr)
    assert data["by_token"][0]["token"] == "ABC"
    assert data["by_token"][0]["total_qty"] == 9
    assert data["by_token"][1]["token"] is None
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=True,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_cdm_manifest_read_fill_threshold_passed() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_MANIFEST_READ_DATA,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--fill-threshold", "50"])
    assert result.exit_code == 0
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=50,
        validate=False,
        token_qty=None,
    )


def test_cdm_manifest_read_fill_threshold_invalid() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_MANIFEST_READ_DATA,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--fill-threshold", "150"])
    assert result.exit_code == 2
    assert "--fill-threshold must be between 0 and 100" in result.stderr
    mock_manifest_read.assert_not_called()


def test_cdm_manifest_read_fill_threshold_low() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_MANIFEST_READ_DATA,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--fill-threshold", "-1"])
    assert result.exit_code == 2
    assert "--fill-threshold must be between 0 and 100" in result.stderr
    mock_manifest_read.assert_not_called()


def test_cdm_manifest_read_no_fill_class_prints_empty() -> None:
    from tests.unit.test_cli import _mock_com

    data = copy.deepcopy(_MANIFEST_READ_DATA)
    data["manifest"]["sheets"][0].pop("fill_class")
    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=data,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB"])
    assert result.exit_code == 0
    assert "[fill: empty]" in result.stderr
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=False,
        token_qty=None,
    )


def test_cdm_manifest_read_validate_passed() -> None:
    from tests.unit.test_cli import _mock_com

    data = copy.deepcopy(_MANIFEST_READ_DATA)
    data["validation"] = {"valid": True, "warnings": [], "errors": []}
    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=data,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--validate"])
    assert result.exit_code == 0
    assert "VALID: OK" in result.stderr
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=True,
        token_qty=None,
    )


def test_cdm_manifest_read_validate_requires_job_name() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_MANIFEST_READ_DATA,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "--validate"])
    assert result.exit_code == 2
    assert "--validate requires a job name" in result.stderr
    mock_manifest_read.assert_not_called()


def test_cdm_manifest_read_token_qty_parsed() -> None:
    from tests.unit.test_cli import _mock_com

    data = copy.deepcopy(_MANIFEST_READ_DATA)
    data["validation"] = {"valid": True, "warnings": [], "errors": []}
    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=data,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(
            app,
            [
                "cdm",
                "manifest",
                "JOB",
                "--validate",
                "--token-qty",
                "ABC=4",
                "--token-qty",
                "DEF=2",
            ],
        )
    assert result.exit_code == 0
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=True,
        token_qty={"ABC": 4, "DEF": 2},
    )


def test_cdm_manifest_read_token_qty_requires_validate() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_MANIFEST_READ_DATA,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--token-qty", "ABC=4"])
    assert result.exit_code == 2
    assert "--token-qty requires --validate" in result.stderr
    mock_manifest_read.assert_not_called()


def test_cdm_manifest_read_token_qty_duplicate() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_MANIFEST_READ_DATA,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(
            app,
            [
                "cdm",
                "manifest",
                "JOB",
                "--validate",
                "--token-qty",
                "ABC=4",
                "--token-qty",
                "ABC=5",
            ],
        )
    assert result.exit_code == 2
    assert 'duplicate --token-qty for token "ABC"' in result.stderr
    mock_manifest_read.assert_not_called()


def test_cdm_manifest_read_token_qty_invalid_format() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_MANIFEST_READ_DATA,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(
            app,
            [
                "cdm",
                "manifest",
                "JOB",
                "--validate",
                "--token-qty",
                "ABC",
            ],
        )
    assert result.exit_code == 2
    assert 'invalid --token-qty "ABC" (expected token=qty)' in result.stderr
    mock_manifest_read.assert_not_called()


def test_cdm_manifest_read_token_qty_invalid_value() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=_MANIFEST_READ_DATA,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(
            app, ["cdm", "manifest", "JOB", "--validate", "--token-qty", "ABC=-1"]
        )
    assert result.exit_code == 2
    assert 'invalid --token-qty "ABC=-1" (expected token=qty)' in result.stderr
    mock_manifest_read.assert_not_called()


def test_cdm_manifest_read_validate_text_errors_and_warnings() -> None:
    from tests.unit.test_cli import _mock_com

    data = copy.deepcopy(_MANIFEST_READ_DATA)
    data["validation"] = {
        "valid": False,
        "warnings": ["1 parts without csv_order_number and custom_field_1"],
        "errors": ['token "ABC": expected 8, got 7'],
    }
    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=data,
        ),
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--validate"])
    assert result.exit_code == 1
    assert 'ERROR: token "ABC": expected 8, got 7' in result.stderr
    assert "WARNING: 1 parts without csv_order_number and custom_field_1" in result.stderr
    assert "VALID: FAILED (1 errors)" in result.stderr


def test_cdm_manifest_read_validate_warnings_exit_2() -> None:
    from tests.unit.test_cli import _mock_com

    data = copy.deepcopy(_MANIFEST_READ_DATA)
    data["validation"] = {
        "valid": True,
        "warnings": ["1 parts without csv_order_number and custom_field_1"],
        "errors": [],
    }
    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=data,
        ),
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--validate"])
    assert result.exit_code == 2
    assert "VALID: OK" in result.stderr


def test_cdm_manifest_read_validate_ok_exit_0() -> None:
    from tests.unit.test_cli import _mock_com

    data = copy.deepcopy(_MANIFEST_READ_DATA)
    data["validation"] = {"valid": True, "warnings": [], "errors": []}
    with (
        _mock_com(),
        _wide_console(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=data,
        ),
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--validate"])
    assert result.exit_code == 0
    assert "VALID: OK" in result.stderr


def test_cdm_manifest_read_validate_json_contains_validation() -> None:
    from tests.unit.test_cli import _mock_com

    data = copy.deepcopy(_MANIFEST_READ_DATA)
    data["validation"] = {
        "valid": False,
        "warnings": [],
        "errors": ['token "ABC": expected 8, got 7'],
    }
    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.manifest_read",
            return_value=data,
        ) as mock_manifest_read,
    ):
        result = runner.invoke(app, ["cdm", "manifest", "JOB", "--validate", "--json"])
    assert result.exit_code == 0
    out = json.loads(result.stderr)
    assert out["validation"]["valid"] is False
    assert out["validation"]["errors"] == ['token "ABC": expected 8, got 7']
    mock_manifest_read.assert_called_once_with(
        job_name="JOB",
        material=None,
        data_dir=None,
        nc_root=None,
        by_token=False,
        fill_threshold=None,
        validate=True,
        token_qty=None,
    )


def test_cdm_process_command() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            return_value={"success": True, "job_name": "JOB-001", "processed": True},
        ) as mock_process,
    ):
        result = runner.invoke(app, ["cdm", "process", "JOB-001"])
    assert result.exit_code == 0
    assert "CDM job processed: JOB-001" in result.stderr
    mock_process.assert_called_once_with(job_name="JOB-001")


def test_cdm_process_command_timeout_and_output_root() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            return_value={"success": True, "job_name": "JOB-001", "processed": True},
        ) as mock_process,
    ):
        result = runner.invoke(
            app,
            ["cdm", "process", "JOB-001", "--timeout", "600", "--output-root", "C:/out"],
        )
    assert result.exit_code == 0
    assert "ignored with --method" not in result.stderr
    mock_process.assert_called_once_with(
        job_name="JOB-001", timeout_seconds=600, output_root="C:/out"
    )


def test_cdm_process_command_relative_output_root_exit2() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            return_value={"success": True, "job_name": "JOB-001", "processed": True},
        ) as mock_process,
    ):
        result = runner.invoke(app, ["cdm", "process", "JOB-001", "--output-root", "out/dir"])
    assert result.exit_code == 2
    assert "--output-root must be an absolute path" in result.stderr
    mock_process.assert_not_called()


def test_cdm_process_command_method_flag_removed() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            return_value={"success": True, "job_name": "JOB-001", "processed": True},
        ) as mock_process,
    ):
        result = runner.invoke(app, ["cdm", "process", "JOB-001", "--method", "vbs"])
    assert result.exit_code != 0
    assert "No such option" in result.stderr
    mock_process.assert_not_called()


def test_cdm_process_command_psexec_flag_removed() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            return_value={"success": True, "job_name": "JOB-001", "processed": True},
        ) as mock_process,
    ):
        result = runner.invoke(
            app, ["cdm", "process", "JOB-001", "--psexec", "C:/temp/PsExec64.exe"]
        )
    assert result.exit_code != 0
    assert "No such option" in result.stderr
    mock_process.assert_not_called()


def test_cdm_process_command_failure() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            return_value={"success": False, "job_name": "JOB-001", "processed": False},
        ),
    ):
        result = runner.invoke(app, ["cdm", "process", "JOB-001"])
    assert result.exit_code == 1
    assert "CDM job processing failed: JOB-001" in result.stderr


def test_cdm_process_command_failure_detail_and_log() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            return_value={
                "success": False,
                "job_name": "JOB-001",
                "status": "Failed",
                "processed": False,
                "detail": "nesting error: sheet too small",
                "log": "line1: macro started\nline2: nesting failed",
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "process", "JOB-001"])
    assert result.exit_code == 1
    assert "Status: Failed" in result.stderr
    assert "Detail:" in result.stderr
    assert "nesting error: sheet too small" in result.stderr
    assert "Log:" in result.stderr
    assert "line1: macro started" in result.stderr
    assert "line2: nesting failed" in result.stderr


def test_cdm_process_command_failure_no_detail_or_log() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            return_value={"success": False, "job_name": "JOB-001", "processed": False},
        ),
    ):
        result = runner.invoke(app, ["cdm", "process", "JOB-001"])
    assert result.exit_code == 1
    assert "CDM job processing failed: JOB-001" in result.stderr
    assert "Detail:" not in result.stderr
    assert "Log:" not in result.stderr


def test_cdm_process_command_failure_broken_contract() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            return_value={"success": False},
        ),
    ):
        result = runner.invoke(app, ["cdm", "process", "JOB-001"])
    assert result.exit_code == 1
    assert "KeyError" not in result.stderr
    assert "CDM job processing failed: JOB-001" in result.stderr


def test_cdm_process_command_not_found() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            side_effect=RuntimeError("cdm: job not found: NOPE"),
        ),
    ):
        result = runner.invoke(app, ["cdm", "process", "NOPE"])
    assert result.exit_code == 1
    assert "job not found" in result.stderr


def test_cdm_process_command_local_runtime_error_stale_macro_exit2() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            side_effect=RuntimeError(
                "cdm: STALE_MACRO: previous headless macro invocation did not complete "
                "(last log line: 'PN=X'); AlphaCAM VBA host is hung — gateway must restart "
                "before processing"
            ),
        ) as mock_process,
    ):
        result = runner.invoke(app, ["cdm", "process", "JOB-001"])
    assert result.exit_code == 2
    assert "previous macro invocation hung" in result.stderr
    assert "restart AlphaCAM" in result.stderr
    assert "CDM job processing failed" not in result.stderr
    mock_process.assert_called_once_with(job_name="JOB-001")


def test_cdm_process_command_local_runtime_error_other_still_propagates() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            side_effect=RuntimeError("cdm: job not found: NOPE"),
        ) as mock_process,
    ):
        result = runner.invoke(app, ["cdm", "process", "NOPE"])
    assert result.exit_code != 2
    assert "restart AlphaCAM" not in result.stderr
    assert "previous macro invocation hung" not in result.stderr
    mock_process.assert_called_once_with(job_name="NOPE")


def test_cdm_process_command_report_ok() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            return_value={
                "success": True,
                "job_name": "JOB-001",
                "processed": True,
                "report": {
                    "success": True,
                    "manifest_file": "JOB-001 - MDF18.acrepd",
                },
            },
        ) as mock_process,
    ):
        result = runner.invoke(app, ["cdm", "process", "JOB-001"])
    assert result.exit_code == 0
    assert "Report: OK" in result.stderr
    assert "JOB-001 - MDF18.acrepd" in result.stderr
    mock_process.assert_called_once_with(job_name="JOB-001")


def test_cdm_process_command_report_skipped() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            return_value={
                "success": True,
                "job_name": "JOB-001",
                "processed": True,
                "report": {
                    "success": False,
                    "skipped": True,
                    "error": "reports disabled for job configuration (GenerateReports=False)",
                },
            },
        ) as mock_process,
    ):
        result = runner.invoke(app, ["cdm", "process", "JOB-001"])
    assert result.exit_code == 0
    assert "Report: NOT CREATED" in result.stderr
    assert "GenerateReports=False" in result.stderr
    mock_process.assert_called_once_with(job_name="JOB-001")


def test_cdm_process_command_report_error() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            return_value={
                "success": True,
                "job_name": "JOB-001",
                "processed": True,
                "report": {"success": False, "error": "failed to read report flag"},
            },
        ) as mock_process,
    ):
        result = runner.invoke(app, ["cdm", "process", "JOB-001"])
    assert result.exit_code == 0
    assert "Report: NOT CREATED" in result.stderr
    assert "failed to read report flag" in result.stderr
    mock_process.assert_called_once_with(job_name="JOB-001")


def test_cdm_process_command_warnings() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            return_value={
                "success": True,
                "job_name": "JOB-001",
                "processed": True,
                "warnings": ["nesting warning: sheet waste high", "press not found: P1"],
            },
        ) as mock_process,
    ):
        result = runner.invoke(app, ["cdm", "process", "JOB-001"])
    assert result.exit_code == 0
    assert "WARNING" in result.stderr
    assert "nesting warning: sheet waste high" in result.stderr
    assert "press not found: P1" in result.stderr
    mock_process.assert_called_once_with(job_name="JOB-001")


def test_cdm_process_command_stale_macro_exit2() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            return_value={
                "success": False,
                "status": "stale_macro",
                "job_name": "JOB-001",
                "detail": "previous macro invocation hung - gateway auto-restarting, retry in ~60s",
                "auto_restart": True,
            },
        ) as mock_process,
    ):
        result = runner.invoke(app, ["cdm", "process", "JOB-001"])
    assert result.exit_code == 2
    assert "previous macro invocation hung" in result.stderr
    assert "auto-restarting" in result.stderr
    assert "Retry" in result.stderr
    assert "CDM job processing failed" not in result.stderr
    mock_process.assert_called_once_with(job_name="JOB-001")


def test_cdm_process_command_stale_macro_without_detail() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            return_value={"success": False, "status": "stale_macro", "job_name": "JOB-001"},
        ) as mock_process,
    ):
        result = runner.invoke(app, ["cdm", "process", "JOB-001"])
    assert result.exit_code == 2
    assert "previous macro invocation hung" in result.stderr
    assert "Detail:" not in result.stderr
    mock_process.assert_called_once_with(job_name="JOB-001")


def test_cdm_process_command_plain_failure_still_exit1() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch(
            "alphacam_cli.core.application.Application.process_cdm_job",
            return_value={
                "success": False,
                "status": "failed",
                "job_name": "JOB-001",
                "detail": "x",
            },
        ),
    ):
        result = runner.invoke(app, ["cdm", "process", "JOB-001"])
    assert result.exit_code == 1
    assert "CDM job processing failed: JOB-001" in result.stderr
    assert "Status: failed" in result.stderr
    assert "Detail:" in result.stderr
    assert "auto-restarting" not in result.stderr
