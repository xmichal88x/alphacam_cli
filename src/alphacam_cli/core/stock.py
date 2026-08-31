from __future__ import annotations

import contextlib
from typing import Any, Literal, TypedDict

_NESTING_TYPELIB = "{6702E3DF-142C-4627-8EA2-4C47EBC78441}"

_GRAIN_LABELS = {0: "none", 1: "x", 2: "y"}
_UNIT_LABELS = {0: "mm", 1: "cm", 2: "m", 3: "inches"}

SHEET_WRITABLE = frozenset(
    {
        "name",
        "width",
        "height",
        "quantity",
        "reserved",
        "grain_direction",
        "cost",
        "length_units",
        "inherit_cost",
        "user_id",
        "gui_position",
    }
)
SHEET_READONLY = frozenset(
    {
        "id",
        "is_offcut",
        "thickness",
        "thickness_id",
        "zones_count",
        "material_name",
    }
)
THICKNESS_WRITABLE = frozenset(
    {
        "thickness",
        "thickness_units",
        "area_units",
        "weight_units",
        "cost_per_area",
        "cost_per_weight",
        "cost_is_by_weight",
        "weight_per_area",
        "gui_position",
    }
)
THICKNESS_READONLY = frozenset(
    {
        "id",
        "whole_sheets_count",
        "offcuts_count",
        "sheets_count",
    }
)
MATERIAL_WRITABLE = frozenset({"name", "gui_position"})
MATERIAL_READONLY = frozenset({"id", "sheets_count", "whole_sheets_count", "offcuts_count"})


class OffcutCreateResult(TypedDict, total=False):
    success: bool
    status: Literal["invalid_input", "blocked", "unsupported", "com_error", "created", "not_found"]
    error: str
    reason: str
    sheet_id: int
    diag: str
    material: str
    thickness: float
    name: str


OPERATIONS = {
    "stock_list": "read all materials/sheets/thicknesses from database",
    "stock_set": (
        "change sheet quantity (absolute or delta);"
        " writable: name, width, height, quantity, reserved,"
        " grain_direction, cost"
    ),
    "stock_add": "add new sheet to database (via thickness.NewSheet + WholeSheets.Add + Store)",
    "stock_offcut_create": "blocked until a real ISheetPaths source is proven",
    "stock_delete": "delete sheet from database (via sheet.Delete)",
}


def _ensure_nesting_typelib() -> None:
    from win32com.client import gencache  # type: ignore[import-untyped]

    gencache.EnsureModule(_NESTING_TYPELIB, 0, 1, 3)


def _get_sheet_database(app: Any) -> Any:
    """Get the SheetDatabase from the app, with fallback to AcamNest.Nesting or Nesting CoClass."""
    import win32com.client as win32  # type: ignore[import-untyped]

    candidates: list[Any] = []
    with contextlib.suppress(Exception):
        candidates.append(app.Nesting.SheetDatabase)
    for progid in ("AcamNest.Nesting", "{57250022-AD47-4205-AA0D-9F8039C315B3}"):
        with contextlib.suppress(Exception):
            candidates.append(win32.Dispatch(progid).SheetDatabase)
    if candidates:
        return candidates[0]
    with contextlib.suppress(Exception):
        return win32.Dispatch("{1C2252AB-0AED-4650-A92C-F5354919A8AE}")
    raise RuntimeError("no sheet database available")  # noqa: TRY003


def _read_sheet(s: Any) -> dict[str, Any]:
    try:
        thick_obj = s.Thickness
        thickness_val = float(thick_obj.Thickness)
        thickness_id = int(thick_obj.Id)
    except Exception:
        thickness_val = 0.0
        thickness_id = 0
    try:
        zones_count = int(s.Zones.Count)
    except Exception:
        zones_count = 0
    grain = int(s.GrainDirection)
    return {
        "id": int(s.Id),
        "name": str(s.Name),
        "width": float(s.Width),
        "height": float(s.Height),
        "quantity": int(s.Quantity),
        "reserved": int(s.NumReserved),
        "is_offcut": bool(s.IsOffcut),
        "thickness": thickness_val,
        "thickness_id": thickness_id,
        "grain_direction": grain,
        "grain_label": _GRAIN_LABELS.get(grain, "unknown"),
        "cost": float(s.Cost),
        "length_units": int(s.LengthUnits),
        "inherit_cost": bool(s.InheritCost),
        "user_id": str(s.UserID),
        "gui_position": int(s.GUIPosition),
        "zones_count": zones_count,
    }


def _read_thickness(t: Any) -> dict[str, Any]:
    return {
        "id": int(t.Id),
        "thickness": float(t.Thickness),
        "thickness_units": int(t.ThicknessUnits),
        "thickness_units_label": _UNIT_LABELS.get(int(t.ThicknessUnits), "unknown"),
        "area_units": int(t.AreaUnits),
        "weight_units": int(t.WeightUnits),
        "cost_per_area": float(t.CostPerArea),
        "cost_per_weight": float(t.CostPerWeight),
        "cost_is_by_weight": bool(t.CostIsByWeight),
        "weight_per_area": float(t.WeightPerArea),
        "whole_sheets_count": int(t.WholeSheets.Count),
        "offcuts_count": int(t.Offcuts.Count),
        "sheets_count": int(t.Sheets.Count),
    }


def stock_list(app: Any, material_filter: str | None = None) -> dict[str, Any]:
    _ensure_nesting_typelib()
    db = _get_sheet_database(app)
    materials_out = []
    for i in range(1, db.Materials.Count + 1):
        mat = db.Materials.Item(i)
        if material_filter and mat.Name != material_filter:
            continue
        sheets = []
        for j in range(1, mat.WholeSheets.Count + 1):
            sheets.append(_read_sheet(mat.WholeSheets.Item(j)))
        offcuts = []
        for j in range(1, mat.Offcuts.Count + 1):
            offcuts.append(_read_sheet(mat.Offcuts.Item(j)))
        thicknesses = []
        for j in range(1, mat.Thicknesses.Count + 1):
            thicknesses.append(_read_thickness(mat.Thicknesses.Item(j)))
        materials_out.append(
            {
                "id": int(mat.Id),
                "name": str(mat.Name),
                "gui_position": int(mat.GUIPosition),
                "sheets_count": int(mat.WholeSheets.Count + mat.Offcuts.Count),
                "whole_sheets_count": int(mat.WholeSheets.Count),
                "offcuts_count": int(mat.Offcuts.Count),
                "thicknesses": thicknesses,
                "sheets": sheets,
                "offcuts": offcuts,
            }
        )
    return {
        "success": True,
        "materials": materials_out,
        "operations": OPERATIONS,
        "writable_fields": {
            "sheet": sorted(SHEET_WRITABLE),
            "thickness": sorted(THICKNESS_WRITABLE),
            "material": sorted(MATERIAL_WRITABLE),
        },
    }


def stock_set(
    app: Any,
    sheet_name: str,
    qty: int | None = None,
    delta: int | None = None,
) -> dict[str, Any]:
    _ensure_nesting_typelib()
    db = _get_sheet_database(app)
    for i in range(1, db.Materials.Count + 1):
        mat = db.Materials.Item(i)
        for coll in (mat.WholeSheets, mat.Offcuts):
            for j in range(1, coll.Count + 1):
                s = coll.Item(j)
                if str(s.Name) == sheet_name:
                    old_qty = int(s.Quantity)
                    if qty is not None:
                        s.Quantity = int(qty)
                    elif delta is not None:
                        s.Quantity = old_qty + int(delta)
                    else:
                        return {"success": False, "error": "either qty or delta required"}
                    s.Save()
                    return {
                        "success": True,
                        "sheet_id": int(s.Id),
                        "material": str(mat.Name),
                        "old_qty": old_qty,
                        "new_qty": int(s.Quantity),
                        "name": sheet_name,
                    }
    return {"success": False, "error": f"sheet not found: {sheet_name}"}


def stock_add(
    app: Any,
    material_name: str,
    thickness: float,
    width: float,
    height: float,
    quantity: int,
    name: str | None = None,
    grain: int = 0,
) -> dict[str, Any]:
    _ensure_nesting_typelib()
    if width <= 0 or height <= 0:
        return {"success": False, "error": "width and height must be positive"}
    if quantity <= 0:
        return {"success": False, "error": "quantity must be positive"}
    db = _get_sheet_database(app)
    for i in range(1, db.Materials.Count + 1):
        mat = db.Materials.Item(i)
        if str(mat.Name) != material_name:
            continue
        thick = None
        for j in range(1, mat.Thicknesses.Count + 1):
            t = mat.Thicknesses.Item(j)
            if abs(float(t.Thickness) - thickness) < 0.1:
                thick = t
                break
        if thick is None:
            return {
                "success": False,
                "error": f"thickness {thickness}mm not found in {material_name}",
            }
        new_sheet = thick.NewSheet()
        if name:
            new_sheet.Name = name
        new_sheet.Width = float(width)
        new_sheet.Height = float(height)
        new_sheet.Quantity = int(quantity)
        new_sheet.GrainDirection = int(grain)
        mat.WholeSheets.Add(new_sheet)
        new_sheet.Store()
        return {
            "success": True,
            "sheet_id": int(new_sheet.Id),
            "name": str(new_sheet.Name),
            "material": material_name,
            "thickness": thickness,
            "width": float(width),
            "height": float(height),
            "quantity": int(quantity),
        }
    return {"success": False, "error": f"material not found: {material_name}"}


def _find_material_by_name(db: Any, material_name: str) -> Any | None:
    for i in range(1, int(db.Materials.Count) + 1):
        material = db.Materials.Item(i)
        if str(material.Name) == material_name:
            return material
    return None


def _find_thickness(material: Any, thickness: float) -> Any | None:
    for i in range(1, int(material.Thicknesses.Count) + 1):
        candidate = material.Thicknesses.Item(i)
        try:
            if abs(float(candidate.Thickness) - thickness) < 0.1:
                return candidate
        except Exception:
            continue
    return None


def _safe_set_sheet_fields(
    sheet: Any, *, name: str | None, width: float, height: float, quantity: int
) -> None:
    if name:
        sheet.Name = name
    sheet.Width = float(width)
    sheet.Height = float(height)
    sheet.Quantity = int(quantity)


def stock_offcut_create(
    app: Any,
    material_name: str,
    thickness: float,
    width: float,
    height: float,
    quantity: int,
    name: str | None = None,
    drawing: Any = None,
) -> OffcutCreateResult:
    """Create an offcut by inserting a temporary sheet into the active drawing to obtain IPaths."""
    if not isinstance(material_name, str) or not material_name.strip():
        return {"success": False, "status": "invalid_input", "error": "material_name is required"}
    if thickness <= 0:
        return {"success": False, "status": "invalid_input", "error": "thickness must be positive"}
    if width <= 0 or height <= 0:
        return {
            "success": False,
            "status": "invalid_input",
            "error": "width and height must be positive",
        }
    if isinstance(quantity, bool) or quantity <= 0:
        return {"success": False, "status": "invalid_input", "error": "quantity must be positive"}

    if drawing is None:
        return {
            "success": False,
            "status": "blocked",
            "reason": "offcut creation is blocked: no active drawing available",
        }

    try:
        _ensure_nesting_typelib()
        db = _get_sheet_database(app)
    except Exception as exc:
        return {"success": False, "status": "com_error", "error": f"COM setup failed: {exc}"}

    material = _find_material_by_name(db, material_name)
    if material is None:
        return {
            "success": False,
            "status": "not_found",
            "error": f"material not found: {material_name}",
        }

    thick = _find_thickness(material, thickness)
    if thick is None:
        return {
            "success": False,
            "status": "not_found",
            "error": f"thickness {thickness}mm not found in {material_name}",
        }

    _diag: list[str] = []
    try:
        i_drw = app.ActiveDrawing
        if i_drw is None:
            return {
                "success": False,
                "status": "blocked",
                "reason": (
                    "offcut creation is blocked: no active drawing available for shape creation"
                ),
            }

        _diag.append(f"i_drw={type(i_drw).__name__}")

        # Step A: create rectangle geometry + path collection
        if not hasattr(i_drw, "CreateRectangle") or not hasattr(i_drw, "CreatePathCollection"):
            return {
                "success": False,
                "status": "blocked",
                "reason": (
                    "offcut creation is blocked: drawing lacks CreateRectangle/CreatePathCollection"
                ),
                "diag": " | ".join(_diag),
            }

        sheet_shape = None
        try:
            sheet_shape = i_drw.CreateRectangle(0.0, 0.0, float(width), float(height))
            _diag.append(f"CreateRectangle OK: {type(sheet_shape).__name__}")
        except Exception as exc:
            _diag.append(f"CreateRectangle FAIL: {exc}")
            return {
                "success": False,
                "status": "com_error",
                "error": f"CreateRectangle failed: {exc}",
                "diag": " | ".join(_diag),
            }

        paths_coll = None
        try:
            paths_coll = i_drw.CreatePathCollection()
            paths_coll.Add(sheet_shape)
            _diag.append(f"CreatePathCollection OK: {type(paths_coll).__name__}")
        except Exception as exc:
            _diag.append(f"CreatePathCollection FAIL: {exc}")
            return {
                "success": False,
                "status": "com_error",
                "error": f"CreatePathCollection failed: {exc}",
                "diag": " | ".join(_diag),
            }

        # Step B: NewOffcut
        sheet = thick.NewOffcut(paths_coll)
        _diag.append(f"NewOffcut OK: id={sheet.Id}, IsOffcut={sheet.IsOffcut}")

        if name:
            sheet.Name = name
        sheet.Quantity = int(quantity)
        _diag.append(f"Set fields OK: name={name}, qty={quantity}")

        # Step C: Store to persist (SaveOffcutToDatabase fails with E_FAIL; Store works)
        try:
            sheet.Store()
            _diag.append("Store OK")
        except Exception as exc:
            _diag.append(f"Store FAIL: {exc}")
            return {
                "success": False,
                "status": "com_error",
                "error": f"Store failed: {exc}",
                "diag": " | ".join(_diag),
            }

        try:
            sheet_id = int(sheet.Id)
        except Exception:
            sheet_id = 0
        _diag.append(f"sheet_id={sheet_id}")

        return {
            "success": True,
            "status": "created",
            "sheet_id": sheet_id,
            "material": material_name,
            "thickness": thickness,
            "name": str(sheet.Name),
            "diag": " | ".join(_diag),
        }
    except Exception as exc:
        _diag_str = " | ".join(_diag) if "_diag" in dir() else "no diag"
        return {
            "success": False,
            "status": "com_error",
            "error": f"offcut creation failed: {exc}",
            "diag": _diag_str,
        }


def stock_delete(app: Any, sheet_name: str) -> dict[str, Any]:
    _ensure_nesting_typelib()
    db = _get_sheet_database(app)
    for i in range(1, db.Materials.Count + 1):
        mat = db.Materials.Item(i)
        for coll in (mat.WholeSheets, mat.Offcuts):
            for j in range(1, coll.Count + 1):
                s = coll.Item(j)
                if str(s.Name) == sheet_name:
                    s.Delete()
                    return {"success": True, "deleted": sheet_name, "material": str(mat.Name)}
    return {"success": False, "error": f"sheet not found: {sheet_name}"}


def _find_sheet_by_database_id(db: Any, sheet_id: int) -> tuple[Any | None, bool, str | None]:
    """Return the sheet, whether readback is supported, and an error if lookup failed."""
    try:
        find_by_id = db.FindSheetByDatabaseID
    except Exception:
        find_by_id = None

    if callable(find_by_id):
        try:
            return find_by_id(sheet_id), True, None
        except Exception as exc:
            return None, True, f"stable-ID lookup failed for {sheet_id}: {exc}"

    try:
        for i in range(1, int(db.Materials.Count) + 1):
            material = db.Materials.Item(i)
            for collection in (material.WholeSheets, material.Offcuts):
                for j in range(1, int(collection.Count) + 1):
                    sheet = collection.Item(j)
                    try:
                        if int(sheet.Id) == sheet_id:
                            return sheet, False, None
                    except Exception as exc:
                        return None, False, f"sheet ID read failed during lookup: {exc}"
    except Exception as exc:
        return None, False, f"fallback lookup failed for {sheet_id}: {exc}"
    return None, False, None


def stock_offcut_delete(app: Any, sheet_id: int) -> dict[str, Any]:
    """Delete exactly one offcut selected by its stable database ID."""
    if isinstance(sheet_id, bool) or not isinstance(sheet_id, int) or sheet_id <= 0:
        return {
            "success": False,
            "status": "invalid_id",
            "error": "sheet_id must be a positive integer",
        }

    try:
        _ensure_nesting_typelib()
        db = _get_sheet_database(app)
    except Exception as exc:
        return {"success": False, "status": "com_error", "error": f"COM setup failed: {exc}"}

    sheet, readback_supported, lookup_error = _find_sheet_by_database_id(db, sheet_id)
    if lookup_error:
        return {
            "success": False,
            "status": "com_error",
            "error": lookup_error,
            "sheet_id": sheet_id,
        }
    if sheet is None:
        return {
            "success": False,
            "status": "not_found",
            "error": f"offcut not found: {sheet_id}",
            "sheet_id": sheet_id,
        }

    try:
        actual_id = int(sheet.Id)
        is_offcut = sheet.IsOffcut
        if actual_id != sheet_id:
            return {
                "success": False,
                "status": "com_error",
                "error": f"stable ID mismatch: expected {sheet_id}, got {actual_id}",
                "sheet_id": sheet_id,
            }
        if is_offcut is not True:
            return {
                "success": False,
                "status": "wrong_type",
                "error": f"sheet {sheet_id} is not an offcut",
                "sheet_id": sheet_id,
            }
        name = str(sheet.Name)
    except Exception as exc:
        return {
            "success": False,
            "status": "com_error",
            "error": f"offcut validation failed for {sheet_id}: {exc}",
            "sheet_id": sheet_id,
        }

    if not readback_supported:
        return {
            "success": False,
            "status": "unsupported",
            "error": "offcut delete requires stable-ID readback support",
            "sheet_id": sheet_id,
        }

    try:
        sheet.Delete()
    except Exception as exc:
        return {
            "success": False,
            "status": "delete_error",
            "error": f"offcut delete failed for {sheet_id}: {exc}",
            "sheet_id": sheet_id,
        }

    if readback_supported:
        try:
            if db.FindSheetByDatabaseID(sheet_id) is not None:
                return {
                    "success": False,
                    "status": "readback_failure",
                    "error": f"offcut {sheet_id} still exists after delete",
                    "sheet_id": sheet_id,
                }
        except Exception as exc:
            return {
                "success": False,
                "status": "readback_failure",
                "error": f"offcut readback failed for {sheet_id}: {exc}",
                "sheet_id": sheet_id,
            }

    return {"success": True, "status": "deleted", "sheet_id": sheet_id, "name": name}
