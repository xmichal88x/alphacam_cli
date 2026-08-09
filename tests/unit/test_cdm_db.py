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
