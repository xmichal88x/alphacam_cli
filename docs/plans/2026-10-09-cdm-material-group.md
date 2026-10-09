# CDM Material Group (multi-sheet nesting) — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Dodać do CLI/API samodzielny blok „grupa materiału" — możliwość wskazania, że job/pozycje mają korzystać z **wielu arkuszy** jednego materiału (np. `MDF_18` = `MDF_18` 2440×1220 + `MDF18` 2800×2070), tak by nester sam dobrał arkusze wg `Nesting_SheetOrderType` (Best Utilisation / Picked Order).

**Architecture:** AlphaCAM AM rozgałęzia się per część po `JobFile.FkMaterialID` (zweryfikowane w IL `AcamAddIns.dll`):
- `FkMaterialID != 0` → używa JEDNEGO arkusza `GetByID("m"+FkMaterialID)` (obecna ścieżka CLI, `--material`).
- `FkMaterialID == 0` → czyta listę z tabeli **`AM_SelectedSheets(fkJobDetailID, SelectedSheetID, Quantity)`**; pusta → modalny komunikat = **HANG** w Session 0; niepusta → obiekt `MultiMateriał` → wszystkie arkusze jako kandydaci.

Zatem grupa = wiersze w `AM_SelectedSheets` + `CDM_OrderDetails.fkMaterialID = 0`. Nowy blok CLI zapisuje to przez VistaDB (jedyny stabilny interfejs; COM `NestMaterialDatabaseSheets` nie utrwala).

**Tech Stack:** Python 3.11+, Typer, pytest, PowerShell + `VistaDB.5.NET40.dll` (skrypty `scripts/vdb5_*.ps1`), SQLite (`sheet_database_v2.db`), gateway JSON-RPC, VM125 (192.168.100.60, AlphaCAM 2025 Router).

---

## Scope & Guardrails

- **Nowy blok, nie przepływ.** `--material-group` to parametr istniejącego bloku importu; nie dodajemy nowych komend „end-to-end".
- **Nie łamać `--material`.** Ścieżka pojedynczego arkusza zostaje bez zmian (domyślna).
- **Walidacja obowiązkowa (inaczej HANG):** każdy `SelectedSheetID` musi istnieć w `sheets.id`; grupa bez arkuszy = twardy błąd.
- **`--sheet-order` zmienia konfigurację globalnie** (`Nesting_SheetOrderType` jest w `AM_ConfigurationSettings`, per konfiguracja) — oznaczyć jako opcjonalne/ryzykowne, z jawnym komunikatem; domyślnie nie ruszać.
- **Nie modyfikować** `C:\ALPHACAM\LICOMDAT\sheet_database_v2.db` w repo; testy live sprzątają po sobie (job, katalog wyjściowy, offcuty, wiersze AM_SelectedSheets).
- Wszystkie skrypty `vdb5_*.ps1` — nadal twarde ścieżki instalacji (świadome, pre-existing).
- `sheet_materials()` (nazwa→id, priorytet arkusze>materiały) zostaje dla `--material`; nowy resolver grup działa na **tabeli `materials`**, by `--material-group MDF_18` wskazywał grupę, nie arkusz.

## Fakty zweryfikowane na VM125 (nie badaj od nowa)

- Sheet DB: `materials(1=17mm, 2=MDF_18)`, `thicknesses(material_id, thickness)`, `sheets(id, thickness_id, name, width, height, quantity, position, offcut, shape)`. MDF_18 → arkusze id2 „MDF_18" 2440×1220×18, id7 „MDF18" 2800×2070×18.
- E2E: detal `fkMaterialID=0` + `AM_SelectedSheets{2,7}` → SUCCESS, użyte OBA arkusze. Detal `=0` bez `AM_SelectedSheets` → HANG. Detal `≠0` + wiele wierszy selected → nest ZEPSUTY.

### Jak AlphaCAM sam wybiera arkusz z grupy (ZWERYFIKOWANE E2E, 2026-10-09)
- **AlphaCAM decyduje sam**, sterowany `Nesting_SheetOrderType`:
  - `0 = Best Utilisation` → wybiera arkusz dający najlepsze wypełnienie (najmniejszy wystarczający), **ignoruje kolejność listy** (test O5: lista `[7,2]` → wybrał 2 = mniejszy).
  - `1 = Picked Order` → wybiera wg **kolejności wierszy w `AM_SelectedSheets`** (test O2a vs O2b).
- **Offcuty NIE mają wrodzonego priorytetu** — używane tylko, gdy są jawnie w `AM_SelectedSheets`; wtedy Best-Util często je wybiera (są małe → najlepsze wypełnienie), a Picked-Order — gdy są pierwsze na liście. Aby „najpierw offcuty": `SheetOrderType=1` + offcuty pierwsze na liście.
- **Offcuty NIE są auto-dodawane** — grupa z samych całych arkuszy ich nie uwzględnia, mimo że istnieją w bazie (test O3).
- `Nesting_OffcutPreference` = **tylko kierunek generowanego odcinka** (0=Vertical, 1=Horizontal), nie priorytet.
- **Offcuty geometrycznie:** w tabeli `sheets` mają `width=height=0`; realna geometria w polu `shape` (poligon). Nester czyta poligon; do `AM_SelectedSheets` wystarcza `id`.
- `AM_SelectedSheets.Quantity` = `NestSheet.Required`: **0 = brak limitu** (nester używa ile trzeba); `N≥1` = maks. liczba arkuszy tego typu. Zbyt mały limit przy niedoborze → **twardy crash `0x800ADF09`** (bez czytelnego błędu; reset gatewaya). **Domyślnie ustawiać 0.**
- `finalize_cdm_job` (JobType=1 + kopiowanie `AM_SelectedSheetDefaults`→`AM_SelectedSheets`) jest w `scripts/vdb5_finalize_job.ps1` (INSERT…WHERE NOT EXISTS — ustawić po naszym zapisie, nie nadpisze).

---

## Task 1: Resolver grup — `material_groups()` w cdm_db

**Files:**
- Create: `scripts/sheet_material_groups.py`
- Modify: `src/alphacam_cli/core/cdm_db.py` (po `sheet_materials`, ~linia 91)
- Test: `tests/unit/test_cdm_db.py`

**Step 1: Write the failing test**

```python
def test_material_groups_parses_script(monkeypatch):
    from alphacam_cli.core import cdm_db

    def fake_run(*a, **k):
        class P:
            returncode = 0
            stdout = json.dumps({"groups": {
                "MDF_18": [
                    {"id": 2, "name": "MDF_18", "width": 2440, "height": 1220, "quantity": 100},
                    {"id": 7, "name": "MDF18", "width": 2800, "height": 2070, "quantity": 100},
                ],
                "17mm": [{"id": 1, "name": "Arkusz 1", "width": 1220, "height": 2440, "quantity": 100}],
            }})
        return P()

    monkeypatch.setattr(cdm_db.subprocess, "run", fake_run)
    groups = cdm_db.material_groups()
    assert [s["id"] for s in groups["MDF_18"]] == [2, 7]


def test_material_groups_empty_on_failure(monkeypatch):
    from alphacam_cli.core import cdm_db

    def fake_run(*a, **k):
        class P:
            returncode = 1
            stdout = ""
        return P()

    monkeypatch.setattr(cdm_db.subprocess, "run", fake_run)
    assert cdm_db.material_groups() == {}
```

**Step 2: Run test to verify it fails**
Run: `python -m pytest tests/unit/test_cdm_db.py -k material_groups -v`
Expected: FAIL — `AttributeError: module 'alphacam_cli.core.cdm_db' has no attribute 'material_groups'`

**Step 3: Write minimal implementation**

`scripts/sheet_material_groups.py`:

```python
import json
import sqlite3
import sys

DB_PATH = r"C:\ALPHACAM\LICOMDAT\sheet_database_v2.db"


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        sheets = conn.execute(
            "SELECT s.id, s.name, s.width, s.height, s.quantity, t.material_id, t.thickness "
            "FROM sheets s JOIN thicknesses t ON s.thickness_id = t.id WHERE s.offcut = 0"
        ).fetchall()
        materials = dict(conn.execute("SELECT id, name FROM materials").fetchall())
    finally:
        conn.close()
    groups: dict[str, list[dict]] = {}
    for sid, name, w, h, qty, mat_id, thick in sheets:
        mat_name = materials.get(mat_id)
        if not isinstance(mat_name, str) or not mat_name.strip():
            continue
        groups.setdefault(mat_name, []).append(
            {"id": int(sid), "name": name, "width": float(w), "height": float(h),
             "quantity": int(qty), "thickness": float(thick)}
        )
    print(json.dumps({"groups": groups}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`src/alphacam_cli/core/cdm_db.py` (po `sheet_materials`):

```python
def material_groups() -> dict[str, list[dict[str, Any]]]:
    """Material name -> its whole sheets (id/name/width/height/quantity/thickness).

    Reads the SQLite sheet database via a helper script; empty dict on failure.
    Also includes single-sheet materials (a group of one).
    """
    script_path = os.path.join(_scripts_dir(), "sheet_material_groups.py")
    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=20, check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return {}
        data = json.loads(proc.stdout)
    except Exception as e:
        logger.warning("cdm material groups: sheet db read failed: %r", e)
        return {}
    if isinstance(data, dict) and "value" in data:
        data = data["value"]
    if not isinstance(data, dict):
        return {}
    raw = data.get("groups")
    if not isinstance(raw, dict):
        return {}
    groups: dict[str, list[dict[str, Any]]] = {}
    for name, rows in raw.items():
        if not isinstance(name, str) or not isinstance(rows, list):
            continue
        cleaned: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict) or row.get("id") is None:
                continue
            try:
                cleaned.append(
                    {
                        "id": int(row["id"]),
                        "name": str(row.get("name") or ""),
                        "width": float(row.get("width") or 0),
                        "height": float(row.get("height") or 0),
                        "quantity": int(row.get("quantity") or 0),
                        "thickness": float(row.get("thickness") or 0),
                    }
                )
            except (TypeError, ValueError):
                continue
        if cleaned:
            groups[name] = cleaned
    return groups
```

**Step 4: Run test to verify it passes**
Run: `python -m pytest tests/unit/test_cdm_db.py -k material_groups -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/sheet_material_groups.py src/alphacam_cli/core/cdm_db.py tests/unit/test_cdm_db.py
git commit -m "feat(cdm): material_groups() resolver from sheet database"
```

### Verification

1. **Format & Lint** — `ruff format --check src/alphacam_cli/core/cdm_db.py scripts/sheet_material_groups.py && ruff check src/alphacam_cli/core/cdm_db.py scripts/sheet_material_groups.py`
2. **Type check** — `mypy src/alphacam_cli/core/cdm_db.py`
3. **Regression** — `python -m pytest tests/unit/test_cdm_db.py -q`
4. **Error handling** — script failure/timeout/malformed JSON → `{}` (nie wyjątek).
5. **Kaizen** — brak duplikacji z `sheet_materials()`; wspólny `_scripts_dir()`.

**Report:** files, pre-existing errors, new issues, decisions.

---

## Task 2: `resolve_material_group()` + walidacja

**Files:**
- Modify: `src/alphacam_cli/core/cdm_db.py`
- Test: `tests/unit/test_cdm_db.py`

**Step 1: Write the failing test**

```python
def test_resolve_material_group_ok(monkeypatch):
    from alphacam_cli.core import cdm_db
    monkeypatch.setattr(cdm_db, "material_groups", lambda: {"MDF_18": [
        {"id": 2, "name": "MDF_18", "quantity": 100}, {"id": 7, "name": "MDF18", "quantity": 100}]})
    sheets = cdm_db.resolve_material_group("MDF_18", quantity=0)
    assert [(s["id"], s["quantity"]) for s in sheets] == [(2, 0), (7, 0)]


def test_resolve_material_group_missing(monkeypatch):
    from alphacam_cli.core import cdm_db
    monkeypatch.setattr(cdm_db, "material_groups", lambda: {})
    with pytest.raises(RuntimeError, match="material group not found"):
        cdm_db.resolve_material_group("NOPE", quantity=0)


def test_resolve_material_group_empty(monkeypatch):
    from alphacam_cli.core import cdm_db
    monkeypatch.setattr(cdm_db, "material_groups", lambda: {"X": []})
    with pytest.raises(RuntimeError, match="no sheets"):
        cdm_db.resolve_material_group("X", quantity=1)
```

**Step 2: Run test to verify it fails**
Run: `python -m pytest tests/unit/test_cdm_db.py -k resolve_material_group -v`
Expected: FAIL — `AttributeError`

**Step 3: Write minimal implementation**

```python
def resolve_material_group(material_name: str, quantity: int | None = None) -> list[dict[str, Any]]:
    """All whole sheets of a material as ``[{"id", "name", "quantity"}, ...]``.

    ``quantity`` overrides each sheet's Required count (``None`` keeps the
    sheet's stock quantity; 0 = no limit). Raises RuntimeError when the
    material is unknown or has no sheets (both would hang AM processing).
    """
    name = (material_name or "").strip()
    groups = material_groups()
    if name not in groups:
        raise RuntimeError(f"cdm: material group not found: {name or material_name}")
    rows = groups[name]
    if not rows:
        raise RuntimeError(f"cdm: material group has no sheets: {name}")
    out: list[dict[str, Any]] = []
    for row in rows:
        qty = int(row.get("quantity") or 0) if quantity is None else int(quantity)
        out.append({"id": int(row["id"]), "name": str(row.get("name") or ""), "quantity": qty})
    return out
```

**Step 4: Run test to verify it passes**
Expected: PASS.

**Step 5: Commit**

```bash
git add src/alphacam_cli/core/cdm_db.py tests/unit/test_cdm_db.py
git commit -m "feat(cdm): resolve_material_group with validation"
```

### Verification
1. `ruff format --check && ruff check` (plik), 2. `mypy src/alphacam_cli/core/cdm_db.py`, 3. `pytest tests/unit/test_cdm_db.py -q`. 4. Error handling: brak materiału / brak arkuszy → czytelny RuntimeError (nie HANG). 5. Kaizen: reużyj `material_groups`.

---

## Task 3: Skrypt VistaDB — zapis `AM_SelectedSheets`

**Files:**
- Create: `scripts/vdb5_set_selected_sheets.ps1`
- Modify: `src/alphacam_cli/core/cdm_db.py` (wrapper)
- Test: `tests/unit/test_cdm_db.py` (mock subprocess)

**Step 1: Write the failing test**

```python
def test_set_selected_sheets_ok(monkeypatch):
    from alphacam_cli.core import cdm_db
    captured = {}
    def fake_run(cmd, *a, **k):
        captured["cmd"] = cmd
        class P:
            returncode = 0
            stdout = "sheet_rows: 2\n"
        return P()
    monkeypatch.setattr(cdm_db.subprocess, "run", fake_run)
    assert cdm_db.set_selected_sheets("E2E J", [{"id": 2, "quantity": 0}, {"id": 7, "quantity": 1}]) is True
    assert "-Sheets:2:0,7:1" in " ".join(captured["cmd"])


def test_set_selected_sheets_empty_rejected():
    from alphacam_cli.core import cdm_db
    with pytest.raises(RuntimeError, match="at least one sheet"):
        cdm_db.set_selected_sheets("J", [])
```

**Step 2: Run test to verify it fails**
Expected: FAIL — no attribute.

**Step 3: Write minimal implementation**

`scripts/vdb5_set_selected_sheets.ps1`:

```powershell
param(
    [string]$JobName,
    [string]$Sheets   # "id:qty,id:qty"
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -Path 'C:\Program Files\Hexagon\ALPHACAM 2025\VistaDB.5.NET40.dll'
$conn = New-Object VistaDB.Provider.VistaDBConnection('Data Source=C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5')
$conn.Open()
try {
    $job = $JobName.Replace("'", "''")
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = "SELECT JobDetailID FROM AM_JobDetails WHERE JobName = '$job'"
    $r = $cmd.ExecuteReader()
    $jdId = $null
    if ($r.Read()) { $jdId = [int]$r.GetValue(0) }
    $r.Close()
    if ($null -eq $jdId) { Write-Output "sheet_rows: 0"; exit 0 }

    $del = $conn.CreateCommand()
    $del.CommandText = "DELETE FROM AM_SelectedSheets WHERE fkJobDetailID = $jdId"
    [void]$del.ExecuteNonQuery()

    $count = 0
    foreach ($pair in ($Sheets -split ',')) {
        $parts = $pair -split ':'
        if ($parts.Count -ne 2) { continue }
        $sheetId = [int]$parts[0]; $qty = [int]$parts[1]
        $ins = $conn.CreateCommand()
        $ins.CommandText = "INSERT INTO AM_SelectedSheets (fkJobDetailID, SelectedSheetID, Quantity) VALUES ($jdId, $sheetId, $qty)"
        $count += $ins.ExecuteNonQuery()
    }
    Write-Output ("sheet_rows: " + $count)
} finally {
    $conn.Close()
}
```

`core/cdm_db.py` (obok `set_order_detail_material`):

```python
def set_selected_sheets(job_name: str, sheets: list[dict[str, Any]]) -> bool:
    """Replace AM_SelectedSheets for a job (group selection); True when inserted.

    ``sheets`` = ``[{"id": int, "quantity": int}, ...]``. Empty list is rejected
    (an empty selection makes AM processing hang).
    """
    if not sheets:
        raise RuntimeError("cdm: set_selected_sheets requires at least one sheet")
    spec = ",".join(f"{int(s['id'])}:{int(s.get('quantity') or 0)}" for s in sheets)
    script_path = os.path.join(_scripts_dir(), "vdb5_set_selected_sheets.ps1")
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path,
             f"-JobName:{job_name}", f"-Sheets:{spec}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=20, check=False,
        )
    except Exception as e:
        logger.warning("cdm selected sheets: vdb5 update failed: %r", e)
        return False
    if proc.returncode != 0:
        logger.warning("cdm selected sheets: vdb5 update failed: %s", proc.stdout.strip())
        return False
    match = re.search(r"(?m)^sheet_rows:\s*(\d+)", proc.stdout)
    return bool(match and int(match.group(1)) > 0)
```

> **Uwaga VistaDB:** `$values`/`$Values` case-insensitivity i `param([string])` + `-split` już raz spowodowały bug (zob. `vdb5_set_has_drilling.ps1`). Tu używamy `$pair`/`$parts`/`$count` — brak kolizji z `$JobName`/`$Sheets`.

**Step 4: Run test to verify it passes**
Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/vdb5_set_selected_sheets.ps1 src/alphacam_cli/core/cdm_db.py tests/unit/test_cdm_db.py
git commit -m "feat(cdm): set_selected_sheets (AM_SelectedSheets group write)"
```

### Verification
1. ruff/mypy, 2. `pytest tests/unit/test_cdm_db.py -q`, 3. Error handling: puste wejście → RuntimeError; job nie istnieje → `sheet_rows: 0` (False). 4. Kaizen: spójny wzorzec z pozostałymi `vdb5_*`.

---

## Task 4: Application — integracja `material_group` w import (i create)

**Files:**
- Modify: `src/alphacam_cli/core/application.py` (`import_cdm_csv:1086`, `_import_cdm_csv_mapped:1142`, `create_cdm_job:671`, `import_cdm_preview:1323`)
- Test: `tests/unit/test_application.py`

**Step 1: Write the failing tests**

```python
def test_import_material_group_sets_zero_detail_and_selected(monkeypatch):
    # mock _resolve_import_setting, read_cdm_csv, parse_cdm_rows_mapped, get_cdm_automation_manager
    # assert: cdm_db.set_selected_sheets called with resolved group;
    #         cdm_db.set_order_detail_material called with 0;
    #         cdm_db.set_job_material called with 0;
    #         result["material"] == "MDF_18 (group)"
    ...
```

(oraz test: `--material` i `--material-group` razem → RuntimeError; grupa nieznana → RuntimeError).

**Step 2: Run tests to verify they fail**
Run: `python -m pytest tests/unit/test_application.py -k "material_group" -v`
Expected: FAIL.

**Step 3: Implementacja (kluczowe fragmenty)**

Sygnatury — dodaj `material_group: str | None = None`, `sheets: str | None = None`:

```python
def import_cdm_csv(self, csv, job=None, name=None, config=None, separator=None,
                   has_header=False, material=None, material_group=None, sheets=None,
                   import_setting=None, preview=False) -> dict[str, Any]:
    if material and material_group:
        raise RuntimeError("cdm: --material and --material-group are mutually exclusive")
    if material_group and sheets:
        raise RuntimeError("cdm: --material-group and --sheets are mutually exclusive")
    ...
```

W `_import_cdm_csv_mapped` (po obliczeniu `material_id`), rozgałąź grupowa:

```python
group_sheets: list[dict[str, Any]] | None = None
group_label: str | None = None
if material_group:
    group_sheets = cdm_db.resolve_material_group(material_group, quantity=None)
    group_label = f"{material_group} (group: " + ", ".join(
        f"{s['name']}#{s['id']} x{s['quantity']}" for s in group_sheets) + ")"
elif sheets:
    parsed = _parse_sheets_spec(sheets)          # helper: "2:0,7:1" -> [{id,quantity}]
    valid_ids = {s["id"] for grp in cdm_db.material_groups().values() for s in grp}
    bad = [s["id"] for s in parsed if s["id"] not in valid_ids]
    if bad:
        raise RuntimeError(f"cdm: unknown sheet id(s): {bad}")
    group_sheets = parsed
    group_label = f"sheets: {sheets}"
```

Po `SaveToDatabase`/utworzeniu joba i zapisie detali — zamiast pojedynczego materiału:

```python
if group_sheets is not None:
    if not cdm_db.set_job_material(job_name, 0):
        errors.append(f"job {job_name}: failed to clear job material")
    if not cdm_db.set_order_detail_material(job_name, 0):
        errors.append(f"job {job_name}: failed to clear order detail material")
    if not cdm_db.set_selected_sheets(job_name, group_sheets):
        errors.append(f"job {job_name}: failed to set selected sheets")
    if not cdm_db.finalize_cdm_job(job_name):
        errors.append(f"job {job_name}: failed to finalize job")
    material_label = group_label
elif material_id is not None:
    ... (dotychczasowa ścieżka)
```

> **Kolejność:** `AM_SelectedSheets` zapisywać PO utworzeniu joba; `finalize_cdm_job` (INSERT…WHERE NOT EXISTS) nie nadpisze istniejących wierszy. Gdy `AM_SelectedSheetDefaults` są puste (stan obecny) finalize dorzuci 0 wierszy — bezpieczne.

`create_cdm_job`: dodać `material_group`/`sheets` → analogicznie (dla pustego joba zapisać selected sheets + `fkMaterialID=0`; detale dodawane później importem `--job`).

`import_cdm_preview`: rozpoznać grupę i zwrócić `"material_group": {name, sheets:[...]}` (bez zapisu).

**Step 4: Run tests to verify they pass**
Expected: PASS (nowe + istniejące import tests).

**Step 5: Commit**

```bash
git add src/alphacam_cli/core/application.py tests/unit/test_application.py
git commit -m "feat(cdm): material_group in import/create (AM_SelectedSheets + fkMaterialID=0)"
```

### Verification
1. ruff/mypy `core/application.py`. 2. `pytest tests/unit/test_application.py -q`. 3. Error handling: konflikt flag (exit 2 na CLI), nieznany sheet id → RuntimeError. 4. Security: brak SQL z wejścia użytkownika (tylko inty). 5. Kaizen: helper `_parse_sheets_spec`, DRY.

**Report:** files, pre-existing errors, new issues, decisions.

---

## Task 5: Gateway RPC — parametry `material_group`/`sheets`

**Files:**
- Modify: `src/alphacam_cli/gateway/server.py` (`_handler_cdm_import_csv:833`, `_handler_cdm_import_preview:875`, `_handler_create_cdm_job`)
- Modify: `src/alphacam_cli/gateway/client.py`, `src/alphacam_cli/gateway/remote.py`
- Modify: `docs/gateway.md`
- Test: `tests/unit/test_gateway_server.py`, `tests/unit/test_remote.py`

**Step 1: Write the failing tests** — handler przekazuje `material_group`/`sheets` do `import_cdm_csv`; klient/remote serializują param; konflikt walidowany po stronie serwera (lub delegowany).

**Step 2: Run** `pytest tests/unit/test_gateway_server.py tests/unit/test_remote.py -k "material_group" -v` → FAIL.

**Step 3: Implementacja** — dodać `material_group = str(params.get("material_group") or "").strip() or None`, `sheets = str(params.get("sheets") or "").strip() or None`; przekazać dalej; zaktualizować tabele RPC w `docs/gateway.md` (`import_cdm_csv`, `create_cdm_job`).

**Step 4: Run** → PASS.

**Step 5: Commit** `feat(cdm): material_group over RPC`.

### Verification
1. ruff/mypy `gateway`; 2. `pytest tests/unit/test_gateway_server.py tests/unit/test_remote.py -q`; 3. Error handling/transport; 4. Kaizen: brak duplikacji.

---

## Task 6: CLI — opcje `--material-group` / `--sheets`

**Files:**
- Modify: `src/alphacam_cli/cli/cdm.py:222` (`import_csv`) + `create` (linia 40)
- Test: `tests/unit/test_cli_cdm.py`

**Step 1: Write the failing tests** — `import` z `--material-group MDF_18` wywołuje `ac.import_cdm_csv(material_group="MDF_18", material=None)`; `--material` + `--material-group` → exit 2; output zawiera „Group: …".

**Step 2: Run** `pytest tests/unit/test_cli_cdm.py -k material_group -v` → FAIL.

**Step 3: Implementacja**

```python
material_group: str | None = typer.Option(
    None, "--material-group",
    help="Nest on ALL sheets of this material group (sheet database name), nester picks by config",
),
sheets: str | None = typer.Option(
    None, "--sheets", help="Explicit sheets 'id:qty,id:qty' (mutually exclusive with --material-group)",
),
```

Walidacja (exit 2) dla kombinacji; przekazanie do `ac.import_cdm_csv(...)`; w podsumowaniu: `Group: <label>`. Zaktualizować `create` analogicznie.

**Step 4: Run** → PASS.

**Step 5: Commit** `feat(cdm): --material-group CLI option`.

### Verification
1. ruff/mypy `cli/cdm.py`; 2. `pytest tests/unit/test_cli_cdm.py -q`; 3. UX/exit codes (0/1/2); 4. Kaizen.

---

## Task 7 (opcjonalny, ryzykowny): `--sheet-order best|picked`

**Files:** `scripts/vdb5_set_sheet_order.ps1` (nowy), `core/cdm_db.py`, `core/application.py`, `cli/cdm.py`, `docs/gateway.md`, testy.

- `Nesting_SheetOrderType` jest **per konfiguracja** (`AM_ConfigurationSettings`) — zmiana wpływa na WSZYSTKIE joby tej konfiguracji. Wymagany jawny komunikat/warning i przywracanie. **Domyślnie nie ruszać.**
- `best` → 0, `picked` → 1. Zapis przez skrypt z `-ConfigName`/`-Value`; zwrócić poprzednią wartość.
- Oznaczyć jako P2; zaimplementować tylko po akceptacji użytkownika (może pozostać poza v1).

### Verification
1. ruff/mypy; 2. testy; 3. **live**: potwierdzić że 0 vs 1 zmienia wybór arkusza (grupa), potem przywrócić.

---

## Task 8: Testy jednostkowe — pełny przebieg

**Files:** `tests/unit/test_cdm_db.py`, `test_application.py`, `test_cli_cdm.py`, `test_gateway_server.py`, `test_remote.py`

**Steps:** uruchom i uzupełnij brakujące przypadki: konflikt flag, nieznana grupa, grupa z 1 arkuszem, `--sheets` z nieznanym id, preview grupy, gateway round-trip.
Run: `python -m pytest -q`
Expected: wszystko zielone, 0 regresji.

**Commit** `test(cdm): material group coverage` (jeśli dopisane).

### Verification
1. `ruff format --check src tests && ruff check src tests`; 2. `mypy src`; 3. `python -m pytest -q`; 4. Kaizen.

---

## Task 9: E2E na VM125 — grupa działa

**Files:** próba live (skrypty w `C:\temp`, nie w repo); wynik do `tasks.md`.

**Preflight:** `connect info`; `cdm stock list` (MDF_18 = 2 arkusze). Backup: zapisz `AM_SelectedSheets`, `AM_JobDetails.fkMaterialID`, `CDM_OrderDetails` dla użytych jobów.

**Kroki:**
1. `cdm import <csv> --name "E2E Grp CLI 01" --material-group MDF_18` → OK, „Group: …".
2. Weryfikacja DB: `CDM_OrderDetails.fkMaterialID = 0`; `AM_SelectedSheets` = {2, 7}.
3. `cdm process "E2E Grp CLI 01"` → Sukces; manifest: **oba** arkusze (`MDF_18 2440×1220` + `MDF18 2800×2070`), wszystkie części zanestowane, 0 unmatched.
4. (jeśli T7) `--sheet-order picked` → wybór wg kolejności; przywróć.
5. Test negatywny: `--material-group NIE_MA` → czytelny błąd, **bez HANG**.
6. Sprzątanie: `cdm delete`; usuń katalog wyjściowy, offcuty (`stock offcut-delete`), CSV; przywróć DB do stanu sprzątania; `cdm jobs` = 10; `stock list` MDF_18 = 2 whole / 17mm = 1 whole.

**Uwaga:** po zawieszonym `cdm process` reset: `taskkill /F /IM Acam.exe` → `sc stop AlphaCAMGateway` → 10s → `sc start AlphaCAMGateway` → ~55s.

### Verification
Zapisz surowe manifesty/DB; potwierdź że grupa headless działa i walidacja chroni przed HANG.

---

## Task 10: Ustalenie domyślnego `Quantity` (E2E) + dopięcie

**Cel:** potwierdzić semantykę `AM_SelectedSheets.Quantity` (0 = brak limitu? czy liczba arkuszy?), by dobrać domyślną wartość w `resolve_material_group`.
**Kroki:** job grupy z `--sheets 2:0,7:0` i z `--sheets 2:5,7:5`; porównaj liczbę użytych arkuszy w manifeście. Wybierz domyślną (prawdopodobnie 0) i udokumentuj. Zaktualizuj `resolve_material_group`/CLI help.

### Verification
Dowód z manifestów; brak regresji; commit `fix(cdm): default group sheet quantity`.

---

## Task 11: Dokumentacja + tasks.md

**Files:** `README.md`, `docs/gateway.md`, `tasks.md`.

- README: sekcja `cdm import` — `--material-group` (grupa = wiele arkuszy; nester wybiera wg konfiguracji), ostrzeżenie o HANG przy błędnym arkuszu, że `--material` = pojedynczy arkusz.
- `docs/gateway.md`: parametry RPC.
- `tasks.md`: oznaczyć TODO grupy jako zrobione; nowe lekcje (mechanizm IL, HANG, Quantity).

### Verification
Dokumentacja spójna z kodem; brak haseł/ścieżek maszynowych w README poza dozwolonymi.

---

## Decyzje projektowe (zaktualizowane po E2E offcutów, 2026-10-09)

- **`--material-group NAME`** = wybór grupy; CLI enumeruje arkusze materiału do `AM_SelectedSheets` i pozwala **AlphaCAMowi zdecydować** (`Nesting_SheetOrderType`). Domyślnie: **tylko całe arkusze** (`offcut=0`).
- **`--include-offcuts`** (bool) = do grupy dołącz także offcuty materiału (`offcut=1`). Bez tego offcuty NIE są kandydatami (nie są auto-dodawane).
- **`--sheet-order best|picked`** (opcjonalne): `best`=0 (AlphaCAM wybiera najlepsze wypełnienie), `picked`=1 (kolejność listy).
- **Quantity domyślnie = 0** (brak limitu — bezpieczniej niż za mały limit, który powoduje crash `0x800ADF09`).
- `resolve_material_group(name, include_offcuts=False, quantity=None)` — filtruje `offcut` i opcjonalnie zwraca offcuty (bez potrzeby geometrii, wystarcza `id`).
- `stock list`/resolver muszą tolerować offcuty z `width=height=0` (geometria w `shape`) — nie używać W/H offcuta do niczego poza prezentacją.

### PRZEPIS GWARANTUJĄCY ZUŻYCIE OFFCUTÓW NAJPIERW (ZWERYFIKOWANE E2E 2026-10-09)
1. `CDM_OrderDetails.fkMaterialID = 0` oraz `AM_JobDetails.fkMaterialID = 0` (ścieżka grupowa).
2. `AM_SelectedSheets(fkJobDetailID, SelectedSheetID, Quantity)`:
   - **offcuty PIERWSZE**, każdy `Quantity = 1` (liczba fizycznych sztuk offcutu),
   - **całe arkusze NA KOŃCU**, każdy `Quantity = 0` (bez limitu — przejmą resztę zamówienia).
3. `Nesting_SheetOrderType = 1` (**Picked Order**).

Efekt (E2E C1/C5): offcuty wypełniane po kolei i w całości, dopiero potem pełny arkusz.

**Czego NIE używać:**
- **Best Utilisation (0) NIE gwarantuje** — dla zamówienia na 10 części pominął offcuty i wybrał pełny arkusz (optymalizuje liczbę/wypełnienie arkuszy, nie „małe najpierw"). Nadaje się tylko, gdy chcemy globalne optimum, nie zużycie offcutów.
- `Quantity = 0` **dla offcutu** jest błędne (nieskończone kopie TYPU arkusza, nie konkretnej sztuki) — offcuty zawsze `Quantity = 1`.
- `Quantity ≥ 1` przy niedoborze → crash `0x800ADF09`.

**Ważne:** nesting **nie usuwa** zużytych offcutów z `sheet_database_v2.db` — i **nasze narzędzie tego NIE robi** (to byłby przepływ pracy, poza zakresem). Zużyte offcuty kasuje operator lub osobny, samodzielny blok `stock offcut-delete`, wywołany przez aplikację zewnętrzną.

**Konfiguracja `Nesting_SheetOrderType` jest GLOBALNA (per konfiguracja AM).** Ustawienie „picked" dotyczy wszystkich jobów tej konfiguracji → opcja CLI musi ostrzegać, a docelowo rozważyć dedykowaną konfigurację (np. „Fronty (offcuts)").

### Nowa opcja wygody: `--prefer-offcuts` (= nazwa robocza)
Realizuje powyższy przepis jednym przełącznikiem w obrębie bloku importu (BEZ żadnego przetwarzania po fakcie): `--material-group NAME --prefer-offcuts` →
- kolejność `AM_SelectedSheets` = najpierw offcuty (`Quantity=1`), potem całe arkusze (`Quantity=0`),
- wymusza `sheet-order=picked` (z warningiem o globalnym wpływie).
- **NIE usuwa offcutów** — to zadanie operatora/osobnego bloku.

## Risks & Decisions

- **HANG zamiast błędu:** brak/nieistniejący `SelectedSheetID` lub puste `AM_SelectedSheets` przy `fkMaterialID=0` zawiesza AM (modalny `QuickMessageExclamation` w Session 0). Mitygacja: walidacja w T2/T4 + twarde błędy.
- **Konflikt ścieżek:** detal `≠0` + wiele wierszy selected → zepsuty nest. Mitygacja: w trybie grupy wymuszamy `fkMaterialID=0` na jobie i detalach.
- **`--sheet-order` globalny:** `Nesting_SheetOrderType` dotyczy całej konfiguracji; domyślnie nie ruszamy; opcja P2 z warningiem.
- **Semantyka `Quantity`:** do potwierdzenia (T10); domyślnie ostrożnie (0 = brak limitu, jeśli potwierdzone).
- **`finalize_cdm_job` (WHERE NOT EXISTS):** uruchamiać PO zapisie `AM_SelectedSheets` (nie nadpisze). Puste `AM_SelectedSheetDefaults` (stan obecny) → 0 dodanych wierszy.
- **Zgodność wsteczna:** `--material` bez zmian; `sheet_materials()` bez zmian.

## Non-goals

- **Bez usuwania/konsumowania offcutów z bazy** — żadnego auto-cleanup po procesie; narzędzie tylko przygotowuje wybór arkuszy, nie prowadzi przepływu.
- Bez nowych komend „end-to-end"; bez zmiany niskopoziomowego nesting API (`nest run`).
- Bez modyfikacji `sheet_database_v2.db` w repo.
- Bez obsługi per-wierszowej grupy w CSV (jeden materiał/grupa na import; per-element `fkMaterialID` można ustawiać w DB osobno — przyszły kaizen).
