from __future__ import annotations

import os
import pathlib
from unittest.mock import ANY, MagicMock, PropertyMock

import pytest

from alphacam_cli.core import cdm_db, headless
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


def _setting_with(fields: list[tuple[int, int]]) -> dict[str, object]:
    return {
        "id": 3,
        "name": "sklep CSV",
        "selected": True,
        "create_job": True,
        "delimiter_char": ",",
        "sub_delimiter_char": ";",
        "ignore_header": False,
        "is_cdm_import": True,
        "fields": [{"column_number": col, "parameter_type": ptype} for col, ptype in fields],
    }


def _mock_cdm_db(
    monkeypatch: pytest.MonkeyPatch,
    setting: dict[str, object],
    materials: dict[str, int] | None = None,
    defaults: dict[str, object] | None = None,
) -> MagicMock:
    set_order_detail_material = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.import_settings", lambda: [setting])
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: materials or {})
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.set_order_detail_material", set_order_detail_material
    )
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: defaults or {"config_name": "Fronty", "material_id": None},
    )
    return set_order_detail_material


_SHOP_FIELDS = [
    (1, 256),
    (2, 259),
    (3, 257),
    (4, 258),
    (5, 264),
    (6, 524),
    (7, 512),
    (8, 513),
    (9, 261),
    (10, 266),
    (11, 267),
    (12, 275),
]

_LEGACY_FIELDS = [(1, 256), (2, 259), (3, 257), (4, 258), (5, 264)]


def _mock_selected_import_setting(
    monkeypatch: pytest.MonkeyPatch,
    *,
    create_job: bool = True,
    fields: list[tuple[int, int]] | None = None,
) -> dict[str, object]:
    setting = _setting_with(fields or _LEGACY_FIELDS)
    setting["create_job"] = create_job
    setting["selected"] = True
    monkeypatch.setattr("alphacam_cli.core.cdm_db.import_settings", lambda: [setting])
    return setting


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
    _mock_selected_import_setting(monkeypatch)
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
    _mock_selected_import_setting(monkeypatch)
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
    _mock_selected_import_setting(monkeypatch)
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
    _mock_selected_import_setting(monkeypatch)
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
    _mock_selected_import_setting(monkeypatch)
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
    _mock_selected_import_setting(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file))
    assert result["success"] is False
    assert result["items"] == 0
    assert any("cleanup failed" in e for e in result["errors"])
    cleanup.assert_called_once_with(am, job, "order")


def test_import_cdm_csv_mapped_setters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    set_order_detail_material = _mock_cdm_db(
        monkeypatch,
        _setting_with(_SHOP_FIELDS),
        materials={"MDF_18": 5},
    )
    set_job_material = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", set_job_material)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(
        "PS_03,1,500,400,1;2;3,MDF_18,Zamowienie X,Fronty,Jan Kowalski,CF1,CF2,CF3\n",
        encoding="utf-8",
    )
    result = _app_with_am(am).import_cdm_csv(str(csv_file), import_setting=3)
    assert result["success"] is True
    assert result["items"] == 1
    assert result["job_name"] == "Zamowienie X"
    assert result["material"] == "MDF_18"
    assert result["errors"] == []
    assert result["import_setting"] == "sklep CSV"
    assert job.JobName == "Zamowienie X"
    am.ConfigurationSettings.GetByName.assert_called_once_with("Fronty")
    assert detail.CSV_CustomerName == "Jan Kowalski"
    assert detail.CustomField1 == "CF1"
    assert detail.CustomField2 == "CF2"
    assert detail.CustomField3 == "CF3"
    assert detail.Width == 500.0
    assert detail.Length == 400.0
    assert detail.Quantity == 1
    assert detail.UserVariableString == ";".join(["1", "2", "3"] + ["0"] * 47)
    assert detail.ActiveInProcess is True
    set_order_detail_material.assert_called_once_with("Zamowienie X", 5)
    set_job_material.assert_not_called()
    detail.SaveToDatabase.assert_called_once_with()


def test_import_cdm_csv_mapped_not_cdm_setting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    setting = _setting_with(_SHOP_FIELDS)
    setting["is_cdm_import"] = False
    monkeypatch.setattr("alphacam_cli.core.cdm_db.import_settings", lambda: [setting])
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("PS_03,1,500,400,1;2;3\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="is not a CDM import setting"):
        _app_with_am(am).import_cdm_csv(str(csv_file), import_setting=3)
    am.NewCDMJob.assert_not_called()


def test_import_cdm_csv_mapped_empty_separator_uses_setting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    _mock_cdm_db(monkeypatch, _setting_with(_SHOP_FIELDS), materials={"MDF_18": 5})
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(
        "PS_03,1,500,400,1;2;3,MDF_18,Zamowienie X,Fronty,Jan Kowalski,CF1,CF2,CF3\n",
        encoding="utf-8",
    )
    result = _app_with_am(am).import_cdm_csv(str(csv_file), import_setting=3, separator="")
    assert result["success"] is True
    assert result["items"] == 1
    assert result["errors"] == []


def test_import_cdm_csv_mapped_material_from_column_6(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    set_order_detail_material = _mock_cdm_db(
        monkeypatch,
        _setting_with([(1, 256), (2, 259), (3, 257), (4, 258), (5, 264), (6, 524)]),
        materials={"MDF_18": 5},
    )
    set_job_material = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", set_job_material)
    csv_file = tmp_path / "parts.csv"
    csv_file.write_text("PS_03,1,500,400,1;2;3,MDF_18\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file), import_setting="sklep CSV")
    assert result["success"] is True
    assert result["items"] == 1
    assert result["job_name"] == "parts"
    assert result["material"] == "MDF_18"
    assert result["errors"] == []
    set_order_detail_material.assert_called_once_with("parts", 5)
    set_job_material.assert_not_called()
    am.NewCDMJob.assert_called_once_with()
    am.ConfigurationSettings.GetByName.assert_called_once_with("Fronty")


def test_import_cdm_csv_mapped_material_sets_only_order_detail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    _mock_cdm_db(monkeypatch, _setting_with(_SHOP_FIELDS), materials={"MDF_18": 5})
    set_job_material = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", set_job_material)
    set_order_detail_material = MagicMock(return_value=True)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.set_order_detail_material", set_order_detail_material
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(
        "PS_03,1,500,400,1;2;3,MDF_18,Zamowienie X,Fronty,Jan Kowalski,CF1,CF2,CF3\n",
        encoding="utf-8",
    )
    result = _app_with_am(am).import_cdm_csv(str(csv_file), import_setting=3)
    assert result["success"] is True
    assert result["errors"] == []
    set_order_detail_material.assert_called_once_with("Zamowienie X", 5)
    set_job_material.assert_not_called()


def test_import_cdm_csv_mapped_no_material_ok(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    _mock_cdm_db(monkeypatch, _setting_with(_LEGACY_FIELDS), materials={"MDF_18": 5})
    set_job_material = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", set_job_material)
    set_order_detail_material = MagicMock(return_value=True)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.set_order_detail_material", set_order_detail_material
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file), import_setting=3)
    assert result["success"] is True
    assert result["items"] == 1
    assert result["material"] is None
    assert result["errors"] == []
    set_order_detail_material.assert_not_called()
    set_job_material.assert_not_called()


def test_import_cdm_csv_mapped_active_setter_fails_fallback_db(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    _mock_cdm_db(monkeypatch, _setting_with(_LEGACY_FIELDS), materials={"MDF_18": 5})
    set_order_details_active = MagicMock(return_value=True)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.set_order_details_active", set_order_details_active
    )
    type(detail).ActiveInProcess = PropertyMock(side_effect=RuntimeError("no setter"))
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file), import_setting=3)
    assert result["success"] is True
    assert result["items"] == 1
    assert result["errors"] == []
    set_order_details_active.assert_called_once_with("order")
    detail.SaveToDatabase.assert_called_once_with()


def test_import_cdm_csv_mapped_sets_has_drilling(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    _mock_cdm_db(
        monkeypatch,
        _setting_with([(1, 256), (2, 259), (3, 257), (4, 258), (5, 264), (6, 298)]),
        materials={"MDF_18": 5},
        defaults={"config_name": "Fronty", "material_id": 5},
    )
    set_has_drilling = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_has_drilling", set_has_drilling)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("PS_03,1,500,400,1;2;3,1\nPS_04,1,600,400,1;2;3,0\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file), import_setting=3)
    assert result["success"] is True
    assert result["items"] == 2
    assert result["errors"] == []
    set_has_drilling.assert_called_once_with("order", [True, False])


def test_import_cdm_csv_mapped_no_drilling_column(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    _mock_cdm_db(
        monkeypatch,
        _setting_with([(1, 256), (2, 259), (3, 257), (4, 258), (5, 264)]),
        materials={"MDF_18": 5},
        defaults={"config_name": "Fronty", "material_id": 5},
    )
    set_has_drilling = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_has_drilling", set_has_drilling)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("PS_03,1,500,400,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file), import_setting=3)
    assert result["success"] is True
    assert result["items"] == 1
    assert result["errors"] == []
    set_has_drilling.assert_not_called()


def test_import_cdm_csv_mapped_setter_warning_keeps_detail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    _mock_cdm_db(
        monkeypatch,
        _setting_with([(1, 256), (2, 259), (3, 257), (4, 258), (5, 264), (6, 261), (7, 298)]),
        materials={"MDF_18": 5},
        defaults={"config_name": "Fronty", "material_id": 5},
    )
    set_has_drilling = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_has_drilling", set_has_drilling)
    type(detail).CSV_CustomerName = PropertyMock(side_effect=RuntimeError("boom"))
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(
        "PS_03,1,500,400,1;2;3,Jan Kowalski,1\nPS_04,1,600,400,1;2;3,Anna Nowak,0\n",
        encoding="utf-8",
    )
    result = _app_with_am(am).import_cdm_csv(str(csv_file), import_setting=3)
    assert result["success"] is True
    assert result["items"] == 2
    assert len([e for e in result["errors"] if "CSV_CustomerName failed" in e]) == 2
    assert detail.SaveToDatabase.call_count == 2
    set_has_drilling.assert_called_once_with("order", [True, False])


def test_import_cdm_csv_import_setting_not_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    monkeypatch.setattr("alphacam_cli.core.cdm_db.import_settings", lambda: [])
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("PS_03,1,500,400,1;2;3\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="cdm: import settings not found: 99"):
        _app_with_am(am).import_cdm_csv(str(csv_file), import_setting=99)
    am.NewCDMJob.assert_not_called()


def test_import_cdm_csv_fallback_no_import_setting_uses_selected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    detail = MagicMock()
    am.NewCDMJob.return_value = job
    job.AddCDMOrderDetail.return_value = detail
    _mock_selected_import_setting(monkeypatch)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file))
    assert result["success"] is True
    assert result["items"] == 1
    assert result["job_name"] == "order"
    assert result["import_setting"] == "sklep CSV"
    am.NewCDMJob.assert_called_once_with()
    am.ConfigurationSettings.GetByName.assert_called_once_with("Fronty")


def test_import_cdm_csv_no_selected_setting_lists_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    settings = [
        _setting_with([(1, 256), (2, 259), (3, 257), (4, 258), (5, 264)]),
        _setting_with([(1, 256), (2, 259)]),
    ]
    settings[0]["name"] = "sklep CSV"
    settings[1]["name"] = "Ustawienia Importu CSV 2"
    settings[1]["id"] = 4
    settings[0]["selected"] = False
    settings[1]["selected"] = False
    settings[1]["create_job"] = False
    monkeypatch.setattr("alphacam_cli.core.cdm_db.import_settings", lambda: settings)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    with pytest.raises(
        RuntimeError,
        match=(
            "cdm: no import setting selected; pass --import-setting or select one in "
            "Automation Manager \\(available: 3 'sklep CSV', 4 'Ustawienia Importu CSV 2'\\)"
        ),
    ):
        _app_with_am(am).import_cdm_csv(str(csv_file))
    am.NewCDMJob.assert_not_called()


def test_import_cdm_csv_create_job_false_requires_job(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    _mock_selected_import_setting(monkeypatch, create_job=False)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    with pytest.raises(
        RuntimeError,
        match="cdm: job is required \\(import setting 'sklep CSV' does not create jobs\\)",
    ):
        _app_with_am(am).import_cdm_csv(str(csv_file))
    am.NewCDMJob.assert_not_called()


def test_import_cdm_preview_no_com(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    am = MagicMock()
    _mock_cdm_db(monkeypatch, _setting_with(_SHOP_FIELDS), materials={"MDF_18": 5})
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(
        "PS_03,1,500,400,1;2;3,MDF_18,Zamowienie X,Fronty,Jan Kowalski,CF1,CF2,CF3\n",
        encoding="utf-8",
    )
    result = _app_with_am(am).import_cdm_preview(str(csv_file), import_setting=3)
    assert result["success"] is True
    assert result["items"] == 1
    assert result["job_name"] == "Zamowienie X"
    assert result["config"] == "Fronty"
    assert result["material"] == "MDF_18"
    assert result["errors"] == []
    assert result["job"] is None
    assert result["setting"] == {
        "id": 3,
        "name": "sklep CSV",
        "delimiter_char": ",",
        "sub_delimiter_char": ";",
        "create_job": True,
        "selected": True,
    }
    descriptions = result["field_map"]
    assert descriptions[0] == {"column": 1, "field": "door_type", "required": True}
    assert len(result["rows"]) == 1
    assert result["rows"][0]["style"] == "PS_03"
    assert result["rows"][0]["quantity"] == 1
    assert result["rows"][0]["customer_name"] == "Jan Kowalski"
    assert result["rows"][0]["custom_fields"] == {"1": "CF1", "2": "CF2", "3": "CF3"}
    am.assert_not_called()


def test_import_cdm_preview_no_setting_uses_selected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    _mock_selected_import_setting(monkeypatch)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": None, "material_id": None},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_preview(str(csv_file))
    assert result["success"] is False
    assert result["setting"] == {
        "id": 3,
        "name": "sklep CSV",
        "delimiter_char": ",",
        "sub_delimiter_char": ";",
        "create_job": True,
        "selected": True,
    }
    assert result["field_map"] != []
    assert result["job"] is None
    assert result["job_name"] == "order"
    assert result["config"] is None
    assert result["material"] is None
    assert result["items"] == 1
    assert result["rows"][0]["style"] == "P003"
    assert result["errors"] == [
        "job order: no material set (required for processing)",
        "cdm: no default configuration found",
    ]
    am.assert_not_called()


def test_import_cdm_preview_with_job_uses_job_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    _mock_selected_import_setting(monkeypatch)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": None, "material_id": None},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_preview(str(csv_file), job="EXISTING")
    assert result["success"] is True
    assert result["job_name"] == "EXISTING"
    assert result["job"] == "EXISTING"
    assert result["errors"] == ["job EXISTING: no material set (required for processing)"]
    am.assert_not_called()


def test_import_cdm_preview_with_job_ignores_mapped_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    _mock_cdm_db(
        monkeypatch,
        _setting_with(_SHOP_FIELDS),
        materials={"MDF_18": 5},
        defaults={"config_name": "Fronty", "material_id": 5},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(
        "PS_03,1,500,400,1;2;3,MDF_18,Zamowienie X,Fronty,Jan Kowalski,CF1,CF2,CF3\n",
        encoding="utf-8",
    )
    result = _app_with_am(am).import_cdm_preview(str(csv_file), job="EXISTING", import_setting=3)
    assert result["success"] is True
    assert result["job_name"] == "EXISTING"
    assert result["config"] is None
    assert result["material"] == "MDF_18"
    assert result["errors"] == []
    am.assert_not_called()


def test_import_cdm_preview_create_job_false_requires_job(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    _mock_selected_import_setting(monkeypatch, create_job=False)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    with pytest.raises(
        RuntimeError,
        match="cdm: job is required \\(import setting 'sklep CSV' does not create jobs\\)",
    ):
        _app_with_am(am).import_cdm_preview(str(csv_file))
    am.assert_not_called()


def test_import_cdm_preview_missing_file() -> None:
    app = Application(MagicMock())
    with pytest.raises(RuntimeError, match="cdm: csv file not found: "):
        app.import_cdm_preview("C:/temp/nope.csv", import_setting=3)


def test_import_cdm_csv_create_job_false_with_job_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    job = MagicMock()
    detail = MagicMock()
    job.JobName = "X"
    job.AddCDMOrderDetail.return_value = detail
    jobs = MagicMock()
    jobs.Count = 1
    jobs.Item.return_value = job
    am.Jobs = jobs
    _mock_selected_import_setting(monkeypatch, create_job=False)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file), job="X")
    assert result["success"] is True
    assert result["items"] == 1
    assert result["job_name"] == "X"
    am.NewCDMJob.assert_not_called()
    job.SaveToDatabase.assert_not_called()
    job.AddCDMOrderDetail.assert_called_once_with("P003")


def test_import_cdm_preview_create_job_false_with_job_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    _mock_selected_import_setting(monkeypatch, create_job=False)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": None, "material_id": None},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_preview(str(csv_file), job="EXISTING")
    assert result["success"] is True
    assert result["items"] == 1
    assert result["job_name"] == "EXISTING"
    assert result["job"] == "EXISTING"
    assert result["errors"] == ["job EXISTING: no material set (required for processing)"]
    am.assert_not_called()


def test_import_cdm_csv_empty_job_string_requires_job(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    _mock_selected_import_setting(monkeypatch, create_job=False)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    with pytest.raises(
        RuntimeError,
        match="cdm: job is required \\(import setting 'sklep CSV' does not create jobs\\)",
    ):
        _app_with_am(am).import_cdm_csv(str(csv_file), job="")
    am.NewCDMJob.assert_not_called()


def test_import_cdm_preview_empty_job_string_requires_job(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    _mock_selected_import_setting(monkeypatch, create_job=False)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    with pytest.raises(
        RuntimeError,
        match="cdm: job is required \\(import setting 'sklep CSV' does not create jobs\\)",
    ):
        _app_with_am(am).import_cdm_preview(str(csv_file), job="")
    am.assert_not_called()


def test_import_cdm_csv_whitespace_job_with_name_no_mutual_exclusion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    _mock_selected_import_setting(monkeypatch, create_job=True)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file), job="   ", name="X", preview=True)
    assert result["success"] is True
    assert result["job_name"] == "X"
    assert result["job"] is None
    am.assert_not_called()


def test_import_cdm_preview_whitespace_job_with_name_no_mutual_exclusion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    _mock_selected_import_setting(monkeypatch, create_job=True)
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_preview(str(csv_file), job="  ", name="X")
    assert result["success"] is True
    assert result["job_name"] == "X"
    assert result["job"] is None
    am.assert_not_called()


def test_import_cdm_preview_material_not_found_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    _mock_cdm_db(monkeypatch, _setting_with(_SHOP_FIELDS), materials={})
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(
        "PS_03,1,500,400,1;2;3,MDF_18,Zamowienie X,Fronty,Jan Kowalski,CF1,CF2,CF3\n",
        encoding="utf-8",
    )
    result = _app_with_am(am).import_cdm_preview(str(csv_file), import_setting=3)
    assert result["success"] is False
    assert result["errors"] == ["cdm: material not found: MDF_18"]
    assert result["material"] == "MDF_18"
    am.assert_not_called()


def test_import_cdm_preview_no_default_config_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    _mock_cdm_db(
        monkeypatch,
        _setting_with(_LEGACY_FIELDS),
        materials={"MDF_18": 5},
        defaults={"config_name": None, "material_id": 5},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_preview(str(csv_file), import_setting=3)
    assert result["success"] is False
    assert result["errors"] == ["cdm: no default configuration found"]
    assert result["material"] == "MDF_18"
    assert result["config"] is None
    am.assert_not_called()


def test_import_cdm_preview_material_from_defaults_ok(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    _mock_cdm_db(
        monkeypatch,
        _setting_with(_LEGACY_FIELDS),
        materials={"MDF_18": 5},
        defaults={"config_name": "Fronty", "material_id": 5},
    )
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_preview(str(csv_file), import_setting=3)
    assert result["success"] is True
    assert result["errors"] == []
    assert result["material"] == "MDF_18"
    assert result["config"] == "Fronty"
    am.assert_not_called()


def test_import_cdm_csv_fallback_skips_selected_non_cdm_setting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    non_cdm = _setting_with(_LEGACY_FIELDS)
    non_cdm["name"] = "Zwykly import"
    non_cdm["is_cdm_import"] = False
    cdm = _setting_with(_LEGACY_FIELDS)
    cdm["id"] = 4
    cdm["name"] = "sklep CDM"
    cdm["selected"] = False
    monkeypatch.setattr("alphacam_cli.core.cdm_db.import_settings", lambda: [non_cdm, cdm])
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    with pytest.raises(
        RuntimeError,
        match=(
            "cdm: no import setting selected; pass --import-setting or select one in "
            "Automation Manager \\(available: 4 'sklep CDM'\\)"
        ),
    ):
        _app_with_am(am).import_cdm_csv(str(csv_file))
    am.NewCDMJob.assert_not_called()


def test_import_cdm_csv_numeric_name_setting_not_reachable_by_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    setting = _setting_with(_LEGACY_FIELDS)
    setting["name"] = "123"
    setting["selected"] = False
    monkeypatch.setattr("alphacam_cli.core.cdm_db.import_settings", lambda: [setting])
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;2;3\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="cdm: import settings not found: 123"):
        _app_with_am(am).import_cdm_csv(str(csv_file), import_setting="123")
    am.NewCDMJob.assert_not_called()


def test_cdm_import_settings_list(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = [
        _setting_with(_SHOP_FIELDS),
        _setting_with([(1, 256), (2, 259)]),
    ]
    monkeypatch.setattr("alphacam_cli.core.cdm_db.import_settings", lambda: settings)
    result = Application(MagicMock()).cdm_import_settings()
    assert len(result["settings"]) == 2
    first = result["settings"][0]
    assert first["id"] == 3
    assert first["name"] == "sklep CSV"
    assert first["selected"] is True
    assert first["create_job"] is True
    assert first["delimiter_char"] == ","
    assert first["fields_count"] == 12
    assert first["fields"].startswith("1→door_type")
    assert "6→job_material_id" in first["fields"]
    assert "12→door_custom_field_3" in first["fields"]
    assert result["settings"][1]["fields_count"] == 2


def test_cdm_order_details_application(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"job_name": "X", "door_type": "P1"}]
    monkeypatch.setattr("alphacam_cli.core.cdm_db.order_details", lambda job_name: rows)
    result = Application(MagicMock()).cdm_order_details(job_name="X")
    assert result["order_details"] == rows
    assert result["job_name"] == "X"


def test_cdm_order_details_application_no_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("alphacam_cli.core.cdm_db.order_details", lambda job_name: [])
    result = Application(MagicMock()).cdm_order_details()
    assert result["order_details"] == []
    assert result["job_name"] is None


def test_cdm_door_paths_application(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"type_name": "T1", "path": "dir"}]
    monkeypatch.setattr("alphacam_cli.core.cdm_db.door_paths", lambda type_name: rows)
    result = Application(MagicMock()).cdm_door_paths(type_name="T1")
    assert result["door_paths"] == rows
    assert result["type_name"] == "T1"


def test_cdm_materials_application(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"id": 1, "name": "MDF_18"}]
    monkeypatch.setattr("alphacam_cli.core.cdm_db.materials", lambda: rows)
    result = Application(MagicMock()).cdm_materials()
    assert result["materials"] == rows


def test_cdm_configs_application(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"config_name": "Fronty"}]
    monkeypatch.setattr("alphacam_cli.core.cdm_db.configs", lambda show: rows)
    result = Application(MagicMock()).cdm_configs(show="all")
    assert result["configs"] == rows
    assert result["show"] == "all"


def test_cdm_lookups_application(monkeypatch: pytest.MonkeyPatch) -> None:
    lookups = {"edge_types": [{"id": 1, "label": "Prosty"}]}
    monkeypatch.setattr("alphacam_cli.core.cdm_db.lookups", lambda: lookups)
    result = Application(MagicMock()).cdm_lookups()
    assert result["lookups"] == lookups


def test_import_cdm_csv_preview_flag_delegates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    am = MagicMock()
    _mock_cdm_db(monkeypatch, _setting_with(_SHOP_FIELDS), materials={"MDF_18": 5})
    csv_file = tmp_path / "order.csv"
    csv_file.write_text(
        "PS_03,1,500,400,1;2;3,MDF_18,Zamowienie X,Fronty,Jan Kowalski,CF1,CF2,CF3\n",
        encoding="utf-8",
    )
    result = _app_with_am(am).import_cdm_csv(str(csv_file), import_setting=3, preview=True)
    assert result["success"] is True
    assert result["items"] == 1
    assert "field_map" in result
    assert result["setting"]["name"] == "sklep CSV"
    am.assert_not_called()


# --- Application.create_cdm_job ---


class _JobNoMeta:
    """COM job mock without guessed metadata setters (hasattr -> False)."""

    def SaveToDatabase(self) -> None:  # noqa: N802
        pass

    def __getattr__(self, name: str) -> object:
        raise AttributeError(name)


def test_create_cdm_job_empty_job(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    job = MagicMock()
    am.NewCDMJob.return_value = job
    config_obj = MagicMock()
    am.ConfigurationSettings.GetByName.return_value = config_obj
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.sheet_materials",
        lambda: {"MDF18 - 2800 x 2070": 4},
    )
    set_job_material = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", set_job_material)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.finalize_cdm_job", lambda jn: True)
    app = _app_with_am(am)
    result = app.create_cdm_job("JOB-001")
    assert result == {
        "success": True,
        "job_name": "JOB-001",
        "config": "Fronty",
        "material": "MDF18 - 2800 x 2070",
        "warnings": [],
    }
    assert job.JobName == "JOB-001"
    assert job.ConfigurationSetting == config_obj
    am.ConfigurationSettings.GetByName.assert_called_once_with("Fronty")
    job.SaveToDatabase.assert_called_once_with()
    set_job_material.assert_called_once_with("JOB-001", 4)
    job.AddCDMOrderDetail.assert_not_called()


def test_create_cdm_job_job_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.find_cdm_job",
        MagicMock(return_value=MagicMock()),
    )
    app = _app_with_am(am)
    with pytest.raises(RuntimeError, match="cdm: job already exists: JOB-001"):
        app.create_cdm_job("JOB-001")
    am.NewCDMJob.assert_not_called()


def test_create_cdm_job_explicit_config_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    am = MagicMock()
    job = MagicMock()
    am.NewCDMJob.return_value = job
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 2})
    set_job_material = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", set_job_material)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.finalize_cdm_job", lambda jn: True)
    defaults = MagicMock()
    monkeypatch.setattr("alphacam_cli.core.cdm_db.vdb5_job_defaults", defaults)
    app = _app_with_am(am)
    result = app.create_cdm_job("JOB-001", config="Fronty", material="MDF_18")
    assert result["config"] == "Fronty"
    assert result["material"] == "MDF_18"
    assert result["warnings"] == []
    am.ConfigurationSettings.GetByName.assert_called_once_with("Fronty")
    set_job_material.assert_called_once_with("JOB-001", 2)
    defaults.assert_not_called()


def test_create_cdm_job_config_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    job = MagicMock()
    am.NewCDMJob.return_value = job
    am.ConfigurationSettings.GetByName.side_effect = RuntimeError("boom")
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 4})
    app = _app_with_am(am)
    with pytest.raises(RuntimeError, match="cdm: config not found: Fronty"):
        app.create_cdm_job("JOB-001", config="Fronty")
    job.SaveToDatabase.assert_not_called()


def test_create_cdm_job_material_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 2})
    app = _app_with_am(am)
    with pytest.raises(RuntimeError, match="cdm: material not found: X"):
        app.create_cdm_job("JOB-001", material="X")
    am.NewCDMJob.assert_not_called()


def test_create_cdm_job_no_default_config(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": None, "material_id": 4},
    )
    app = _app_with_am(am)
    with pytest.raises(RuntimeError, match="cdm: no default configuration found"):
        app.create_cdm_job("JOB-001")
    am.NewCDMJob.assert_not_called()


def test_create_cdm_job_no_default_material(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": None},
    )
    app = _app_with_am(am)
    with pytest.raises(RuntimeError, match="cdm: no default material found"):
        app.create_cdm_job("JOB-001")
    am.NewCDMJob.assert_not_called()


def test_create_cdm_job_material_set_failed_removes_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    am = MagicMock()
    job = MagicMock()
    am.NewCDMJob.return_value = job
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 4})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", lambda jn, mid: False)
    cleanup = MagicMock(return_value=(True, ""))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.cleanup_created_job", cleanup)
    app = _app_with_am(am)
    with pytest.raises(RuntimeError, match="cdm: failed to set material for job JOB-001"):
        app.create_cdm_job("JOB-001")
    cleanup.assert_called_once_with(am, job, "JOB-001", log=ANY)
    job.SaveToDatabase.assert_called_once_with()


def test_create_cdm_job_material_set_failed_cleanup_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    am = MagicMock()
    job = MagicMock()
    am.NewCDMJob.return_value = job
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 4})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", lambda jn, mid: False)
    cleanup = MagicMock(return_value=(False, "failed"))
    monkeypatch.setattr("alphacam_cli.core.cdm_db.cleanup_created_job", cleanup)
    app = _app_with_am(am)
    with pytest.raises(RuntimeError, match="cleanup failed"):
        app.create_cdm_job("JOB-001")
    cleanup.assert_called_once_with(am, job, "JOB-001", log=ANY)


def test_create_cdm_job_metadata_com_setter(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    job = MagicMock()
    am.NewCDMJob.return_value = job
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 4})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", lambda jn, mid: True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.finalize_cdm_job", lambda jn: True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.customers", lambda: {"Klient A": 7})
    set_job_customer = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_customer", set_job_customer)
    set_job_po = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_po", set_job_po)
    set_job_due_date = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_due_date", set_job_due_date)
    set_job_description = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_description", set_job_description)
    save_snapshot: list[str] = []
    original_save = job.SaveToDatabase

    def _snapshot_save() -> None:
        save_snapshot.append(
            f"{job.Customer}|{job.PurchaseOrderNumber}|{job.DueDate}|{job.JobDescription}"
        )
        original_save()

    job.SaveToDatabase = _snapshot_save
    import alphacam_cli.core.application as app_module

    calls: list[tuple[str, ...]] = []
    original_setter = app_module._try_com_job_setter

    def _counting_setter(job: object, candidates: tuple[str, ...], value: object) -> bool:
        calls.append(candidates)
        return original_setter(job, candidates, value)

    monkeypatch.setattr(app_module, "_try_com_job_setter", _counting_setter)
    app = _app_with_am(am)
    result = app.create_cdm_job(
        "JOB-001",
        customer="Klient A",
        po="PO-1",
        due_date="2026-08-10",
        description="opis",
    )
    assert result["warnings"] == []
    assert job.Customer == "Klient A"
    assert job.PurchaseOrderNumber == "PO-1"
    assert job.DueDate == "2026-08-10"
    assert job.JobDescription == "opis"
    assert save_snapshot == ["Klient A|PO-1|2026-08-10|opis"]
    assert calls.count(("Customer", "CustomerName")) == 1
    assert calls.count(("PurchaseOrderNumber", "PO")) == 1
    assert calls.count(("DueDate",)) == 1
    assert calls.count(("JobDescription", "Description")) == 1
    set_job_customer.assert_not_called()
    set_job_po.assert_not_called()
    set_job_due_date.assert_not_called()
    set_job_description.assert_not_called()


def test_create_cdm_job_metadata_db_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    job = _JobNoMeta()
    am.NewCDMJob.return_value = job
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 4})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", lambda jn, mid: True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.finalize_cdm_job", lambda jn: True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.customers", lambda: {"Klient A": 7})
    set_job_customer = MagicMock(return_value=True)
    set_job_po = MagicMock(return_value=True)
    set_job_due_date = MagicMock(return_value=True)
    set_job_description = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_customer", set_job_customer)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_po", set_job_po)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_due_date", set_job_due_date)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_description", set_job_description)
    app = _app_with_am(am)
    result = app.create_cdm_job(
        "JOB-001",
        customer="Klient A",
        po="PO-1",
        due_date="2026-08-10",
        description="opis",
    )
    assert result["warnings"] == []
    set_job_customer.assert_called_once_with("JOB-001", 7)
    set_job_po.assert_called_once_with("JOB-001", "PO-1")
    set_job_due_date.assert_called_once_with("JOB-001", "2026-08-10")
    set_job_description.assert_called_once_with("JOB-001", "opis")


def test_create_cdm_job_metadata_db_fallback_failed_warns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    am = MagicMock()
    job = _JobNoMeta()
    am.NewCDMJob.return_value = job
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 4})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", lambda jn, mid: True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.finalize_cdm_job", lambda jn: True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.customers", lambda: {"Klient A": 7})
    set_job_customer = MagicMock(return_value=False)
    set_job_po = MagicMock(return_value=True)
    set_job_due_date = MagicMock(return_value=True)
    set_job_description = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_customer", set_job_customer)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_po", set_job_po)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_due_date", set_job_due_date)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_description", set_job_description)
    app = _app_with_am(am)
    result = app.create_cdm_job(
        "JOB-001",
        customer="Klient A",
        po="PO-1",
        due_date="2026-08-10",
        description="opis",
    )
    assert result["success"] is True
    assert "failed to set customer" in result["warnings"]
    assert "failed to set purchase order number" not in result["warnings"]
    assert "failed to set due date" not in result["warnings"]
    assert "failed to set job description" not in result["warnings"]
    set_job_customer.assert_called_once_with("JOB-001", 7)
    set_job_po.assert_called_once_with("JOB-001", "PO-1")
    set_job_due_date.assert_called_once_with("JOB-001", "2026-08-10")
    set_job_description.assert_called_once_with("JOB-001", "opis")


def test_create_cdm_job_customer_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    job = MagicMock()
    am.NewCDMJob.return_value = job
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 4})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", lambda jn, mid: True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.finalize_cdm_job", lambda jn: True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.customers", lambda: {"Inny": 1})
    app = _app_with_am(am)
    result = app.create_cdm_job("JOB-001", customer="Klient A")
    assert result["success"] is True
    assert "cdm: customer not found: Klient A" in result["warnings"]


def test_create_cdm_job_customer_db_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    job = MagicMock()
    am.NewCDMJob.return_value = job
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 4})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", lambda jn, mid: True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.finalize_cdm_job", lambda jn: True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.customers", lambda: {})
    app = _app_with_am(am)
    result = app.create_cdm_job("JOB-001", customer="Klient A")
    assert result["success"] is True
    assert "cdm: customer database unavailable; customer not set" in result["warnings"]


def test_create_cdm_job_invalid_due_date(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    app = _app_with_am(am)
    with pytest.raises(RuntimeError, match="cdm: invalid due date"):
        app.create_cdm_job("JOB-001", due_date="2026-13-40")
    am.NewCDMJob.assert_not_called()


def test_create_cdm_job_create_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    am = MagicMock()
    am.NewCDMJob.side_effect = RuntimeError("boom")
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 4})
    with pytest.raises(RuntimeError, match="cdm: create job failed: boom"):
        _app_with_am(am).create_cdm_job("JOB-001")


def test_create_cdm_job_customer_com_setter_stripped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    am = MagicMock()
    job = MagicMock()
    am.NewCDMJob.return_value = job
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 4})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", lambda jn, mid: True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.finalize_cdm_job", lambda jn: True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.customers", lambda: {"Klient A": 7})
    set_job_customer = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_customer", set_job_customer)
    result = _app_with_am(am).create_cdm_job("JOB-001", customer="  Klient A  ")
    assert result["warnings"] == []
    assert job.Customer == "Klient A"
    set_job_customer.assert_not_called()


class _JobHasattrBoom:
    """Job mock whose attribute probe raises (mimics COM com_error on hasattr)."""

    def SaveToDatabase(self) -> None:  # noqa: N802
        pass

    def __getattr__(self, name: str) -> object:
        raise RuntimeError("com boom")  # noqa: TRY003


def test_create_cdm_job_com_hasattr_error_uses_db_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    am = MagicMock()
    job = _JobHasattrBoom()
    am.NewCDMJob.return_value = job
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {"MDF_18": 4})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", lambda jn, mid: True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.finalize_cdm_job", lambda jn: True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.customers", lambda: {"Klient A": 7})
    set_job_customer = MagicMock(return_value=True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_customer", set_job_customer)
    result = _app_with_am(am).create_cdm_job("JOB-001", customer="Klient A")
    assert result["warnings"] == []
    set_job_customer.assert_called_once_with("JOB-001", 7)


def test_create_cdm_job_material_label_defaults_id_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    am = MagicMock()
    job = MagicMock()
    am.NewCDMJob.return_value = job
    monkeypatch.setattr("alphacam_cli.core.cdm_db.find_cdm_job", MagicMock(return_value=None))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.vdb5_job_defaults",
        lambda: {"config_name": "Fronty", "material_id": 4},
    )
    monkeypatch.setattr("alphacam_cli.core.cdm_db.sheet_materials", lambda: {})
    monkeypatch.setattr("alphacam_cli.core.cdm_db.set_job_material", lambda jn, mid: True)
    monkeypatch.setattr("alphacam_cli.core.cdm_db.finalize_cdm_job", lambda jn: True)
    result = _app_with_am(am).create_cdm_job("JOB-001")
    assert result["material"] == "id:4"


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
    _mock_selected_import_setting(monkeypatch)
    csv_file = tmp_path / "order.csv"
    csv_file.write_text("P003,1,500,500,1;18;0;0\n", encoding="utf-8")
    result = _app_with_am(am).import_cdm_csv(str(csv_file))
    assert result["success"] is True
    assert result["material"] is None
    defaults.assert_called_once_with()
    am.ConfigurationSettings.GetByName.assert_called_once_with("Fronty")


# --- Application.process_cdm_job (headless) ---


def _mock_headless_process(
    monkeypatch: pytest.MonkeyPatch,
    *,
    output_root: str | None = "C:/out",
    count: int | None = 1,
    run_result: object = None,
    run_side_effect: Exception | None = None,
    read_result: dict[str, object] | None = None,
) -> MagicMock:
    monkeypatch.setattr("alphacam_cli.core.cdm_db.job_count", MagicMock(return_value=count))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.job_output_root", MagicMock(return_value=output_root)
    )
    run = MagicMock(return_value=run_result, side_effect=run_side_effect)
    monkeypatch.setattr("alphacam_cli.core.application.headless.run_headless", run)
    monkeypatch.setattr(
        "alphacam_cli.core.application.headless.read_job_result",
        MagicMock(return_value=read_result),
    )
    return run


def test_process_cdm_job_headless_success(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = MagicMock(returncode=0)
    run = _mock_headless_process(
        monkeypatch,
        run_result=proc,
        read_result={
            "success": True,
            "status": "Sukces",
            "log": "Status przetwarzania zadania: Sukces",
            "file_mtime": 1234.0,
        },
    )
    result = Application(MagicMock()).process_cdm_job("JOB-001", method="vbs")
    assert result == {
        "success": True,
        "job_name": "JOB-001",
        "status": "Sukces",
        "processed": True,
        "method": "vbs",
        "psexec_rc": 0,
        "vbs_log": None,
        "log": "Status przetwarzania zadania: Sukces",
    }
    run.assert_called_once()
    args, kwargs = run.call_args
    assert args[0] == headless.DEFAULT_MACHINE
    assert args[1].endswith(os.path.join("vbs_hp_cli.vbs"))
    assert kwargs == {"timeout_seconds": 300}


def test_process_cdm_job_headless_custom_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = MagicMock(returncode=0)
    run = _mock_headless_process(
        monkeypatch,
        run_result=proc,
        read_result={"success": True, "status": "Sukces", "log": ""},
    )
    machine = {"psexec": "C:/tools/PsExec.exe", "psexec_args": [], "cscript": "cscript"}
    Application(MagicMock()).process_cdm_job(
        "JOB-001",
        machine=machine,
        timeout_seconds=600,
        output_root="C:/custom",
        method="vbs",
    )
    args, kwargs = run.call_args
    assert args[0] == machine
    assert kwargs == {"timeout_seconds": 600}


def test_process_cdm_job_no_output_root(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_headless_process(monkeypatch, output_root=None)
    with pytest.raises(RuntimeError, match="cdm: output root not found: JOB-001"):
        Application(MagicMock()).process_cdm_job("JOB-001", method="vbs")


def test_process_cdm_job_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = MagicMock(returncode=1)
    _mock_headless_process(
        monkeypatch,
        run_result=proc,
        read_result={"success": False, "status": "Błąd", "log": "Status: Błąd"},
    )
    result = Application(MagicMock()).process_cdm_job("JOB-001", method="vbs")
    assert result["success"] is False
    assert result["processed"] is False
    assert result["status"] == "Błąd"
    assert result["psexec_rc"] == 1


def test_process_cdm_job_missing_result(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_headless_process(
        monkeypatch,
        run_result=MagicMock(returncode=0),
        read_result={"success": False, "status": "missing"},
    )
    result = Application(MagicMock()).process_cdm_job("JOB-001", method="vbs")
    assert result["success"] is False
    assert result["status"] == "missing"
    assert result["log"] is None


def test_process_cdm_job_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_headless_process(monkeypatch, count=0)
    with pytest.raises(RuntimeError, match="cdm: job not found: JOB-001"):
        Application(MagicMock()).process_cdm_job("JOB-001", method="vbs")


def test_process_cdm_job_existence_check_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_headless_process(monkeypatch, count=None)
    with pytest.raises(RuntimeError, match="cdm: job existence check failed: JOB-001"):
        Application(MagicMock()).process_cdm_job("JOB-001", method="vbs")


def test_process_cdm_job_empty_name() -> None:
    app = Application(MagicMock())
    with pytest.raises(RuntimeError, match="cdm: job_name is required"):
        app.process_cdm_job("   ", method="vbs")


def test_process_cdm_job_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    _mock_headless_process(
        monkeypatch,
        run_side_effect=subprocess.TimeoutExpired(cmd=[], timeout=300),
    )
    with pytest.raises(RuntimeError, match="cdm: process job timed out after 300s"):
        Application(MagicMock()).process_cdm_job("JOB-001", method="vbs")


def test_process_cdm_job_subprocess_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_headless_process(
        monkeypatch,
        run_side_effect=FileNotFoundError("C:/temp/PsExec64.exe"),
    )
    with pytest.raises(RuntimeError, match="cdm: process job failed"):
        Application(MagicMock()).process_cdm_job("JOB-001", method="vbs")


def test_process_cdm_job_unknown_method(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(RuntimeError, match=r"cdm: unknown method: xyz \(expected inproc\|vbs\)"):
        Application(MagicMock()).process_cdm_job("JOB-001", method="xyz")


# --- Application.process_cdm_job_inproc ---


def _mock_inproc_process(
    monkeypatch: pytest.MonkeyPatch,
    *,
    output_root: str | None = "C:/out",
    count: int | None = 1,
    read_result: dict[str, object] | None = None,
) -> MagicMock:
    monkeypatch.setattr("alphacam_cli.core.cdm_db.job_count", MagicMock(return_value=count))
    monkeypatch.setattr(
        "alphacam_cli.core.cdm_db.job_output_root", MagicMock(return_value=output_root)
    )
    run = MagicMock()
    monkeypatch.setattr(
        "alphacam_cli.core.application.headless.read_job_result",
        MagicMock(return_value=read_result),
    )
    return run


def test_process_cdm_job_inproc_success(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _mock_inproc_process(
        monkeypatch,
        read_result={
            "success": True,
            "status": "Sukces",
            "log": "Status przetwarzania zadania: Sukces",
            "file_mtime": 1234.0,
        },
    )
    result = Application(run).process_cdm_job("JOB-001")
    assert result["success"] is True
    assert result["job_name"] == "JOB-001"
    assert result["status"] == "Sukces"
    assert result["processed"] is True
    assert result["method"] == "inproc"
    assert isinstance(result["elapsed_s"], float)
    assert result["elapsed_s"] >= 0
    assert result["log"] == "Status przetwarzania zadania: Sukces"
    run.Run.assert_called_once_with("ApplyMachiningAfterNesting.Events.HeadlessProcess", "JOB-001")


def test_process_cdm_job_inproc_default_is_inproc(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _mock_inproc_process(monkeypatch, read_result={"success": False, "status": "missing"})
    result = Application(run).process_cdm_job("JOB-001")
    assert result["method"] == "inproc"
    run.Run.assert_called_once()


def test_process_cdm_job_inproc_com_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    import pythoncom

    run = _mock_inproc_process(monkeypatch)
    run.Run.side_effect = pythoncom.com_error(
        -2147417842, "Aplikacja wywołała interfejs, który został skierowany na inny wątek"
    )
    with pytest.raises(RuntimeError, match=r"cdm: process job failed: .*inny wątek"):
        Application(run).process_cdm_job("JOB-001")
    run.Run.assert_called_once_with("ApplyMachiningAfterNesting.Events.HeadlessProcess", "JOB-001")


def test_process_cdm_job_inproc_com_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _mock_inproc_process(monkeypatch)
    run.Run.side_effect = OSError("0x80004002")
    with pytest.raises(RuntimeError, match=r"cdm: process job failed: .*0x80004002"):
        Application(run).process_cdm_job("JOB-001")
