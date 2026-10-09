import json
import sqlite3
import sys
from typing import Any

DB_PATH = r"C:\ALPHACAM\LICOMDAT\sheet_database_v2.db"

_SHEETS_SQL = (
    "SELECT s.id, s.name, s.width, s.height, s.quantity, s.offcut, s.position, "
    "t.thickness, t.material_id "
    "FROM sheets s JOIN thicknesses t ON s.thickness_id = t.id"
)


def _as_int(value: Any) -> int:
    return int(value)


def _read_materials(conn: sqlite3.Connection) -> dict[int, str]:
    rows: list[tuple[Any, ...]] = conn.execute("SELECT id, name FROM materials").fetchall()
    return {_as_int(row[0]): row[1] for row in rows if isinstance(row[1], str) and row[1].strip()}


def _sort_key(sheet: dict[str, Any]) -> tuple[int, int, int]:
    return (
        _as_int(sheet["offcut"] or 0),
        _as_int(sheet["position"] or 0),
        _as_int(sheet["id"]),
    )


def _read_sheets(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows: list[tuple[Any, ...]] = conn.execute(_SHEETS_SQL).fetchall()
    sheets = [
        {
            "id": _as_int(row[0]),
            "name": row[1],
            "width": row[2],
            "height": row[3],
            "quantity": row[4],
            "offcut": row[5],
            "position": row[6],
            "thickness": row[7],
            "material_id": row[8],
        }
        for row in rows
    ]
    sheets.sort(key=_sort_key)
    return sheets


def _material_name(materials: dict[int, str], material_id: Any) -> str | None:
    try:
        return materials.get(int(material_id))
    except (TypeError, ValueError):
        return None


def _sheet_payload(sheet: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": sheet["id"],
        "name": sheet["name"],
        "width": sheet["width"],
        "height": sheet["height"],
        "quantity": sheet["quantity"],
        "thickness": sheet["thickness"],
        "offcut": sheet["offcut"],
    }


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        materials = _read_materials(conn)
        sheets = _read_sheets(conn)
    finally:
        conn.close()
    groups: dict[str, list[dict[str, Any]]] = {}
    for sheet in sheets:
        material_name = _material_name(materials, sheet["material_id"])
        if material_name is None:
            continue
        groups.setdefault(material_name, []).append(_sheet_payload(sheet))
    print(json.dumps({"groups": groups}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
