# TASKS.md — Alphacam CLI

## Status: ~85% gotowości produkcyjnej — PRZED v1.0.0

- ruff ✅ mypy ✅ pytest **140/140** ✅ build wheel ✅
- COM safety: STA thread ✅ cross-thread marshal ✅
- CI: publish workflow ✅ lint ✅ typecheck ✅

---

## Zrealizowane w bieżącej sesji (Sprint v1.0.0)

### P0 — Cross-thread COM (Fix krytyczny)
- [x] `com/manager.py` — dedykowany STA thread z message pumpą (zamiast ThreadPoolExecutor)
- [x] Marshal dispatch przez CoMarshalInterThreadInterfaceInStream (Windows) / direct (Linux)
- [x] Usunięto dead code: `_dispatch_lock`, zewnętrzne `CoInitializeEx`

### P0 — Testy
- [x] **com/manager.py** — 14 testów (timeout, ProgID fallback, error handling, _owned, Quit)
- [x] **core/application.py** — 15 testów (12 nowych: new_drawing, quit, select_tool, find, nesting, post, None return)
- [x] **core/drawing.py** — 18 testów (14 nowych: create_circle/text/2d/polygon, save_as, output_nc, clear, select_all, CamPath, Geo2D, Text)

### P1 — Testy CLI + Machining + Common
- [x] **cli/*.py** — 31 testów (20 nowych przez CliRunner z mockowanym COM)
- [x] **core/machining.py** — 15 testów (14 nowych: wszystkie settery + 6 metod dispatch)
- [x] **cli/common.py** — 4 testy dla `@handle_com_errors` (exit 0,1,3,4)

### P1 — CI
- [x] `.github/workflows/publish.yml` — PyPI trusted publishing (OIDC), lint + typecheck + test przed build

### P2 — Fixy jakości (z /diagnose)
- [x] **PE-02**: NcEventHandler nc_path — konstruktor opcjonalny + ustawiany po DispatchWithEvents
- [x] **PE-03/04/06**: batch.py — progress.advance zawsze wywoływany, summary przed raise, logowanie typer.Exit
- [x] **nest.py**: TRY301 — raise typer.Exit poza blokiem try
- [x] **pyproject.toml**: long_description_content_type + py.typed force-include

### P2-P3 — Dodatkowe testy
- [x] **core/events.py** — 5 testów dla NcEventHandler
- [x] **core/tool.py** — 3 testy edge case (None, empty name, zero diameter)
- [x] **cli/diagnose.py** — 2 testy (success + connection error)

### Fixy pre-existing błędów
- [x] **PE-01**: Cross-thread COM — STA thread + marshal
- [x] **PE-02**: NcEventHandler nc_path — optional + post-set
- [x] **PE-03**: batch.py progress.advance pomijane — naprawione
- [x] **PE-04**: batch.py brak summary przy błędzie — naprawione
- [x] **PE-06**: handle_com_errors nie loguje typer.Exit — naprawione

### Świadomie pominięte na tę sesję
- PE-05: batch.py niespójna obsługa błędów — naprawione przez refaktor _process_file
- PE-08: _dispatch_lock dead code — usunięty w STA refaktorze
- PE-09: zewnętrzne CoInitializeEx — usunięty w STA refaktorze
- PE-10: mylący docstring — zaktualizowany w STA refaktorze

---

## Pozostałe zadania PRZED v1.0.0 (niedokończone)

### P0 — Krytyczne
- [x] ~~Cross-thread COM~~ — STA thread + marshal ✅
- [x] ~~Testy com/manager.py~~ — 14 testów ✅
- [x] ~~Testy core/application.py~~ — 15 testów ✅
- [x] ~~Testy core/drawing.py~~ — 18 testów ✅
- [x] ~~Workflow publish PyPI~~ — `.github/workflows/publish.yml` ✅

### P1 — Ważne
- [x] ~~Testy cli/*.py~~ — 31 testów z mockami ✅
- [x] ~~Testy core/machining.py~~ — 15 testów ✅
- [x] ~~Testy cli/common.py~~ — 4 testy dla handle_com_errors ✅

### P2-P3 — Do zrobienia w kolejnej sesji

- [x] **Dodać code coverage do CI** — `pytest-cov` + upload (Codecov/Coveralls) + gate <70%
- [ ] **Przesunąć classifier na `5 - Production/Stable`** — po stabilizacji (decyzja: zostać na 4-Beta)
- [x] **Windows setup docs do README** — pywin32, COM registration, VC++
- [x] **Ukryć console podczas PyInstaller build** — `console=False` w .spec
- [ ] **Dodać testy integracyjne** — 3 testy w `test_workflows.py` (obecnie stuby, gotowe na Windows)
- [x] **Fix PE-07**: batch.py save_as fail po output_nc (częściowy sukces) — rozdzielenie try/except
- [x] **Fix PE-11**: conftest.py ComError brak strerror — dodany atrybut
- [x] **Fix PE-12**: ac_app None w finally (manager.py) — Quit w finally + guard
- [x] **Fix PE-14**: batch brak podsumowania przy błędzie — len(files)→len(results)
- [x] **Fix PE-15**: typer.Exit wewnątrz except Exception — ctx.exit(1)

---

## Pre-existing błędy (z /diagnose)

### Naprawione wcześniej
- [x] `tests/conftest.py:19-31` — mocki win32com → pytest_configure hook
- [x] `core/application.py:150` — podwójne "licomdat" → fix path
- [x] `core/nesting.py:37` — brak None-check w nest() → dodany

### Naprawione w bieżącej sesji
- [x] **PE-01** Cross-thread COM — STA thread + marshal ✅
- [x] **PE-02** NcEventHandler nc_path — optional + post-set ✅
- [x] **PE-03** batch.py progress.advance pomijane — naprawione ✅
- [x] **PE-04** batch.py brak summary przy błędzie — naprawione ✅
- [x] **PE-05** batch.py niespójna obsługa błędów — naprawione przez refaktor _process_file ✅
- [x] **PE-06** handle_com_errors nie loguje typer.Exit — naprawione ✅
- [x] **PE-08** _dispatch_lock dead code — usunięty w STA refaktorze ✅
- [x] **PE-09** zewnętrzne CoInitializeEx — usunięty w STA refaktorze ✅
- [x] **PE-10** mylący docstring — zaktualizowany w STA refaktorze ✅
- [x] **PE-13** dwuwarstwowe CoInitialize — usunięte w STA refaktorze ✅

### Naprawione w tej sesji
- [x] **PE-07** batch.py save_as fail — rozdzielenie try/except ✅
- [x] **PE-11** conftest.py ComError.strerror — dodany atrybut ✅
- [x] **PE-12** manager.py ac_app None — Quit w finally + guard ✅
- [x] **PE-14** batch.py podsumowanie — len(files)→len(results) ✅
- [x] **PE-15** batch.py typer.Exit — ctx.exit(1) ✅
- [x] **PE-16** manager.py except:pass — forward + logging ✅

---

## Pre-existing issues (do rozważenia)

1. **manager.py:56** — `_RPC_E_CHANGED_MODE`: ciche kontynuowanie po MTA, marshal może nie działać
2. **manager.py:94** — `CoMarshal` łapie tylko `TypeError`, inne wyjątki propagują do `except Exception`
3. **manager.py:112** — `Quit()` z `owned=True` zamyka AlphaCAM, brak opcji `keep_alive`
4. **manager.py:144** — `CoGetInterfaceAndReleaseStream` może zgubić strumień przy wyjątku
5. **batch.py:93** — Progress desc nie aktualizowany po `break` z pętli
6. **batch.py:108** — Log błędów pomija warningi gdy `fail_count=0`
7. **test_cli.py:196-354** — 18 funkcji bez `-> None` return type (mypy strict)

## Znane ograniczenia (świadomy design)

1. **Batch processing jest single-threaded** — AlphaCAM single-instance, parallel nie jest możliwy
2. **Brak wsparcia dla Nesting z geometrią** — CSV tylko wymiary, nie tworzy geometrii
3. **OutputNC wymaga event sink** — zaimplementowane w tej sesji (`output_nc_with_events`)
4. **COM safety wymaga refactoringu** — cross-thread COM issue w P0.1
