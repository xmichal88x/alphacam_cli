# From Job material + material-group in `cdm create` — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement task-by-task.

**Goal:** (1) `cdm import --job` bez jawnego materiału ma zachować materiał joba (semantyka GUI „From Job"), a nie nadpisywać go domyślnym z bazy; (2) `cdm create` ma obsługiwać grupy materiału (`--material-group/--include-offcuts/--prefer-offcuts/--sheets/--sheet-order`) tak jak `cdm import`.

**Architecture:** Rozstrzyganie materiału przenieść na etap importu z priorytetem: jawne (`--material`/`--material-group`/`--sheets`) > materiał joba (gdy `--job`, bez jawnego) > domyślny z bazy (nowy job). W trybie grupy job/detale mają `fkMaterialID=0` + wiersze `AM_SelectedSheets`. `cdm create` w trybie grupy ustawia 0 + selected sheets + (opcjonalnie) `Nesting_SheetOrderType`.

**Tech Stack:** Python 3.11/Typer, PowerShell+VistaDB (`scripts/vdb5_*.ps1`), SQLite (`sheet_database_v2.db`), gateway JSON-RPC, VM125.

---

## Zakres

- **Nie łamać** ścieżek jawnych (`--material`, `--material-group`) ani tworzenia nowego joba (domyślny materiał z bazy).
- **From Job** dotyczy tylko `cdm import --job` bez jawnego materiału/grupy.
- **Job grupowy** (`fkMaterialID=0` + `AM_SelectedSheets`): import bez materiału **zachowuje grupę** (detale 0, nie rusza `AM_SelectedSheets`).
- **Narzędzie, nie przepływ:** brak usuwania offcutów; brak przywracania konfiguracji.

## Fakty (zweryfikowane)
- `AM_JobDetails.fkMaterialID` = materiał joba; `CDM_OrderDetails.fkMaterialID` = materiał pozycji; 0 → ścieżka grupy (pusta `AM_SelectedSheets` = HANG).
- Obecnie `_import_cdm_csv_mapped` (application.py ~1240, ~1386-1392) zawsze ustawia job+detale na rozwiązany `material_id` (jawny/domyślny z `vdb5_job_defaults`), nadpisując materiał joba.
- `create_cdm_job` (application.py 671-829) wymaga materiału (jawnego lub domyślnego); brak grupy.
- Helper walidacji `_validate_group_options` już istnieje w `application.py`.

---

## Task A1: `cdm_db.job_material_id()` + skrypt

**Files:** Create `scripts/vdb5_job_material.ps1`; Modify `src/alphacam_cli/core/cdm_db.py`; Test `tests/unit/test_cdm_db.py`.

**Step 1 (test, TDD):** monkeypatch `subprocess.run` → `job_material_id("J")` parsuje `material: 7` → `7`; puste/rc≠0/wyjątek → `None`.

**Step 3 (impl):** skrypt: `param([string]$JobName)`; escapuj `'`; `SELECT fkMaterialID FROM AM_JobDetails WHERE JobName='<esc>'`; `Write-Output ("material: " + $val)`. Funkcja:
```python
def job_material_id(job_name: str) -> int | None:
    """fkMaterialID of a job (AM_JobDetails); None when missing/read fails."""
```
uruchamia skrypt (`-JobName:`), przy błędzie `logger.warning` + `None`; parse `^material:[ \t]*(-?\d+)` → int, puste → None.

**Verification:** ruff + mypy `cdm_db.py`; `pytest tests/unit/test_cdm_db.py -q`.

## Task A2: „From Job" w `_import_cdm_csv_mapped`

**Files:** Modify `src/alphacam_cli/core/application.py`; Test `tests/unit/test_application.py`.

Rozstrzygnięcie (nietryb grupowy):
1. `material_name = _cdm_material_name(details, material)` (jawne/CSV) → `material_source="explicit"`, `material_id=materials[name]`.
2. else jeśli `job`: `job_mat = cdm_db.job_material_id(job_name)`:
   - `None` → `material_source="database-default"`, `material_id=defaults["material_id"]`, warning.
   - `==0` → `material_source="job-group"` (bez `material_id`).
   - `>0` → `material_source="job"`, `material_id=job_mat`.
3. else (nowy job) → `"database-default"`, `material_id=defaults["material_id"]`.

Zastosowanie (po detalach):
- `group_sheets is not None` → bez zmian.
- `"job-group"` → `set_order_detail_material(job,0)`; **NIE** `set_job_material`; nie ruszać `AM_SelectedSheets`; `material_label="from job (group)"`.
- `"job"` → `set_order_detail_material(job, material_id)`; **NIE** `set_job_material`; `material_label=<nazwa id>`.
- `"explicit"`/`"database-default"` → jak dziś (`set_job_material` + `set_order_detail_material`).
- Brak materiału i brak fallback → warning „no material set".
Wynik: dodaj `"material_source"`.

**Testy:** job z materiałem (bez `--material`) → brak `set_job_material`, `set_order_detail_material(job, jobmat)`, źródło `job`; job=0 → źródło `job-group`, `set_order_detail_material(job,0)`, brak `set_job_material`; brak odczytu → fallback DB + warning; nowy job → DB default (regresja bez zmian); jawny `--material` → nadpisuje (regresja).
**Verification:** ruff/mypy `application.py`; `pytest tests/unit/test_application.py -q`.

## Task B1: grupa w `create_cdm_job`

**Files:** Modify `src/alphacam_cli/core/application.py`; Test `tests/unit/test_application.py`.

Sygnatura: dodaj keyword `material_group=None, include_offcuts=False, prefer_offcuts=False, sheets=None, sheet_order=None`.
- Wywołaj `_validate_group_options(material, material_group, sheets, include_offcuts, prefer_offcuts, sheet_order)`.
- Rozwiąż `group_sheets`/label (jak w imporcie: `prefer_offcuts` → `include_offcuts=True, offcuts_first=True`, `effective_sheet_order="picked"`).
- Materiał: gdy tryb grupowy — nie wymagaj materiału; `material_label` = label grupy. Inaczej dotychczas.
- Po `SaveToDatabase`: tryb grupowy → `set_job_material(job,0)` → `finalize_cdm_job(job)` → `set_selected_sheets(job, group_sheets)` → opcjonalnie `set_sheet_order(config_name, 0/1)` (+warning) ; każdy błąd krytyczny → cleanup+raise (jak dziś). Bez grup → dotychczas.
- Wynik: `material` = label grupy; dodaj `material_group` (label) i `material_source` jeśli sensownie.

**Testy:** create z `--material-group` → `resolve_material_group`, `set_job_material(job,0)`, `set_selected_sheets`, `finalize`; `--prefer-offcuts` → offcuts_first + `set_sheet_order(cfg,1)` + warning; walidacje (material+group, prefer bez grupy, prefer+best).
**Verification:** ruff/mypy; `pytest tests/unit/test_application.py -q`.

## Task B2: RPC `create_cdm_job`

**Files:** Modify `gateway/server.py` (`_handler_create_cdm_job`), `gateway/client.py`, `gateway/remote.py`, `docs/gateway.md`; Test `tests/unit/test_gateway_server.py`, `test_remote.py`.

Dodaj parametry `material_group, include_offcuts, prefer_offcuts, sheets, sheet_order` (jak dla importu) i przekaż do `create_cdm_job`.
**Verification:** ruff/mypy; `pytest tests/unit/test_gateway_server.py tests/unit/test_remote.py -q`.

## Task C: CLI `cdm create`

**Files:** Modify `src/alphacam_cli/cli/cdm.py` (`create`); Test `tests/unit/test_cli_cdm.py`.

Dodaj opcje `--material-group/--include-offcuts/--prefer-offcuts/--sheets/--sheet-order` (+ te same walidacje CLI co w imporcie, `Exit(2)`), przekaż do `ac.create_cdm_job`. Wynik: gdy `material_group` → linia `Group:` (bez duplikatu `Material:`).
**Verification:** ruff/mypy; `pytest tests/unit/test_cli_cdm.py -q`.

## Task D: Docs + tasks.md

**Files:** `README.md` (sekcja `create` + `import` — semantyka From Job), `docs/gateway.md`, `tasks.md`.
- README: opisać „From Job" (import `--job` bez materiału = materiał joba), oraz `create` z opcjami grupy.

## Task E: E2E na VM125

- Sync `src`+`scripts` na VM (tar+scp), restart gateway.
- E2E-1 (From Job): `cdm create J --material MDF_18` → `cdm import csv --job J` (bez materiału) → job/detale = MDF_18 (nie domyślny z bazy gdy różny); potwierdź brak nadpisania.
- E2E-2 (create group): `cdm create J2 --material-group MDF_18 --prefer-offcuts` → DB: job=0, `AM_SelectedSheets` offcuts-first Q=1 + całe Q=0, config `SheetOrderType=1` → `cdm import csv --job J2` (bez materiału) → grupa zachowana (detale 0, selected niezmienione) → `cdm process` → offcuty pierwsze.
- Negatywne: brak HANG; sprzątanie.

## Task F: code-reviewer + poprawki + pełna bramka.

---

## Risks
- **Odczyt materiału joba zawiedzie** → fallback DB + warning (nie cichy HANG). 
- **`--job` bez materiału, job bez materiału (0) i brak selected sheets** → HANG; ale to stan przed importem; nasza ścieżka „job-group" nie pogarsza (zachowuje existing selected). 
- **Regresja create** — tylko dla nowych opcji grupowych; brak grup = dotychczas.
