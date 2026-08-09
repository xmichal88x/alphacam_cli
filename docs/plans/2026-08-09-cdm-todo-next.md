# CDM TODO-next Implementation Plan

> **For agents:** Implement tasks one by one (1 task = 1 subagent). Exact paths below. After each task: `ruff check src tests && mypy src && pytest tests/unit -q` (ruff format check, mypy, tests must pass).

**Goal:** Dokończyć CDM: import CSV headless, pełne `cdm types` (vdb5), `cdm delete`, sprzątanie server.py, README, E2E na maszynie.

**Architecture:** Rozszerzenie handlerów RPC (server.py `_handler_*` + `_dispatch`) i warstwy core/remote/client/CLI dla CDM. Odczyt VistaDB przez PowerShell subprocess (bez COM). E2E przez SSH/gateway na laptop-monika.

**Tech Stack:** Python 3.11 (typer, win32com), PowerShell + VistaDB.5.NET40.dll, pytest.

**Kontekst (fakty z raportu Session 0, NIE łamać):**
- Handler RPC działa w wątku STA serwera — NIE tworzyć wątków roboczych ani drugiego `_com_call` (deadlock).
- Używać `GetAutomationManagerAddInGUI()` — `_cdm_automation_manager()` w server.py już to robi.
- `job.Process()` i `ImportCSVToJob(path, None)` WISZĄ w Session 0 (dialogi). Import działa tylko z poprawnym `ImportSettings` — weryfikacja E2E.
- Baza: `C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5`, tabela `CDM_DoorTypes` ("Typ Frontu 1".."47", "L_B_10mm" itd.).
- VistaDB DLL: `C:\Program Files\Hexagon\ALPHACAM 2025\VistaDB.5.NET40.dll`.
- `str()` na obiektach COM wywołuje default method → zawsze `repr()`.
- Aktualnie: ruff 0, mypy 0, 428 passed. Komunikaty CLI po angielsku.
- Odczytać wzorce istniejących handlerów `_handler_run_cdm`/`_handler_cdm_jobs` (server.py:1114-1205) i metod `run_cdm`/`cdm_jobs` (application.py:473-554) — nowe metody mają je naśladować.

---

## Task 1: `cdm import` — import CSV do joba CDM (headless)

**Files:**
- Modify: `src/alphacam_cli/gateway/server.py` — `_handler_cdm_import_csv` (po `_handler_cdm_jobs`)
- Modify: `src/alphacam_cli/core/application.py` — `import_cdm_csv` (po `cdm_jobs`)
- Modify: `src/alphacam_cli/gateway/client.py` — `RemoteSession.import_cdm_csv` (po `cdm_jobs`)
- Modify: `src/alphacam_cli/gateway/remote.py` — `RemoteApplication.import_cdm_csv` (po `cdm_jobs`)
- Modify: `src/alphacam_cli/cli/cdm.py` — komenda `import`
- Test: `tests/unit/test_gateway_server.py`, `tests/unit/test_remote.py`, `tests/unit/test_cli_cdm.py`

**Spec RPC `cdm_import_csv`** (params: `csv` wymagany — ścieżka Windows na serwerze; `job_name` opcjonalny; `separator` default `,`; `has_header` default True):
1. Brak `csv` → `COMError("cdm: csv path is required")`.
2. `am = self._cdm_automation_manager()` (błędy → `COMError("cdm: automation manager unavailable: ...")`).
3. Job: gdy `job_name` → przeszukać `am.Jobs` (1..Count) po `JobName`; brak → `COMError("cdm: job not found: <name>")`. Gdy brak `job_name` → `am.NewCDMJob()`, `JobName` = basename pliku bez rozszerzenia (≤60 znaków), `SaveToDatabase()`.
4. ImportSettings (defensywnie, każdy krok w try/except):
   - `settings = am.NewImportSetting()` jeśli `hasattr`; potem ustawić pola po nazwach (każde w try/except): `Separator`, `Delimiter`, `HeaderRow`, `FirstRowIsHeader`, `HasHeader`, `SkipFirstRow` (separator z params, header wg `has_header`).
   - Fallback: `am.ImportSettings.Item(1)` gdy Count>0; inaczej `None`.
5. `ok = job.ImportCSVToJob(csv, settings)` → `{"success": bool(ok), "job_name": ..., "csv": csv}`.
6. Błędy COM → `COMError("cdm: import csv failed: ...")`.

Core `import_cdm_csv` — lokalny odpowiednik wg wzorca `run_cdm` z application.py (używa `get_automation_manager_addin()`), ta sama logika.

CLI `cdm import CSV [--job NAME] [--separator ","] [--no-header]` → `OK: CDM job updated: <job>` lub `OK: CDM job created: <job>` + `Imported: <csv>`.

Testy: mock COM wzorowany na `_mock_cdm_com` (test_gateway_server.py:1005); przypadki: nowy job z nazwy pliku, istniejący job po nazwie, job not found, brak csv, NewImportSetting nie istnieje → fallback Item(1), błąd COM → czytelny komunikat. test_remote: delegacja params. test_cli_cdm: wywołanie komendy + output.

**Verify:** ruff + mypy + pytest; commit `feat: cdm import (CSV to job, headless ImportSettings)`.

---

## Task 2: `cdm types` pełne — odczyt CDM_DoorTypes z vdb5

**Files:**
- Create: `scripts/vdb5_door_types.ps1`
- Modify: `src/alphacam_cli/gateway/server.py` — rozszerzyć `_handler_cdm_types`
- Test: `tests/unit/test_gateway_server.py`

**Spec:**
1. Skrypt PowerShell `scripts/vdb5_door_types.ps1`: Add-Type VistaDB.5.NET40.dll → open `Data Source=C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5` → `SELECT * FROM CDM_DoorTypes` → wyjście JSON: linia `{"types":[{"id":N,"name":"..."}]}` na stdout (nazwa = kolumna TypeName lub Name — wykryć kolumnę defensywnie: pierwsza kolumna string). Bez echo, tylko JSON na stdout.
2. `_handler_cdm_types`: najpierw istniejąca logika COM (types z jobów). Następnie subprocess `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\vdb5_door_types.ps1` (ścieżka skryptu: obok repo — użyć `os.path.dirname(__file__)` → `../../../scripts`), timeout ~20s, parse JSON. Merge: lista z vdb5 (pełna) + z jobów (dedupe po nazwie). Gdy subprocess błąd → zwrócić COM-listę + `note` o fallbacku. Gdy oba puste → jak teraz ("no CDM jobs...").
3. Testy: mock `subprocess.run` (json) → typy z vdb5; subprocess fail → fallback COM; dedupe.

**Verify:** ruff + mypy + pytest; commit `feat: cdm types reads CDM_DoorTypes from VistaDB`.

---

## Task 3: `cdm delete` — usuwanie joba CDM

**Files:**
- Modify: `src/alphacam_cli/gateway/server.py` — `_handler_cdm_delete_job`
- Modify: `src/alphacam_cli/core/application.py` — `delete_cdm_job`
- Modify: `src/alphacam_cli/gateway/client.py`, `gateway/remote.py` — delegacje
- Modify: `src/alphacam_cli/cli/cdm.py` — komenda `delete`
- Test: test_gateway_server.py, test_remote.py, test_cli_cdm.py

**Spec RPC `cdm_delete_job`** (params: `job_name` wymagany):
1. Brak → `COMError("cdm: job_name is required")`.
2. Znaleźć job w `am.Jobs` po `JobName`; brak → `COMError("cdm: job not found: <name>")`.
3. `job.DeleteFromDB()` gdy `hasattr`; w przeciwnym razie `COMError("cdm: DeleteFromDB unavailable on job")`. Błąd → `COMError("cdm: delete job failed: ...")`.
4. Sukces → `{"success": True, "job_name": ...}`.

Core/CLI analogicznie (CLI: `cdm delete JOB_NAME` → `OK: CDM job deleted: <name>`).

**Verify:** ruff + mypy + pytest; commit `feat: cdm delete (job cleanup headless)`.

---

## Task 4: Sprzątanie server.py — usunąć probe

**Files:**
- Modify: `src/alphacam_cli/gateway/server.py`

**Spec:**
1. Usunąć w całości `_handler_cdm_probe` (linie ~845-1079).
2. Usunąć sekcję `_am_probe` z `_handler_probe_nest` (linie ~685-842: `_am_log`, wszystkie `out["am_*"]`, `out["agq_*"]`, `out["ara_*"]`, `astyles_apply_real` itd.) — zostawić resztę `_handler_probe_nest` (probe nest/stl) nietkniętą.
3. Po usunięciu NIE może zostać odwołań do `C:\temp\am_probe_gw.log` / `C:\temp\cdm_probe2.log`.
4. Nie usuwać `_cdm_automation_manager`, `_cdm_known_door_types`, `_handler_run_cdm/_handler_cdm_types/_handler_cdm_jobs`.
5. Upewnić się (grep), że żadne testy nie odwołują się do `_handler_cdm_probe`/`am_probe` (obecnie brak) → usunięcie bezpieczne.
6. Sprawdzić, czy `_handler_probe_nest` po usunięciu sekcji AM ma sens (usuń też nieużywane zmienne: `q_drw`, `raw_drw`, `astyles_any` itd. — zostaw tylko te używane przez pozostałą część).

**Verify:** ruff + mypy + pytest (pełny suite); commit `chore: remove cdm/am probe handlers from server.py`.

---

## Task 5: README — sekcja CDM

**Files:**
- Modify: `README.md`

**Spec:** Dodać sekcję `### \`alphacam cdm\`` w stylu istniejących sekcji (po `### \`alphacam autostyle apply\``, przed NC/nest — wg kolejności w pliku): opis komend `create`, `types`, `jobs`, `import`, `delete` + przykłady CLI (lokalnie i `--remote`), uwaga że `Process` wymaga GUI (Session 2). Styl zgodny z resztą README (markdown, przykłady kodu).

**Verify:** commit `docs: README cdm section`.

---

## Task 6: E2E na maszynie (główny agent, po Tasks 1-5)

SSH `48797@100.71.109.69` + RPC `--remote --host 100.71.109.69`:
1. git push → SSH `git pull` → `taskkill /F /IM Acam.exe` → `sc stop AlphaCAMGateway` → `sc start AlphaCAMGateway` → czekać ~40s.
2. scp testowy CSV (`Style,Width,Height,Qty,Material`) do `C:\temp\cdm_e2e.csv` → `cdm import` (z `--job` i bez) → sprawdzić `cdm jobs`.
3. `cdm types` → pełna lista (w tym typy bez jobów).
4. `cdm delete` na jobie testowym → `cdm jobs` (liczba spadła).
5. Probe `CreateJobsFromCSVFile` (czy wisi) → zapis do TASKS.md.
6. Usunąć logi `C:\temp\am_probe_gw.log`, `C:\temp\cdm_probe2.log` na maszynie.
7. Ewentualne fixy po E2E → subagent debugger.

## Task 7 (warunkowo, po E2E): `CreateJobsFromCSVFile` bulk — tylko jeśli E2E pokaże, że nie wisi.
