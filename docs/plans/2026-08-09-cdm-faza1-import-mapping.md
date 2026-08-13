# Faza 1 — CDM Import z mapowaniem AM_ImportSettings — Plan wdrożenia

> **Data:** 2026-08-09 | **Maszyna testowa:** laptop-monika (AlphaCAM 2025 Router, gateway RPC Session 0, SSH 48797@100.71.109.69)
> **Źródło:** `docs/plans/2026-08-09-am-przemysl-4.0-raport.md` (sekcja 20, Faza 1) + `tasks.md`
> **Cel:** `cdm import` używa mapowania pól z bazy (AM_ImportSettings + AM_ImportSettingsParameter), ustawia nowe pola OrderDetails (klient, nr zamówienia, komentarz, oversize, rotation, custom fields), dodaje `--preview` (suchy import). Wszystkie taski kończone testami E2E na laptopie Monika + pętla /fixloop.

---

## Kontekst (stan obecny)

- `cdm import CSV [--name] [--config] [--job] [--separator] [--header] [--material]` — sztywny parser 5 kolumn: `Style,Qty,Width,Height,DesignDims[,Material]`; materiał z kol 6; **ignoruje mapowanie z bazy** (raport sekcja 11, P1).
- Baza `AutomationManager.vdb5`: `AM_ImportSettings` (id 3 "sklep CSV": DelimiterChar=`,`, IgnoreHeader=False, IsCDMImport=True, CreateJob=True, Selected=True; id 4 "Ustawienia Importu CSV 2"), `AM_ImportSettingsParameter` (kolumna `ParameterType` — NIE "Type"): id3 → kol1=256, kol2=259, kol3=257, kol4=258, kol5=264, kol6=524, kol7=512, kol8=513.
- Typy pól (enum z AcamAddIns.dll): **CDM**: 256=cdmDoorType, 257=cdmDoorWidth, 258=cdmDoorHeight, 259=cdmDoorQuantity, 260=cdmDoorMaterial, 261=cdmDoorCustomerName, 262=cdmDoorOrderNumber, 263=cdmDoorItemNumber, 264=cdmDoorDesignDimensions, 265=cdmDoorProductionComment, 266..290=cdmDoorCustomField1..25, 271=rotation, 272=angle, 274=nest priority, 298=drilling, 299=small nest; **JOB**: 512=jobName, 513=jobfkConfigID, 514=jobfkSetupID, 515=jobfkToolOrderID, 516=jobPurchaseOrderNumber, 517=jobWorkOrderNumber, 518=jobDescription, 519=jobProgrammerName, 520=jobOrderDate, 521=jobDueDate, 522=jobCustomer, 523=jobParentJob, 524=jobFkMaterialID.
- CDM_OrderDetails kolumny do ustawiania przez settery COM: CSV_CustomerName, CSV_OrderNumber, CSV_ItemNumber, ProductionComment, OversizeX, OversizeY, CornerRadius, RotationMethod, RotationAngle, NestingPriority, IgnoreOuterGeometry, SmallNestPart, HasDrilling, CDMCustomField1..25. **Nazwy setterów COM wymaga potwierdzenia** (Task 0 — reflection).
- Architektura: `core/cdm_db.py` (pure + subprocess ps1) współdzielony przez `core/application.py` (local) i `gateway/server.py` (remote); klient `gateway/client.py` → RPC `cdm_import_csv`; CLI `cli/cdm.py`; testy unit (pytest), ruff, mypy, PyInstaller `alphacam.spec` (datas scripts/).

---

## Zadania

### Task 0: RESEARCH — reflection setterów OrderDetail + dump AM_ImportSettings z vdb5 (na maszynie)

**Cel:** potwierdzić nazwy property/setterów COM na `IAutomationManagerOrderDetail` (dla nowych pól) oraz schemat/dane `AM_ImportSettings` + `AM_ImportSettingsParameter` z VistaDB.

**Pliki:** tylko skrypty diagnostyczne na maszynie (`C:\temp\`), NIC w repo.

**Kroki:**
1. SSH na laptop-monika; PowerShell reflection `AcamAddIns.dll` (wzorzec z tasks.md — enum `AutomationManagerImportSettingFieldType` odczytany przez reflection DLL): `Add-Type -Path 'C:\ALPHACAM\...\AcamAddIns.dll'` + wypisz nazwy property `IAutomationManagerOrderDetail` (getter+setter) oraz property `IAutomationManagerImportSetting` / `IAutomationManagerImportSettingField`.
2. VistaDB dump: `AM_ImportSettings` (SELECT *), `AM_ImportSettingsParameter` (SELECT *) przez `VistaDB.5.NET40.dll` (wzorzec vdb5_job_defaults.ps1).
3. Zapisać wyniki do `C:\temp\faza1_research\` i pobrać raport do sesji (cat przez SSH).

**Weryfikacja:** kompletna lista setterów detail (nazwa → typ), lista pól ImportSettings z kolumnami, potwierdzenie kolumny `ParameterType`.
**Subagent:** `general` (SSH + PowerShell, bez zmian w repo).

---

### Task 1: `scripts/vdb5_import_settings.ps1` + `scripts/vdb5_order_details.ps1`

**Cel:** odczyt ustawień importu (mapowanie kolumn) i dump pozycji joba z VistaDB → JSON (wzorzec `vdb5_job_defaults.ps1`).

**Pliki:**
- Create: `scripts/vdb5_import_settings.ps1` — SELECT z `AM_ImportSettings` + `AM_ImportSettingsParameter` (JOIN po ImportSettingID), JSON: `[{id, name, delimiter_char, sub_delimiter_char, ignore_header, is_cdm_import, create_job, selected, fields: [{column_number, parameter_type}]}]`.
- Create: `scripts/vdb5_order_details.ps1` — SELECT z `CDM_OrderDetails` po nazwie joba (przez JOIN z AM_JobDetails), JSON per rekord (wszystkie interesujące kolumny: StyleName, Quantity, wymiary, CSV_*, Oversize*, ProductionComment, CornerRadius, Rotation*, NestingPriority, CustomField1..25, UserVariableString, fkMaterialID...) — narzędzie weryfikacji E2E.
- Test: `tests/unit/test_cdm_db.py` (dla funkcji z Task 2; skrypt ps1 testowany na maszynie w Task 6).

**Pułapki (z tasks.md):** `[fkMaterialID]` escape (MATERIAL keyword), SELECT po nazwie działa (UPDATE nie), `param()` pierwsza instrukcja, PS 5.1 JSON array.
**Weryfikacja:** ruff 0, mypy 0, pytest green.
**Subagent:** implementer (sekwencyjnie).

---

### Task 2: `core/cdm_db.py` — mapy typów pól + `import_settings()` + `parse_cdm_rows_mapped()`

**Cel:** pure logika mapowania z bazy; nic COM-owego.

**Pliki:**
- Modify: `src/alphacam_cli/core/cdm_db.py`:
  - `IMPORT_FIELD_NAMES: dict[int, str]` — pełna mapa typów 256-299 (CDM) i 512-524 (JOB) wg kontekstu (nazwy: door_type, door_width, door_height, door_quantity, door_material, door_customer_name, door_order_number, door_item_number, door_design_dimensions, door_production_comment, door_custom_field_1..25, door_rotation, door_angle, door_nest_priority, door_drilling, door_small_nest, job_name, job_config_id, job_setup_id, job_tool_order_id, job_purchase_order_number, job_work_order_number, job_description, job_programmer_name, job_order_date, job_due_date, job_customer, job_parent_job, job_material_id).
  - `import_settings() -> list[dict]` — subprocess `vdb5_import_settings.ps1` (wzorzec `vdb5_job_defaults`), fallback `[]`, obsługa `{"value": [...]}`.
  - `find_import_setting(settings, key: str | int) -> dict | None` — po id lub nazwie (casefold).
  - `parse_cdm_rows_mapped(rows, field_map: dict[int, str], has_header: bool, default_job_name: str) -> (details, errors)` — **wymagane pola wg mapy**: door_type (256), door_quantity (259), door_width (257), door_height (258); opcjonalne: design_dims (264), material (260), customer_name (261), order_number (262), item_number (263), production_comment (265), oversize_x/y (z 266+? — tylko pola w mapie), custom fields (266..290 jako dict), rotation/angle/nest_priority/drilling/small_nest; pola JOB (512/513/524) zwracane per-wiersz; walidacje jak w `parse_cdm_rows` (qty/width/height > 0, zły typ → error per wiersz). Zachowanie: wiersz bez wymaganych pól z mapy → error "row N: missing required field ...".
- Test: `tests/unit/test_cdm_db.py` — nowe case'y: parsowanie mapy 8-kolumnowej ("sklep CSV"), brak wymaganych pól, custom fields, pola JOB, fallback import_settings, find_import_setting.

**Weryfikacja:** ruff 0, mypy 0, `pytest tests/unit/test_cdm_db.py` green.
**Subagent:** implementer.

---

### Task 3: `core/application.py` — `import_cdm_csv` z mapowaniem + preview + nowe pola

**Cel:** local mode API.

**Pliki:**
- Modify: `src/alphacam_cli/core/application.py` (`import_cdm_csv`, nowa metoda `import_cdm_preview`, `cdm_import_settings`):
  - Nowe parametry `import_cdm_csv`: `import_setting: str | int | None = None`, `preview: bool = False`.
  - `import_setting` → `cdm_db.import_settings()` + `find_import_setting`; separator/header z ustawienia (chyba że jawne `--separator`/`--header`); `field_map` = {column_number: name}.
  - Bez `import_setting` → stara ścieżka (`parse_cdm_rows`) — **zachowanie wsteczne**.
  - Z mapowaniem: `parse_cdm_rows_mapped`; pola CDM ustawiane na detailu (settery wg wyników Task 0: CornerRadius, RotationMethod, RotationAngle, NestingPriority, IgnoreOuterGeometry, SmallNestPart, HasDrilling, CSV_CustomerName, CSV_OrderNumber, CSV_ItemNumber, ProductionComment, OversizeX, OversizeY, CDMCustomField1..25); UserVariableString dopełniany do 50 (istniejący wzorzec); materiał z pola 260 / kolumny job_material_id (524) / defaults; jobName (512) → nazwa joba (priorytet: `--name` > CSV jobName > basename); config (513) → `GetByName`.
  - `import_cdm_preview(csv, import_setting, separator, has_header, job, name, config, material) -> dict` — **bez COM**: czyta + mapuje + zwraca `{success, setting, field_map, rows: [{row, style, quantity, width, height, fields...}], errors, would_create_job, job_name}`.
  - `cdm_import_settings() -> dict` — lista ustawień z bazy (id, name, selected, fields count).
- Test: `tests/unit/test_cdm_core.py` — mapped import (settery wywołane na mock detail), preview bez COM (am nie dotknięty), zachowanie wsteczne bez import_setting, import_settings list.

**Weryfikacja:** ruff 0, mypy 0, pytest green.
**Subagent:** implementer.

---

### Task 4: `gateway/server.py` — handler rozszerzony + preview + settings list

**Cel:** remote mode API (Session 0).

**Pliki:**
- Modify: `src/alphacam_cli/gateway/server.py`:
  - `_handler_cdm_import_csv`: parametry `import_setting` (str|int), `preview` (bool) — ta sama logika co Task 3 (wspólne pure części z cdm_db); COM settery nowych pól na detailu; materiał/name/config z pól JOB.
  - `_handler_cdm_import_preview` — deleguje do cdm_db (bez COM).
  - `_handler_cdm_import_settings` — `cdm_db.import_settings()` → lista.
- Modify: `src/alphacam_cli/gateway/client.py` + `src/alphacam_cli/gateway/remote.py`: `import_cdm_csv(..., import_setting=None, preview=False)`, `import_cdm_preview(...)`, `cdm_import_settings()`.
- Test: `tests/unit/test_gateway_server.py` (handler z mockiem COM), `tests/unit/test_remote.py` / test_cli (proxying parametrów).

**Weryfikacja:** ruff 0, mypy 0, pytest green.
**Subagent:** implementer.

---

### Task 5: `cli/cdm.py` — `--import-setting`, `--preview`, `import-settings list`

**Cel:** interfejs użytkownika.

**Pliki:**
- Modify: `src/alphacam_cli/cli/cdm.py`:
  - `import` → opcje `--import-setting N|NAZWA`, `--preview`; przy preview druk tabelę (rich): ustawienie, separator, mapowanie kolumn (kol→pole), wiersze (Style, Qty, W×H, materiał, klient, nr zamówienia, komentarz, oversize, custom), errors; bez COM. Przy realnym imporcie z mapowaniem drukuj summary (jak dziś + ustawienie).
  - Nowa komenda `import-settings list` — tabela (ID, Nazwa, Selected, Delimiter, Kolumny: "1→cdmDoorType, ...").
- Test: `tests/unit/test_cli_cdm.py` — wywołania z `--import-setting 3` / `--preview`, przekazanie parametrów do `Application.import_cdm_csv` / `import_cdm_preview`, komenda import-settings list.

**Weryfikacja:** ruff 0, mypy 0, pytest green.
**Subagent:** implementer.

---

### Task 6: E2E na laptop-monika (żywy AlphaCAM, Session 0)

**Cel:** potwierdzenie na produkcji.

**Pliki:** żadne stałe w repo — CSV testowe w `C:\temp\faza1_e2e\` na maszynie.

**Kroki:**
1. `git push` (zadania 1-5 zcommittowane) → SSH `git pull` w `C:\Users\48797\Documents\PROJEKTY\alphacam_cli\alphacam_cli` → `sc stop AlphaCAMGateway` → `sc start AlphaCAMGateway` → czekać ~25s → `alphacam --remote --host 100.71.109.69 ping` (lub `get-info`).
2. CSV 8-kolumnowy wg "sklep CSV" (ID3): `Style,Qty,Width,Height,DesignDims,Materiał,JobName,ConfigName` (z prawdziwym stylem np. `PS_03`, materiał `MDF_18`, config `Fronty`) → `cdm import C:\temp\faza1_e2e\e2e1.csv --import-setting 3` → success; `cdm jobs` widać joba z nazwy kol 7.
3. Weryfikacja w bazie: `scripts/vdb5_order_details.ps1` (przez SSH) → fkMaterialID, StyleName, Quantity, wymiary, UserVariableString (50 pozycji) zgodne 1:1.
4. CSV z nowymi polami CDM (jeśli Task 0 potwierdzi settery): kolumny customer_name (261), order_number (262), production_comment (265), oversize itd. → import → weryfikacja CDM_OrderDetails (CSV_CustomerName, CSV_OrderNumber, ProductionComment, OversizeX/Y...).
5. `cdm import --preview C:\temp\faza1_e2e\e2e1.csv --import-setting 3` → sucho (0 zmian w bazie — job_count/order_details przed/po).
6. `cdm import-settings list` → widać "sklep CSV" (3) + "Ustawienia Importu CSV 2" (4).
7. Zachowanie wsteczne: `cdm import 5kol.csv` (bez --import-setting) → działa jak dotąd.
8. Sprzątanie: `cdm delete` jobów testowych; weryfikacja przez VistaDB (job_count).
9. Raport z wynikami do `tasks.md` (sekcja logu sesji).

**Weryfikacja:** wszystkie kroki E2E ✅, testy unit nadal green (na Linuxie przed pushem), ruff/mypy 0.
**Subagent:** implementer/test (z SSH), sekwencyjnie po Task 5.

---

### Task 7: Pętla /fixloop (code-reviewer + fixy + build)

**Cel:** 0 issues w code-review, potem build.

**Kroki (wg /fixloop z globalnego AGENTS.md):**
1. Load `code-reviewer` skill.
2. `git diff --stat` → scope (zadania 0-6).
3. Read każdy zmieniony plik w całości.
4. Dispatch `code-reviewer` subagent (pełna treść plików + kontekst sesji) → structured issues.
5. Issues → fix subagenci (1 issue = 1 subagent) → po fixach `ruff + mypy + pytest` → powrót do kroku 2 (max 5 iteracji).
6. 0 issues → build (`python -m build` lub ekwiwalent wg repo).
7. Raport końcowy + aktualizacja `tasks.md`.

---

## Pułapki / recepty (obowiązkowe przy implementacji i E2E)

- `str()` na COM → zawsze `repr()` (default method pułapka).
- `DeleteFromDB` na świeżym obiekcie = cichy no-op; weryfikacja usunięcia tylko przez VistaDB.
- am.Jobs stęchła po usunięciu — nie weryfikować przez COM.
- AddCDMOrderDetail rzuca przy złym typie → error per wiersz + cleanup joba (istniejący wzorzec).
- VistaDB: MATERIAL keyword (`[fkMaterialID]`), SELECT po nazwie działa (UPDATE nie), schemat DBO.
- SSH: parametry ze spacjami przez cmd są zwodnicze — testy ps1 przez subprocess/handler, nie przez ssh z paramami.
- Po zmianach kodu serwera: taskkill Acam.exe? (tylko przy wiszącym STA) + sc stop/start AlphaCAMGateway.
- `reg copy` HKCU→HKU\.DEFAULT tylko jeśli zmieniały się ustawienia GUI — w tej sesji nie.

## Komendy weryfikacji (każdy task)

```bash
cd /root/projects/alphacam_cli
.venv/bin/ruff check src tests scripts 2>/dev/null || python -m ruff check src tests
.venv/bin/mypy src 2>/dev/null || python -m mypy src
.venv/bin/pytest tests/unit -q 2>/dev/null || python -m pytest tests/unit -q
```

## Po planie — wykonanie

Wykonanie w tej sesji: **subagent-driven-development** — świeży subagent per task (sekwencyjnie; Task 0 pierwszy), review spec + quality po każdym tasku, po Task 6 → Task 7 (/fixloop).
