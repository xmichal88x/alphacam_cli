from __future__ import annotations

import os
import pathlib
import sys
import types
from typing import Any
from unittest.mock import MagicMock

import pytest

from alphacam_cli.core import cdm_db


def _mock_run(
    monkeypatch: pytest.MonkeyPatch, stdout: str = "[]", returncode: int = 0
) -> MagicMock:
    run = MagicMock(return_value=types.SimpleNamespace(stdout=stdout, returncode=returncode))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.subprocess.run", run)
    return run


def test_find_cdm_job_found(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    j1 = MagicMock()
    j1.JobName = "JOB-001"
    j2 = MagicMock()
    j2.JobName = "JOB-002"
    jobs = MagicMock()
    jobs.Count = 2
    jobs.Item.side_effect = [j1, j2]
    am.Jobs = jobs
    assert cdm_db.find_cdm_job(am, "JOB-002") is j2
    assert jobs.Item.call_count == 2


def test_find_cdm_job_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    jobs = MagicMock()
    jobs.Count = 0
    am.Jobs = jobs
    assert cdm_db.find_cdm_job(am, "NOPE") is None


def test_find_cdm_job_item_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    j2 = MagicMock()
    j2.JobName = "JOB-002"
    jobs = MagicMock()
    jobs.Count = 2
    jobs.Item.side_effect = [RuntimeError("bad item"), j2]
    am.Jobs = jobs
    assert cdm_db.find_cdm_job(am, "JOB-002") is j2


def test_find_cdm_job_propagates_count_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()

    class _BoomCount:
        @property
        def Count(self) -> int:  # noqa: N802 - mimics COM Jobs.Count
            raise RuntimeError("db locked")  # noqa: TRY003

    am.Jobs = _BoomCount()
    with pytest.raises(RuntimeError, match="db locked"):
        cdm_db.find_cdm_job(am, "X")


def test_sheet_materials_subprocess_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch).side_effect = FileNotFoundError("python")
    assert cdm_db.sheet_materials() == {}


def test_sheet_materials_nonzero_returncode(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout="", returncode=1)
    assert cdm_db.sheet_materials() == {}


def test_sheet_materials_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout="not json")
    assert cdm_db.sheet_materials() == {}


def test_sheet_materials_parses_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(
        monkeypatch,
        stdout='{"sheets": [{"name": "MDF_18", "id": 3}, {"name": "  MDF_18  ", "id": 9}]}',
    )
    assert cdm_db.sheet_materials() == {"MDF_18": 3}


def test_sheet_materials_value_wrap(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout='{"value": {"materials": [{"name": "Oak", "id": "7"}]}}')
    assert cdm_db.sheet_materials() == {"Oak": 7}


def test_vdb5_job_defaults_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout='{"config_name": "Fronty", "material_id": "4"}')
    assert cdm_db.vdb5_job_defaults() == {"config_name": "Fronty", "material_id": 4}


def test_vdb5_job_defaults_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch).side_effect = RuntimeError("powershell missing")
    assert cdm_db.vdb5_job_defaults() == {"config_name": None, "material_id": None}


def test_vdb5_door_type_names_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(
        monkeypatch,
        stdout='[{"TypeName": "Typ Frontu 1"}, {"Name": "L_B_10mm"}]',
    )
    assert cdm_db.vdb5_door_type_names() == (["Typ Frontu 1", "L_B_10mm"], True)


def test_vdb5_door_type_names_skips_system_row(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(
        monkeypatch,
        stdout=(
            '[{"TypeName": "Typ Frontu 1"},'
            ' {"TypeName": "Alphacam Created System Database Field - Do not delete"}]'
        ),
    )
    assert cdm_db.vdb5_door_type_names() == (["Typ Frontu 1"], True)


def test_vdb5_door_type_names_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch).side_effect = FileNotFoundError("powershell")
    assert cdm_db.vdb5_door_type_names() == ([], False)


def test_set_job_material_rows_updated(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _mock_run(monkeypatch, stdout="rows: 1\ndetail_rows: 1")
    assert cdm_db.set_job_material("order", 4) is True
    args, _ = run.call_args
    assert args[0][args[0].index("-JobName") + 1] == "order"
    assert args[0][args[0].index("-MaterialID") + 1] == "4"


def test_set_job_material_no_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout="rows: 0")
    assert cdm_db.set_job_material("order", 4) is False


def test_set_job_material_ignores_detail_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout="detail_rows: 1")
    assert cdm_db.set_job_material("order", 4) is False


def test_set_job_material_subprocess_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch).side_effect = FileNotFoundError("powershell")
    assert cdm_db.set_job_material("order", 4) is False


def test_set_has_drilling_rows_updated(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _mock_run(monkeypatch, stdout="rows: 2")
    assert cdm_db.set_has_drilling("order", [True, False]) is True
    args, _ = run.call_args
    assert args[0][args[0].index("-JobName") + 1] == "order"
    assert args[0][args[0].index("-Values") + 1] == "1;0"
    assert args[0][args[0].index("-JobName") : args[0].index("-Values") + 2] == [
        "-JobName",
        "order",
        "-Values",
        "1;0",
    ]


def test_set_has_drilling_no_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout="rows: 0")
    assert cdm_db.set_has_drilling("order", [True]) is False


def test_set_has_drilling_nonzero_returncode(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout="", returncode=1)
    assert cdm_db.set_has_drilling("order", [True]) is False


def test_set_has_drilling_subprocess_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch).side_effect = FileNotFoundError("powershell")
    assert cdm_db.set_has_drilling("order", [True]) is False


def test_job_count_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _mock_run(monkeypatch, stdout="count: 5")
    assert cdm_db.job_count("order") == 5
    args, _ = run.call_args
    assert args[0][args[0].index("-JobName") + 1] == "order"


def test_job_count_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout="count: 0")
    assert cdm_db.job_count("order") == 0


def test_job_count_nonzero_returncode(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout="", returncode=1)
    assert cdm_db.job_count("order") is None


def test_job_count_bad_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout="not a count")
    assert cdm_db.job_count("order") is None


def test_job_count_subprocess_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch).side_effect = FileNotFoundError("powershell")
    assert cdm_db.job_count("order") is None


def test_read_cdm_csv_utf8_bom_stripped(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "bom.csv"
    f.write_bytes(b"\xef\xbb\xbfStyle,Quantity,Width,Length,DesignDimensions\nP003,1,400,300,0\n")
    rows = cdm_db.read_cdm_csv(str(f), ",")
    assert rows[0][0] == "Style"
    assert rows[1][0] == "P003"


def test_read_cdm_csv_cp1250(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "cp1250.csv"
    f.write_bytes("P003;Ilość;400;300;0;MDF\n".encode("cp1250"))
    rows = cdm_db.read_cdm_csv(str(f), ";")
    assert rows[0][1] == "Ilość"


def test_read_cdm_csv_utf8_polish_chars(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "utf8.csv"
    f.write_bytes("P003;1;400;300;0;Dąb\n".encode())
    rows = cdm_db.read_cdm_csv(str(f), ";")
    assert rows[0][5] == "Dąb"


def test_read_cdm_csv_multi_char_separator(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "sep.csv"
    f.write_bytes(b"P003,1,400,300,0\n")
    with pytest.raises(RuntimeError, match="cdm: separator must be a single character"):
        cdm_db.read_cdm_csv(str(f), ";;")


def test_parse_cdm_rows_valid_row() -> None:
    rows = [["P003", "1", "400", "300", "1;18", "MDF"]]
    details, errors = cdm_db.parse_cdm_rows(rows, False)
    assert errors == []
    assert details == [
        {
            "row": 1,
            "style": "P003",
            "quantity": 1,
            "width": 400.0,
            "length": 300.0,
            "design_dims": "1;18",
        }
    ]


def test_parse_cdm_rows_header_skipped() -> None:
    rows = [
        ["Style", "Quantity", "Width", "Length", "DesignDimensions"],
        ["P003", "1", "400", "300", "0"],
    ]
    details, errors = cdm_db.parse_cdm_rows(rows, True)
    assert errors == []
    assert [d["style"] for d in details] == ["P003"]
    assert details[0]["row"] == 2


def test_parse_cdm_rows_quantity_must_be_positive() -> None:
    rows = [["P003", "0", "400", "300", "0"], ["P004", "-2", "400", "300", "0"]]
    details, errors = cdm_db.parse_cdm_rows(rows, False)
    assert details == []
    assert errors == ["row 1: quantity must be positive", "row 2: quantity must be positive"]


def test_parse_cdm_rows_width_length_must_be_positive() -> None:
    rows = [["P003", "1", "0", "300", "0"], ["P004", "1", "400", "-5", "0"]]
    details, errors = cdm_db.parse_cdm_rows(rows, False)
    assert details == []
    assert errors == ["row 1: width must be positive", "row 2: length must be positive"]


def test_parse_cdm_rows_short_row() -> None:
    rows = [["P003", "1"]]
    details, errors = cdm_db.parse_cdm_rows(rows, False)
    assert details == []
    assert errors == ["row 1: expected at least 5 columns, got 2"]


def test_parse_cdm_rows_empty_style() -> None:
    rows = [["", "1", "400", "300", "0"]]
    details, errors = cdm_db.parse_cdm_rows(rows, False)
    assert details == []
    assert errors == ["row 1: style is required"]


def test_parse_cdm_rows_invalid_values() -> None:
    rows = [
        ["P003", "abc", "400", "300", "0"],
        ["P004", "1", "x", "300", "0"],
        ["P005", "1", "400", "y", "0"],
    ]
    details, errors = cdm_db.parse_cdm_rows(rows, False)
    assert details == []
    assert errors == [
        "row 1: invalid quantity: 'abc'",
        "row 2: invalid width: 'x'",
        "row 3: invalid length: 'y'",
    ]


def test_parse_cdm_rows_empty_rows_skipped() -> None:
    rows = [[""], ["P003", "1", "400", "300", "0"], []]
    details, errors = cdm_db.parse_cdm_rows(rows, False)
    assert errors == []
    assert [d["row"] for d in details] == [2]


# --- cleanup_created_job ---


def _cleanup_env(
    monkeypatch: pytest.MonkeyPatch,
    job: MagicMock,
    found: Any = None,
    count: int | None = 0,
) -> MagicMock:
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=found))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.job_count", MagicMock(return_value=count))
    return job


def test_cleanup_created_job_deleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = MagicMock()
    found = MagicMock()
    _cleanup_env(monkeypatch, job, found=found, count=0)
    deleted, reason = cdm_db.cleanup_created_job(MagicMock(), job, "order")
    assert (deleted, reason) == (True, "")
    job.DeleteFromDB.assert_called_once_with()
    found.DeleteFromDB.assert_called_once_with()


def test_cleanup_created_job_delete_via_lookup_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = MagicMock()
    del job.DeleteFromDB
    found = MagicMock()
    _cleanup_env(monkeypatch, job, found=found, count=0)
    deleted, reason = cdm_db.cleanup_created_job(MagicMock(), job, "order")
    assert (deleted, reason) == (True, "")
    found.DeleteFromDB.assert_called_once_with()


def test_cleanup_created_job_still_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = MagicMock()
    _cleanup_env(monkeypatch, job, found=None, count=1)
    deleted, reason = cdm_db.cleanup_created_job(MagicMock(), job, "order")
    assert (deleted, reason) == (False, "failed")


def test_cleanup_created_job_unverified_count_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = MagicMock()
    _cleanup_env(monkeypatch, job, found=None, count=None)
    deleted, reason = cdm_db.cleanup_created_job(MagicMock(), job, "order")
    assert (deleted, reason) == (False, "unverified")


def test_cleanup_created_job_exception_logged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = MagicMock()
    job.DeleteFromDB.side_effect = RuntimeError("db locked")
    monkeypatch.setattr("alphacam_cli.core.cdm_db.job_count", MagicMock(return_value=0))
    calls: list[str] = []
    deleted, reason = cdm_db.cleanup_created_job(MagicMock(), job, "order", log=calls.append)
    assert (deleted, reason) == (False, "failed")
    assert any("db locked" in msg for msg in calls)


# --- _scripts_dir ---


def test_scripts_dir_source_tree() -> None:
    result = cdm_db._scripts_dir()
    assert os.path.basename(result) == "scripts"
    assert os.path.isdir(result)


def test_scripts_dir_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", r"C:\bundle", raising=False)
    assert cdm_db._scripts_dir() == os.path.join(r"C:\bundle", "scripts")


# --- import field mapping ---


def test_import_field_name_known() -> None:
    assert cdm_db.import_field_name(256) == "door_type"
    assert cdm_db.import_field_name(259) == "door_quantity"
    assert cdm_db.import_field_name(264) == "door_design_dimensions"
    assert cdm_db.import_field_name(271) == "door_rotation_method"
    assert cdm_db.import_field_name(298) == "door_drilling"
    assert cdm_db.import_field_name(299) == "door_small_nest"
    assert cdm_db.import_field_name(512) == "job_name"
    assert cdm_db.import_field_name(524) == "job_material_id"


def test_import_field_name_unknown() -> None:
    assert cdm_db.import_field_name(999) is None
    assert cdm_db.import_field_name(0) is None
    assert cdm_db.import_field_name(1) is None
    assert cdm_db.import_field_name(270) is None


def test_import_field_name_custom_fields_range() -> None:
    assert cdm_db.import_field_name(275) == "door_custom_field_3"
    assert cdm_db.import_field_name(297) == "door_custom_field_25"
    for parameter_type in range(275, 298):
        assert cdm_db.import_field_name(parameter_type) is not None


def test_import_settings_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = (
        '[{"id": 3, "name": "sklep CSV", "selected": false, "delimiter_char": ",",'
        ' "sub_delimiter_char": ";", "ignore_header": false, "is_cdm_import": true,'
        ' "create_job": true, "fields": [{"column_number": 1, "parameter_type": 256},'
        ' {"column_number": 2, "parameter_type": 259}]},'
        ' {"id": 4, "name": "Ustawienia Importu CSV 2", "create_job": false,'
        ' "delimiter_char": ",", "fields": [{"column_number": 1, "parameter_type": 256}]}]'
    )
    run = _mock_run(monkeypatch, stdout=stdout)
    settings = cdm_db.import_settings()
    assert len(settings) == 2
    assert settings[0]["id"] == 3
    assert settings[0]["name"] == "sklep CSV"
    assert settings[0]["delimiter_char"] == ","
    assert settings[0]["is_cdm_import"] is True
    assert settings[0]["fields"] == [
        {"column_number": 1, "parameter_type": 256},
        {"column_number": 2, "parameter_type": 259},
    ]
    assert settings[1]["name"] == "Ustawienia Importu CSV 2"
    assert settings[1]["create_job"] is False
    args, _ = run.call_args
    assert "vdb5_import_settings.ps1" in args[0][-1]


def test_import_settings_value_wrap(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(
        monkeypatch,
        stdout=(
            '{"value": [{"id": 3, "name": "sklep CSV", "delimiter_char": ",",'
            ' "fields": [{"column_number": 1, "parameter_type": 256}]}]}'
        ),
    )
    settings = cdm_db.import_settings()
    assert len(settings) == 1
    assert settings[0]["id"] == 3


def test_import_settings_fallback_subprocess_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_run(monkeypatch).side_effect = FileNotFoundError("powershell")
    assert cdm_db.import_settings() == []


def test_import_settings_fallback_nonzero_returncode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_run(monkeypatch, stdout="", returncode=1)
    assert cdm_db.import_settings() == []


def test_import_settings_fallback_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_run(monkeypatch, stdout="not json")
    assert cdm_db.import_settings() == []


def test_import_settings_fallback_not_a_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_run(monkeypatch, stdout='{"config_name": "x"}')
    assert cdm_db.import_settings() == []


def test_import_settings_skips_malformed_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_run(
        monkeypatch,
        stdout=(
            '[{"id": 5, "name": "No delimiter"},'
            ' "not a dict",'
            ' {"id": 6, "name": "Bad fields", "delimiter_char": ";", "fields": "nope"},'
            ' {"id": 7, "name": "Clean", "delimiter_char": ",",'
            ' "fields": [{"column_number": 1, "parameter_type": 256},'
            ' {"column_number": 2}]}]'
        ),
    )
    settings = cdm_db.import_settings()
    assert len(settings) == 1
    assert settings[0]["id"] == 7
    assert settings[0]["fields"] == [{"column_number": 1, "parameter_type": 256}]


def test_find_import_setting_by_id() -> None:
    settings = [
        {"id": 3, "name": "sklep CSV", "delimiter_char": ",", "fields": []},
        {"id": 4, "name": "Ustawienia Importu CSV 2", "delimiter_char": ";", "fields": []},
    ]
    assert cdm_db.find_import_setting(settings, 4)["name"] == "Ustawienia Importu CSV 2"
    assert cdm_db.find_import_setting(settings, 3)["name"] == "sklep CSV"


def test_find_import_setting_by_name() -> None:
    settings = [{"id": 3, "name": "sklep CSV", "delimiter_char": ",", "fields": []}]
    assert cdm_db.find_import_setting(settings, "sklep CSV")["id"] == 3


def test_find_import_setting_name_casefold_trim() -> None:
    settings = [{"id": 3, "name": "  Sklep csv  ", "delimiter_char": ",", "fields": []}]
    assert cdm_db.find_import_setting(settings, "SKLEP CSV")["id"] == 3


def test_find_import_setting_not_found() -> None:
    settings = [{"id": 3, "name": "sklep CSV", "delimiter_char": ",", "fields": []}]
    assert cdm_db.find_import_setting(settings, 999) is None
    assert cdm_db.find_import_setting(settings, "nope") is None
    assert cdm_db.find_import_setting([], 3) is None


def test_field_map_from_setting() -> None:
    setting = {
        "id": 3,
        "fields": [
            {"column_number": 8, "parameter_type": 513},
            {"column_number": 1, "parameter_type": 256},
            {"column_number": 2, "parameter_type": 259},
            {"column_number": 3, "parameter_type": 257},
            {"column_number": 4, "parameter_type": 258},
            {"column_number": 5, "parameter_type": 264},
            {"column_number": 6, "parameter_type": 524},
            {"column_number": 7, "parameter_type": 512},
            {"column_number": 9, "parameter_type": 999},
            {"column_number": 10, "parameter_type": 0},
            {"column_number": 11, "parameter_type": 1},
        ],
    }
    field_map = cdm_db.field_map_from_setting(setting)
    assert field_map == {
        1: "door_type",
        2: "door_quantity",
        3: "door_width",
        4: "door_height",
        5: "door_design_dimensions",
        6: "job_material_id",
        7: "job_name",
        8: "job_config_id",
        9: "unknown_999",
    }
    assert list(field_map.items())[0] == (1, "door_type")


def test_field_map_from_setting_no_fields() -> None:
    assert cdm_db.field_map_from_setting({"id": 3, "fields": None}) == {}
    assert cdm_db.field_map_from_setting({"id": 3}) == {}


def test_parse_cdm_rows_mapped_sklep_csv() -> None:
    field_map = {
        1: "door_type",
        2: "door_quantity",
        3: "door_width",
        4: "door_height",
        5: "door_design_dimensions",
        6: "job_material_id",
        7: "job_name",
        8: "job_config_id",
    }
    rows = [
        [
            "P003",
            "1",
            "500",
            "500",
            "1;18;0;0;30;45;40;90;50;3;0",
            "MDF_18",
            "Zamowienie X",
            "Fronty",
        ]
    ]
    details, errors = cdm_db.parse_cdm_rows_mapped(rows, field_map, False)
    assert errors == []
    assert details == [
        {
            "row": 1,
            "style": "P003",
            "quantity": 1,
            "width": 500.0,
            "length": 500.0,
            "design_dims": "1;18;0;0;30;45;40;90;50;3;0",
            "material": None,
            "customer_name": None,
            "order_number": None,
            "item_number": None,
            "production_comment": None,
            "oversize_x": None,
            "oversize_y": None,
            "corner_radius": None,
            "rotation_method": None,
            "rotation_angle": None,
            "nest_priority": None,
            "ignore_outer_geometry": None,
            "small_nest_part": None,
            "has_drilling": None,
            "custom_fields": {},
            "job_name": "Zamowienie X",
            "job_config_id": "Fronty",
            "job_setup_id": None,
            "job_tool_order_id": None,
            "job_purchase_order_number": None,
            "job_work_order_number": None,
            "job_description": None,
            "job_programmer_name": None,
            "job_order_date": None,
            "job_due_date": None,
            "job_customer": None,
            "job_parent_job": None,
            "job_material_id": "MDF_18",
        }
    ]


def test_parse_cdm_rows_mapped_missing_required_field() -> None:
    field_map = {1: "door_type", 2: "door_quantity", 3: "door_height"}
    rows = [["P003", "1", "300"]]
    details, errors = cdm_db.parse_cdm_rows_mapped(rows, field_map, False)
    assert details == []
    assert errors == ["import settings map is missing required field(s): door_width"]


def test_parse_cdm_rows_mapped_missing_door_type() -> None:
    field_map = {1: "door_quantity", 2: "door_width", 3: "door_height"}
    rows = [["1", "400", "300"]]
    details, errors = cdm_db.parse_cdm_rows_mapped(rows, field_map, False)
    assert details == []
    assert errors == ["import settings map is missing required field(s): door_type"]


def test_parse_cdm_rows_mapped_bool_and_numbers() -> None:
    field_map = {
        1: "door_type",
        2: "door_quantity",
        3: "door_width",
        4: "door_height",
        5: "door_customer_name",
        6: "door_production_comment",
        7: "door_custom_field_1",
        8: "door_custom_field_2",
        9: "door_rotation_angle",
        10: "door_small_nest",
        11: "door_drilling",
    }
    rows = [
        ["P003", "1", "400", "300", "Jan Kowalski", "komentarz", "cf1", "", "45.5", "true", "0"],
        ["P004", "2", "500", "400", "", "", "", "cf2", "90", "no", "1"],
    ]
    details, errors = cdm_db.parse_cdm_rows_mapped(rows, field_map, False)
    assert errors == []
    first = details[0]
    assert first["customer_name"] == "Jan Kowalski"
    assert first["production_comment"] == "komentarz"
    assert first["custom_fields"] == {"1": "cf1"}
    assert first["rotation_angle"] == 45.5
    assert first["small_nest_part"] is True
    assert first["has_drilling"] is False
    second = details[1]
    assert second["customer_name"] is None
    assert second["production_comment"] is None
    assert second["custom_fields"] == {"2": "cf2"}
    assert second["rotation_angle"] == 90.0
    assert second["small_nest_part"] is False
    assert second["has_drilling"] is True


def test_parse_cdm_rows_mapped_unknown_field_ignored() -> None:
    field_map = {
        1: "door_type",
        2: "door_quantity",
        3: "door_width",
        4: "door_height",
        5: "unknown_273",
    }
    rows = [["P003", "1", "400", "300", "x"]]
    details, errors = cdm_db.parse_cdm_rows_mapped(rows, field_map, False)
    assert errors == []
    assert len(details) == 1
    detail = details[0]
    assert "unknown_273" not in detail
    assert detail["style"] == "P003"
    assert detail["quantity"] == 1
    assert detail["width"] == 400.0
    assert detail["length"] == 300.0


def test_parse_cdm_rows_mapped_unknown_column_beyond_row_length() -> None:
    field_map = {
        1: "door_type",
        2: "door_quantity",
        3: "door_width",
        4: "door_height",
        15: "unknown_400",
    }
    rows = [["P003", "1", "400", "300", "x"]]
    details, errors = cdm_db.parse_cdm_rows_mapped(rows, field_map, False)
    assert errors == []
    assert len(details) == 1
    detail = details[0]
    assert detail["style"] == "P003"
    assert detail["quantity"] == 1
    assert detail["width"] == 400.0
    assert detail["length"] == 300.0


def test_parse_cdm_rows_mapped_invalid_values() -> None:
    field_map = {
        1: "door_type",
        2: "door_quantity",
        3: "door_width",
        4: "door_height",
        5: "door_small_nest",
        6: "door_rotation_angle",
    }
    rows = [
        ["P003", "abc", "400", "300", "", ""],
        ["P004", "1", "400", "300", "maybe", ""],
        ["P005", "1", "400", "300", "", "xyz"],
        ["P006", "0", "400", "300", "", ""],
        ["P007", "1", "0", "300", "", ""],
    ]
    details, errors = cdm_db.parse_cdm_rows_mapped(rows, field_map, False)
    assert details == []
    assert errors == [
        "row 1: invalid quantity: 'abc'",
        "row 2: invalid value for door_small_nest: maybe",
        "row 3: invalid value for door_rotation_angle: xyz",
        "row 4: quantity must be positive",
        "row 5: width must be positive",
    ]


def test_parse_cdm_rows_mapped_rotation_method_int() -> None:
    field_map = {
        1: "door_type",
        2: "door_quantity",
        3: "door_width",
        4: "door_height",
        5: "door_rotation_method",
    }
    rows = [["P003", "1", "500", "400", "3"]]
    details, errors = cdm_db.parse_cdm_rows_mapped(rows, field_map, False)
    assert errors == []
    assert details[0]["rotation_method"] == 3
    assert isinstance(details[0]["rotation_method"], int)


def test_parse_cdm_rows_mapped_rotation_method_invalid() -> None:
    field_map = {
        1: "door_type",
        2: "door_quantity",
        3: "door_width",
        4: "door_height",
        5: "door_rotation_method",
    }
    rows = [["P003", "1", "500", "400", "abc"]]
    details, errors = cdm_db.parse_cdm_rows_mapped(rows, field_map, False)
    assert details == []
    assert errors == ["row 1: invalid value for door_rotation_method: abc"]


def test_parse_cdm_rows_mapped_nest_priority_int() -> None:
    field_map = {
        1: "door_type",
        2: "door_quantity",
        3: "door_width",
        4: "door_height",
        5: "door_nest_priority",
    }
    rows = [["P003", "1", "500", "400", "7"]]
    details, errors = cdm_db.parse_cdm_rows_mapped(rows, field_map, False)
    assert errors == []
    assert details[0]["nest_priority"] == 7
    assert isinstance(details[0]["nest_priority"], int)


def test_parse_cdm_rows_mapped_nest_priority_invalid() -> None:
    field_map = {
        1: "door_type",
        2: "door_quantity",
        3: "door_width",
        4: "door_height",
        5: "door_nest_priority",
    }
    rows = [["P003", "1", "500", "400", "high"]]
    details, errors = cdm_db.parse_cdm_rows_mapped(rows, field_map, False)
    assert details == []
    assert errors == ["row 1: invalid value for door_nest_priority: high"]


def test_parse_cdm_rows_mapped_header_skipped() -> None:
    field_map = {1: "door_type", 2: "door_quantity", 3: "door_width", 4: "door_height"}
    rows = [
        ["Style", "Quantity", "Width", "Height"],
        ["P003", "1", "400", "300"],
    ]
    details, errors = cdm_db.parse_cdm_rows_mapped(rows, field_map, True)
    assert errors == []
    assert [d["style"] for d in details] == ["P003"]
    assert details[0]["row"] == 2


def test_parse_cdm_rows_mapped_empty_rows_skipped() -> None:
    field_map = {1: "door_type", 2: "door_quantity", 3: "door_width", 4: "door_height"}
    rows = [[""], ["P003", "1", "400", "300"], []]
    details, errors = cdm_db.parse_cdm_rows_mapped(rows, field_map, False)
    assert errors == []
    assert [d["row"] for d in details] == [2]


def test_parse_cdm_rows_mapped_short_row() -> None:
    field_map = {
        1: "door_type",
        2: "door_quantity",
        3: "door_width",
        4: "door_height",
        5: "job_name",
    }
    rows = [["P003", "1", "400", "300"]]
    details, errors = cdm_db.parse_cdm_rows_mapped(rows, field_map, False)
    assert details == []
    assert errors == ["row 1: expected at least 5 columns, got 4"]


def test_field_map_descriptions() -> None:
    field_map = {1: "door_type", 2: "door_quantity", 5: "job_name", 9: "unknown_999"}
    assert cdm_db.field_map_descriptions(field_map) == [
        {"column": 1, "field": "door_type", "required": True},
        {"column": 2, "field": "door_quantity", "required": True},
        {"column": 5, "field": "job_name", "required": False},
        {"column": 9, "field": "unknown_999", "required": False},
    ]
