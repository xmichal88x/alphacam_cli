from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

from alphacam_cli.core.stock import (
    stock_add,
    stock_delete,
    stock_list,
    stock_offcut_create,
    stock_offcut_delete,
    stock_set,
)


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_list_basic(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    db.Materials.Count = 1
    mat = db.Materials.Item.return_value
    mat.Name = "MDF_18"
    mat.Id = 2
    mat.GUIPosition = 0
    mat.WholeSheets.Count = 1
    sheet = mat.WholeSheets.Item.return_value
    sheet.Id = 1
    sheet.Name = "MDF_18"
    sheet.Width = 2440.0
    sheet.Height = 1220.0
    sheet.Quantity = 100
    sheet.NumReserved = 0
    sheet.IsOffcut = False
    sheet.Cost = 0.0
    sheet.GrainDirection = 0
    sheet.LengthUnits = 0
    sheet.InheritCost = False
    sheet.UserID = ""
    sheet.GUIPosition = 0
    sheet.Zones.Count = 0
    sheet.Thickness.Thickness = 18.0
    sheet.Thickness.Id = 1
    mat.Offcuts.Count = 0
    mat.Thicknesses.Count = 1
    t = mat.Thicknesses.Item.return_value
    t.Id = 1
    t.Thickness = 18.0
    t.ThicknessUnits = 0
    t.AreaUnits = 0
    t.WeightUnits = 0
    t.CostPerArea = 0.0
    t.CostPerWeight = 0.0
    t.CostIsByWeight = False
    t.WeightPerArea = 0.0
    t.WholeSheets.Count = 1
    t.Offcuts.Count = 0
    t.Sheets.Count = 1

    result = stock_list(app)
    assert result["success"] is True
    assert len(result["materials"]) == 1
    assert "operations" in result
    assert "writable_fields" in result
    assert "sheet" in result["writable_fields"]
    assert "quantity" in result["writable_fields"]["sheet"]
    m = result["materials"][0]
    assert m["name"] == "MDF_18"
    assert m["id"] == 2
    assert len(m["sheets"]) == 1
    s = m["sheets"][0]
    assert s["id"] == 1
    assert s["quantity"] == 100
    assert s["width"] == 2440.0
    assert s["thickness"] == 18.0
    assert s["thickness_id"] == 1
    assert s["grain_label"] == "none"
    assert s["cost"] == 0.0
    assert m["thicknesses"][0]["thickness"] == 18.0
    assert m["thicknesses"][0]["cost_per_area"] == 0.0


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_list_filter(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    db.Materials.Count = 2
    mat1 = MagicMock()
    mat1.Name = "MDF_18"
    mat1.Id = 2
    mat1.GUIPosition = 0
    mat1.WholeSheets.Count = 0
    mat1.Offcuts.Count = 0
    mat1.Thicknesses.Count = 0
    mat2 = MagicMock()
    mat2.Name = "17mm"
    mat2.Id = 1
    mat2.GUIPosition = 0
    mat2.WholeSheets.Count = 0
    mat2.Offcuts.Count = 0
    mat2.Thicknesses.Count = 0
    db.Materials.Item.side_effect = [mat1, mat2]

    result = stock_list(app, material_filter="MDF_18")
    assert result["success"] is True
    assert len(result["materials"]) == 1
    assert result["materials"][0]["name"] == "MDF_18"


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_set_absolute(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    db.Materials.Count = 1
    mat = db.Materials.Item.return_value
    mat.Name = "MDF_18"
    mat.WholeSheets.Count = 1
    sheet = mat.WholeSheets.Item.return_value
    sheet.Name = "MDF_18"
    sheet.Quantity = 100

    result = stock_set(app, sheet_name="MDF_18", qty=50)
    assert result["success"] is True
    assert result["old_qty"] == 100
    assert result["new_qty"] == 50
    sheet.Save.assert_called_once()


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_set_delta(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    db.Materials.Count = 1
    mat = db.Materials.Item.return_value
    mat.Name = "MDF_18"
    mat.WholeSheets.Count = 1
    sheet = mat.WholeSheets.Item.return_value
    sheet.Name = "MDF_18"
    sheet.Quantity = 100

    result = stock_set(app, sheet_name="MDF_18", delta=-5)
    assert result["success"] is True
    assert result["old_qty"] == 100
    assert result["new_qty"] == 95
    sheet.Save.assert_called_once()


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_set_not_found(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    db.Materials.Count = 0
    result = stock_set(app, sheet_name="NONEXISTENT")
    assert result["success"] is False
    assert "not found" in result["error"].lower()


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_add(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    db.Materials.Count = 1
    mat = db.Materials.Item.return_value
    mat.Name = "MDF_18"
    mat.Thicknesses.Count = 1
    thick = mat.Thicknesses.Item.return_value
    thick.Thickness = 18.0
    new_sheet = thick.NewSheet.return_value
    new_sheet.Name = "NEW_001"

    result = stock_add(
        app, material_name="MDF_18", thickness=18.0, width=1000.0, height=500.0, quantity=5
    )
    assert result["success"] is True
    assert result["name"] == "NEW_001"
    mat.WholeSheets.Add.assert_called_once()
    new_sheet.Store.assert_called_once()


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_add_custom_name(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    db.Materials.Count = 1
    mat = db.Materials.Item.return_value
    mat.Name = "MDF_18"
    mat.Thicknesses.Count = 1
    thick = mat.Thicknesses.Item.return_value
    thick.Thickness = 18.0

    result = stock_add(
        app,
        material_name="MDF_18",
        thickness=18.0,
        width=1000.0,
        height=500.0,
        quantity=5,
        name="CUSTOM_NAME",
    )
    assert result["success"] is True
    new_sheet = thick.NewSheet.return_value
    assert new_sheet.Name == "CUSTOM_NAME"


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_add_material_not_found(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    db.Materials.Count = 0
    result = stock_add(
        app, material_name="NONEXISTENT", thickness=18.0, width=1000.0, height=500.0, quantity=5
    )
    assert result["success"] is False
    assert "not found" in result["error"].lower()


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_add_thickness_not_found(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    db.Materials.Count = 1
    mat = db.Materials.Item.return_value
    mat.Name = "MDF_18"
    mat.Thicknesses.Count = 1
    mat.Thicknesses.Item.return_value.Thickness = 18.0

    result = stock_add(
        app, material_name="MDF_18", thickness=10.0, width=1000.0, height=500.0, quantity=5
    )
    assert result["success"] is False
    assert "thickness" in result["error"].lower()


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_delete(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    db.Materials.Count = 1
    mat = db.Materials.Item.return_value
    mat.Name = "MDF_18"
    mat.WholeSheets.Count = 1
    mat.Offcuts.Count = 0
    sheet = mat.WholeSheets.Item.return_value
    sheet.Name = "TO_DELETE"

    result = stock_delete(app, sheet_name="TO_DELETE")
    assert result["success"] is True
    assert result["deleted"] == "TO_DELETE"
    sheet.Delete.assert_called_once()


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_delete_from_offcuts(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    db.Materials.Count = 1
    mat = db.Materials.Item.return_value
    mat.Name = "MDF_18"
    mat.WholeSheets.Count = 0
    mat.Offcuts.Count = 1
    sheet = mat.Offcuts.Item.return_value
    sheet.Name = "OFFCUT_TO_DELETE"

    result = stock_delete(app, sheet_name="OFFCUT_TO_DELETE")
    assert result["success"] is True
    assert result["deleted"] == "OFFCUT_TO_DELETE"


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_delete_not_found(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    db.Materials.Count = 0
    result = stock_delete(app, sheet_name="NONEXISTENT")
    assert result["success"] is False
    assert "not found" in result["error"].lower()


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_offcut_delete_by_stable_id(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    sheet = MagicMock()
    sheet.Id = 123
    sheet.Name = "OFFCUT_A"
    sheet.IsOffcut = True
    db.FindSheetByDatabaseID.side_effect = [sheet, None]

    result = stock_offcut_delete(app, 123)

    assert result == {
        "success": True,
        "status": "deleted",
        "sheet_id": 123,
        "name": "OFFCUT_A",
    }
    db.FindSheetByDatabaseID.assert_any_call(123)
    sheet.Delete.assert_called_once_with()


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_offcut_delete_uses_id_fallback_when_lookup_api_is_unavailable(_mock_ensure):
    app = MagicMock()
    sheet = MagicMock()
    sheet.Id = 456
    sheet.Name = "DUPLICATE_NAME"
    sheet.IsOffcut = True
    material = SimpleNamespace(
        WholeSheets=SimpleNamespace(Count=0),
        Offcuts=SimpleNamespace(Count=1, Item=lambda _index: sheet),
    )
    db = SimpleNamespace(Materials=SimpleNamespace(Count=1, Item=lambda _index: material))
    app.Nesting.SheetDatabase = db

    result = stock_offcut_delete(app, 456)

    assert result["success"] is False
    assert result["status"] == "unsupported"
    assert result["sheet_id"] == 456
    sheet.Delete.assert_not_called()


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_offcut_delete_rejects_missing_or_invalid_id(_mock_ensure):
    app = MagicMock()

    for invalid_id in (None, 0, -1, "123", True):
        result = stock_offcut_delete(app, invalid_id)
        assert result["success"] is False
        assert result["status"] == "invalid_id"

    app.Nesting.SheetDatabase.FindSheetByDatabaseID.assert_not_called()


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_offcut_delete_not_found_does_not_delete(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    db.FindSheetByDatabaseID.return_value = None

    result = stock_offcut_delete(app, 404)

    assert result == {
        "success": False,
        "status": "not_found",
        "error": "offcut not found: 404",
        "sheet_id": 404,
    }
    db.FindSheetByDatabaseID.assert_called_once_with(404)


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_offcut_delete_rejects_whole_sheet_without_delete(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    sheet = MagicMock()
    sheet.Id = 123
    sheet.Name = "WHOLE_SHEET"
    sheet.IsOffcut = False
    db.FindSheetByDatabaseID.return_value = sheet

    result = stock_offcut_delete(app, 123)

    assert result["success"] is False
    assert result["status"] == "wrong_type"
    sheet.Delete.assert_not_called()


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_offcut_delete_is_fail_closed_when_type_read_fails(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    sheet = MagicMock()
    sheet.Id = 123
    type(sheet).IsOffcut = PropertyMock(side_effect=RuntimeError("IsOffcut unavailable"))
    db.FindSheetByDatabaseID.return_value = sheet

    result = stock_offcut_delete(app, 123)

    assert result["success"] is False
    assert result["status"] == "com_error"
    sheet.Delete.assert_not_called()


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_offcut_delete_reports_delete_com_error(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    sheet = MagicMock()
    sheet.Id = 123
    sheet.IsOffcut = True
    sheet.Name = "OFFCUT_A"
    sheet.Delete.side_effect = RuntimeError("COM delete failed")
    db.FindSheetByDatabaseID.return_value = sheet

    result = stock_offcut_delete(app, 123)

    assert result["success"] is False
    assert result["status"] == "delete_error"
    assert "COM delete failed" in result["error"]


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_offcut_delete_reports_readback_failure(_mock_ensure):
    app = MagicMock()
    db = app.Nesting.SheetDatabase
    sheet = MagicMock()
    sheet.Id = 123
    sheet.IsOffcut = True
    sheet.Name = "OFFCUT_A"
    db.FindSheetByDatabaseID.side_effect = [sheet, sheet]

    result = stock_offcut_delete(app, 123)

    assert result["success"] is False
    assert result["status"] == "readback_failure"
    sheet.Delete.assert_called_once_with()


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_offcut_create_is_blocked_without_verified_sheet_paths(_mock_ensure):
    app = MagicMock()

    result = stock_offcut_create(
        app,
        material_name="MDF_18",
        thickness=18.0,
        width=1000.0,
        height=500.0,
        quantity=1,
        name="TEST_OFFCUT",
        drawing=MagicMock(),
    )

    assert result["success"] is False
    assert result["status"] in {"blocked", "unsupported"}
    assert "ISheetPaths" in result["reason"]
    app.Nesting.SheetDatabase.Materials.assert_not_called()
    app.Nesting.SheetDatabase.FindSheetByDatabaseID.assert_not_called()
    app.Nesting.SheetDatabase.SaveOffcutToDatabase.assert_not_called()


@patch("alphacam_cli.core.stock._ensure_nesting_typelib")
def test_stock_offcut_create_validates_dimensions_and_quantity_before_com(_mock_ensure):
    app = MagicMock()

    for width, height, quantity in ((0, 500.0, 1), (1000.0, -1, 1), (1000.0, 500.0, 0)):
        result = stock_offcut_create(
            app,
            material_name="MDF_18",
            thickness=18.0,
            width=width,
            height=height,
            quantity=quantity,
            name="TEST_OFFCUT",
            drawing=MagicMock(),
        )

        assert result["success"] is False
        assert result["status"] == "invalid_input"

    app.Nesting.SheetDatabase.assert_not_called()
