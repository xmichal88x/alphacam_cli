from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
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
