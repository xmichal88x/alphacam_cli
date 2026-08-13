# TASKS.md — Alphacam CLI

## Status: ~93% gotowości produkcyjnej — PRZED v1.0.0

- ruff ✅ mypy src/ **0 błędów** ✅ pytest **165/165** (91.25% coverage) ✅ build wheel ✅
- COM safety: STA thread ✅ marshal ✅ cleanup (result_sent guard) ✅ keep_alive ✅
- CI: publish workflow ✅ lint ✅ typecheck ✅ coverage gate 70% ✅

---

## Zrealizowane w bieżącej sesji (Sprint v1.0.0)

### P0 — Procesowanie CDM w Session 0 (2026-08-13, E2E potwierdzone)- [x] **ROOT CAUSE 80004002**: `job.Process()` cross-process przez COM marshal → makro eventów AM dostaje obiekty przez marshal → 80004002 + brak obróbek. Makro `HeadlessProcess(JobName)` uruchamiane IN-PROC (`App.Run` na referencji COM) → pełne obróbki + NC. (raport: docs/raporty/2026-08-13-session0-opcjaA.md)
- [x] **core/application.py**: `process_cdm_job_inproc` (App.Run makra na referencji COM gateway, ~33-41s) + `process_cdm_job(method="inproc"|"vbs")` — default inproc
- [x] **BUG naprawiony**: Run w osobnym wątku → RPC_E_WRONG_THREAD; naprawa: bezpośrednio na wątku STA
- [x] **gateway/server.py**: handler `method` (walidacja inproc|vbs), usunięty tymczasowy handler probe_run_macro
- [x] **client.py/remote.py**: parametr method — naprawione pre-existing LSP "No parameter named machine/timeout_seconds/output_root"
- [x] **cli/cdm.py**: opcja `--method inproc|vbs`
- [x] **E2E laptop Monika**: Prod E2E 01 (2 części) 40.7s Sukces NC 3690 B; Prod E2E 02 (1 część) 36.1s Sukces NC 1744 B; JEDEN proces Acam (Session 0) dla create+import+process; pytest 848 passed
- [ ] **Fallback vbs wymaga Acam w Session 1** (GetObject 429 przy Session 0-only) — odnotowane, nie jest defaultem

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

## Zaległe zadania PRZED v1.0.0 (NIE wymagają Windows)

### P1 — Stabilność i coverage

- [x] **manager.py:128-135** — STA worker `except Exception` cicho połyka błędy gdy `result_sent=True`. Main thread nigdy się nie dowie o awarii wątku STA. Fix: zawsze wkładać błąd do `result_queue` (użyć `maxsize=2` by nie blokować). (commit f198d47)
- [x] **Pokrycie error pathów** — dodać testy dla brakujących linii w: (commit d547826, 734 testów; coverage: mill 100%, diagnose 100%, nest 100%, main 100%; nc już był 100%)
  - [x] `mill.py:35-36,63-64,96-99,122-123,157-158,165-166` (87% → 100%)
  - [x] `diagnose.py:30-31,47,57-58` (88% → 100%)
  - [x] `nest.py:44,55-57,69-70,115-119` (86% → 100%)
  - [x] `nc.py:25-26,30-31,44-45` (81% → 100%)
  - [x] `main.py:74-79` (85% → 100%)

### P2 — Jakość i DX

- [x] **README: update test count** — mówi "20+ unit tests", powinno być "165+" (commit 2543920 — "734+ unit tests")
- [x] **`nest.py:list_nests()`** — nie używa `@handle_com_errors` (inconsistency) (potwierdzone — już było w HEAD)
- [x] **`publish.yml`** — dodać `ruff check tests/` i `mypy tests/` przed publikacją (a3764cb — plik już zawierał `ruff check src/ tests/` i `mypy src/ tests/`; dodatkowo naprawiono mypy tests/ — bb39ed3 — i ruff B009 — b877af1)
- [x] **Pre-commit hooks** — dodać `.pre-commit-config.yaml` z ruff + mypy (a3764cb — `.pre-commit-config.yaml` istnieje)
- [x] **CONTRIBUTING.md** — instructions for local dev, adding commands, running tests (2543920/a3764cb — plik istnieje)

### P3 — Kosmetyka i detale

- [x] **Przesunąć classifier na `5 - Production/Stable`** — po zakończeniu P1 (już było w pyproject)
- [ ] **GitHub PAT** — dodać `workflow` scope lub przejść na SSH
- [x] **Dodać `--show-completion` dokumentację** w README (już była)

## Zadania wymagające Windows (do zrobienia przez użytkownika)

- [x] **Testy integracyjne** — 3 testy w `test_workflows.py` (create→mill→nc, batch, nest) — CZĘŚCIOWO: mill_nc PASS + nest PASS (Session 0, komity 8b5619c/269fd40/0f21f05); batch NIE przechodzi — hang drugiego OutputNC w jednej sesji COM (potwierdzone 12/12 przebiegów) — osobne P1
- [x] **Weryfikacja marshal path na realnym AlphaCAM** — potwierdzić że `result` typu "marshaled" a nie "simple" — potwierdzone "marshaled" end-to-end (probe na maszynie, obiekt IAlphaCamApp przez CoGetInterfaceAndReleaseStream)
- [ ] **Rozszerzenie puli ProgID** — dodać autodetekcję lub dokumentację jak znaleźć

---

## Manifest (arkusz→WO) — braki zdiagnozowane 2026-08-09

### M1 — Odczyt wyników nestingu (BLOKER manifestu)
- [ ] **core/nesting.py + core/drawing.py**: wrapper na `GetNestData` / `NestPartInstance` (pozycja, rotacja, sheet assignment) / `GetNestInformation` — obecnie `create_nest_data()` zwraca surowy COM (drawing.py:39), brak jakiegokolwiek odczytu wyników nestingu
- [ ] **CLI: komenda `nest inspect`** — odczyt wynikowego nestingu: części → arkusz, pozycje, rotacje (wyjście JSON/tekst)

### M2 — Odczyt wynikowego .anl (BLOKER manifestu)
- [ ] **cli/nest.py**: po `nd.DoNest()` (i w trybie advanced po `nesting.Nest`) odczytać wynik — obecnie komenda kończy się po nestingu bez odczytu wyników (nest.py:258-260)
- [ ] **Parser .anl wynikowego** (części, ilości, przypisanie do arkuszy)

### M3 — CDM: wyniki nestingu (zależne od RQ-PA-016 / eksperymentu na produkcji)
- [ ] **cli/cdm.py**: komenda odczytu wyników CDM po przetworzeniu przez Automation Manager (co wypluwa: arkusz → drzwi) — na razie order-details czyta tylko dane wejściowe zamówienia; do potwierdzenia formatu wyników na produkcji

### M4 — .ard nie generowany mimo deklaracji
- [ ] **cli/nest.py**: help `run` deklaruje "Output directory for .anl and .ard files" (nest.py:29) ale .ard nie jest zapisywany — poprawić (albo generować raport, albo zmienić help)

### M5 — Walidacja konwencji nazw części vs numer WO
- [ ] Komenda/skrypt walidujący czy nazwy części w CSV/CDM pasują do wzorca `WC-<order>-<product>` (konwencja konektora Woo→WO) — wspiera weryfikację blokera A.4 planu automatyzacji

### M6 — Zależności i weryfikacja (nie blokery)
- [ ] Testy integracyjne (3 workflows: create→mill→nc, batch, nest) — czekają na Windows+AlphaCAM (już w sekcji wymagających Windows; odwołać się do tego)
- [ ] Weryfikacja marshal path na realnym AlphaCAM (już w sekcji wymagających Windows)
- [ ] RQ-PA-016 (repo production-automation): co dokładnie generuje CDM po przetworzeniu CSV — determinuje implementację M3

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
- [x] **PE-16** manager.py except:pass — forward + logging + result_sent flag ✅

### Fixloop — code review fixes
- [x] **manager.py:12** — _RPC_E_CHANGED_MODE: -2147417846 → -2147417850 ✅
- [x] **manager.py:42** — import sys przeniesiony na poziom modułu ✅
- [x] **manager.py:98** — CoMarshal except (TypeError, pythoncom.com_error) ✅
- [x] **manager.py:106-108** — result_sent flag (use-after-free COM guard) ✅
- [x] **manager.py:52,63-64** — ac_app/owned przed CoInitializeEx (UnboundLocalError) ✅
- [x] **manager.py:69** — redundant owned=False usunięty ✅
- [x] **batch.py:46** — redundant result["status"]=STATUS_OK usunięty ✅
- [x] **batch.py:114** — exit code: usunięto and not continue_on_error ✅
- [x] **conftest.py:17** — ComError super().__init__(description) zamiast (hresult, ...) ✅
- [x] **test_batch.py** — with mock_com usunięty z 5 testów ✅
- [x] **test_com_manager.py** — patch.object → string path ✅
- [x] **publish.yml:30** — tests/ → tests/unit/ (konsystencja z ci.yml) ✅

### Fixloop 2 — code review fixes (bieżąca sesja)
- [x] **test_com_manager.py:192-212** — dead code: mock_uninit.assert_not_called() poza pytest.raises ✅
- [x] **test_cli.py:144-183** — 7 testów _requires_windows: patch sys.platform dla Windows CI ✅
- [x] **test_cli.py:186-193** — tautologiczny test_diagnose_no_com: konkretna asercja ✅

---

## Zrealizowane w bieżącej sesji (Sprint v1.0.0 cz.2)

### P3 — Design (z /diagnose)

- [x] **manager.py:112** — `keep_alive` opcja w `alphacam_context()` (nie zamykać AlphaCAM) ✅
- [x] **manager.py:144** — `CoGetInterfaceAndReleaseStream` try/except + `CoReleaseMarshalData` cleanup ✅
- [x] **manager.py:133-138** — timeout w result_queue: stop_event.set() + thread.join() (pre-existing bug) ✅
- [x] **test_com_manager.py** — test dla keep_alive + marshal failure ✅

### P1 — Zwiększenie coverage'u (100% na 4 plikach)

- [x] **cli/batch.py (47% → 100%)** — 6 testów CLI `process()` z CliRunner ✅
- [x] **cli/post.py (39% → 100%)** — 4 testy CLI `list`, `info` ✅
- [x] **core/config.py (61% → 100%)** — 8 testów config load/save/merge ✅
- [x] **cli/nest.py (22% → 86%)** — 5 testów CLI `run`, `list` ✅

### P2 — Jakość

- [x] **test_cli.py:196-354** — `-> None` do 18 funkcji (mypy strict) ✅
- [x] **batch.py:93** — Progress description po `break` z pętli ✅
- [x] **batch.py:108** — Log warningów gdy `fail_count=0` a są warningi ✅

## Pre-existing issues (do rozważenia)

1. **manager.py:56** — `_RPC_E_CHANGED_MODE`: ciche kontynuowanie po MTA, marshal może nie działać (low)
2. **manager.py:58** — `result_sent` flaga: teoretyczna luka przy rzadkim wyjątku spoza TypeError|com_error (low)
3. **tests/conftest.py:11-27** — ComError mock wpływa na wszystkie testy, nie tylko potrzebujące (medium)
4. **batch.py:45-46** — save_as fail z `status="OK"`: NC wygenerowany, drawing nie zapisany. Intencjonalny design. (info)
5. **Duplikacja flow importu CSV między gateway a core** — pełna duplikacja logiki importu CSV: `gateway/server.py` (handlery `import_cdm_csv`/`import_cdm_preview` + lokalne helpery `_resolve_cdm_import_setting`/`_cdm_material_name`/`_cdm_job_name`/`_cdm_config_name`/`_FIELD_SETTERS`; legacy + mapped import, 894-1204) vs `core/application.py` (`import_cdm_csv`/`_import_cdm_csv_mapped`/`import_cdm_preview`/`_resolve_import_setting`; 668-986). Obie kopie obecnie zsynchronizowane (linia w linię), ale każda zmiana kontraktu jest wprowadzana 2× → fabryka dryfu (widoczne drobne dryfity, np. `preview` flag w params). Fix docelowy: server deleguje do metod core (wzorzec `create_cdm_job` — walidacja params + COMError w handlerze) lub wspólny moduł (wzorzec dedupu `cdm_db` z tasks.md:605). (MAJOR — code review 2026-08-10, iteracja 1)
6. **`_handler_probe_nest` (server.py:448-802)** — ~350 linii debugowego kodu z hardcoded ścieżkami (C:\Program Files\Hexagon..., C:\Users\48797...) w produkcji. Do przeniesienia do narzędzia debug lub usunięcia. (MINOR)
7. **`_cdm_automation_manager` (server.py:804-817)** — duplikuje logikę addins interface z `core/application.py:410-495` (ten sam CLSID 39BFE38A-...) zamiast delegować przez `get_automation_manager_addin()`. (NIT)

## Znane ograniczenia (świadomy design)

1. **Batch processing jest single-threaded** — AlphaCAM single-instance, parallel nie jest możliwy
2. **Brak wsparcia dla Nesting z geometrią** — CSV tylko wymiary, nie tworzy geometrii
3. **OutputNC wymaga event sink** — zaimplementowane w tej sesji (`output_nc_with_events`)
4. **COM safety** — STA thread + result_sent guard + keep_alive ✅
5. **Batch processing trzyma jedną sesję COM na cały katalog** (świadomy design — blok iteracyjny, izolacja per wywołanie CLI; znany bug drugiego OutputNC w jednej sesji wymaga świeżej sesji na wywołanie)

### Nowe P1 (znalezione w tej sesji 2026-08-09)

- [ ] **Batch hang: drugi OutputNC w tej samej sesji COM wisi w Session 0** (12/12 przebiegów: part_0.nc=177B OK, part_1.nc=0B wisi). Diagnoza: core/drawing.py output_nc (linia ~153) — COM call OutputNC nie wraca przy drugim wywołaniu w jednej sesji. Do zbadania: output_nc_with_events/NcEventHandler, świeży context per plik w batch, lub retry. Blokuje test_batch_processing.
- [ ] **Acam.exe trzyma handle pliku NC po OutputNC w Session 0** (>60s) — test mill_nc obejście: cleanup best-effort (teardown_class); do zbadania czy OutputNC zamyka plik po zamknięciu sesji COM.

---

## Kierunki na przyszłość

- [ ] **Custom import (wizja, decyzja użytkownika 2026-08-10)** — import można rozbudować w przyszłości jako CUSTOM IMPORT: logika tworzenia typu importu w bibliotece (`AM_ImportSettings`) z własnymi kolumnami → dopasowanie do dowolnych plików CSV, których dane nie są poukładane. Tylko jako wizja na przyszłość — bez wpływu na obecny kontrakt (csv2 = CreateJob=No, import do istniejącego zadania; sklep CSV = CreateJob=Yes).

### Fixloop (2026-08-13) — review commita fb31f1f, 0 issues
- Review 1: 15 issues (2 high: RCE use_shell, brak timeoutu STA; 7 medium; 6 low) → fixy A-G
- Review 2: 6 nowych LOW (N1 cleanup nie w finally; N2/N3 docs; N4 brak testu min_mtime; N5 path traversal job_name; N6 timeout<=0) → fixy
- Review 3: 3 LOW (timeout 0; stale detail; docs log) → fixy
- Review 4: 1 minor (test stale→fresh) → fix
- Final: **0 issues**; ruff/mypy czyste; pytest 867 passed; build wheel OK
- E2E sanity laptop Monika: "Fixloop Sanity 01" 38.5s Sukces, NC 1744 B, .ard 84466 B
- Kod zsynchronizowany na maszynę (6 plików SAME), usługa RUNNING

## Otwarte po fixloop (do osobnych sesji)
- [ ] **Watchdog dla inproc na wątku STA** (code review #1, high) — `process_cdm_job_inproc` jest synchroniczny na jedynym wątku STA gateway; zawieszenie makra = permanentny deadlock usługi (klient ma socket timeout, serwer nie). Rozważ: watchdog per-call + restart usługi (SCM Recovery) lub drugi wątek STA z marshal referencji (CoMarshalInterThreadInterfaceInStream). Makro jest stabilne (6× E2E 33-41s), ale brak zabezpieczenia.
- [ ] Usunąć/odciąć pozostałe pre-existing: duplikacja importu CSV (server vs core), `_cdm_automation_manager` duplikat (server.py) — wg TASKS pre-existing #5/#7.
