# CDM Improvements — Plan i Raport Wykonania (2026-08-09)

> Data: 2026-08-09 | Status: **zaimplementowane** (ruff 0, mypy 0, 529 passed) | E2E na maszynie: do wykonania (plan poniżej)

**Goal:** Doprowadzić CDM do pełnej używalności headless: import CSV do jobów (z walidacją przed utworzeniem), materiały z bazy/CSV, pełne `cdm types` z VistaDB, usunięcie nieaktualnej flagi `--process`, sprzątnięcie server.py, aktualizacja README.

**Kontekst:** Komendy CDM w `src/alphacam_cli/cli/cdm.py` (create/types/jobs/import/delete), handler RPC w wątku STA serwera (bez wątków roboczych). Baza: `C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5` (VistaDB 5). Import CSV do jobów nie wymaga GUI — wcześniejsza notka "requires GUI (Session 2)" była nieaktualna.

---

## Zmiany (wykonane)

### T1 — Wspólny moduł `core/cdm_db.py`
- Nowy moduł: `read_cdm_csv` (UTF-8 z BOM → CP1250, separator 1-znakowy), `parse_cdm_rows` (walidacja wierszy → details/errors), `sheet_materials` (nazwa materiału → ID z SQLite), `vdb5_job_defaults` (config + material z `AM_JobFileDefaults`), `set_job_material` (update `AM_JobDetails.fkMaterialID`), `vdb5_door_type_names`, `merge_door_types` (dedupe casefold), `find_cdm_job`.
- Używany wspólnie przez core `application.py` i gateway `server.py` (koniec duplikacji logiki).

### T2 — `cdm import` — read/parse CSV + walidacja przed utworzeniem
- `import_cdm_csv` (core) / `_handler_cdm_import_csv` (gateway): format `Style,Quantity,Width,Height,DesignDimensions[,Material]`; kolumna 6 (materiał) opcjonalna, nadpisuje default; `--material` nadpisuje wszystko.
- **parse-before-create:** wszystkie wiersze walidowane zanim job powstanie — przy wszystkich złych wierszach job NIE jest tworzony (exit 1, czytelne błędy per wiersz).
- Nowy job: nazwa z `--name` lub basename CSV (max 60), config z `--config` lub default z bazy; istniejący job przez `--job` (wzajemnie wykluczone z `--name`).

### T3 — `cdm create` — walidacja, duplikat, `--material`; usunięcie `--process`
- `run_cdm`: walidacja job_name/type_name (non-empty), width/length/quantity > 0, duplikat nazwy joba → czytelny błąd `cdm: job already exists: <name>`.
- `--material` (nazwa z `AM_Materials`; brak w bazie → `cdm: material not found`), default materiału z `AM_JobFileDefaults`.
- Flaga `--process` USUNIĘTA (wymagała GUI, nie miała sensu headless).

### T4 — `cdm types` — pełna lista + logowanie
- Typy z bazy VistaDB (`CDM_DoorTypes` przez `scripts/vdb5_door_types.ps1`) + z jobów (COM), merge z dedupe (casefold) — `merge_door_types`.
- Fallback: gdy vdb5 nieczytelne → typy z jobów + `note` w wyniku; logowanie przez `logging` (brak stdout pollution).

### T5 — Dokumentacja
- `README.md`: sekcja CDM zaktualizowana (usunięto nieaktualne "requires GUI (Session 2)" i `--process`; opis aktualnych opcji create/import, format CSV, walidacja; przykład produkcyjny `--remote --host 100.71.109.69 cdm import`).

---

## Status weryfikacji

- `pytest tests/unit -q` → **529 passed** (4.61s)
- `ruff check src tests` → 0 issues
- `mypy src` → Success, no issues (37 files)

---

## Plan E2E — laptop-monika (pozostało do wykonania)

**Dostęp:** SSH `48797@100.71.109.69` (laptop-monika, Windows 11) + RPC `alphacam --remote --host 100.71.109.69` (gateway AlphaCAMGateway, port 8721).

1. `git push` → SSH: `git pull` → `taskkill /F /IM Acam.exe` → `sc stop AlphaCAMGateway` → `sc start AlphaCAMGateway` → czekać ~40 s.
2. scp testowy CSV (z kolumną 6 = materiał i bez niej) do `C:\temp\cdm_e2e.csv`.
3. Testy RPC:
   - `cdm import` z `--job` i bez (`--name`), sprawdzić `cdm jobs` (liczba pozycji).
   - `cdm import` ze złym CSV → exit 1, job nie utworzony.
   - `cdm create` duplikat nazwy → czytelny błąd; `--material` znany/nieznany.
   - `cdm types` → pełna lista (VistaDB + joby), `cdm delete` → `cdm jobs` (liczba spadła).
4. Ewentualne błędy E2E → subagent debugger; wyniki do `tasks.md`.
