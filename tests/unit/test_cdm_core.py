from __future__ import annotations

import pathlib
from unittest.mock import MagicMock

import pytest

from alphacam_cli.core import cdm_db
from alphacam_cli.core.application import Application


def _am_with_details(am: MagicMock, *type_names: str) -> MagicMock:
    details = MagicMock()
    details.Count = len(type_names)
    details.Item.side_effect = [MagicMock(TypeName=n) for n in type_names]
    job = MagicMock()
    job.CDMOrderDetails = details
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job
    am.Jobs = jobs
    return am


def _app_with_am(am: MagicMock) -> Application:
    app = Application(MagicMock())
    app.get_automation_manager_addin = lambda: am  # type: ignore[method-assign]
    return app


# --- merge_door_types (pure) ---


def test_merge_door_types_vdb5_and_com() -> None:
    result = cdm_db.merge_door_types(
        ["M_01", "Typ Frontu 47"],
        ["Typ Frontu 1", "m_01"],
        True,
    )
    assert result == {
        "types": [
            {"id": 1, "name": "Typ Frontu 1"},
            {"id": 2, "name": "m_01"},
            {"id": 3, "name": "Typ Frontu 47"},
        ],
        "source": "vdb5+com",
    }


def test_merge_door_types_com_only_fallback() -> None:
    result = cdm_db.merge_door_types(["Typ Frontu 47"], [], False)
    assert result == {
        "types": [{"id": 1, "name": "Typ Frontu 47"}],
        "note": "vdb5 read failed; types from jobs only",
        "source": "com",
    }


def test_merge_door_types_empty_vdb5_ok() -> None:
    assert cdm_db.merge_door_types([], [], True) == {
        "types": [],
        "note": "no CDM door types found",
    }


def test_merge_door_types_empty_vdb5_fail() -> None:
    assert cdm_db.merge_door_types([], [], False) == {
        "types": [],
        "note": "no CDM door types found",
    }


# --- Application.cdm_types ---


def test_cdm_types_merge_vdb5_and_com(monkeypatch: pytest.MonkeyPatch) -> None:
    am = _am_with_details(MagicMock(), "Typ Frontu 47", "m_01")
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_door_type_names",
        lambda: (["Typ Frontu 1", "M_01"], True),
    )
    result = _app_with_am(am).cdm_types()
    assert result == {
        "types": [
            {"id": 1, "name": "Typ Frontu 1"},
            {"id": 2, "name": "M_01"},
            {"id": 3, "name": "Typ Frontu 47"},
        ],
        "source": "vdb5+com",
    }


def test_cdm_types_dedup_casefold(monkeypatch: pytest.MonkeyPatch) -> None:
    am = _am_with_details(MagicMock(), "M_01", "m_01")
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_door_type_names",
        lambda: (["m_01", "Typ Frontu 1"], True),
    )
    result = _app_with_am(am).cdm_types()
    assert result == {
        "types": [
            {"id": 1, "name": "m_01"},
            {"id": 2, "name": "Typ Frontu 1"},
        ],
        "source": "vdb5+com",
    }


def test_cdm_types_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    am.Jobs.Count = 0
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_door_type_names",
        lambda: ([], True),
    )
    result = _app_with_am(am).cdm_types()
    assert result == {"types": [], "note": "no CDM door types found"}


def test_cdm_types_vdb5_fail_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    am = _am_with_details(MagicMock(), "Typ Frontu 47")
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_door_type_names",
        lambda: ([], False),
    )
    result = _app_with_am(am).cdm_types()
    assert result == {
        "types": [{"id": 1, "name": "Typ Frontu 47"}],
        "note": "vdb5 read failed; types from jobs only",
        "source": "com",
    }


def test_cdm_types_vdb5_fail_no_com(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    am.Jobs.Count = 0
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_door_type_names",
        lambda: ([], False),
    )
    result = _app_with_am(am).cdm_types()
    assert result == {"types": [], "note": "no CDM door types found"}


def test_cdm_types_skips_broken_items(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()

    class _BadJob:
        @property
        def CDMOrderDetails(self) -> MagicMock:  # noqa: N802 - mimics COM
            raise RuntimeError("broken")  # noqa: TRY003

    good = MagicMock()
    good.TypeName = "OK_Type"
    details = MagicMock()
    details.Count = 1
    details.Item.return_value = good
    good_job = MagicMock()
    good_job.CDMOrderDetails = details
    jobs = MagicMock()
    jobs.Count = 2
    jobs.Item.side_effect = [_BadJob(), good_job]
    am.Jobs = jobs
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_door_type_names",
        lambda: ([], True),
    )
    result = _app_with_am(am).cdm_types()
    assert result == {
        "types": [{"id": 1, "name": "OK_Type"}],
        "source": "vdb5+com",
    }


def test_cdm_types_com_read_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()

    class _BoomJobs:
        @property
        def Count(self) -> int:  # noqa: N802 - mimics COM Jobs.Count
            raise RuntimeError("db locked")  # noqa: TRY003

    am.Jobs = _BoomJobs()
    with pytest.raises(RuntimeError, match="cdm: read door types failed: db locked"):
        _app_with_am(am).cdm_types()


# --- Application.import_cdm_csv ---


def test_import_cdm_csv_all_details_fail_deletes_job(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    job.JobName = "order"
    job.AddCDMOrderDetail.side_effect = RuntimeError("type does not exist")
    am.NewCDMJob.return_value = job
    cleanup = MagicMock(return_value=(True, ""))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.cleanup_created_job", cleanup)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\nP004,1,600,400,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file))
    assert result["success"] is False
    assert result["items"] == 0
    assert result["errors"].count("job order: no valid order details, deleted") == 1
    assert any("door type not found: P003" in e for e in result["errors"])
    assert any("door type not found: P004" in e for e in result["errors"])
    cleanup.assert_called_once_with(am, job, "order")


def test_import_cdm_csv_all_details_fail_delete_via_lookup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    job.JobName = "order"
    job.AddCDMOrderDetail.side_effect = RuntimeError("type does not exist")
    am.NewCDMJob.return_value = job
    cleanup = MagicMock(return_value=(True, ""))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.cleanup_created_job", cleanup)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file))
    assert result["success"] is False
    assert result["items"] == 0
    assert result["errors"].count("job order: no valid order details, deleted") == 1
    cleanup.assert_called_once_with(am, job, "order")


def test_import_cdm_csv_all_details_fail_cleanup_still_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    job.JobName = "order"
    job.AddCDMOrderDetail.side_effect = RuntimeError("type does not exist")
    am.NewCDMJob.return_value = job
    cleanup = MagicMock(return_value=(False, "failed"))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.cleanup_created_job", cleanup)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file))
    assert result["success"] is False
    assert result["items"] == 0
    assert result["errors"].count("job order: no valid order details, cleanup failed") == 1
    assert not any("no valid order details, deleted" in e for e in result["errors"])
    cleanup.assert_called_once_with(am, job, "order")


def test_import_cdm_csv_all_details_fail_cleanup_unverified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    job.JobName = "order"
    job.AddCDMOrderDetail.side_effect = RuntimeError("type does not exist")
    am.NewCDMJob.return_value = job
    cleanup = MagicMock(return_value=(False, "unverified"))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.cleanup_created_job", cleanup)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file))
    assert result["success"] is False
    assert result["items"] == 0
    assert result["errors"].count("job order: no valid order details, cleanup unverified") == 1
    cleanup.assert_called_once_with(am, job, "order")


def test_import_cdm_csv_all_details_fail_keeps_existing_job(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    job.JobName = "X"
    job.AddCDMOrderDetail.side_effect = RuntimeError("type does not exist")
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job
    am.Jobs = jobs
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\nP004,1,600,400,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file), job="X")
    assert result["success"] is False
    assert result["items"] == 0
    assert not any("no valid order details" in e for e in result["errors"])
    am.NewCDMJob.assert_not_called()
    job.DeleteFromDB.assert_not_called()


def test_import_cdm_csv_cleanup_failure_reports_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    job.JobName = "order"
    job.AddCDMOrderDetail.side_effect = RuntimeError("type does not exist")
    am.NewCDMJob.return_value = job
    cleanup = MagicMock(return_value=(False, "failed"))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.cleanup_created_job", cleanup)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file))
    assert result["success"] is False
    assert result["items"] == 0
    assert any("cleanup failed" in e for e in result["errors"])
    cleanup.assert_called_once_with(am, job, "order")


# --- Application.run_cdm ---


def test_run_cdm_job_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.find_cdm_job",
        MagicMock(return_value=MagicMock()),
    )
    app = _app_with_am(am)
    with pytest.raises(RuntimeError, match="cdm: job already exists: JOB-001"):
        app.run_cdm("JOB-001", "Typ Frontu 1")
    am.NewCDMJob.assert_not_called()


def test_run_cdm_add_detail_failure_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    am = MagicMock()
    job = MagicMock()
    job.AddCDMOrderDetail.side_effect = RuntimeError("FOREIGN KEY constraint failed")
    am.NewCDMJob.return_value = job
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": None, "material_id": None},
    )
    cleanup = MagicMock(return_value=(True, ""))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.cleanup_created_job", cleanup)
    app = _app_with_am(am)
    with pytest.raises(RuntimeError, match="cdm: door type not found: XYZ"):
        app.run_cdm("JOB-001", "XYZ")
    cleanup.assert_called_once_with(am, job, "JOB-001")


def test_run_cdm_save_detail_failure_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    am = MagicMock()
    job = MagicMock()
    detail = MagicMock()
    detail.SaveToDatabase.side_effect = RuntimeError("db locked")
    job.AddCDMOrderDetail.return_value = detail
    am.NewCDMJob.return_value = job
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": None, "material_id": None},
    )
    cleanup = MagicMock(return_value=(True, ""))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.cleanup_created_job", cleanup)
    app = _app_with_am(am)
    with pytest.raises(RuntimeError, match="cdm: save order detail failed: db locked"):
        app.run_cdm("JOB-001", "Typ Frontu 1")
    cleanup.assert_called_once_with(am, job, "JOB-001")


# --- m2: vdb5_job_defaults fetched at most once ---


def test_import_cdm_csv_defaults_fetched_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    defaults = MagicMock(return_value={"config_name": "Fronty", "material_id": 4})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.vdb5_job_defaults", defaults)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.sheet_materials",
        lambda: {"MDF18 - 2800 x 2070": 4},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file))
    assert result["success"] is True
    assert result["material"] == "MDF18 - 2800 x 2070"
    defaults.assert_called_once_with()
    am.ConfigurationSettings.GetByName.assert_called_once_with("Fronty")
