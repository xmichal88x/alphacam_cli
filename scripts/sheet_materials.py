import json
import sqlite3
import sys

DB_PATH = r"C:\ALPHACAM\LICOMDAT\sheet_database_v2.db"
_TABLES = ("sheets", "materials")


def _read_names(conn: sqlite3.Connection, table: str) -> list[dict[str, int | str]]:
    rows = conn.execute(f"SELECT id, name FROM {table}").fetchall()
    return [
        {"id": row[0], "name": row[1]} for row in rows if isinstance(row[1], str) and row[1].strip()
    ]


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        data = {table: _read_names(conn, table) for table in _TABLES}
    finally:
        conn.close()
    print(json.dumps(data, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
