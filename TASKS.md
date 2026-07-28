# TASKS.md — Alphacam CLI

## Status: ~42% gotowości produkcyjnej — PRZED v1.0.0

- ruff ✅ mypy ✅ pytest 48/48 ✅ code-review ✅ /fixloop ✅
- build: alphacam_cli-0.1.0 wheel ✅

---

## Zrealizowane w bieżącej sesji

### Wersja 1.0.0 — zadania wykonane

- [x] LICENSE — plik z licencją MIT
- [x] CHANGELOG.md — historia zmian
- [x] `.venv` do `.gitignore`
- [x] Fix `find_tool_files` / `find_drawing_files` — usunięto podwójne "licomdat/licomdir"
- [x] None-check w Drawing, CamPath, Geo2D, Text (+ testy)
- [x] Event sink NC Output (events.py + output_nc_with_events + test)
- [x] Timeout COM (CONNECT_TIMEOUT=30s + ThreadPoolExecutor)
- [x] Mocki win32com w conftest — izolacja w pytest_configure
- [x] Testy Nesting — 26 testów
- [x] PyPI metadata (license, authors, readme, classifiers, urls)

### Poprawki z /fixloop

- [x] logger import mill.py — przeniesiony na górę pliku
- [x] None-check na Nesting.nest() return value
- [x] type(handler) → NcEventHandler w drawing.py
- [x] batch.py — restrukturyzacja typer.Exit poza try/except
- [x] nest.py — komentarz o braku @handle_com_errors
- [x] diagnostic.py — try/except dla _GetInterfaceCount()

---

## Droga do wersji 1.0.0 — zadania przed wydaniem produkcyjnym

### P0 — Krytyczne (MUSZĄ być przed v1.0.0)

- [ ] **Naprawić cross-thread COM** — `com/manager.py` używa `ThreadPoolExecutor`:
  - `_connect()` woła `CoInitializeEx`/`CoUninitialize` w wątku roboczym
  - Obiekt COM (`ac_app`) jest używany z main thread
  - To narusza reguły COM apartment — ryzyko crash/AV
  - Rozwiązania: (a) dedykowany STA thread (b) `CoMarshalInterThreadInterfaceInStream` (c) single-thread z timeoutem przez `signal`/`threading.Timer`

- [ ] **Dodać testy `com/manager.py`** — obecnie 0% pokrycia, 0 testów:
  - Test: timeout connection (mock opóźnienia)
  - Test: fallback przez PROG_IDS
  - Test: AlphacamConnectionError gdy wszystkie ProgID failują
  - Test: AlphacamComError dla COM error
  - Test: _owned=False dla GetActiveObject, _owned=True dla Dispatch
  - Test: Quit() wołany tylko gdy _owned=True
  - Test: CoUninitialize wołany w finally
  - Test: RPC_E_CHANGED_MODE obsłużony
  - Min. 15 testów, >70% pokrycia

- [ ] **Dopaść testy `core/application.py`** — obecnie ~25% (3 testy):
  - `new_drawing()`, `quit()`, `select_tool()`, `get_current_tool()`, `create_mill_data()`
  - `find_tool_files()`, `find_drawing_files()`, `get_nesting()`, `select_post()`
  - `open_drawing()`, `create_temp_drawing()`
  - Test: None return z COM → None zwrócone
  - Min. 8-10 testów

- [ ] **Dopaść testy `core/drawing.py`** — obecnie ~20%:
  - `create_circle()`, `create_text()`, `create_2d_geometry()`, `create_polygon()`
  - `save_as()`, `output_nc()`, `output_nc_with_events()`, `clear()`
  - `select_all_geometries()`, `CamPath.*`, `Geo2D.*`, `Text.*`
  - Min. 8-10 testów

- [ ] **Dodać workflow publish na PyPI** — `.github/workflows/publish.yml`:
  - Trigger: tag v* (np. v0.1.0)
  - Trusted Publishing (OIDC) lub PyPI token
  - `hatchling build` → `twine upload`
  - Wymaga konta PyPI + konfiguracji

### P1 — Ważne przed v1.0.0

- [ ] **Dodać testy `cli/*.py`** — obecnie 0 testów rzeczywistej logiki:
  - Test: każdej komendy CLI przez `CliRunner` z typer
  - Test: `@handle_com_errors` dekorator na każdej komendzie
  - Test: walidacja wejść (depth, RPM, feed)
  - Min. 15-20 testów

- [ ] **Dopaść testy `core/machining.py`** — obecnie ~10%:
  - Settery dla MillData (wszystkie propertisy)
  - Metody: `rough_finish()`, `pocket()`, `drill_tap()`, `engrave()`, `saw()`, `machine_surfaces()`
  - Min. 10 testów

- [ ] **Dodać testy `cli/common.py`** — `@handle_com_errors` dekorator:
  - Test: łapie AlphacamConnectionError → exit code 3
  - Test: łapie AlphacamComError → exit code 4
  - Test: przepuszcza inne błędy → exit code 1
  - Test: sukces → exit code 0
  - Min. 4 testy

### P2 — Rozsądne przed / shortly after 1.0.0

- [ ] **Poprawić `batch.py` — `_should_exit` flag**:
  - Zamienić na czystszy wzorzec (np. `raise typer.Exit(code=1)` poza try/except)
  - Usunąć `_should_exit` flag

- [ ] **Poprawić `nest.py:107` — `# noqa: TRY301`**:
  - Użyć `raise typer.Exit` poza blokiem try

- [ ] **Dodać `long_description_content_type` w pyproject.toml**:
  - `long_description = "file: README.md"`
  - `long_description_content_type = "text/markdown"`

- [ ] **Dodać `package_data` dla `py.typed`**:
  - `[tool.hatch.build.targets.wheel.force-include]`
  - Lub: `packages = ["src/alphacam_cli"]` + include `py.typed`

- [ ] **Dodać code coverage do CI**:
  - `pytest-cov` w dev dependencies
  - Upload raportu (Codecov / Coveralls)
  - Gate: <70% → fail

- [ ] **Dodać Windows setup docs do README**:
  - Jak zainstalować pywin32
  - COM registration AlphaCAM
  - Wymagane biblioteki VC++

- [ ] **Przesunąć classifier na `5 - Production/Stable`**:
  - Dopiero po naprawieniu wszystkich P0

### P3 — Niski priorytet

- [ ] **Dodać testy `core/events.py`** — dedykowane testy jednostkowe
- [ ] **Dodać testy `core/tool.py`** — edge case'y (None, puste narzędzie)
- [ ] **Dodać testy `cli/diagnose.py`** — test logiki diagnostyki
- [ ] **Ukryć console podczas PyInstaller build** — `console=False` w .spec
- [ ] **Dodać logowanie do pliku w batch** — już jest, ale sprawdzić czy działa poprawnie

---

## Pre-existing błędy (z code review)

### Naprawione w tej sesji
- [x] `tests/conftest.py:19-31` — mocki win32com → pytest_configure hook
- [x] `core/application.py:150` — podwójne "licomdat" → fix path
- [x] `core/nesting.py:37` — brak None-check w nest() → dodany

### Złożone issue — wymagają decyzji architektonicznej
- `com/manager.py:65-97` — COM apartment threading (P0.1)
- `core/drawing.py:68-75` — dual path ambiguity w output_nc_with_events
- `com/manager.py:52` — mixed threading model (MTA vs STA)

---

## Znane ograniczenia (świadomy design)

1. **Batch processing jest single-threaded** — AlphaCAM single-instance, parallel nie jest możliwy
2. **Brak wsparcia dla Nesting z geometrią** — CSV tylko wymiary, nie tworzy geometrii
3. **OutputNC wymaga event sink** — zaimplementowane w tej sesji (`output_nc_with_events`)
4. **COM safety wymaga refactoringu** — cross-thread COM issue w P0.1
