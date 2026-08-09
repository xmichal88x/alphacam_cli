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
    assert "-JobName:order" in args[0]
    assert "-MaterialID:4" in args[0]


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
    assert "-JobName:order" in args[0]
    assert "-Values:1;0" in args[0]
    assert args[0][args[0].index("-JobName:order") : args[0].index("-Values:1;0") + 1] == [
        "-JobName:order",
        "-Values:1;0",
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
    assert "-JobName:order" in args[0]


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


# --- order_details ---

_ORDER_DETAIL_ROW = (
    '{"job_name": "Zamowienie X", "style_name": "P003",'
    ' "csv_customer_name": "Jan Kowalski", "csv_order_number": "ORD-1",'
    ' "csv_item_number": "ITEM-1", "production_comment": "komentarz",'
    ' "user_variable_string": "1;18", "user_description_string": "opis",'
    ' "user_value_0": "a", "user_value_1": "b", "user_value_2": "c",'
    ' "user_value_3": "d", "user_value_4": "e", "user_value_5": "f",'
    ' "user_value_6": "g", "style_number": 3, "quantity": 2, "material_id": 4,'
    ' "rotation_method": 1, "nesting_priority": 5, "fk_type_id": 7,'
    ' "cdm_pk": 10, "cdm_order_id": 20, "fk_parent_order_detail_id": 0,'
    ' "width": 400.5, "length": 300.5, "corner_radius": 8.0,'
    ' "oversize_x": 0.0, "oversize_y": 0.0, "rotation_angle": 90.0,'
    ' "ignore_outer_geometry": true, "small_nest_part": false,'
    ' "has_drilling": true, "bypass_nest": false, "active_in_process": true,'
    ' "custom_fields": {"1": "cf1", "25": "cf25"}}'
)


def test_order_details_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    second = _ORDER_DETAIL_ROW.replace("P003", "P004").replace('"quantity": 2', '"quantity": 1')
    _mock_run(monkeypatch, stdout=f"[{_ORDER_DETAIL_ROW},{second}]")
    details = cdm_db.order_details()
    assert len(details) == 2
    first = details[0]
    assert first["style_name"] == "P003"
    assert first["quantity"] == 2
    assert first["width"] == 400.5
    assert first["length"] == 300.5
    assert first["material_id"] == 4
    assert first["cdm_pk"] == 10
    assert first["cdm_order_id"] == 20
    assert first["fk_type_id"] == 7
    assert first["fk_parent_order_detail_id"] == 0
    assert first["active_in_process"] is True
    assert first["has_drilling"] is True
    assert first["user_value_0"] == "a"
    assert first["user_value_6"] == "g"
    assert first["custom_fields"] == {"1": "cf1", "25": "cf25"}
    assert details[1]["style_name"] == "P004"
    assert details[1]["quantity"] == 1


def test_order_details_passes_job_name(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _mock_run(monkeypatch, stdout="[]")
    assert cdm_db.order_details("Zamowienie X") == []
    args, _ = run.call_args
    assert "-JobName:Zamowienie X" in args[0]
    assert args[0][args[0].index("-File") + 1].endswith("vdb5_order_details.ps1")


def test_order_details_no_job_name(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _mock_run(monkeypatch, stdout="[]")
    assert cdm_db.order_details() == []
    args, _ = run.call_args
    assert "-JobName" not in args[0]


def test_order_details_job_name_with_dash(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _mock_run(monkeypatch, stdout="[]")
    assert cdm_db.order_details("-foo") == []
    args, _ = run.call_args
    assert "-JobName:-foo" in args[0]
    assert "-foo" not in args[0]


def test_order_details_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch).side_effect = FileNotFoundError("powershell")
    assert cdm_db.order_details() == []
    _mock_run(monkeypatch, stdout="", returncode=1)
    assert cdm_db.order_details() == []
    _mock_run(monkeypatch, stdout="not json")
    assert cdm_db.order_details() == []


def test_order_details_value_wrap(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout=f'{{"value": [{_ORDER_DETAIL_ROW}]}}')
    details = cdm_db.order_details()
    assert len(details) == 1
    assert details[0]["style_name"] == "P003"


# --- door_paths ---

_DOOR_PATH_ROW = (
    '{"path_id": 3, "cdm_path_id": 0, "door_type_id": 11, "door_type": "L_B_10mm",'
    ' "path_number": 1, "path_name": "Ryfle Ball 10mm", "group_id": 1,'
    ' "tool_name": "", "tool_full_path": "", "tool_number": 0, "tool_offset": 0,'
    ' "machining_method": "MachiningStyle", "machining_style":'
    ' "LICOMDIR\\\\Styles\\\\Fronty\\\\Ball_10mm_AZ.ary", "cut_type": "Full",'
    ' "creation_method": "MachiningStyle", "last_modified": "2026-01-01 12:00:00",'
    ' "insert_file_path": "", "safe_rapid": 5.0, "rapid_down_to": 2.0,'
    ' "final_depth": -10.5, "final_depth_percentage": 100.0, "spindle_speed": 12000.0,'
    ' "down_feed": 1500.0, "cut_feed": 3000.0, "cut_direction": 1.0,'
    ' "material_top": 0.0, "stock": 0.0, "chord_error": 0.02,'
    ' "thickness_first_cut": 1.0, "thickness_last_cut": 1.0,'
    ' "thickness_first_cut_percent": 0.0, "thickness_last_cut_percent": 0.0,'
    ' "diameter": 10.0, "step_length": 0.0, "path_offset_value": 0.0,'
    ' "pocket_boundary": 0.0, "lead_line_length": 3.0, "lead_line_length_out": 3.0,'
    ' "lead_arc_radius": 0.0, "lead_approach_angle": 45.0, "lead_overlap": 0.0,'
    ' "lead3d_approach_angle": 0.0, "lead3d_approach": 0.0, "width_of_cut": 10.0,'
    ' "insert_file_point_x": 0.0, "insert_file_point_y": 0.0,'
    ' "engrave_corner_angle": 0.0, "partial_start_elem_dist": 0.0,'
    ' "partial_end_elem_dist": 0.0, "deceleration_distance": 0.0,'
    ' "slow_down_to": 0.0, "do_not_slow_down_radius": 0.0,'
    ' "ignore_angle_greater_than": 0.0, "simple_engrave_feed": 0.0,'
    ' "simple_engrave_clearance": 0.0, "is_final_depth_percent": true,'
    ' "comp_on_rapid": false, "slope_in": true, "slope_out": false,'
    ' "depths_of_cut_specified": false, "multiple_passes": true,'
    ' "tool_direction_cw": false, "tool_direction_reversed": true,'
    ' "pocket3d_approach": false, "slow_down_for_corners": true,'
    ' "accelerate_out_of_corner": false, "tool_side_partial_reverse": true,'
    ' "mc_comp": 0, "tool_in_out": 1, "tool_side": 0, "lead_in": 1,'
    ' "lead_out": 1, "insert_file_reference_point": 0, "number_of_cuts": 1,'
    ' "xy_corners": 0, "final_pass_island": 0, "pocket_type": 0,'
    ' "start_cutting": 0, "path_offset_side": 0, "path_offset_from": 0,'
    ' "lead_entry_point_is_corner": 0, "partial_start_elem_index": 0,'
    ' "partial_end_elem_index": 0, "number_of_steps": 0,'
    ' "insert_parametric_group_number": 0}'
)


def test_door_paths_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    second = _DOOR_PATH_ROW.replace('"path_id": 3', '"path_id": 4').replace(
        '"path_number": 1', '"path_number": 2'
    )
    _mock_run(monkeypatch, stdout=f"[{_DOOR_PATH_ROW},{second}]")
    paths = cdm_db.door_paths()
    assert len(paths) == 2
    first = paths[0]
    assert first["path_id"] == 3
    assert first["path_number"] == 1
    assert first["door_type_id"] == 11
    assert first["door_type"] == "L_B_10mm"
    assert first["path_name"] == "Ryfle Ball 10mm"
    assert first["tool_name"] == ""
    assert first["machining_method"] == "MachiningStyle"
    assert first["machining_style"] == r"LICOMDIR\Styles\Fronty\Ball_10mm_AZ.ary"
    assert first["cut_type"] == "Full"
    assert first["creation_method"] == "MachiningStyle"
    assert first["spindle_speed"] == 12000.0
    assert first["final_depth"] == -10.5
    assert first["diameter"] == 10.0
    assert first["lead_in"] == 1
    assert first["lead_out"] == 1
    assert first["tool_in_out"] == 1
    assert first["is_final_depth_percent"] is True
    assert first["slope_in"] is True
    assert first["slope_out"] is False
    assert first["multiple_passes"] is True
    assert first["tool_direction_reversed"] is True
    assert first["slow_down_for_corners"] is True
    assert paths[1]["path_id"] == 4
    assert paths[1]["path_number"] == 2


def test_door_paths_passes_type_name(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _mock_run(monkeypatch, stdout="[]")
    assert cdm_db.door_paths("L_B_10mm") == []
    args, _ = run.call_args
    assert "-TypeName:L_B_10mm" in args[0]
    assert args[0][args[0].index("-File") + 1].endswith("vdb5_door_paths.ps1")


def test_door_paths_no_type_name(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _mock_run(monkeypatch, stdout="[]")
    assert cdm_db.door_paths() == []
    args, _ = run.call_args
    assert "-TypeName" not in args[0]


def test_door_paths_type_name_with_dash(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _mock_run(monkeypatch, stdout="[]")
    assert cdm_db.door_paths("-foo") == []
    args, _ = run.call_args
    assert "-TypeName:-foo" in args[0]
    assert "-foo" not in args[0]


def test_door_paths_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch).side_effect = FileNotFoundError("powershell")
    assert cdm_db.door_paths() == []
    _mock_run(monkeypatch, stdout="", returncode=1)
    assert cdm_db.door_paths() == []
    _mock_run(monkeypatch, stdout="not json")
    assert cdm_db.door_paths() == []


def test_door_paths_value_wrap(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout=f'{{"value": [{_DOOR_PATH_ROW}]}}')
    paths = cdm_db.door_paths()
    assert len(paths) == 1
    assert paths[0]["path_name"] == "Ryfle Ball 10mm"


# --- materials ---

_MATERIAL_ROWS = (
    '[{"id": 1, "name": "Not Selected", "width": 0.0, "length": 0.0,'
    ' "thickness": 0.0, "grain_restriction": 0},'
    ' {"id": 2, "name": "Material 2 - 2070 x 2800", "width": 2070.0,'
    ' "length": 2800.0, "thickness": 19.0, "grain_restriction": 1},'
    ' {"id": 3, "name": "Material 3 - 2440 x 1220", "width": 2440.0,'
    ' "length": 1220.0, "thickness": 19.0, "grain_restriction": 0},'
    ' {"id": 4, "name": "Material 4 - Imperial 96 x 48", "width": 96.0,'
    ' "length": 48.0, "thickness": 0.75, "grain_restriction": 0}]'
)


def test_materials_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout=_MATERIAL_ROWS)
    materials = cdm_db.materials()
    assert len(materials) == 4
    first = materials[0]
    assert first["id"] == 1
    assert first["name"] == "Not Selected"
    assert first["width"] == 0.0
    assert first["length"] == 0.0
    assert first["thickness"] == 0.0
    assert first["grain_restriction"] == 0
    second = materials[1]
    assert second["name"] == "Material 2 - 2070 x 2800"
    assert second["width"] == 2070.0
    assert second["length"] == 2800.0
    assert second["thickness"] == 19.0
    assert second["grain_restriction"] == 1
    assert materials[2]["width"] == 2440.0
    assert materials[2]["length"] == 1220.0
    assert materials[3]["width"] == 96.0
    assert materials[3]["length"] == 48.0
    assert materials[3]["thickness"] == 0.75


def test_materials_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch).side_effect = FileNotFoundError("powershell")
    assert cdm_db.materials() == []
    _mock_run(monkeypatch, stdout="", returncode=1)
    assert cdm_db.materials() == []
    _mock_run(monkeypatch, stdout="not json")
    assert cdm_db.materials() == []


def test_materials_value_wrap(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout=f'{{"value": {_MATERIAL_ROWS}}}')
    materials = cdm_db.materials()
    assert len(materials) == 4
    assert materials[0]["name"] == "Not Selected"


# --- configs ---

_CONFIG_40 = (
    '{"id": 40, "name": "CDM_Materiał 17mm", "post_processor": "Fanuc",'
    ' "drawing_output_location": "C:\\\\out", "nc_output_location": "C:\\\\nc",'
    ' "report_output_location": "", "nc_extension": "nc", "custom_vba_macro": "",'
    ' "compiled_file_name": "", "compiled_base_name": "",'
    ' "replace_space_with_underscore": false, "disable_screen_updates": true,'
    ' "clear_output_folders": false, "generate_nc": true, "generate_reports": false,'
    ' "create_default_material": false, "save_generated_autostyles": true,'
    ' "read_file_information_on_import": false, "show_material_selector_after_import": false,'
    ' "nesting_method": 0, "nesting_pack_to": 1, "nesting_gap_between_paths": 2.0,'
    ' "nesting_gap_at_sheet_edge": 0.0, "nesting_extra_gap_at_lead_start": 0.0,'
    ' "nesting_time_per_sheet": 30, "nesting_optimisation_level": 3,'
    ' "nesting_search_resolution": 0.5, "nesting_cut_small_parts_first": true,'
    ' "nesting_total_time": 0.0, "nesting_sheet_order_type": 0,'
    ' "nesting_sheet_alignment": 0, "nesting_alignment_z_level": 0.0,'
    ' "nesting_join_saw_cuts_tolerance": 0.0, "nesting_inactivity_timeout": 0.0}'
)

_CONFIG_41 = _CONFIG_40.replace('"id": 40', '"id": 41').replace(
    '"name": "CDM_Materiał 17mm"', '"name": "Fronty"'
)

_CDM_ROW_A = (
    '{"cdm_configuration_setting_id": 5, "fk_configuration_setting_id": 41,'
    ' "part_recovery_x": 10.5, "part_recovery_y": 0.0, "part_recovery_ignore_grain": false,'
    ' "capture_nested_part_positions": true, "disable_nesting": false,'
    ' "disable_nesting_oversize_x": 0.0, "disable_nesting_oversize_y": 0.0,'
    ' "use_default_press": false, "press_group_by_material_thickness": true,'
    ' "custom_macro": "", "use_data_from_tool_file": false, "use_same_start_point": false,'
    ' "use_drawing_extents_for_inserted_drawing_operations": false,'
    ' "generate_nc_for_parts": true, "z_depth_tolerance": 0.0,'
    ' "preview_material_thickness": 19.0}'
)

_CDM_ROW_B = _CDM_ROW_A.replace(
    '"cdm_configuration_setting_id": 5', '"cdm_configuration_setting_id": 6'
)


def test_configs_parses_and_merges(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = f'{{"configs": [{_CONFIG_40},{_CONFIG_41}], "cdm": [{_CDM_ROW_A},{_CDM_ROW_B}]}}'
    _mock_run(monkeypatch, stdout=stdout)
    configs = cdm_db.configs()
    assert len(configs) == 2
    cfg40 = configs[0]
    assert cfg40["id"] == 40
    assert cfg40["name"] == "CDM_Materiał 17mm"
    assert cfg40["post_processor"] == "Fanuc"
    assert cfg40["generate_nc"] is True
    assert cfg40["nesting_method"] == 0
    assert cfg40["nesting_gap_between_paths"] == 2.0
    assert cfg40["nesting_cut_small_parts_first"] is True
    assert cfg40["cdm"] == {}
    cfg41 = configs[1]
    assert cfg41["id"] == 41
    assert cfg41["name"] == "Fronty"
    assert cfg41["cdm"]["disable_nesting"] is False
    assert cfg41["cdm"]["capture_nested_part_positions"] is True
    assert cfg41["cdm"]["part_recovery_x"] == 10.5
    assert cfg41["cdm"]["press_group_by_material_thickness"] is True
    assert cfg41["cdm"]["preview_material_thickness"] == 19.0
    assert cfg41["cdm"]["fk_configuration_setting_id"] == 41


def test_configs_show_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = f'{{"configs": [{_CONFIG_40},{_CONFIG_41}], "cdm": [{_CDM_ROW_A}]}}'
    _mock_run(monkeypatch, stdout=stdout)
    assert [cfg["id"] for cfg in cdm_db.configs("FRONTY")] == [41]
    assert cdm_db.configs("NIE MA") == []
    assert [cfg["id"] for cfg in cdm_db.configs("  ")] == [40, 41]


def test_configs_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch).side_effect = FileNotFoundError("powershell")
    assert cdm_db.configs() == []
    _mock_run(monkeypatch, stdout="", returncode=1)
    assert cdm_db.configs() == []
    _mock_run(monkeypatch, stdout="not json")
    assert cdm_db.configs() == []


def test_configs_missing_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout='{"configs": "nope"}')
    assert cdm_db.configs() == []
    _mock_run(monkeypatch, stdout='{"configs": [{"id": 1, "name": "X"}], "cdm": "nope"}')
    configs = cdm_db.configs()
    assert len(configs) == 1
    assert configs[0]["cdm"] == {}


def test_configs_value_wrap(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = f'{{"value": {{"configs": [{_CONFIG_41}], "cdm": [{_CDM_ROW_A}]}}}}'
    _mock_run(monkeypatch, stdout=stdout)
    configs = cdm_db.configs()
    assert len(configs) == 1
    assert configs[0]["name"] == "Fronty"
    assert configs[0]["cdm"]["disable_nesting"] is False


def test_configs_cdm_duplicate_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    second = (
        _CDM_ROW_A.replace('"disable_nesting": false', '"disable_nesting": true')
        .replace('"part_recovery_x": 10.5', '"part_recovery_x": 20.0')
        .replace('"cdm_configuration_setting_id": 5', '"cdm_configuration_setting_id": 7')
    )
    stdout = f'{{"configs": [{_CONFIG_41}], "cdm": [{_CDM_ROW_A},{second}]}}'
    _mock_run(monkeypatch, stdout=stdout)
    configs = cdm_db.configs()
    assert len(configs) == 1
    cdm = configs[0]["cdm"]
    assert cdm["cdm_configuration_setting_id"] == 7
    assert cdm["disable_nesting"] is True
    assert cdm["part_recovery_x"] == 20.0
    assert cdm["part_recovery_ignore_grain"] is False
    assert cdm["preview_material_thickness"] == 19.0


def test_configs_orphan_cdm_rows_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    orphan = _CDM_ROW_A.replace(
        '"fk_configuration_setting_id": 41', '"fk_configuration_setting_id": 999'
    )
    stdout = f'{{"configs": [{_CONFIG_41}], "cdm": [{orphan}]}}'
    _mock_run(monkeypatch, stdout=stdout)
    configs = cdm_db.configs()
    assert len(configs) == 1
    assert configs[0]["id"] == 41
    assert configs[0]["cdm"] == {}


# --- lookups ---

_SETUP_ROW_1 = (
    '{"id": 1, "name": "None", "fe_what_to_extract": 0, "fe_use_panel_alignment": true,'
    ' "fe_chord_tolerance": 0.01, "fe_z_level_step": 1.0, "fe_use_open_air_pocket_method": false,'
    ' "fe_limit_through_holes": false, "fe_max_dia_drilled_holes": 10.0,'
    ' "fe_extract_all_faces": true,'
    ' "geometry_query": "", "geometry_auto_query": "", "fe_contour_extraction_mode": 1,'
    ' "fe_drillable_holes_extraction_mode": 0, "imp_project_3d_to_2d": false,'
    ' "imp_step_length": 0.5,'
    ' "imp_common_line_removal": true, "imp_join_resulting_geos": false,'
    ' "imp_convert_spline": false,'
    ' "imp_delete_original": false, "imp_join_resulting_lines_or_arcs": true,'
    ' "imp_set_element_z_levels": true, "setup_seq_num": 1}'
)

_SETUP_ROW_93 = (
    _SETUP_ROW_1.replace('"id": 1', '"id": 93')
    .replace('"name": "None"', '"name": "Nowe Ustawienia 1"')
    .replace('"fe_use_panel_alignment": true', '"fe_use_panel_alignment": false')
    .replace('"fe_chord_tolerance": 0.01', '"fe_chord_tolerance": 0.05')
    .replace('"setup_seq_num": 1', '"setup_seq_num": 2')
)

_CUSTOMER_ROW_1 = (
    '{"id": 1, "name": "Not Selected", "address_line_1": "", "address_line_2": "",'
    ' "city": "", "country": "", "post_zip_code": "", "contact_name": "",'
    ' "telephone_number": "", "email_address": "", "website_address": ""}'
)

_MACHINING_ORDER_ROW = (
    '{"tool_order_id": 1, "fk_tool_order_list_id": 19, "machining_style_name": "BALL 2MM 2F:0:0",'
    ' "layer_name": "@@_MachiningStyleListTool", "seq_num": 1, "is_multidrill": false,'
    ' "list_name": "Narzędzia 19"}'
)

_DOORSTYLE_ROW = (
    '{"id": 1, "full_file_name": "C:\\\\Styles\\\\front.ary", "vba_project_name": "fronts"}'
)

_MULTIDRILL_ROW = (
    '{"id": 1, "name": "Głowica 1", "selected": true, "feed_rate": 1500.0,'
    ' "spindle_speed": 12000.0, "safe_rapid_distance": 5.0, "rapid_down_to": 2.0,'
    ' "material_top": 0.0, "bottom_of_hole": -19.0}'
)

_FITTING_ROW = '{"id": 1, "fk_job_file_id": 0, "fitting_type": "sys", "fitting_file": ""}'

_LAYER_MAPPING_ROW = (
    '{"layer_mapping_id": 1, "fk_setup_id": 1, "layer_name": "Okucia",'
    ' "machining_style_name": "BALL 2MM 2F:0:0", "machining_order": 1, "is_feature_layer": false,'
    ' "tool_side_closed_geo": 0, "tool_side_open_geo": 0, "tool_direction_closed_geo": 0,'
    ' "tool_direction_open_geo": 0, "start_point": 0, "layer_order": 1,'
    ' "apply_individually_to_each_geometry": false, "setup_name": "None"}'
)


def test_lookups_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = (
        f'{{"setups": [{_SETUP_ROW_1},{_SETUP_ROW_93}],'
        f' "customers": [{_CUSTOMER_ROW_1}],'
        f' "machining_orders": [{_MACHINING_ORDER_ROW}]}}'
    )
    _mock_run(monkeypatch, stdout=stdout)
    data = cdm_db.lookups()
    assert len(data["setups"]) == 2
    setup = data["setups"][0]
    assert setup["id"] == 1
    assert setup["name"] == "None"
    assert setup["fe_use_panel_alignment"] is True
    assert setup["fe_chord_tolerance"] == 0.01
    assert setup["fe_contour_extraction_mode"] == 1
    assert setup["imp_join_resulting_lines_or_arcs"] is True
    assert setup["setup_seq_num"] == 1
    assert data["setups"][1]["name"] == "Nowe Ustawienia 1"
    assert data["setups"][1]["fe_use_panel_alignment"] is False
    assert data["setups"][1]["fe_chord_tolerance"] == 0.05
    assert len(data["customers"]) == 1
    assert data["customers"][0]["id"] == 1
    assert data["customers"][0]["name"] == "Not Selected"
    assert data["customers"][0]["email_address"] == ""
    assert len(data["machining_orders"]) == 1
    order = data["machining_orders"][0]
    assert order["tool_order_id"] == 1
    assert order["fk_tool_order_list_id"] == 19
    assert order["machining_style_name"] == "BALL 2MM 2F:0:0"
    assert order["layer_name"] == "@@_MachiningStyleListTool"
    assert order["seq_num"] == 1
    assert order["is_multidrill"] is False
    assert order["list_name"] == "Narzędzia 19"
    for key in ("doorstyles", "multidrill", "fittings", "layers_mapping"):
        assert data[key] == []


def test_lookups_full(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = (
        f'{{"setups": [{_SETUP_ROW_1}], "customers": [{_CUSTOMER_ROW_1}],'
        f' "machining_orders": [{_MACHINING_ORDER_ROW}], "doorstyles": [{_DOORSTYLE_ROW}],'
        f' "multidrill": [{_MULTIDRILL_ROW}], "fittings": [{_FITTING_ROW}],'
        f' "layers_mapping": [{_LAYER_MAPPING_ROW}]}}'
    )
    _mock_run(monkeypatch, stdout=stdout)
    data = cdm_db.lookups()
    assert set(data) == set(cdm_db.LOOKUP_KEYS)
    assert len(data["setups"]) == 1
    assert len(data["customers"]) == 1
    assert len(data["machining_orders"]) == 1
    assert data["doorstyles"][0]["full_file_name"] == r"C:\Styles\front.ary"
    assert data["doorstyles"][0]["vba_project_name"] == "fronts"
    assert data["multidrill"][0]["id"] == 1
    assert data["multidrill"][0]["name"] == "Głowica 1"
    assert data["multidrill"][0]["selected"] is True
    assert data["multidrill"][0]["spindle_speed"] == 12000.0
    assert data["multidrill"][0]["bottom_of_hole"] == -19.0
    assert data["fittings"][0] == {
        "id": 1,
        "fk_job_file_id": 0,
        "fitting_type": "sys",
        "fitting_file": "",
    }
    layer = data["layers_mapping"][0]
    assert layer["layer_mapping_id"] == 1
    assert layer["fk_setup_id"] == 1
    assert layer["machining_order"] == 1
    assert layer["is_feature_layer"] is False
    assert layer["tool_side_closed_geo"] == 0
    assert layer["apply_individually_to_each_geometry"] is False
    assert layer["setup_name"] == "None"


def test_lookups_missing_section(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = f'{{"setups": [{_SETUP_ROW_1}], "customers": [{_CUSTOMER_ROW_1}]}}'
    _mock_run(monkeypatch, stdout=stdout)
    data = cdm_db.lookups()
    assert data["fittings"] == []
    assert data["machining_orders"] == []
    assert len(data["setups"]) == 1


def test_lookups_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = {key: [] for key in cdm_db.LOOKUP_KEYS}
    _mock_run(monkeypatch).side_effect = FileNotFoundError("powershell")
    assert cdm_db.lookups() == expected
    _mock_run(monkeypatch, stdout="", returncode=1)
    assert cdm_db.lookups() == expected
    _mock_run(monkeypatch, stdout="not json")
    assert cdm_db.lookups() == expected


def test_lookups_skips_malformed_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_run(monkeypatch, stdout=f'{{"setups": [{_SETUP_ROW_1}, "nope", 42]}}')
    data = cdm_db.lookups()
    assert len(data["setups"]) == 1
    assert data["setups"][0]["id"] == 1


def test_lookups_single_row_section_wrapped_as_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = (
        f'{{"customers": {_CUSTOMER_ROW_1},'
        f' "fittings": {_FITTING_ROW},'
        f' "machining_orders": [{_MACHINING_ORDER_ROW}]}}'
    )
    _mock_run(monkeypatch, stdout=stdout)
    data = cdm_db.lookups()
    assert data["customers"] == [
        {
            "id": 1,
            "name": "Not Selected",
            "address_line_1": "",
            "address_line_2": "",
            "city": "",
            "country": "",
            "post_zip_code": "",
            "contact_name": "",
            "telephone_number": "",
            "email_address": "",
            "website_address": "",
        }
    ]
    assert data["fittings"] == [
        {"id": 1, "fk_job_file_id": 0, "fitting_type": "sys", "fitting_file": ""}
    ]
    assert len(data["machining_orders"]) == 1
    assert data["machining_orders"][0]["machining_style_name"] == "BALL 2MM 2F:0:0"
