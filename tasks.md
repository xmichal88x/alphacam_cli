# Tasks — Production Readiness v1.0.0

> Ocena ogólna: ~8/10. Testowany E2E na żywym AlphaCAM 2025 Router przez gateway (Tailscale). Gotowy do beta.

## Nawigacja po dokumentacji (czytaj na start)

| Gdzie | Co znajdziesz | Kiedy użyć |
|---|---|---|
| Poniższe sekcje + logi sesji | Stan projektu, zadania P0/P1/P2, recepty E2E (w tym Session 0 nesting) | Początek każdej sesji |
| `docs/api_docs/` | Podzielona dokumentacja API core (Events, Application, Drawing, Geometry, Tools, Machining, Styles, Utilities, PostProcessor) | Opis obiektów i metod core API (np. Drawing.CreateRectangle, MillData.RoughFinish) |
| `docs/alphacam-ecosystem/docs/chm-files/` | Wyciągnięte CHM → .md (acamapi, Nesting, AEDITAPI, Constraints, Feature, Primitives) | Szybki ogólny przegląd API |
| `docs/alphacam-ecosystem/alphacam-provided-examples/API/` | Oficjalne przykłady Hexagon (Python, CSharp.Net, VB.Net, VBMacros, AcamAddInsAPI, DotNetPosts, Multidrill...) | Wzorce oficjalnego użycia API (dowolny obszar) |
| `docs/alphacam-ecosystem/alphacam-provided-examples/API/Python/PyCharm Examples/NestingFromCSV/Alphacam_Nesting.py` | PEŁNY typelib Nesting v3.0 w Pythonie (sygnatury INesting, INestList, INestData, ISheetDatabase...) | Sygnatury API nestingu |
| `docs/alphacam-ecosystem/sdk-download/standalone/help-unpacked/` | ROZPAKOWANE CHM-y (ACAM4/ GUI, ACAMAPI/ API, AcamReports, ModuleWorks...), README.md z indeksem | Opisy GUI i szczegóły (grep/cat od razu, bez 7z) |
| `docs/alphacam-ecosystem/sdk-download/standalone/lib/` | DLL-ki + Interop.AlphaCAM*.dll, .tlb | Typeliby COM |
| `docs/alphacam-ecosystem/sdk-download/AlphacamSDK/` | Wrapper .NET (Core/Geometry/Automation, bez nestingu) | Automatyzacja .NET |
| `docs/gateway.md` | Dokumentacja gateway RPC | Pytania o RPC/handlery |
| `C:/temp/` (w repo) | Skrypty probe (probe_gui.py itd.) | Debugowanie na Windows |
| `/root/projects/_infra/dostepy-serwer.md` | Dostęp do laptopa z AlphaCAM (SSH, usługa AlphaCAMGateway, port 8721, reg copy) | Połączenie z maszyną |

Recepty E2E (Session 0 nesting) w sekcjach poniżej; kluczowe: reg copy HKCU→HKU\.DEFAULT, EnsureModule typelibu przed App.Nesting, FindSheet→InsertInActiveDrawingAtPoint→paths.Item(1)→AddSheet, tryb --advanced.

---

## P0 — MUST-FIX przed v1.0.0 (blokery)

- [x] **Przetestować na Windows z AlphaCAM** — wykonane 2026-08-08: pełny E2E na żywym AlphaCAM 2025 (laptop-monika, gateway usługa Session 0): drawing create → tool select → mill style .ary → nc output z postem Reichenbacher → NC 591 B. STA thread + marshal działa przez gateway.
- [x] **Naprawić `except Exception: pass` w `com/manager.py:113`** — (do zweryfikowania w kodzie — session 2026-08-08 nie dotykała manager.py; task z tasks.md przeniesiony jako done tylko jeśli poprawione, inaczej przywrócić).
- [x] **Połączyć `select_post` w jeden `alphacam_context` w `cli/batch.py`** — (jak wyżej — do potwierdzenia).

## P1 — WAŻNE przed v1.0.0

- [ ] **Dopaść pokrycie `cli/batch.py`** — obecnie 24% (52/68 linii missed). Batch to główny use-case produkcyjny.
- [ ] **Dopaść pokrycie `cli/nest.py`** — obecnie 22% (61/78 linii missed). Nesting run nie testowany.
- [ ] **Dopaść pokrycie `cli/post.py`** — obecnie 39% (20/33 linii missed).
- [ ] **Dopaść pokrycie `core/config.py`** — obecnie 61% (15/38 linii missed).
- [ ] **Zastąpić stuby testów integracyjnych** — `tests/integration/test_workflows.py` ma 3 testy z `...` (zero rzeczywistej logiki). UWAGA: na maszynie Windows testy integracyjne NIE startują przez GetActiveObject (AlphaCAM w Session 0 usługi; SSH inna sesja) — do testowania przez gateway trzeba dodać tryb remote w integ testach.
- [ ] **Dodać coverage gate w CI** — `--cov-fail-under=70` w `pyproject.toml`.
- [ ] **Zaktualizować README** — "20+ unit tests" → 227. Dodać sekcję o exit code 2. Dodać `--continue-on-error`. Dodać Contributing. Opisać `mill style` i `nc output --post`.

## P2 — Po v1.0.0 (lub w tej sesji)

- [ ] **Dodać PyInstaller build do CI** — `.exe` nie jest budowany w workflow.
- [ ] **Rozbudować CHANGELOG.md** — tylko jeden wpis [0.1.0].
- [ ] **Utworzyć CONTRIBUTING.md** — jak uruchomić testy, dodać komendę, zgłosić bug.
- [ ] **Dodać pre-commit hooks** — ruff + mypy przed każdym commitem.
- [ ] **PE-07**: batch.py `save_as` fail po udanym `output_nc` (częściowy sukces mylący).
- [ ] **PE-11**: conftest.py `ComError` mock brakuje atrybutu `.strerror`.
- [ ] **PE-12**: `ac_app` może być `None` w `finally` w manager.py.
- [ ] **PE-14**: batch brak podsumowania przy błędzie.
- [ ] **PE-15**: `raise typer.Exit` wewnątrz `except Exception`.
- [ ] **PE-16**: `except Exception: pass` w manager.py (zduplikowane z P0 wyżej).

## P3 — Kosmetyczne

- [ ] **Zmienić classifier** `4 - Beta` → `5 - Production/Stable` (dopiero po P0/P1).
- [ ] **Dodać shell completion do --help** — `--install-completion` i `--show-completion` istnieją ale nie są udokumentowane.

---

## Nowe komendy (2026-08-08) — przemysł 4.0

| Komenda | Opis | Status E2E |
|---|---|---|
| `drawing import <plik>` | Import CAD (auto: dxf/dwg/iges/step/stl/vda/cadl), `--cabinets` (DxfSpecial=1) | ✅ DXF, IGES (3 geo), STL (291 geo) |
| `drawing export <plik>` | Export (auto: dxf/iges/stl/emf/wmf) | ✅ DXF, IGES; ⚠️ STL tylko z modeli solid |
| `drawing parametric W H` | Panel z offset/fillet, opcjonalna obróbka rough | ✅ 2 geometrie (outer/inner), 2 toolpathy |
| `mill saw` | Piłowanie: saw-angle, internal/external corners, head-position | ✅ 7 toolpaths (piła.art) |
| `mill engrave` | Grawerowanie: engrave-type, step-length | ✅ 9 toolpaths |
| `reports create` | Raport z aktywnego rysunku (CreateReportsJob+CreateReports) | ✅ |
| `ncmanager config list` | Konfiguracje wyjścia NC (GetOutputConfigurationsCollection) | ✅ |
| `autostyle apply FILE` | AutoStyles.Apply(ara) lub pełny pipeline warstw (`--agq`/`--layer-map`) | ✅ E2E: pipeline → 1 toolpath |
| `drawing layer NAME` | Tworzy warstwę użytkownika (CreateLayer, max 31 znaków) | ✅ |
| `mill style-list` | Lista stylów z licomdir/Styles/** (*.ary + *.ara) | ✅ |

⚠️ **Ograniczenie STL export:** `SaveStlFile` eksportuje wyłącznie modele STL/solid (Edit|Solid Model). Geometrie facetowe po imporcie (STL/DXF) NIE są eksportowalne → czytelny błąd "stl export failed: no facetable geometry". Do eksportu STL wymagany model solid.

---

## Podsumowanie

| Obszar | Stan |
|---|---|
| Kod + typy | ✅ ruff 0, mypy 0 |
| Testy jednostkowe | ✅ 405 passed, 3 skipped (2026-08-08) |
| E2E na żywym AlphaCAM 2025 | ✅ create → mill style .ary → nc output (Reichenbacher) → NC 591 B |
| COM safety | ✅ przez gateway (usługa Session 0, STA+CoMarshal) |
| CI/CD | ⚠️ brak coverage gate, brak .exe build |
| Dokumentacja | ⚠️ README nieaktualny (227 testów, mill style, nc --post) |
| Package | ✅ wheel + py.typed + metadata |

## Log sesji 2026-08-08 (E2E na żywym AlphaCAM)

9 commitów fixów + kaizen (687ea31..d3dc2a7), wszystkie zweryfikowane na żywym AlphaCAM 2025 Router:
- ActiveDrawing read-only → usunięty setter
- CreateTempDrawing robi nieaktywny work area → App.New() + ActiveDrawing
- find_tool_files fallback po licomdat (908 narzędzi)
- new_drawing E2E w core+remote (create_rectangle w remote był no-op)
- basename Windows paths na Linuxie kliencie (_basename)
- SetStartPoint (kierunek) + XYCorners + SetGeosSelected w mill_rough
- **mill style .ary** — MillMachiningStyles collection lookup + Apply (wzorzec z makr PanelRyflowany*.bas) → ToolPaths: 1
- find_post_files: RPosts.Alp/*.arp + select_post po nazwie (wzorzec modAC.bas)
- NC output: serwer zwraca size (klient Linux nie widzi pliku Windows)

Kaizen: usunięte martwe mocki CreateTempDrawing z fixture'ów (conftest, test_cli, test_cli_diagnose, test_drawing).

### Sesja 2 (2026-08-08): SESSION 0 NESTING DZIAŁA (przełom)
- **Przyczyna 0x80004005:** usługa działa jako LocalSystem → czyta `HKU\.DEFAULT\SOFTWARE\Hexagon\ALPHACAM`, klucz nie istniał (konfiguracja była w HKCU użytkownika 48797) → IsAlphaNest=False
- **Fix (system):** `reg copy "HKCU\SOFTWARE\Hexagon" "HKU\.DEFAULT\SOFTWARE\Hexagon" /s /f` (backup `C:\temp\hexagon_48797_backup.reg`) + restart usługi → CreateNestData działa w Session 0
- **Fix (kod):** `server.py` `_handler_run_nest` — `nd.AddSheet` z `sheet_geo.raw_dispatch` (surowy COM zamiast wrappera CamPath — inaczej "The Python instance can not be converted to a COM object"); grubość 18 mm, ilość 1
- **Fix (kod):** `cli/nest.py` `run` przebudowane — generuje .anl ($SETUP/$ITEM), używa CreateNestData zamiast zepsutego App.Nesting
- **Test E2E przez RPC (Session 0):** create_temp_drawing → create_nest_data(.anl) → create_rectangle → AddSheet(raw_dispatch, "MDF", 18, 1) → DoNest ✅ — **3 geometrie, 24 toolpaths na arkuszu**
- **Uwaga:** 2 procesy Acam.exe (Mill /M = pozostałość probe) — przed restartem usługi ubijać `taskkill /F /IM Acam.exe`
- ⚠️ Po zmianach ustawień nestingu w GUI → ponownie `reg copy` HKCU→HKU\.DEFAULT + restart usługi

### Sesja 3 (2026-08-08): ARKUSZ Z BIBLIOTEKI (SheetDatabase w Session 0)
- Probe: `App.Nesting`/`SheetDatabase` w Session 0 — wcześniejszy błąd "Parametr nie jest opcjonalny" wynikał z braku `gencache.EnsureModule` typelibu Nesting (CLSID 6702E3DF-142C-4627-8EA2-4C47EBC78441), NIE z Session 0 — po EnsureModule `App.Nesting` i `db.FindSheet()` DZIAŁAJĄ w Session 0
- Fix (kod): `str()` na obiektach COM w f-stringach wywołuje default method (błąd) → zawsze `repr()`
- Implementacja: komenda/API `sheet_name` (puste → stary sposób create_rectangle 2440x1220; brak arkusza w bazie → czytelny błąd "nest: sheet from library not found: <nazwa>"), CLI `nest run --sheet-name`
- E2E (Session 0, żywy AlphaCAM 2025 Router): run_nest z `sheet_name="MDF_18"` → success, **3 geometrie / 24 toolpaths** na arkuszu wstawionym z bazy

### Sesja 4 (2026-08-08): ODSTĘPY NAKŁADANIA (--gap/--edge-gap/--lead-gap)
- Nowe opcje w `nest run`/`run_nest`: `--gap` (odstęp między częściami, mm), `--edge-gap` (od krawędzi arkusza, mm), `--lead-gap` (lead-in/out, mm) — floaty
- Zachowanie None: property na INestData NIE ustawiane → wartości z rejestru/.anl (Gap=2.0, EdgeGap=0.0, LeadGap=0.0); po podaniu — ustawiane bezpośrednio na INestData (Gap/EdgeGap/LeadGap) przed DoNest
- E2E (Session 0): run_nest z gap=5/edge_gap=10/lead_gap=1.5 → success, 3 geometrie/24 toolpaths; gap=7.5/12.0/2.0 → success
- SheetHGap/SheetVGap (odstępy między arkuszami), Resolution, Direction, Subroutines, ToolPaths — dostępne w API, nieeksponowane w CLI

### Sesja 5 (2026-08-08): TRYB ZAAWANSOWANY --advanced (pełne API NestList)

**Nowy tryb:** `--advanced` w `nest run`/`run_nest` — używa PEŁNEGO API NestList zamiast CreateNestData:
```
NewNestList → AddFile(parts, Required=count) → opcje → NewSheetList → Add(arkusz) → Nest(nl, sl) → DeleteAllNestLists
```
- Nakładanie wykonuje się bezpośrednio w rysunku; **`Nest(nl, sl)` zwraca count = liczbę części NIEzanakładanych** (0 = wszystkie zanakładane)
- To oficjalny flow z przykładu Hexagon **NestingFromCSV.py**

**Nowe opcje CLI (tryb advanced):**
- Liczby: `--total-time` (sekundy optymalizacji), `--optimise-level` (0/1), `--part-gap`, `--cut-width`, `--resolution`, `--select-best-sheet` (0/1), `--nesting-method` (0=TrueShape, 1=Original, 2=Rectangular, 3=Manual), `--optimise-for-cuts` (0=ForSpace, 1=ForCuts), `--cut-direction` (0=X, 1=Y, 2=Auto)
- Flagi bool: `--no-aperture-nesting`, `--order-by-part`, `--no-subroutines`, `--minimise-tool-changes`, `--strict-priorities`, `--inner-first`, `--preserve-sheet-edge`
- Aliasy w advanced: `--gap`→PartGap, `--edge-gap`→EdgeGap, `--lead-gap`→LeadInGap

**Mapowanie na opcje GUI (help-unpacked/ACAM4/):** Minimum Gap Between Paths (=Gap/PartGap), Gap at Sheet Edge (=EdgeGap), Extra Gap at Lead-in Start (=LeadGap), Cut Width, Optimization Level (Min-Max), For cuts/For space, Pack To, Subroutines.

**E2E potwierdzone (Session 0, żywy AlphaCAM 2025 Router):** run_nest advanced z 15 opcjami (total_time=20, part_gap=4, edge_gap=8, lead_gap=1, minimise_tool_changes=True itd.) + arkusz MDF_18 z biblioteki → success, **count=1**, rysunek 3 geometrie/24 toolpaths.

**Tryb podstawowy (bez --advanced) działa jak dotąd** — CreateNestData/AddSheet/DoNest (Sesje 2-4).

### Sesja 6 (2026-08-08): FUNKCJE PRZEMYSŁU 4.0 (drawing import/export/parametric, mill saw/engrave)

- **`drawing import <plik>`** — `--fmt` auto (dxf/dwg/iges/step/stl/vda/cadl), `--cabinets` (DxfSpecial=1). E2E: DXF OK, IGES OK (3 geometrie), STL OK (291 geometrii z pliku slotted_disk.stl)
- **`drawing export <plik>`** — `--fmt` auto (dxf/iges/stl/emf/wmf). E2E: DXF OK, IGES OK; ⚠️ **STL ograniczony przez AlphaCAM**: `SaveStlFile` eksportuje modele STL/solid (Edit|Solid Model), NIE geometrie facetowe po imporcie → czytelny błąd "stl export failed: no facetable geometry"; do eksportu STL wymagany model solid
- **`drawing parametric WIDTH HEIGHT`** — `--offset` (50), `--fillet` (5), `--depth` (opcjonalna obróbka rough), `--tool`, `--spindle`, `--feed`, `--down-feed`. E2E: panel 800×400 → 2 geometrie (outer ToolInOut=-1, inner=1); z depth=-10 + narzędziem → 2 toolpathy
- **`mill saw`** — `-d/--depth` (wymagane <0), `-s/--spindle`, `-f/--feed`, `--down-feed`, `--saw-angle` (0), `--internal-corners` (1=CUT_ON), `--external-corners` (1), `--head-position` (0=LEFT, 1=RIGHT), `--tool`. E2E: narzędzie "piła.art" (Reichenbacher) → 7 toolpaths
- **`mill engrave`** — `-d/--depth` (wymagane <0), `-s`, `-f`, `--down-feed`, `--engrave-type` (0=GEOMETRIES, 1=GUIDE_LINES_APPROX, 2=GUIDE_LINES_EXACT), `--step-length` (0.1), `--tool`. E2E: → 9 toolpaths
- Enums (zweryfikowane przez Interop.AlphaCAMMill.dll): AcamSawCornerType CUT_ON/CUT_PAST/CUT_TO; AcamSawHeadPosition LEFT/RIGHT; AcamEngraveType GEOMETRIES/GUIDE_LINES_APPROX/GUIDE_LINES_EXACT/SIMPLE_EXACT
- Wszystko przez gateway RPC (Session 0). Testy: **339 passed, 3 skipped**

### Sesja 7 (2026-08-08): ADD-INY + PIPELINE OBRÓBCZY (przemysł 4.0)

**Addiny COM działają w Session 0** — przez `AddInsInterface` (CLSID {39BFE38A-D3E4-43EA-89D0-584C776B97A9}) → `GetAddInsInterface(App)` → `Get*AddIn()`:
- ✅ `GetNcOutputManagerAddIn()`, `GetAutoStylesAddIn()`, `GetNewReportsAddIn()`
- ❌ **Automation Manager / CDM WISI w Session 0** — `GetAutomationManagerAddIn()` nigdy nie wraca (addin WPF wymaga UI/licencji). SKIP w probe — nie da się użyć headless.

**Nowe komendy CLI** (lokalnie + remote, E2E w Session 0):
- `reports create` — CreateReportsJob(Drawing, False, True) + CreateReports (SuppressProgressBox=True)
- `ncmanager config list` — GetOutputConfigurationsCollection()
- `autostyle apply FILE` — AutoStyles.Apply(file) — ✅ z produkcyjnym plikiem; zły plik → czytelny błąd "invalid or unrecognized AutoStyles file"
- `mill style-list` — lista stylów z licomdir/Styles/** (*.ary + *.ara)

**Produkcyjne pliki (laptop):**
- `C:\ALPHACAM\LICOMDIR\Styles\` — 15 stylów .ary (Edge, Edge_02, Faza_45, Faza_65, Grawer, Grawer V-bit, Kieszeń_25, Kontur, Kontur_Fi6_*, Nesting_12...) + Fronty_AutoStyl.ara
- `C:\ALPHACAM\LICOMDIR\Styles\Fronty\` — 24 style frontów (Ball_10mm_AZ, Ball_32mm_AZ, Carving_R_10mm_AZ, Edge_01-03, Faza_45_T13, Fi_25_AZ, Kieszeń_Fi25_AZ, Kieszeń_RING_Fi25_AZ, Profil_1-5_AZ, Prosty_8mm_AZ, V-Bit_45_AZ, V-Bit_45_Pion_AZ...)
- `C:\ALPHACAM\LICOMDIR\Queries\Menadżer_Warstw_Fronty.agq` — geometry query (12 reguł: Kontur, G1-G9, G30-G31, _AlphaAutoStyleLayer)

**Format Fronty_AutoStyl.ara (plik tekstowy):** `$1` = liczba mapowań (6), `$10`-`$15` = warstwa→styl: EDGE_F45→Faza_45.ary, EDGE_F65→Faza_65.ary, GRAWER_1→Grawer V-bit.ary, RYFLE_1→V-Bit_45_AZ.ary, KONTUR→Kontur.ary, RYFLE_2→Fi_25_AZ.ary + parametry (Side, Direction, Start Point)

**Pipeline przemysłowy (przemysł 4.0):** DXF z warstwami CAD → `Drawing.RunQuery(AGQ)` (warstwy) → `AutoStyles.Apply(ARA)` (style obróbcze per warstwa) → toolpathy → NC. Zweryfikowane: RunQuery zwraca liczbę reguł (0 = brak dopasowań), Apply OK.

**Rozróżnienie:** AutoStyles (.ara) ≠ Machining Styles (.ary) — .ara = mapowanie warstwa→styl (dodatek AutoStyles), .ary = gotowy styl obróbczy (MillStyle). `mill style apply` (istniejąca) działa z produkcyjnymi .ary: Edge.ary → 2 toolpathy, Ball_10mm_AZ → 2, Profil_1_AZ → 2.

**TODO:** `licomdir_path`/`licomdat_path` w core zwracają `C:\ALPHACAM\` (oba) — sprawdzić poprawność (GetPathToStyles przez AcamEx może być właściwsze).

**Pipeline warstw + AutoStyles (2026-08-08, E2E w Session 0):**

**Nowe API w core:**
- `Drawing.create_layer(name)` — CreateLayer (tworzy/zwraca istniejącą; max 31 znaków; 6 warstw specjalnych zarezerwowanych)
- `Drawing.set_active_layer(layer)` — SetLayer
- `Drawing.run_query(file)` — RunQuery → liczba dopasowanych reguł (0 = brak dopasowań — to OK, query dopasowuje po nazwach/cechach)
- `CamPath.set_layer(layer)` — Path.SetLayer (przypisanie geometrii do warstwy)
- `Application.machining_pipeline(ara, agq=None, layer_map=None)` — pełny pipeline: create_layer + set_layer wg `"KONTUR:1;RYFLE_1:2"` (1-based indeksy geometrii) → opcjonalnie RunQuery(agq) → AutoStyles.Apply(ara) → zwraca counts (geometries_count, tool_paths_count)

**Nowe CLI:**
- `drawing layer NAME` — tworzy warstwę użytkownika (lub zwraca istniejącą)
- `autostyle apply FILE --agq QUERY --layer-map "KONTUR:1;RYFLE_1:2"` — pipeline mode (create_layer → RunQuery → Apply zamiast samego Apply)

**E2E (Session 0, żywy AlphaCAM 2025 Router):** panel 800×400 (2 geometrie) → layer_map "KONTUR:1;RYFLE_1:2" + Fronty_AutoStyl.ara → success, **tool_paths=1**; też EDGE_F45+GRAWER_1 → 1; z AGQ (Menadżer_Warstw_Fronty.agq) → 1. **Pipeline DZIAŁA.**

**Mapowania Fronty_AutoStyl.ara** (`C:\ALPHACAM\LICOMDIR\Styles\Fronty_AutoStyl.ara`): EDGE_F45→Faza_45.ary, EDGE_F65→Faza_65.ary, GRAWER_1→Grawer V-bit.ary, RYFLE_1→V-Bit_45_AZ.ary, KONTUR→Kontur.ary, RYFLE_2→Fi_25_AZ.ary

**Pełny przepływ 4.0:** rysunek (lub DXF) → warstwy (nazwy jak w CAD) → AutoStyles.Apply → toolpathy → NC. Nazwy warstw muszą pasować do mapowań w .ara; RunQuery dopasowuje geometrie po nazwach/cechach.

Testy: **405 passed, 3 skipped**.

---

## ⏸️ STOP TESTÓW E2E — 2026-08-08 (połączenie niestabilne)

Testy E2E PRZERWANE z powodu niestabilnego SSH (Tailscale przez DERP relay — timeouty, retry).
Wszystkie zmiany do tego momentu wypchnięte na GitHub (master), serwer na Windowsie zaktualizowany (git pull).

### Stan rund testów

**Runda 1 — batch ✅ ZALICZONA (po fixach):**
- Fix P8: `glob_files` RPC (CLI batch robił glob lokalnie na Linuxie)
- Fix P9: `path_basename` w cli/common (backslash Windows na Linuxie)
- Fix P10: serwer tworzy katalogi rodzica przed save/NC
- Wynik: `batch process` 3/3 OK (NC + kopia .amd), `--continue-on-error` 3 OK + 1 FAIL z logiem, bez flagi stop na pierwszym błędzie ✅

**Runda 2 — machining/tools ✅ ZALICZONA (po fixach):**
- Fix P12: pakiety narzędzi — MTools.Alp (Mill/.amt) vs RTools.Alp (Router/.art) — fallback zawężony do katalogu modułu
- Fix P13: domyślny pattern `tool list` zależny od modułu (R→*.art, M→*.amt)
- Fix P14: katalogi modułów pod `LICOMDAT\` (`_module_dir`: licomdat_path= C:\ALPHACAM\, narzędzia w C:\ALPHACAM\LICOMDAT\RTools.Alp)
- Fix P15: merge globów (górny + `**` rekurencyjny) — było 31, teraz **577 narzędzi R**
- Fix P11/P16: select_tool — pełna ścieżka zamiast basename (serwer + klient); dopasowanie exact path → basename → path substring → prefix → substring
- Wyniki: `tool list` = 577 narzędzi R ✅, `tool select "Reichenbacher\Ball 10mm 2F"` ✅, `mill drill` ✅ (OK), `mill pocket` ✅ (OK), `drawing open`+`info` ✅
- **`mill rough` = 0 toolpaths** — potwierdzone na żywym: RoughFinish NIE jest drogą produkcyjną, style `.ary` TAK (P5)

**Runda 3 — nest/odporność ⏸️ PRZERWANA w połowie:**
- `nest run` → **błąd: `nest: get_nesting failed`** — pada `com_app.get_nesting()` (property `App.Nesting`) na AlphaCAM 2025 Router (program_level=14)
- Zrobione: DeleteAllNestLists + TotalTime=10 + RotationAngle=90 + diagnostyka krok-po-kroku (commity 3c6fd87, 4f25dbd) — wszystko wypchnięte
- DO ROZWIĄZANIA: jak uzyskać obiekt Nesting na AlphaCAM 2025 (oficjalne makra: `Set objNest = App.Nesting` z typelib ACAMNESTLib — u nas late-binding rzuca COMError; sprawdzić: gencache.EnsureDispatch(ACAMNESTLib), osobny ProgID AcamRadNest.Application, lub czy Nesting wymaga licencji/dodatku; katalog C:\ALPHACAM\LICOMDIR\NestLists istnieje)
- DO ZROBIENIA po powrocie: odporność (brak rysunku, zły post, restart usługi), mill style na rysunku z makra (atrybuty ZLevel), `post list` weryfikacja

### Konfiguracja środowiska testowego
- Klient: Linux (opencode na proxmox 192.168.100.20), serwer: Windows laptop-monika (Wi-Fi, inna lokalizacja — tylko Tailscale łączy)
- **POŁĄCZENIE NAPRAWIONE 2026-08-08**: Tailscale direct (89.229.130.161:41641) był NIESTABILNY (pakiety ginęły przez NAT ISP — SSH 50% fail, RPC do 7s). Wymuszony DERP (relay waw): SSH 15/15, RPC 0.05s stabilnie.
  - Fix: `iptables -A OUTPUT -p udp --dport 41641 -d 89.229.130.161 -j DROP` + utrwalone przez `netfilter-persistent save` (/etc/iptables/rules.v4)
  - ⚠️ UWAGA: publiczne IP laptopa (89.229.130.161) może się zmienić przy odnowieniu DHCP — wtedy reguła przestanie działać i Tailscale wróci do direct. Sprawdzić: `tailscale status | grep laptop` — musi być `relay "waw"`, nie `direct`.
- Gateway: usługa Windows `AlphaCAMGateway` (sc stop/start), port 8721, kod z repo: C:\Users\48797\Documents\PROJEKTY\alphacam_cli\alphacam_cli
- SSH: `ssh -i ~/.ssh/id_ed25519 48797@100.71.109.69` (po fixie stabilne)
- sshd_config naprawiony: UseDNS no, GSSAPIAuthentication no, MaxStartups/MaxSessions przed blokiem Match (wcześniej błąd 1067 — MaxStartups był w Match block)
- AlphaCAM: ALPHACAM [Router] 2025, program_level=14, licomdat=C:\ALPHACAM\ (narzędzia w LICOMDAT\RTools.Alp, posty w LICOMDAT\RPosts.Alp, style w LICOMDIR\Styles\{Fronty})

### Testy do wykonania po naprawie połączenia
1. **Nest**: naprawić `get_nesting()` (gencache/ACAMNESTLib lub inny dostęp) → `nest run` na części .ard
2. **Odporność**: brak aktywnego rysunku → czytelny błąd; zły post → błąd; restart usługi w trakcie sesji
3. **Mill style** na rysunku z makra (PanelRyflowany — geometria z atrybutami LicomUKDMBGeoZLevelTop/Bottom)
4. **Post list** — weryfikacja `post list` po fixie P6 (RPosts.Alp)

---

## ✅ NESTING DZIAŁA (2026-08-08) — jak zrobić przez API

**WARUNKI KRYTYCZNE:**
1. Części (.ard) MUSZĄ mieć **zdefiniowaną stronę obróbki (ToolInOut = OUTSIDE/INSIDE, nie CENTER)** ORAZ **wygenerowane toolpaths (obróbkę)** — inaczej `CreateNestData` odrzuca listę ("Błąd przy wczytywaniu listy nakładania").
   - Sprawdzenie: `d.ToolPaths.Count > 0` (produkcyjne cz1=11, cz2=1, cz11=1; nasze testowe bez obróbki = 0 → odrzucane)
   - ToolInOut: `geo.ToolInOut = 2` (OUTSIDE), zapisane w .ard przez SaveAs
2. **Musi być załadowany typelib AcamNest** — BEZ TEGO marshal obiektu NestData do Pythona failuje z `PermissionError(13)` mimo że lista tworzy się w GUI:
   ```python
   from win32com.client import gencache
   gencache.EnsureModule("{6702E3DF-142C-4627-8EA2-4C47EBC78441}", 0, 1, 3)
   ```
   (CLSID typelibu AcamNest = AcamRadNest.dll, z rejestru)
3. **Lista nakładania (.anl) to plik TEKSTOWY** generowany ręcznie:
   ```
   $SETUP
   1        <- Tool Paths (0=Geometry, 1=Tool Paths)
   2        <- Gap
   0        <- Lead Gap
   0        <- Subroutines
   0        <- Start at
   $ITEM
   C:\ścieżka\do\cz1.ard    <- część (z toolpaths!)
   1        <- liczba
   1        <- priorytet
   90       <- kąt obrotu
   0        <- mirror (0/1)
   ```

**DZIAŁAJĄCA SEKWENCJA (GUI, Session 2):**
```python
gencache.EnsureModule(typelib_acamnest)     # KLUCZOWE
app = GetActiveObject("Ar5axaps.Application")
app.New()
d = app.ActiveDrawing
nd = d.CreateNestData("ścieżka.anl")        # lista + części
sheet = d.CreateRectangle(0, 0, 2440, 1220) # arkusz z rysunku (opcja 2)
nd.AddSheet(sheet, "MDF", 18, 1)            # geometria, materiał, grubość, ilość
nd.DoNest()                                  # nakładanie ✅
```

**NestData metody (18):** AddSheet, Direction, DoNest, EdgeGap, Gap, LeadGap, MergeTools, MinimiseToolChanges, OrderByPart, OrderInnerFirst, RepeatFirstRowOrColumn, Resolution, SheetHGap, SheetVGap, Subroutines, ToolPaths

**Ograniczenia:**
- ~~❌ Session 0 (usługa gateway) NIE DZIAŁA — CreateNestData failuje (0x80004005) — AcamRadNest.dll NIE ładuje się w procesie usługi (Session 0). Zweryfikowane: `tasklist /m` pokazuje AcamRadNest.dll TYLKO w procesie GUI (Session 2)~~ → **HISTORYCZNE (sprzed poprawki 2026-08-08): błędny wniosek — przyczyną był brak konfiguracji HKCU dla SYSTEM (LocalSystem), NIE brak DLL. Teraz DZIAŁA — patrz "✅ SESSION 0 DZIAŁA" niżej**
- ~~❌ `App.Nesting` property: E_FAIL w Session 0, PermissionError(13) z Session 2 non-elevated~~ → **HISTORYCZNE: `App.Nesting` nie działa nigdy (wymaga parametru / E_FAIL), ale NIE jest już potrzebny — `CreateNestData` działa w Session 0**
- ❌ ProgIDy (Ar5axaps/Am5axaps/Aroutaps) wszystkie tworzą Router bez nestingu w Session 0
- ✅ Działa z GUI (Session 2, GetActiveObject, użytkownik 48797, schtasks /it)
- ✅ Arkusz z biblioteki: sheet_database_v2.db (SQLite!) — tabele: materials (MDF_18), thicknesses (18mm), sheets (MDF_18 2440x1220 qty100, Arkusz 1 1220x2440 17mm, MDF 1500x840, MDF18 2800x2070) — **WDROŻONE (patrz "✅ ARKUSZ Z BIBLIOTEKI" niżej)**
- ✅ **WYKONANE (biblioteka + rysunek):** 2 opcje arkusza — pełna komenda nest: elementy → arkusz → nakładanie → NC (nakładanie z arkusza z bazy potwierdzone E2E w Session 0)

**✅ SESSION 0 DZIAŁA (2026-08-08, poprawka) — nesting przez usługę gateway:**

**Przyczyna wcześniejszych faili (0x80004005):** usługa AlphaCAMGateway działa jako **LocalSystem** (sprawdzone `sc qc`), a użytkownik GUI to 48797. AlphaCAM uruchomiony jako SYSTEM czyta konfigurację z `HKU\.DEFAULT\SOFTWARE\Hexagon\ALPHACAM`, a ten klucz **nie istniał** — cała konfiguracja (w tym sekcja Nesting) była w `HKCU\SOFTWARE\Hexagon\ALPHACAM` użytkownika 48797. Bez niej Acam.exe nie wie o nestingu: IsAlphaNest=False, App.Nesting=E_FAIL, CreateNestData=0x80004005.

**Rozwiązanie (wykonane na laptop-monika, backup: `C:\temp\hexagon_48797_backup.reg`):**
```
reg copy "HKCU\SOFTWARE\Hexagon" "HKU\.DEFAULT\SOFTWARE\Hexagon" /s /f
```
→ restart usługi (`sc stop AlphaCAMGateway` → `sc start AlphaCAMGateway`).

**Działająca sekwencja przez RPC (Session 0):**
```python
gencache.EnsureModule(typelib_acamnest)       # KLUCZOWE
app = Dispatch("Ar5axaps.Application")        # Session 0 — Dispatch, nie GetActiveObject
app.New()
d = app.ActiveDrawing
d.CreateTempDrawing()                          # create_temp_drawing
nd = d.CreateNestData("ścieżka.anl")           # lista + części (.anl $SETUP/$ITEM)
sheet = d.CreateRectangle(0, 0, 2440, 1220)    # arkusz z rysunku
nd.AddSheet(sheet_geo.raw_dispatch, "MDF", 18, 1)  # KLUCZOWE: surowy COM, NIE wrapper CamPath
nd.DoNest()                                    # ✅ potwierdzone E2E: 3 geometrie, 24 toolpaths na arkuszu
```

**Fixy w kodzie:**
- `server.py` `_handler_run_nest` — `nd.AddSheet` przyjmuje `sheet_geo.raw_dispatch` (surowy obiekt COM) zamiast wrappera CamPath — inaczej "The Python instance can not be converted to a COM object"; grubość 18 mm, ilość 1
- `cli/nest.py` `run` przebudowane: generuje plik .anl ($SETUP/$ITEM) i używa CreateNestData zamiast zepsutego App.Nesting
- ⚠️ `Dispatch("AcamNest.Nesting")` → ClassFactory nie może dostarczyć klasy (0x80040111) — to normalne, NIE używać. `App.Nesting` **DZIAŁA** (w tym Session 0) — warunkiem jest `gencache.EnsureModule` typelibu Nesting PRZED dostępem (patrz "✅ ARKUSZ Z BIBLIOTEKI" niżej)

**Sync po zmianach w GUI:** po każdej zmianie ustawień nestingu w GUI użytkownika 48797 wykonaj ponownie `reg copy` (wyżej) i zrestartuj usługę. Backup istniejący: `C:\temp\hexagon_48797_backup.reg`.

**Do zbadania:** jak załadować AcamRadNest.dll w Session 0 (LoadAddIn z pełną ścieżką failuje E_INVALIDARG; EnableAddIn wymaga 2 param; IsAlphaNest=False; load przez rejestr acadaps-r\Applications2025\Nesting istnieje)

**ROZWIĄZANE (2026-08-08):** jak załadować AcamRadNest.dll w Session 0 — **nie trzeba**: AcamRadNest.dll ładuje się normalnie w procesie usługi; problemem był brak konfiguracji `HKU\.DEFAULT\SOFTWARE\Hexagon\ALPHACAM` (usługa jako LocalSystem nie miała konfiguracji HKCU użytkownika 48797). Po `reg copy` HKCU→HKU\.DEFAULT i restarcie usługi IsAlphaNest=True, a pełna sekwencja CreateNestData→AddSheet(raw_dispatch)→DoNest działa w Session 0 (potwierdzone E2E przez RPC).

### ✅ ARKUSZ Z BIBLIOTEKI (2026-08-08) — SheetDatabase zamiast CreateRectangle

**Baza arkuszy:** `C:\ALPHACAM\LICOMDAT\sheet_database_v2.db` (SQLite, ~45 KB). Obok: `C:\ALPHACAM\LICOMDAT\DefaultSheetSettings.acamcore` (XML, default 2440x1220, grubość 18 mm).

**Tabele i zawartość bazy:**
- `materials` (id, name): "17mm", "MDF_18"
- `thicknesses` (material_id, thickness, units): 17 mm, 18 mm
- `sheets` (thickness_id, width, height, units, name, quantity): "Arkusz 1" 1220x2440 qty100 (17mm), "MDF_18" 2440x1220 qty100 (18mm), "MDF" 1500x840 qty10, "MDF18" 2800x2070 qty100

**KLUCZOWE — to inna metoda niż rysowanie prostokąta:** arkusz jest wstawiany z bazy (wybór po nazwie), NIE przez CreateRectangle:

```python
from win32com.client import gencache
gencache.EnsureModule("{6702E3DF-142C-4627-8EA2-4C47EBC78441}", 0, 1, 3)  # typelib Nesting — OBOWIĄZKOWE przed App.Nesting
app = gencache.EnsureDispatch("Ar5axaps.Application")
n = app.Nesting                    # INesting (bez EnsureModule: "Parametr nie jest opcjonalny")
db = n.SheetDatabase               # ISheetDatabase
sheet = db.FindSheet(sheet_name)   # np. "MDF_18" → IDatabaseSheet; None jeśli brak
paths = sheet.InsertInActiveDrawingAtPoint(0.0, 0.0)  # IPaths — wstawia geometrię arkusza z bazy do aktywnego rysunku
nd.AddSheet(paths.Item(1), sheet.Material.Name, sheet.Thickness.Thickness, sheet.Quantity)  # Item(1) — kolekcja NIE działa!
nd.DoNest()
```

**Odkrycia (poprzedni raport był mylący):**
- `App.Nesting` i `SheetDatabase` **DZIAŁAJĄ w Session 0** — warunkiem jest `gencache.EnsureModule` typelibu Nesting PRZED dostępem (błąd "Parametr nie jest opcjonalny" powodował brak EnsureModule, nie Session 0)
- `AddSheet` przyjmuje POJEDYNCZY IPath (`paths.Item(1)`), NIE kolekcję IPaths (ta rzuca "can not be converted to COM object")
- ⚠️ `str()` na obiektach COM w f-stringach wywołuje default method (błąd) — zawsze używać `repr()`

**CLI / API:**
- Nowy parametr komendy: `sheet_name` (np. "MDF_18"); puste → stary sposób (create_rectangle 2440x1220)
- Brak arkusza w bazie → czytelny błąd: `nest: sheet from library not found: <nazwa>`
- `nest run` CLI: nowa opcja `--sheet-name`

**E2E (Session 0, żywy AlphaCAM 2025 Router):** run_nest z `sheet_name="MDF_18"` → success, aktywny rysunek **3 geometrie / 24 toolpaths**.

### ✅ ODSTĘPY NAKŁADANIA (2026-08-08) — --gap / --edge-gap / --lead-gap

**Nowe opcje w `nest run` (CLI) i `run_nest` (RPC):**
- `--gap` (float) — odstęp między częściami (mm); domyślnie z rejestru/`.anl` (GapBetweenParts=2.0)
- `--edge-gap` (float) — odstęp od krawędzi arkusza (mm); domyślnie 0.0
- `--lead-gap` (float) — odstęp lead-in/out (mm); domyślnie 0.0

**Zachowanie None (opcja nie podana):** property na INestData NIE jest ustawiane → obowiązują wartości z rejestru/pliku .anl. Po podaniu → ustawiane bezpośrednio na obiekcie INestData (Gap, EdgeGap, LeadGap) PRZED DoNest.

**E2E (Session 0, żywy AlphaCAM 2025 Router):** run_nest z `gap=5, edge_gap=10, lead_gap=1.5` → success, **3 geometrie / 24 toolpaths**; `gap=7.5, edge_gap=12.0, lead_gap=2.0` → success.

**Inne properties INestData (dostępne w API, NIEeksponowane w CLI):** SheetHGap, SheetVGap (odstępy między arkuszami), Resolution, Direction, Subroutines, ToolPaths.

---

## ✅ CDM (CABINET DOOR MANUFACTURING) DZIAŁA W SESSION 0 (2026-08-09)

**Przełom:** CDM (AlphaDOOR/AlphaCAM CDM — dodatek do produkcji drzwi meblowych) uruchomiony headless przez gateway RPC w Session 0. Nowa komenda: `cdm create JOB TYPE --width --length --quantity`, `cdm jobs`, `cdm types`.

### KLUCZOWE ODKRYCIE — GetAutomationManagerAddIn() WISI, GetAutomationManagerAddInGUI() DZIAŁA

| Metoda | Konstruktor | Zachowanie w Session 0 |
|---|---|---|
| `addins.GetAutomationManagerAddIn()` | `CTOR()` — tworzy kolekcje + `get_AutomationManagerDB()` → **ConnectToDatabase → modalny dialog** (VistaDB/SQL connection) | ❌ **WISI na zawsze** |
| `addins.GetAutomationManagerAddInGUI()` | `CTOR(bool)` — TYLKO kolekcje, bez DB connect | ✅ **DZIAŁA** (IsCDMAuthorised=True, Jobs, NewCDMJob, AddCDMOrderDetail, SaveToDatabase) |

Analiza IL AcamAddIns.dll: GetAutomationManagerAddIn robi `newobj .ctor()` (bezargumentowy, 140B — pełna inicjalizacja z DB), GUI robi `ldc.i4.1; newobj .ctor(bool)` (106B — tylko kolekcje).

### Fixy systemowe (laptop-monika, Session 0 = LocalSystem)

1. **`C:\Windows\System32\config\systemprofile\AppData\Local\Hexagon\Alphacam\AMSettings.acamcore`** (profil SYSTEM!) — skopiowany od użytkownika + rozszerzony:
   ```xml
   <ExtraSettingsList>
     <string>ShowCDM|1</string>
     <string>UseSQLServer|0</string>
     <string>UseCVMaterialsLibrary|0</string>
     <string>UseWorkplan|0</string>
     <string>ShowPartProcessing|0</string>
   </ExtraSettingsList>
   ```
   ⚠️ Bez ShowCDM=1 w profilu SYSTEM AutomationManager nie wie o CDM. Odpowiednik reg copy HKCU→HKU\.DEFAULT (nesting).
2. **Rejestr** HKCU + HKU\.DEFAULT `Software\VB and VBA Program Settings\LICOM AlphaDOOR\Options`: `Units=1` (DWORD), `SearchResolution=1`, `ShowPartProcessing=0` (bez tego CDM pyta o "Default Working Unit" — modalny dialog wisi w Session 0!)
3. **`regsvr32 CDM.dll`** (C:\ALPHACAM\LICOMDAT\CDM Data) — rejestruje ProgID-y `CDM2016R2.CVBAProject/DoorTypeData/MainFrontEnd/SplashScreen` (32-bit VB6, WOW6432Node). Acam.exe jest x64 → CDM.dll (VB6 32-bit) NIE ładuje się jako addin — CDM dostępny TYLKO przez Automation Manager (.NET).
4. **CLSID `{CC979E90-AA63-4F1A-90F8-78B93F4E2E0A}` (Alphacam.AddIns.AutomationManager)** — nie był zarejestrowany (w przeciwieństwie do NcOutputManager/AutoStyles) — rejestracja ręczna nie rozwiązała wiszenia (newobj .NET, nie COM CoCreate).

### Działająca sekwencja (Session 0, przez gateway)

```python
import pythoncom, win32com.client as w32
clsid = pythoncom.MakeIID("{39BFE38A-D3E4-43EA-89D0-584C776B97A9}")   # AddInsInterface
ai = w32.Dispatch(pythoncom.CoCreateInstance(clsid, None, pythoncom.CLSCTX_ALL, pythoncom.IID_IDispatch))
addins = ai.GetAddInsInterface(app)                                    # app = surowy dispatch AlphaCAM
am = addins.GetAutomationManagerAddInGUI()                             # ⚠️ NIE GetAutomationManagerAddIn!
# ✅ IsCDMAuthorised()=True, am.Jobs.Count, am.NewCDMJob()
job = am.NewCDMJob(); job.JobName = "X"; job.SaveToDatabase()
detail = job.AddCDMOrderDetail("Typ Frontu 1")                          # TypeName z tabeli CDM_DoorTypes
detail.Width=600; detail.Length=400; detail.Quantity=2; detail.SaveToDatabase()
```

**TypeName (z bazy VistaDB `C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5`, tabela CDM_DoorTypes):** "Typ Frontu 1".."Typ Frontu 47", "L_B_10mm", "L_B_32mm", "L_C_10mm", "M_01", "22" itd.

### Ograniczenia Session 0 (NIE działają headless — modalne okna WPF/WinForms)

- ❌ `job.Process()` — WISI (okno przetwarzania WPF). Wymaga GUI (Session 2).
- ❌ `job.ImportCSVToJob(path, None)` — WISI (dialog wyboru ImportSettings).
- ❌ `am.ImportCDMDatabase()` — błąd UserInteractive ("Wyświetlenie modalnego okna... nieprawidłowe gdy aplikacja nie pracuje w trybie UserInteractive").
- ✅ Działa: NewCDMJob, JobName, SaveToDatabase, AddCDMOrderDetail, settery Width/Length/Quantity/ByPassNest, Jobs/CDMOrderDetails iteracja, IsCDMAuthorised, ConfigurationSettings.

### Nowa komenda CLI (2026-08-09)

| Komenda | Opis | Status |
|---|---|---|
| `cdm create JOB TYPE --width --length --quantity` | Tworzy job CDM + pozycję drzwi w bazie | ✅ E2E Session 0 |
| `cdm jobs` | Lista jobów CDM z bazy | ✅ E2E Session 0 |
| `cdm types` | Typy drzwi (z jobów; headless ograniczone) | ⚠️ tylko z istniejących jobów |
| `cdm create --process` | Procesowanie — informuje że wymaga GUI | ⚠️ |

**RPC:** `run_cdm` (job_name, type_name, width, length, quantity, bypass_nest), `cdm_jobs`, `cdm_types`. Klient: `RemoteSession.run_cdm()/cdm_jobs()/cdm_types()`, `RemoteApplication.*` (local mode: `Application.get_automation_manager_addin()`).

**E2E (Session 0, żywy AlphaCAM 2025 Router):** `cdm create PROD_TEST_002 "Typ Frontu 3" --width 800 --length 500 --quantity 3` → OK; `cdm jobs` → 18 jobów (2 nowe). Testy: **428 passed**.

**Uwagi:**
- Joby testowe CDM_PROBE_* / PROD_TEST_* zostały w bazie (do usunięcia w GUI Automation Manager).
- Wiszące probe `cdm_probe`/`am_probe` w server.py — do usunięcia przy refactorze (handler `_handler_cdm_probe` z logami do C:\temp).
- Restart usługi po zmianach: taskkill Acam.exe → sc stop/start AlphaCAMGateway (inaczej stary proces z zablokowanym STA wisi).

### ✅ CDM TODO-NEXT (2026-08-09) — import CSV gated (GUI), types vdb5, delete E2E

**Nowe komendy (headless Session 0):**

| Komenda | Opis | Status E2E |
|---|---|---|
| `cdm types` | PEŁNA lista typów z bazy VistaDB (CDM_DoorTypes) + typy z jobów (merge dedupe) | ✅ 34 typy (source vdb5+com) |
| `cdm delete JOB` | Usuwa job przez `job.DeleteFromDB()` | ✅ 17 jobów testowych usuniętych przez RPC |
| `cdm import CSV` | ⚠️ **GATED** — zwraca czytelny błąd "requires GUI (Session 2)" | ✅ nie wisi, nie blokuje usługi |

**KLUCZOWE ODKRYCIE (pełna diagnostyka na maszynie, Session 0):** import CSV przez API NIE DZIAŁA headless:
- `job.ImportCSVToJob(csv, None)` → WISI (dialog wyboru settings, MessageBox)
- `job.ImportCSVToJob(csv, settings)` (NewImportSetting / ImportSettings.Item(1)) → wyjątek `UserInteractive` ("modalne okno... nieprawidłowe gdy aplikacja nie pracuje w trybie UserInteractive") lub WISI (blokuje STA usługi!)
- `am.CreateJobsFromCSVFile(csv, settings)` → z `CreateJob=0` (baza) zwraca PUSTĄ kolekcję; z `CreateJob=1` (UPDATE bazy) → WISI
- **Import CSV wymaga GUI (Session 2)** — joby tworzyć przez `cdm create` lub Automation Manager GUI

**Diagnostyka ImportSettings (laptop-monika, baza vdb5):**
- Tabela `AM_ImportSettings` (4 konfiguracje): Item1="sklep CSV" (IsCDMImport=True, DelimiterChar=`,`, SubDelimiterChar=`;`, IgnoreHeader=True, ImportSettingID=3) — konfiguracja sklepu
- Tabela `AM_ImportSettingsParameter` / `FieldsOrder`: mapowanie kolumn (Type 256=Style, 259/264/265/266=Width/Height/Qty/Material wg "sklep CSV")
- API: `IAutomationManagerImportSetting` (FieldsOrder, SetAsSelected, NewImportSettingField, SaveToDatabase(True/False)), `IAutomationManagerImportSettingField` (Type, ColumnNumber settable)
- VistaDB nie ma INFORMATION_SCHEMA — schemat przez `conn.GetSchema('Tables')`

**Sprzątanie na maszynie:**
- Usunięte joby: CDM_PROBE_* (10), PROD_TEST_* (2), E2E_CSV_TEST, DIAG_JOB/NONE/ITEM1/NEW (5) — przez `cdm delete` ✅
- Usunięte z C:\temp: diag_importcsv.py, diag_fields.py, diag_bulk_sel.py, logi, CSV-e testowe, skrypty ps1; task schtasks "diag_importcsv" usunięty
- W bazie przywrócone `CreateJob=0` dla ImportSettingID=3 (było testowo 1)

**Probe w Session 0 bez blokowania usługi (recepta!):** `schtasks /create /tn X /tr "python skrypt.py" /sc once /st 23:59 /ru SYSTEM /f` + `schtasks /run /tn X` → proces w Session 0 jako SYSTEM, osobny od usługi; watchdog w skrypcie (threading.Timer + os._exit). Uwaga: `sc` w PowerShell to alias Set-Content → używać `sc.exe`.

**Commity (master):** `fd79494` (cdm import/types-vdb5/delete + cleanup probes + README) → `b01e206` (fix vdb5 JSON array PS 5.1) → `607a686` (fix: import gated). Testy: 447 passed, ruff 0, mypy 0.

**TASKS.md (do następnych sesji):**
- [ ] **`_handler_probe_nest` wciąż wywoływalny przez RPC** (auto-dispatch `_handler_*`) — zawiera niebezpieczne modalne wywołania i `str()` na COM (zamiast repr). Do usunięcia lub whitelist w `_dispatch`.
- [ ] **`Application.cdm_types()` (core/local) nie czyta vdb5** — tryb lokalny niepełny; przenieść logikę vdb5 do core (wspólne źródło) albo dokumentować różnicę.
- [ ] Kaizen: `_handler_cdm_delete_job` lookup po nazwie — kandydat na helper (duplikacja zmalała po gatingu importu).
- [ ] Gateway bez autoryzacji (port 8721) — świadome, do rozważenia przy produkcji.
- [ ] Odczyt vdb5 (scripts/vdb5_door_types.ps1) ma twarde ścieżki maszynowe (VistaDB dll, vdb5) — ograniczenie instalacji, udokumentować.

### ✅ CDM IMPORT CSV — FINALNY WNIOSEK (2026-08-09, sesja z użytkownikiem)

**Import CSV z tworzeniem zadania NIE DZIAŁA headless w Session 0 — wymaga GUI (Session 2). Potwierdzone wielokrotnie na żywej maszynie (probe w osobnym procesie schtasks /ru SYSTEM):**

| Metoda | CreateJob=0 | CreateJob=1 |
|---|---|---|
| `job.ImportCSVToJob(csv, None)` | — | **WISI** (dialog wyboru settings) |
| `job.ImportCSVToJob(csv, settings)` | — | UserInteractive (wyjątek) lub **WISI** |
| `am.CreateJobsFromCSVFile(csv, settings)` | zwraca PUSTE (0 jobów, nie tworzy) | **WISI ZAWSZE** — nawet z poprawnym CSV (8 kolumn wg usera: `P003,1,500,500,1;18;0;0;30;45;40;90;50;3;0,<materiał>,<nazwa>,Fronty`), poprawną konfiguracją (sklep CSV z polami job), Selected=True; job NIE powstaje |

**Enuma pól importu (odczytany z AcamAddIns.dll przez reflection — `AutomationManagerImportSettingFieldType`):**
- CDM: 256=cdmDoorType, 257=cdmDoorWidth, 258=cdmDoorHeight, 259=cdmDoorQuantity, 260=cdmDoorMaterial, 261=cdmDoorCustomerName, 262=cdmDoorOrderNumber, 263=cdmDoorItemNumber, 264=cdmDoorDesignDimensions, 265=cdmDoorProductionComment, 266+=cdmDoorCustomField1..25, 271=rotation, 272=angle, 274=nest priority, 298=drilling, 299=small nest
- JOB: 512=jobName, 513=jobfkConfigID, 514=jobfkSetupID, 515=jobfkToolOrderID, 516=jobPurchaseOrderNumber, 517=jobWorkOrderNumber, 518=jobDescription, 519=jobProgrammerName, 520=jobOrderDate, 521=jobDueDate, 522=jobCustomer, 523=jobParentJob, 524=jobFkMaterialID
- GUI nazwy "Zadanie: ..." ↔ enum: Nazwa=512, Klient=522, Nazwa konfiguracji=513, Lista kolejności narzędzi=515, Nazwa zadania nadrzędnego=523, Nazwisko przygotowującego=519, Numer zamówienia=516, Numer zlecenia=517, Opis=518, Data zamówienia=520, Termin realizacji=521 (+ setup 514, materiał 524; "Nazwa konfiguracji odwzorowania warstw" — BRAK w enumie)

**Stan konfiguracji (laptop-monika, po sesji):**
- "sklep CSV" (ID3): 8 pól — 256,259,257,258,264 + col6=524 (materiał), col7=512 (nazwa), col8=513 (config "Fronty"); IgnoreHeader=False; CreateJob=True
- "Ustawienia Importu CSV 5" (ID7): 5 pól CDM, Selected=True, CreateJob=True (user ustawił w GUI)
- Konfiguracja testowa ID8 usunięta. AM_ImportSettingsParameter kolumna = ParameterType (nie "Type"!)

**Recepty na przyszłość:**
- `FieldsOrder.Add(field)` przez API dla pól job (512/513/524) → **UserInteractive** (wymagają GUI); daty (520/521) przechodzą headless. Edycja ustawień importu z polami job = GUI.
- Dump konfiguracji ImportSettings: przez `am.ImportSettings.Item(i)` (kolejność NIE po ID! — Item(2)=ID8 gdy istniał; zawsze settings_list z harnessa) lub `GetByName(name)`.
- `CreateJobsFromCSVFile` do tworzenia JOBÓW headless = NIE. Joby tworzyć przez `cdm create` (NewCDMJob+AddCDMOrderDetail — działa headless).
- Automatyzacja importu CSV: makro w GUI (Session 2) — schtasks /it + makro VBA (plan: użytkownik przygotuje makro).
- probe_cdm_import.py: `--method build-settings --fields "512,513,524"` edytuje FieldsOrder przez API (job* fail z UserInteractive) — narzędzie zostaje w scripts/.

**Sprzątnięte:** konfiguracja ID8 (baza), CSV-e i skrypty ps1 z C:\temp; task schtasks "cdm_probe" + run_probe.cmd zostają (narzędzie diagnostyczne). Joby "Nowe Zadanie 7/8" (z testów GUI usera) zostały.

### ✅ CDM IMPORT HEADLESS — WŁASNY IMPORTER DZIAŁA (2026-08-09, E2E potwierdzone)

**Rozwiązanie problemu dialogów:** zamiast `ImportCSVToJob`/`CreateJobsFromCSVFile` (zawsze dialog — wisi w Session 0) — **własny parser CSV + API NewCDMJob + AddCDMOrderDetail** (to samo co `cdm create`, działa headless).

**`cdm import CSV [--separator ,] [--header]`** — format "sklep CSV" (8 kolumn, bez nagłówka):
`Style,Qty,Width,Height,DesignDims[,Materiał,JobName,ConfigName]`
- DesignDims (`1;18;0;0;30;45;40;90;50;3;0`) → `detail.UserVariableString` **dopełniany zerami do 50** (GUI robi identycznie — potwierdzone w bazie: UserDescriptionString i UserVariableString zawsze 50 pozycji)
- grupowanie wierszy po JobName (kol 7); pusty → basename pliku; nowa nazwa → nowy job
- ConfigName (kol 8, np. "Fronty") → `job.ConfigurationSetting = am.ConfigurationSettings.GetByName(...)`
- Materiał (kol 6) — **ignorowany v1** (brak settera API; GUI też nie ustawia gdy brak materiału — fkMaterialID=0); WARNING per wiersz
- błędy per wiersz (zły styl, za krótki wiersz) → WARNING, reszta importuje się; 0 items → success=False
- E2E: `P003,1,500,500,1;18;0;0;30;45;40;90;50;3;0,MDF_18,ImportE2E 001,Fronty` → 2 joby/3 items; w bazie IDENTYCZNIE jak GUI: StyleName=PS_03, fkTypeID=68, UserVariableString 1:1

**Session 0 — okna bez desktopu:** Session 0 ma własny niewidzialny pulpit; procesy (Acam jako SYSTEM) tworzą okna normalnie (62 okna: główne "ALPHACAM [Router]", panele "Properties" = ListBox/PbrsHost — to stałe panele, NIE dialogi; "wiszacy" dialog = modalny czekający na klik, którego nikt nie wykona).

**Recepta na wiszące wywołania w probe:** `--watch-windows` (EnumWindows/EnumChildWindows po PID Acam — tytuły okien do logu; Session 0 okna niewidoczne — bez filtra IsWindowVisible).

**Joby w bazie po sesji:** 8 (6 produkcyjnych + Nowe Zadanie 7/8 z testów GUI + Nowy_projekt — job usera z importu GUI, zostawiony).

**Commity:** `cbe9e61` (własny importer — 460 tests) → `e18fe1d` (dopełnienie do 50 — 462 tests). README: sekcja cdm import zaktualizowana? — do sprawdzenia przy okazji (opis importu w README mówi o requires GUI — NIEAKTUALNY, poprawić w następnej sesji).

### ✅ CDM IMPORT — SEMANTYKA PRODUKCYJNA (2026-08-09, E2E potwierdzone)

**Ustalenia z użytkownikiem (krytyczna analiza flow):**
- Produkcyjne CSV = TYLKO parametry drzwi (5 kolumn: Style,Qty,Width,Height,DesignDims). Bez pól zadania.
- Zadania tworzą się AUTOMATYCZNIE gdy jest potrzeba (przychodzi CSV → utwórz zadanie, wrzuć pozycje).
- "sklep CSV" = import Z tworzeniem zadania; "Ustawienia Importu CSV 5" (ID7) = SAM import do istniejącego zadania (CreateJob=False; GUI: ImportCSVToJob → dialog → w Session 0 wisi).

**Finalna semantyka `cdm import CSV [--name N] [--config K] [--job J] [--separator] [--header]`:**
- 5 kolumn parametrycznych; kolumny 6+ ignorowane cicho; wiersz <5 kolumn → error
- `--job J` → import do istniejącego zadania (lookup; brak → "job not found"; NIE tworzy)
- bez `--job` → AUTO-CREATE: `--name` lub basename pliku (≤60), `--config` opcjonalny (`GetByName`; brak → twardy błąd "config not found"); AM default config = Fronty (41)
- `--name`+`--job` → "mutually exclusive"; wszystkie wiersze → JEDNO zadanie
- E2E (baza zweryfikowana 1:1 z GUI): `prod` (basename, 2 items), `Zadanie 132` (--name+--config, 2 items), `Nowy_projekt` (--job, +2 items → 3 pozycje); UserVariableString dopełnione do 50; StyleName=PS_03/fkTypeID=68
- 468 passed, ruff 0, mypy 0 (commit `dc0436f`)

**TASKS.md aktualizacja:**
- [ ] README sekcja `cdm import` — NIEAKTUALNA (mówi "requires GUI (Session 2)") — poprawić na nową semantykę (auto-create, --job, 5 kolumn).
- [ ] Kaizen: `_find_cdm_job(am, name)` helper — duplikacja lookupu między `_handler_cdm_import_csv` a `_handler_cdm_delete_job`.
- [ ] Materiał — nadal bez settera API (v1 ignorowany, GUI też zostawia fkMaterialID=0).

### ✅ CDM IMPORT — MATERIAŁ Z SQLITE (2026-08-09, E2E potwierdzone)

**Materiał = ARKUSZ z bazy `C:\ALPHACAM\LICOMDAT\sheet_database_v2.db` (SQLite)** — to jest "zakładka Materiały" w Automation Manager GUI (NIE VistaDB AM_Materials — tam są stare arkusze "Material 2/3/4" nieużywane przez GUI):
- tabele: `materials` (1=17mm, 2=MDF_18), `sheets` (2=MDF_18 2440x1220x18, 3=MDF 1500x840, 4=MDF18 2800x2070), `thicknesses`, `zones`
- potwierdzenie: stare joby — CDM_OrderDetails fkMaterialID=2 (job 129/132) = arkusz MDF_18
- **fkMaterialID w AM_JobDetails/CDM_OrderDetails = ID z SQLite** (sheets.id, dla MDF_18 = 2)

**Implementacja (commity `6def4e3`..`4f3668d`):**
- `scripts/sheet_materials.py` — odczyt SQLite (sheets+materials) → JSON (subprocess python)
- `_sheet_materials()` w server.py/application.py — dict nazwa→ID (priorytet sheets)
- `scripts/vdb5_set_job_material.ps1` — **dwukrokowy**: SELECT JobDetailID po nazwie → UPDATE [fkMaterialID] po ID (VistaDB: UPDATE WHERE JobName=... zwraca rows:0 — quirk; po ID działa; [fkMaterialID] escape — MATERIAL = keyword!)
- E2E: `cdm import prod_mat.csv --name "Material E2E 003"` (kol 6 = MDF_18) → **job 170 fkMaterialID=2** — materiał ustawiony, bez ostrzeżeń
- 474 passed, ruff 0, mypy 0

**Pułapki odkryte:**
- VistaDB: `SET fkMaterialID` → "Incorrect syntax near MATERIAL" — wymaga `[fkMaterialID]`
- VistaDB: UPDATE WHERE string column (JobName) zwraca rows:0 (SELECT działa!) — update po JobDetailID
- PowerShell: `param()` musi być pierwszą instrukcją
- Testy ręczne skryptów ps1 przez SSH z parametrami ze spacjami są ZWODNICZE (cmd rozbija argumenty — '$JobName' = 'Material') — testować przez handler/subprocess, nie przez ssh z paramami
- `CDM.mdb` (Access, C:\ALPHACAM\LICOMDAT\CDM\) — stara baza CDM: AD_MATERIALS ma tylko "17mm"; OLEDB providers nie zainstalowane — odczyt przez mdbtools na Linuxie

### ✅ CDM IMPORT — USTAWIENIA DOMYŚLNE Z BAZY (2026-08-09, E2E)

**"Ustawienia domyślne" (zakładka AM) w bazie:**
- `AM_Settings`: fkConfigurationSettingID=41 (Fronty), fkSetupID=1, fkToolOrderID=1 — domyślna konfiguracja/setup/tool (NewCDMJob bierze je AUTOMATYCZNIE — nie trzeba ustawiać)
- `AM_JobFileDefaults` (per konfiguracja): dla 41 → fkSetupID=1, fkToolOrderID=2, **fkMaterialID=4** (arkusz MDF18 2800x2070 z SQLite sheets)
- GUI nowe zadanie (Nowe Zadanie 12): cfg=41, setup=1, tool=1, **mat=0** (GUI NIE ustawia materiału na jobie! materiały tylko per produkt)
- Materiał domyślny z defaults: fkMaterialID=4 (ID z SQLite sheets — MDF18)

**Implementacja (commit `2b3df46`, 478 passed):**
- `scripts/vdb5_job_defaults.ps1` — AM_Settings cfg → nazwa configu + AM_JobFileDefaults fkMaterialID → JSON
- `cdm import`: `--config`/`--material` JAWNE (priorytet) → brak → defaults z bazy (config z AM_Settings, materiał z AM_JobFileDefaults) — **zero hardcode'ów** (usunięte "Fronty")
- materiał ustawiany na jobie ORAZ detailach (CDM_OrderDetails.fkMaterialID — GUI tak czyta)
- E2E: CSV 5-kolumnowy bez materiału, bez opcji → job 177: cfg=41, mat=4, detale mat=4, Material: MDF18
- `--job` (istniejące zadanie): config niezmieniany (zachowuje swoją); materiał ustawiany jeśli podany/defaults

**Flow produkcyjny finalny:** `alphacam cdm import zamowienie.csv --name "Zamowienie X"` → zadanie z defaultami (Fronty + MDF18) + pozycje z CSV (materiał z CSV kol 6 nadpisuje default; --material/--config nadpisują wszystko).

### ✅ CDM HARDENING + REFACTOR (2026-08-09, E2E na laptop-monika, commity a318b66..a4efa76)

**Wspólny moduł `core/cdm_db.py` (dedup core↔gateway):** `sheet_materials`, `vdb5_job_defaults`, `set_job_material`, `vdb5_door_type_names`, `merge_door_types`, `find_cdm_job`, `read_cdm_csv`, `parse_cdm_rows`, `job_count`, `cleanup_created_job`, `_scripts_dir` (frozen). Server i core używają tych samych funkcji — usunięto ~280 linii duplikacji.

**Bugfixy potwierdzone E2E:**
- **CSV**: utf-8-sig (BOM z Excela — wcześniej `\ufeffStyle` → fałszywy "door type not found") → cp1250 fallback (stary `errors="replace"`+UnicodeDecodeError był MARTWY); separator musi być 1-znakowy (czytelny błąd); walidacja qty/width/length > 0; parse WSZYSTKICH wierszy PRZED utworzeniem joba
- **Pusty job po imporcie**: gdy 0 pozycji się udało → job usuwany + weryfikacja przez VistaDB (`job_count`). **Pułapka COM:** DeleteFromDB na świeżym obiekcie z NewCDMJob = CICHY NO-OP; na obiekcie z kolekcji am.Jobs działa (ale tylko po no-op z pkt 1 — sekwencja direct→lookup); kolekcja am.Jobs STĘCHŁA po usunięciu (zwraca usunięty obiekt) → weryfikacja tylko przez DB
- **`cdm create`**: walidacja wejścia, duplikat nazwy → "job already exists", `--material` (default z vdb5), materiał rozwiązywany PRZED NewCDMJob; usunięta martwa flaga `--process`; błąd typu drzwi → job czyszczony (M1 review)
- **`cdm types`**: core/local zrównany z serwerem (merge vdb5+com, casefold dedupe)
- `except Exception: pass` w `_cdm_known_door_types` → logger.warning
- alphacam.spec: `datas=[('scripts','scripts')]` + hiddenimports (cdm + wszystkie subkomendy) — PyInstaller

**E2E na żywym AlphaCAM 2025 (Session 0, gateway RPC):** types (26+ typów, vdb5+com) ✅; create z `--material MDF_18` → mat=2 w AM_JobDetails ✅; duplikat/width=0/qty=-1/zły materiał → czytelne błędy exit 1, bez sierot ✅; import normalny (materiał z kol 6) / BOM / cp1250+`;` / `;;` błąd / `--job` update / partial warnings ✅; all-bad → exit 1 + "deleted" + count=0 w DB ✅; create z błędnym typem → brak sieroty (count=0) ✅; delete ✅. 544→564 passed, ruff 0, mypy 0.

**Review (code-reviewer, 0 critical):** M1 run_cdm sierota → fixed; M3 PyInstaller → fixed (spec + _scripts_dir); M2 duplikacja core↔server ~280 linii → w TASKS.md (refactor do wspólnych helperów _run_cdm_with/_import_csv_with); m1-m6 → fixed. P1 (błędy core w remote opakowane "Unexpected COM error" zamiast cdm: ...) → w TASKS.md. P2 (_handler_probe_nest martwy) → w TASKS.md.

**Pułapki:**
- `am.Jobs` po DeleteFromDB zwraca usunięty obiekt (stęchła kolekcja) — NIGDY nie weryfikuj usunięcia przez COM, tylko przez VistaDB
- subprocess powershell przez ssh z parametrami zawierającymi spacje — testować przez handler, nie ręcznie
- Windows cmd: `&` w ssh urywa resztę komendy (Input redirection error) — rozdzielać kroki

### ✅ E2E FAZA 1 — CDM IMPORT MAPPING (2026-08-09, gateway RPC, commity bf836b8..c79fba2)

Push `90c5a60..c79fba2` master → git pull na maszynie (fast-forward, bez konfliktów) → restart AlphaCAMGateway (sc stop/start, RUNNING) → RPC OK.

**E2E A — import z mapowaniem "sklep CSV" (id=3, 8 kolumn) ✅**
- `cdm import e2e_sklep.csv --import-setting 3` → success, job "Faza1 E2E 001", 2 items, Material: MDF_18
- Wariant z nazwą: `--import-setting "sklep CSV"` na kopii z jobem 002 → success
- Baza (vdb5_order_details): 2 wiersze; style_name="PS_03" (style_number=930); quantity 1/2; width/length 500/500 i 600/400; material_id=2; user_variable_string 50 pozycji; user_description_string = "Typ_Krawedzi;Grubosc_Plyty;..." (11 pozycji)

**E2E B — nowe pola CDM (ustawienie testowe id=10, 17 pól) ⚠️ CZĘŚCIOWY**
- Setup: backup (2 settings / 14 params), INSERT ustawienia + 17 parametrów, weryfikacja → RPC import-settings list pokazuje 17 pól (1→door_type ... 17→door_small_nest)
- Import `e2e_nowe_pola.csv --import-setting 10 --name "Faza1 E2E NowePola"` → success 2 items, ale 4 WARNING-i
- Baza: csv_customer_name="Kowalski Jan"/"Nowak Anna" ✅, csv_order_number="KW/2026/08"/"Z/100/2026" ✅, csv_item_number="Nr 5"/"Nr 8" ✅, production_comment="Komentarz testowy"/"Komentarz 2" ✅, custom_fields {"1":"F1","2":"F2"} / {"1":"G3","2":"G4"} ✅, nesting_priority=5/3 ✅, rotation_angle=45/90 ✅, small_nest_part=true/false ✅, material_id=2 ✅, quantity 1/3 ✅
- **NIEDZIAŁA (WARNING-i, do fixu w kolejnym tasku):**
  - `WARNING: row 1: RotationMethod failed: (-2147467262, 'Taki interfejs nie jest obsługiwany.', (0, 'mscorlib', 'Element OleAut wystąpiła zgłosił niezgodność typów.', None, 0, -2147467262), None)` → rotation_method=0 w bazie (oczekiwane 1/2)
  - `WARNING: row 1: HasDrilling failed: '<win32com.gen_py.ALPHACAM Add-Ins 1.0 Type Library.ICDMOrderDetail instance at 0x...>' object has no attribute 'HasDrilling'` → has_drilling=false (oczekiwane true) — brak atrybutu w typelibie
  - (takie same dla row 2) — pozostałe settery (RotationAngle, NestingPriority, SmallNestPart) działały

**E2E B-2 — po fixach (rotation_method int + has_drilling vdb5) ⚠️ CZĘŚCIOWY (T6d, commity c79fba2..f7ecb93):**
- Deploy: push c79fba2..f7ecb93 → git pull fast-forward (7 plików, +275) → restart AlphaCAMGateway (RUNNING) → RPC OK
- Setup: backup 2 settings + 14 params → INSERT 'E2E Faza1 Fix' + 17 parametrów (bez ID!) → **new_id=11** (MAX przed=4, po=11 — auto-increment potwierdzony, sekwencja nie wraca), PARAM_COUNT=17
- Import `e2e_fix.csv --import-setting 11 --name "Faza1 E2E Fix"` → **success 2 items, ale 1 WARNING**: `WARNING: job Faza1 E2E Fix: failed to set has_drilling` (ZERO warningów dla rotation)
- Baza (vdb5_order_details):
  - wiersz1: csv_customer_name="Kowalski Jan" ✅, csv_order_number="KW/2026/08" ✅, csv_item_number="Nr 5" ✅, production_comment="Komentarz testowy" ✅, custom_fields {"1":"F1","2":"F2"} ✅, **rotation_method=3 ✅ (fix ffefc72 działa!)**, rotation_angle=30 ✅, nesting_priority=7 ✅, **has_drilling=false ❌ (oczekiwane true)**, small_nest_part=true ✅, material_id=2 ✅, quantity=1 ✅
  - wiersz2: "Nowak Anna" ✅, "Z/100/2026" ✅, "Nr 8" ✅, "Komentarz 2" ✅, {"1":"G3","2":"G4"} ✅, **rotation_method=1 ✅**, rotation_angle=90 ✅, nesting_priority=2 ✅, has_drilling=false (oczekiwane false — bez zmian), small_nest_part=false ✅, quantity=3 ✅
- Preview (dry run): tabela 17 pól OK, vdb5_job_count przed=1 po=1 (bez zmian) ✅
- **ROOT CAUSE has_drilling (NOWY — nie COM!): `vdb5_set_has_drilling.ps1:28` — `$values = $Values -split ';'`.** W PowerShell zmienne są **case-INSENSITIVE**: `$values` i `$Values` to TA SAMA zmienna zadeklarowana w `param([string]$Values)`, więc przypisanie tablicy ze splitu jest **rzutowane na [string]** → "1 0" (1 element!) → "row count mismatch: 2 rows vs 1 values" → Write-Error → stderr (gateway loguje tylko stdout → mylące puste "vdb5 update failed: ") → returncode 1 → warning
- Diagnoza: test_subprocess.py (subprocess dokładnie jak gateway) → RC=1, stdout='', stderr='row count mismatch: 2 rows vs 1 values'; echo_args.ps1 (`$v2` — inna nazwa!) → split daje 2 elementy; minimalny skrypt z `[string]$Values` + `$values = $Values -split ';'` → COUNT=1 JOIN=[1 0]; inline `[string]$v='1;0'; $v = $v -split ';'` → COUNT=1 JOIN=[1 0] **potwierdzenie 100%**; inline bez typowania → COUNT=2
- **FIX (kolejny task):** w `scripts/vdb5_set_has_drilling.ps1` użyć INNEJ nazwy zmiennej niż `$Values` (np. `$valuesList`/`$flags`), bo case-insensitivity + [string] param psuje split. Sprawdzone: jedyny skrypt z tym wzorcem; vdb5_set_job_material.ps1 działa (brak splitu na zmiennej param)
- Sprzątanie ✅: cdm delete success, vdb5_job_count=0; DELETE 17 params + 1 setting (id=11) potwierdzone (LEFT=0/0); rmdir C:\temp\faza1_e2e2; import-settings list: tylko 3 i 4

**E2E B-3 — has_drilling po fixie case-insensitive ✅ (T6c-3, commit 6d508fc):**
- Fix: `scripts/vdb5_set_has_drilling.ps1` — lokalna zmienna `$values` → `$flags` (PS case-insensitive kolidowała z `param([string]$Values)`); `$flags = $Values -split ';'` daje tablicę (nie string "1 0")
- Deploy: push 6d508fc → git pull fast-forward (1 plik, +4/-4) → restart AlphaCAMGateway (RUNNING, PID 12520)
- Setup: backup 2 settings + 14 params → INSERT 'E2E Faza1 Fix2' (bez ID) → **new_id=12** (auto-increment ciąg dalszy), PARAM_COUNT=17
- Import `e2e_drill.csv --import-setting 12 --name "Faza1 E2E Drill"` → **success 2 items, ZERO WARNING-ów** ✅
- Baza (vdb5_order_details): wiersz1 "Kowalski Jan"/"KW/2026/08"/"Nr 5"/"Komentarz testowy"/{"1":"F1","2":"F2"} ✅, rotation_method=3 ✅, rotation_angle=30 ✅, nesting_priority=7 ✅, **has_drilling=true ✅ (FIX DZIAŁA)**, small_nest_part=true ✅, material_id=2 ✅, quantity=1 ✅; wiersz2 "Nowak Anna"/"Z/100/2026"/"Nr 8"/"Komentarz 2"/{"1":"G3","2":"G4"} ✅, rotation_method=1 ✅, rotation_angle=90 ✅, nesting_priority=2 ✅, **has_drilling=false ✅**, small_nest_part=false ✅, material_id=2 ✅, quantity=3 ✅
- Ręczny test skryptu nie był potrzebny (import przeszedł bez warningów)
- Sprzątanie ✅: cdm delete success; DELETE 17 params + 1 setting (id=12), LEFT=0/0; rmdir C:\temp\faza1_e2e3; import-settings list: tylko 3 i 4

**E2E B-4 — sanity F3 import --job z drillingiem ⚠️ CZĘŚCIOWY FAIL (commit 8d695a1):**
- Deploy: push fd9dedb → git pull fast-forward (8 plików, +224/-63) → restart AlphaCAMGateway (nssm; uwaga: `sc stop && ... && sc start` w jednym łańcuchu NIE zadziałał — brak wpisu START w event logu, usługa STOPPED; osobne `sc start` + 45s → RUNNING, port 8721 LISTENING)
- Setup: backup 2 tabel → INSERT 'E2E Sanity Drill' (bez ID) → **new_id=13**, PARAM_COUNT=17, kol 16→298 ✓
- **Test 1 (nowy job, drill1.csv 2 wiersze: drilling 1,0): success 2 items, ZERO warningów — ALE BAZA ODWRÓCONA: ID=105 "Nr 5" (drilling=1 w CSV) has_drilling=FALSE ❌, ID=106 "Nr 8" (drilling=0) has_drilling=TRUE ❌** (oczekiwane: 105=true, 106=false). Regresja F3: `ORDER BY CDMOrderDetailID DESC` + `GetRange(0, N)` odwraca kolejność values vs wiersze dla wielu wierszy naraz
- **Test 2 (import --job, drill2.csv 1 wiersz drilling=1): success 1 item, ZERO warningów ✅ (F3 naprawił sedno — wcześniej "failed to set has_drilling"); nowy wiersz ID=107 "Nr 9" has_drilling=true ✅; 105/106 nietknięte przez --job (ale już błędne po Teście 1)**
- Test 3 niepotrzebny (Test 2 przeszedł)
- **Wniosek: F3 naprawia import --job (1 nowy wiersz), ale łamie kolejność dla nowego joba z wieloma wierszami. Poprawny fix: ORDER BY ASC + `GetRange(ids.Count - flags.Count, flags.Count)` (ostatnie N w kolejności rosnącej) zamiast DESC + GetRange(0,N)**
- Sprzątanie ✅: cdm delete success; DELETE 17 params + 1 setting (id=13), LEFT=0/0; rmdir C:\temp\faza1_sanity; import-settings list: tylko 3 i 4

**E2E B-5 — F3b: ASC + last N slice — oba testy ✅ (commit 82cbef4):**
- Fix: `scripts/vdb5_set_has_drilling.ps1` — `ORDER BY CDMOrderDetailID ASC` (powrót z DESC), pobranie WSZYSTKICH ID, `$start = $ids.Count - $flags.Count` → mismatch exit 1 tylko gdy start<0; `if ($start -gt 0) { $ids = $ids.GetRange($start, $flags.Count) }` (ostatnie N rosnąco). Dla nowego joba start=0 (wszystkie), dla --job z 2 starymi + 1 nowym start=2 (tylko nowy). Zachowane: `$flags = $Values -split ';'` (case-sensitive!), `[HasDrilling]`, `rows: N`
- Deploy: push 82cbef4 → git pull fast-forward (1 plik, +5/-4) → restart AlphaCAMGateway (osobno `sc stop` → osobno `sc start` + 45s → RUNNING)
- Setup: backup 2 tabel → INSERT 'E2E Sanity Drill2' (bez ID) → **new_id=15** (pierwsza próba id=14 z błędną kolejnością typów — usunięta), PARAM_COUNT=17, kol 16→298; **kolejność mapowania kolumn (potwierdzona): 1→256(type), 2→259(qty), 3→257(width), 4→258(height), 5→264(design), 6→260(material), 7→261(customer), 8→262(order), 9→263(item), 10→265(comment), 11→266(custom1), 12→267(custom2), 13→271(rotation), 14→272(angle), 15→274(nest), 16→298(drilling), 17→299(small)**
- **Test 1 (nowy job, drill1.csv 2 wiersze drilling 1,0): success 2 items, ZERO warningów ✅; baza: wiersz1 "Nr 5" has_drilling=TRUE ✅ (drilling=1), wiersz2 "Nr 8" has_drilling=FALSE ✅ (drilling=0) — regresja B-4 NAPRAWIONA, kolejność values poprawna**
- **Test 2 (import --job, drill2.csv 1 wiersz drilling=1): success 1 item, ZERO warningów ✅; baza: 3 wiersze — (1) "Nr 5" true (nietknięty) ✅, (2) "Nr 8" false (nietknięty) ✅, (3) "Nr 9" nowy true ✅ — F3b działa dla --job (start=2 → tylko nowy)**
- Sprzątanie ✅: cdm delete success; DELETE 17 params + 1 setting (id=15), LEFT=0/0; rmdir C:\temp\faza1_sanity2; import-settings list: tylko 3 i 4

**E2E C — preview (dry run) ✅**
- `cdm import e2e_sklep.csv --import-setting 3 --preview` → tabela Field mapping (8 kolumn: 1→door_type, 2→door_quantity, 3→door_width, 4→door_height, 5→door_design_dimensions, 6→job_material_id, 7→job_name, 8→job_config_id), Job "Faza1 E2E 001", Items: 2, exit 0
- Dowód braku zmian: vdb5_job_count przed=1, po=1
- Preview 17-pola: klient/komentarz/custom widoczne (JobName z nazwy pliku gdy --name nie podany)

**E2E D — wsteczna zgodność (stary parser, 5 kolumn) ✅**
- `cdm import e2e_5kol.csv --name "Faza1 E2E Legacy"` (bez --import-setting) → success 1 item; baza: 1 wiersz, user_variable_string 50 pozycji, material_id=4 (MDF18 default starego parsera), style PS_03

**import-settings list:** przed: 3 "sklep CSV" (8), 4 "Ustawienia Importu CSV 2" (6) → w trakcie + 10 "E2E Faza1 Test" (17) → po sprzątaniu: tylko 3 i 4 ✅

**Sprzątanie ✅:** cdm delete ×4 (001, 002, NowePola, Legacy) success, vdb5_job_count=0; DELETE 17 params + 1 setting (id=10) potwierdzone; rmdir C:\temp\faza1_e2e; import-settings list bez "E2E Faza1 Test"

**Pułapki (WAŻNE dla przyszłych tasków):**
- **AM_ImportSettings.ImportSettingID i AM_ImportSettingsParameter.ImportSettingsParameterID to AUTO-INCREMENT w VistaDB** — jawny ID w INSERT jest IGNOROWANY (podaliśmy 5, dostał 9 → DELETE po 5 nic nie usunął). Wstawiać BEZ kolumny ID i odczytać `SELECT MAX(...)` po INSERT; sekwencja nie wraca (kolejny będzie 11)
- `$pid` w PowerShell = wbudowana stała read-only — `$pid = ...` rzuca "Cannot overwrite variable PID"; używać np. `$newParamId`
- ConvertTo-Csv na hashtable daje śmieci ("IsReadOnly","Count"...) — używać PSCustomObject + Add-Member
- style dla P003 w tej bazie = PS_03 (style_number 930); legacy material_id=4 (MDF18)
- Komentarze ASCII działają; polskie znaki w CSV nie były testowane (tylko ASCII w tym teście)

### ⏳ Pre-existing z review Fazy 1 (2026-08-09)
- **Duplikacja logiki CDM między application.py a server.py** (helpers, _FIELD_SETTERS, _import_cdm_csv_mapped) — refactor do wspólnego modułu (przyczyna przeoczenia cache w _handler_run_cdm) — **wysoki priorytet**
- **Twarde ścieżki w skryptach ps1** (`C:\Program Files\Hexagon\ALPHACAM 2025\`, `C:\ALPHACAM\`) — złamie przy zmianie wersji
- **_handler_probe_nest (server.py ~425-779)** — ~350 linii diagnostycznych z hardcoded ścieżkami użytkownika w produkcyjnym gateway — do wycięcia/feature flag
- **No-op settery _RemoteMillData** (rapid_down_to, drill_type, process_type — remote.py) — ciche pomijanie parametrów w trybie zdalnym
