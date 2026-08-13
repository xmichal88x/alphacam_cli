# Faza 2 — CDM Audyt/podgląd (komendy read) — Plan wdrożenia

> **Data:** 2026-08-09 | **Maszyna testowa:** laptop-monika (AlphaCAM 2025 Router, gateway RPC Session 0, SSH 48797@100.71.109.69)
> **Źródło:** `docs/plans/2026-08-09-am-przemysl-4.0-raport.md` (sekcja 20 "Faza 2", rekomendacje P2/P3 w sekcji 21)
> **Cel:** komendy READ z bazy VistaDB: `order-details list`, `doorpaths list`, `materials list`, `config list/show`, `setups list`, `customers list`, `machining-orders list`, `doorstyles list`, `multidrill list`, `fittings list`, `layers-mapping list`. **Każda komenda kończy się testami E2E na AlphaCAM + pętla fixloop.**

---

## Kontekst (stan po F1)

- Wdrożone: `cdm import` z mapowaniem AM_ImportSettings, `--preview`, `import-settings list` (642 testy, ruff/mypy 0, build OK, push 824c254).
- **Wzorzec F1 dla read-only:** skrypt ps1 (VistaDB.5.NET40.dll, helpery Get-StrVal/Bool/Int/Dbl, mapy pól → snake_case, dynamiczne pomijanie brakujących kolumn przez `$reader.GetName().Trim('[',']')`, JSON przez ArrayList + `ConvertTo-Json -Compress -Depth 10` + wrap `[...]`) → czysta funkcja w `core/cdm_db.py` (subprocess, fallback) → cienkie delegacje w application/server/client/remote (wzorzec `cdm_import_settings`) → CLI rich table.
- **Komendy read NIE wymagają COM** — logika wyłącznie w cdm_db (pure); zero duplikacji biznesowej (świadoma decyzja, inaczej niż F1).

## Faktografia tabel (raport 2026-08-09; potwierdzić nazwy kolumn w T0)

| Tabela | Rekordy | Kluczowe kolumny (do pokazania) |
|---|---|---|
| CDM_OrderDetails | per job | CDM_PK, CDM_OrderID, fkTypeID, StyleName, PressID, ColourID, ColourRotationMethod, HandleID, NestZoneID, fkParentOrderDetailID, ActiveInProcess, ComponentGrouping, PostProcessor, ReverseMachiningFilename, UserValue_0..6 (+ to co już jest w vdb5_order_details) |
| CDM_DoorPaths | 34 | JOIN CDM_DoorTypes po DoorTypeID → TypeName; PathName, PathNumber, ToolName, ToolNumber, ToolOffset, MachiningMethod, SafeRapid, RapidDownTo, FinalDepth, FinalDepthPercentage, IsFinalDepthPercent, McComp, CompOnRapid, XYCorners, SpindleSpeed, DownFeed, CutFeed, CutDirection, LeadIn/Out, SlopeIn/Out, MaterialTop, NumberOfCuts, Stock, ChordError, Diameter, PocketType, StartCutting, StepLength, MultiplePasses, ToolDirectionCW/Reversed, ToolInOut, ToolSide, WidthOfCut, LeadLineLength, LeadArcRadius, LeadApproachAngle, LeadOverlap, LeadEntryPointIsCorner, MachiningStyle, CutType, CreationMethod, PartialStartElemIndex/Dist, PartialEndElemIndex/Dist, NumberOfSteps, SlowDownTo, DecelerationDistance, DoNotSlowDownRadius, IgnoreAngleGreaterThan, SimpleEngraveFeed/Clearance |
| AM_Materials | 4 | MaterialID, MaterialName, SheetWidth, SheetLength, SheetThickness, GrainRestriction |
| AM_ConfigurationSettings | 3 | Podstawowe: ConfigurationSettingName, PostProcessor, DrawingFileOutputLocation, NCFileOutputLocation, ReportFileOutputLocation, NCFileExtension, ReplaceSpaceWithUnderscore, CustomVBAMacro, DisableScreenUpdates, ClearOutputFolders, GenerateNC, GenerateReports, CreateDefaultMaterial, SaveGeneratedAutostyles, ReadFileInformationOnImport, ShowMaterialSelectorAfterImport, CompiledFileName, CompiledBaseName. Nesting (wybrane): Nesting_Method, Nesting_PackTo, Nesting_GapBetweenPaths, Nesting_GapAtSheetEdge, Nesting_ExtraGapAtLeadStart, Nesting_TimePerSheet, Nesting_OptimisationLevel, Nesting_SearchResolution, Nesting_UseBridged, Nesting_UseOnionSkin, Nesting_PreventNestingInApertures, Nesting_UseSupportTags, Nesting_TotalTime, Nesting_SheetOrderType, Nesting_ForceStrictPriorities, Nesting_CommonLineCutting, Nesting_SheetAlignment, Nesting_InactivityTimeout |
| CDM_ConfigurationSettings | 4 (per cfg) | DisableNesting, DisableNestingOversizeX/Y, UseDefaultPress, PressGroupByMaterialThickness, CustomMacro, UseDataFromToolFile, UseSameStartPoint, GenerateNCForParts, ZDepthTolerance, PreviewMaterialThickness, CaptureNestedPartPositions, PartRecoveryX/Y, PartRecoveryIgnoreGrain |
| AM_Setups | 2 | SetupName, GeometryQuery, FE_WhatToExtract, FE_UsePanelAlignment, FE_ZLevelStep, IMP_StepLength, IMP_Project3Dto2D, FE_ContourExtractionMode, FE_DrillableHolesExtractionMode, SetupSeqNum |
| AM_CustomerDetails | 1 | CustomerID, CustomerName, AddressLine1/2, City, Country, PostZipCode, ContactName, TelephoneNumber, EmailAddress, WebsiteAddress |
| AM_MachiningOrder + AM_ToolOrderLists | 28 | m.ToolOrderID, m.fkToolOrderListID, m.MachiningStyleName, m.LayerName, m.SeqNum, m.IsMultidrill, l.Name AS ToolOrderListName (LEFT JOIN) |
| CDM_UserStyles | 265 | UserStyleID, FullFileName, VBAProjectName |
| AM_Multidrill | 0 | MultidrillHeadID, Name, Selected, FeedRate, SpindleSpeed, SafeRapidDistance, RapidDownTo, MaterialTop, BottomOfHole |
| AM_Fittings | 1 | FittingID, fkJobFileID, FittingType, FittingFile |
| AM_LayerMapping | wg bazy | lm.LayerMappingID, lm.fkSetupID, lm.LayerName, lm.MachiningStyleName, lm.MachiningOrder, lm.IsFeatureLayer, lm.ToolSideClosedGeo, lm.ToolDirectionClosedGeo, lm.StartPoint, lm.LayerOrder, lm.ApplyIndividuallyToEachGeometry, s.SetupName (LEFT JOIN AM_Setups) |

---

## Zadania (sekwencyjnie; po każdym: ruff + mypy + pytest + commit)

### T0: RESEARCH — potwierdzenie kolumn tabel na maszynie
**Cel:** `GetSchema('Columns')` + 2-3 przykładowe wiersze + count dla wszystkich tabel z faktografii (nazwy z bracketami, typy bit/int/float, rekordy). **Wykonawca:** subagent general (SSH/PowerShell, skrypty w C:\temp, NIC w repo). Wynik: raport do sesji (używany w T1-T5). Bez E2E.

### T1: `order-details list` — rozszerzenie vdb5_order_details.ps1 + cdm_db.order_details()
**Pliki:** Modify `scripts/vdb5_order_details.ps1`, `src/alphacam_cli/core/cdm_db.py`, `tests/unit/test_cdm_db.py`.
- Mapy pól dodać: str: CDM_PK→cdm_pk, CDM_OrderID→cdm_order_id, PostProcessor→post_processor, ReverseMachiningFilename→reverse_machining_filename; int: PressID, ColourID, HandleID, NestZoneID, fkParentOrderDetailID, fkTypeID, ComponentGrouping; dbl: UserValue_0..6 → user_value_0..6 (prefix); bool: ActiveInProcess→active_in_process; ColourRotationMethod — typ wg T0 (int enum → Get-IntVal).
- `cdm_db.order_details(job_name: str | None = None) -> list[dict]` (wzorzec import_settings(); -JobName gdy podany).
- Testy: parse pełnych pól, fallback → [], argument -JobName.
- E2E: T8.

### T2: `doorpaths list` — scripts/vdb5_door_paths.ps1 + cdm_db.door_paths()
**Pliki:** Create `scripts/vdb5_door_paths.ps1`, Modify `cdm_db.py`, `tests/unit/test_cdm_db.py`.
- `SELECT * FROM CDM_DoorPaths p LEFT JOIN CDM_DoorTypes t ON p.DoorTypeID = t.DoorTypeID`; param `-TypeName` (escape `''`, filtr po t.TypeName). Mapy pól wg faktografii (~40 kluczy snake_case; brakujące kolumny pomijane dynamicznie; typy wg T0).
- `cdm_db.door_paths(type_name: str | None = None) -> list[dict]`.
- Testy: parse, filtr, fallback, door_type z JOIN.
- E2E: T8 (bez filtra → 34; L_B_10mm → ≥1 (PS_03 nie ma ścieżek — tylko typy 4,10,11,15,16,19,20,22,25,31,82,94,98; TypeName="P003" dla PS_03)).

### T3: `materials list` — scripts/vdb5_materials.ps1 + cdm_db.materials()
**Pliki:** Create `scripts/vdb5_materials.ps1`, Modify `cdm_db.py`, `tests/unit/test_cdm_db.py`.
- `SELECT MaterialID, MaterialName, SheetWidth, SheetLength, SheetThickness, GrainRestriction FROM AM_Materials ORDER BY MaterialID` (GrainRestriction typ wg T0).
- `cdm_db.materials() -> list[dict]` (klucze: id, name, width, length, thickness, grain_restriction).
- Testy: parse 4 rekordów, fallback.
- E2E: T9.

### T4: `config list/show` — scripts/vdb5_configs.ps1 + cdm_db.configs()
**Pliki:** Create `scripts/vdb5_configs.ps1`, Modify `cdm_db.py`, `tests/unit/test_cdm_db.py`.
- SELECT * z AM_ConfigurationSettings + CDM_ConfigurationSettings (merge po fkConfigurationSettingID w Pythonie; klucz `cdm` per config). Mapy wg faktografii (podstawowe str/bool, nesting bool/num, cdm bool/str).
- `cdm_db.configs(show: str | None = None) -> list[dict]` — show filtruje po nazwie (casefold); klucze: id, name, post_processor, ..., nesting_*, cdm: {...}.
- Testy: parse, show filter, fallback.
- E2E: T9 ("Fronty" → Alpha Reichenbacher.arp, GenerateNC=True, GenerateReports=False, DisableNesting=False).

### T5: lookups — scripts/vdb5_lookups.ps1 + cdm_db.lookups()
**Pliki:** Create `scripts/vdb5_lookups.ps1`, Modify `cdm_db.py`, `tests/unit/test_cdm_db.py`.
- Jeden skrypt, JSON `{"setups": [...], "customers": [...], "machining_orders": [...], "doorstyles": [...], "multidrill": [...], "fittings": [...], "layers_mapping": [...]}` (7 sekcji; SELECT-y wg faktografii z JOIN-ami).
- `cdm_db.lookups() -> dict[str, list]` — fallback `{key: [] for key in LOOKUP_KEYS}`; walidacja sekcji.
- Testy: parse 7 sekcji, fallback, brakująca sekcja → [].
- E2E: T9 (setups=2, customers=1, machining_orders=28, doorstyles=265, multidrill=0, fittings=1, layers_mapping — tabela PUSTA (0 rekordów, komunikat empty)).

### T6: warstwy RPC + local — czyste delegacje (bez COM)
**Pliki:** Modify `application.py`, `server.py`, `client.py`, `remote.py`, testy (test_cdm_core, test_gateway_server, test_remote).
- Application: `cdm_order_details(job_name=None)`, `cdm_door_paths(type_name=None)`, `cdm_materials()`, `cdm_configs(show=None)`, `cdm_lookups()` — delegacja do cdm_db, wynik `{"order_details": [...], "job_name": ...}` (klucz sekcji jak cdm_import_settings).
- Server: `_handler_cdm_order_details` (job_name), `_handler_cdm_door_paths` (type_name), `_handler_cdm_materials`, `_handler_cdm_configs` (show), `_handler_cdm_lookups` — walidacja str|None, COMError przy błędzie, delegacja do cdm_db (bez COM).
- Client: metody `_call("cdm_order_details", {"job_name": ...})` itd.; Remote: delegacje.
- Testy: proxy parametry, handler bez COM (mock cdm_db), local mode.

### T7: CLI — komendy (subapp-y, wzorzec import-settings list)
**Pliki:** Modify `src/alphacam_cli/cli/cdm.py`, `tests/unit/test_cli_cdm.py`.
- `cdm order-details list JOB` — tabela: Style | Qty | W x L | Materiał | Klient | Nr zam | Item | Komentarz | Custom | Rotation | NestPri | Drilling | SmallNest | Press | Colour | Handle | Active (klucze snake_case z cdm_db).
- `cdm doorpaths list [TYPE]` — Path | Tool | ToolNo | Method | SafeRapid | RapidTo | Depth | Spindle | DownFeed | CutFeed | LeadIn | LeadOut | SlopeIn | SlopeOut | Stock | InOut | Side.
- `cdm materials list` — ID | Name | Width | Length | Thickness | Grain.
- `cdm config list` — ID | Name | Post | NC Ext | GenNC | GenReports | NestMethod | PackTo; `cdm config show NAME` — sekcje Podstawowe/Nesting/CDM.
- `cdm setups list`, `cdm customers list`, `cdm machining-orders list`, `cdm doorstyles list`, `cdm multidrill list`, `cdm fittings list`, `cdm layers-mapping list` — kompaktowe tabele wg faktografii; puste → "No ... found".
- Testy: per komenda — mock metody Application + assert wyjścia (exit 0, zawartość), pusta lista → komunikat.

### T8: E2E-1 na maszynie — order-details + doorpaths (P2)
1. Push → pull na maszynie → restart AlphaCAMGateway (sc stop → osobno sc start → 45s) → RPC sanity.
2. Job testowy: CSV 17-kolumnowy (wzór F1) + tymczasowe ustawienie importu (id auto-increment!) → `cdm import --import-setting N --name "F2 E2E Job"`.
3. `cdm order-details list "F2 E2E Job"` → pełne pola (klient/nr/item/komentarz, custom, rotation 3/1, angle, nest_priority, drilling true/false, small_nest, press_id=0, colour_id=0, handle_id=0, active_in_process=false, user_value_0..6="", fk_parent="").
4. `cdm doorpaths list` → 34; `cdm doorpaths list PS_03` → ≥1 (nazwa typu z bazy F1); zanotować realne wartości (ToolName, Spindle, DownFeed, CutFeed, Depth, LeadIn/Out) do raportu.
5. Weryfikacja bazy: vdb5_order_details pełne pola (nowe klucze).
6. Sprzątanie: delete joba, DELETE ustawienia testowego, rmdir temp.
7. tasks.md: "✅ E2E FAZA 2 — order-details + doorpaths" (bez commita).

### T9: E2E-2 na maszynie — materials/configs/lookups (P3)
1. Deploy (T8 wzorzec).
2. `cdm materials list` → 4 (nazwy/wymiary wg bazy), `cdm config list` → 1/40/41, `cdm config show "Fronty"` → pełne wartości (zapisać).
3. `cdm setups list` → 2; `customers list` → 1; `machining-orders list` → 28 (z listami); `doorstyles list` → 265; `multidrill list` → 0 (komunikat empty); `fittings list` → 1; `layers-mapping list` → wg bazy.
4. Liczby zweryfikować z raportem (sekcja 22); sprzątanie; tasks.md "✅ E2E FAZA 2 — materials/configs/lookups"; pre-existing → tasks.md.

### T10: /fixloop + README + push
1. Load `code-reviewer`; `git diff --stat`; read pliki; dispatch reviewer (kontekst F1); issues → fix subagenci (max 5 iteracji).
2. 0 issues → `.venv/bin/python -m build` (wheel+tar.gz).
3. README: podsekcje cdm (order-details, doorpaths, materials, config, setups, customers, machining-orders, doorstyles, multidrill, fittings, layers-mapping) + przykłady.
4. Commit tasks.md + push; finalna weryfikacja (pytest/ruff/mypy/build); raport końcowy.

---

## Pułapki / recepty (obowiązkowe)

- VistaDB: `MATERIAL` keyword → `[fkMaterialID]`; SELECT po nazwie działa (UPDATE nie); brak INFORMATION_SCHEMA → nazwy kolumn przez `$reader.GetName()` + `.Trim('[', ']')`; `param()` pierwsza instrukcja skryptu; `$ErrorActionPreference='Stop'`; OutputEncoding UTF8; JSON: ArrayList + `ConvertTo-Json -Compress -Depth 10` + wrap `[...]` gdy pojedynczy obiekt; PS 5.1 case-insensitive zmienne (NIE `$values`/`$Values` przy split!).
- CDM_OrderDetails JOIN AM_JobDetails — aliasy `d`/`j` (sprawdzone w F1); LEFT JOIN dla opcjonalnych (doorpaths/layers_mapping).
- Kolejność pól w JSON per skrypt — stała (testy zależą od kluczy).
- Subprocess: `powershell -NoProfile -ExecutionPolicy Bypass -File`, timeout 20, fallback `[]`/puste sekcje, logowanie warning (wzorzec `import_settings()`).
- E2E: `cdm import` job testowy jak w F1 (P003→PS_03, MDF_18); `--import-setting` tymczasowe id; sprzątanie obowiązkowe (joby + INSERT-y + temp).
- Po zmianach: restart usługi; `git pull` w `C:\Users\48797\Documents\PROJEKTY\alphacam_cli\alphacam_cli` (editable install, python systemowy 3.11 — NIE venv).

## Komendy weryfikacji (każdy task)

```bash
cd /root/projects/alphacam_cli
.venv/bin/python -m ruff check src tests scripts
.venv/bin/python -m mypy src
.venv/bin/python -m pytest tests/unit -q
```

## Wykonanie

Subagent-driven (sekwencyjnie): T0 → T1 → ... → T9 → T10 (/fixloop). Po każdym tasku: verification gate + commit. E2E na maszynie: T8 (P2) i T9 (P3) — każda komenda potwierdzona na żywym AlphaCAM. Fixloop: T10.
