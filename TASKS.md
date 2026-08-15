# TASKS.md — Alphacam CLI

## Status: ~95% gotowości produkcyjnej — PRZED v1.0.0

- ruff ✅ mypy src/ **0 błędów** ✅ pytest **892 passed** ✅ build wheel ✅
- COM safety: STA thread ✅ marshal ✅ cleanup (result_sent guard) ✅ keep_alive ✅
- CI: publish workflow ✅ lint ✅ typecheck ✅ coverage gate 70% ✅
- CDM 3 bloki (create/import/process): audyt produkcyjny + 8 fixów + E2E na maszynie ✅

---

## PRODUCTION AUDIT CDM create/import/process (2026-08-13, E2E laptop Monika)

**Werdykt po naprawach: 0 blokerów. Pełny cykl E2E 2×: create→import--job→process (Sukces 35.0s/34.0s) + auto-create→dup-check→process (Sukces 34.0s); NC/.anl/.ard/log wygenerowane; materiał MDF_18 (id 2) na detalach; ActiveInProcess=True; 1 proces Acam.**

### Fixy wdrożone (audyt → fix → E2E):
- [x] **RCE wektor zamknięty (P0)**: usunięty tryb `vbs`/`machine` z całego kontraktu (CLI `--method`/`--psexec`, client/remote/server/core, headless `build_vbs`/`run_headless`). Jedyna metoda procesowania: makro in-proc. −539 linii kodu+testów.
- [x] **Dedup importu (P0)**: server.py przestał re-implementować import CSV (usunięte ~290 linii helperów) — deleguje do core (wzorzec create). Ujednolicona semantyka: ActiveInProcess jawnie True + fallback DB, materiał ustawiany W OBU tabelach (AM_JobDetails + CDM_OrderDetails), default materiału z vdb5_job_defaults, cleanup 0-items, warningi materiału. (było 2 źródła prawdy z dryfem — P1 z audytu)
- [x] **KLUCZOWY — cache AM (P1)**: core `get_automation_manager_addin` łączył AM przez MARSHALED `self._app` → świeże joby niewidoczne w `am.Jobs` (import --job po create failował "AM cache issue"). Fix: nowy `get_cdm_automation_manager` — wzorzec serwera (fresh `gencache.EnsureDispatch` + CoCreateInstance + GUI, retry 3×3s); server `_cdm_automation_manager` deleguje do core (dedup pre-existing #7). **E2E: import --job po create w osobnym RPC działa.**
- [x] **Duplikat joba (P1)**: check "job already exists" przez `cdm_db.job_count` (baza, deterministyczny) zamiast `find_cdm_job` (COM cache) w create + import auto-create; import --job przy find=None → diagnostyczny komunikat cache. **E2E: dup import → "job already exists (use --job...)".**
- [x] **Walidacja job_name na brzegu (P1)**: `_validate_job_name` w core (zakaz `/ \ : * ? " < > | . .. ` + control chars, max 60) — create/import/process + handlery RPC; polskie znaki i spacje przechodzą (E2E: "AudytE2E 002").
- [x] **`_com_call` timeout (P1)**: `result_q.get(timeout=300s poll 30s)`; martwy wątek STA → czytelny COMError "STA worker died" (zamiast wiecznego wiszenia); żywy wątek → czeka (legalnie wolne operacje).
- [x] **CLI (P1/P2)**: `--name`+`--job` → exit 2; process failure drukuje detail+log; pusty CSV → "No rows imported"; `result.get` zamiast KeyError.
- [x] **Locale logu (P1)**: `read_job_result` — case-insensitive "sukces"/"success", status line match po "status"+":" (odporny na PL/EN locale).
- [x] **docs/gateway.md**: kontrakt process bez vbs/machine; dodane import_cdm_csv/import_cdm_preview.
- [x] Code review: 0 blokerów; uwagi (output_root strip, _sta_thread=None test, preview walidacja, read_error testy, backtick w forbidden chars) — wdrożone.

### Weryfikacje maszynowe (rozstrzygnięte):
- **ActiveInProcess**: detale po imporcie przez gateway mają True (COM default) — core ustawia jawnie (odporność na zmianę defaultu).
- **Spacje w `-JobName:` ps1**: subprocess argv binduje poprawnie (test na maszynie: RC 0, `[]` zamiast błędu) — fix cudzysłowów NIEpotrzebny (false positive).
- **SCM Recovery**: nssm bez AppExit → domyślny Restart + AppRestartDelay=5000ms — usługa wstaje sama po os._exit(1).
- **vdb5_set_has_drilling off-by-N**: false positive — values z ok_details (count==detali w bazie), GetRange poprawny w obu trybach.
- **Restart usługi**: przez ssh `sc stop/start` CICHO failował (2×) — używać `powershell Stop-Service/Start-Service` z weryfikacją PID Acam (StartTime!).

### Otwarcie (po tej sesji):
- [ ] **watchdog inproc → izolacja procesowania** (os._exit zabija całą usługę; recovery nssm potwierdzony, ale job wisi) — TASKS.md "Otwarte po fixloop"
- [ ] `core/session.py` (plan A refaktoru) — jeden punkt połączenia COM; obecnie 4+ (sta_worker, run_nest ×2, get_cdm_automation_manager)
- [ ] `scripts/e2e_cdm.sh` — skrypt E2E (restart → create → import → process → weryfikacja NC)
- [ ] README: sekcja `cdm import` — auto-create wymaga settingu z CreateJob=1 (np. `--import-setting "sklep CSV"`; domyślny "Ustawienia Importu CSV 2" = CreateJob=0 → "job is required")
- [ ] `get_automation_manager_addin` (core) — martwe API (0 użyć) po T2c; usunąć lub oznaczyć deprecated
- [ ] probe_cdm_import.py/probe_cdm_process.py — nadal pakowane do exe (alphacam.spec:6)

## RAPORT AUTOMATYCZNIE PRZY PROCESS (2026-08-13) — sterowany ustawieniami CDM

**Decyzja użytkownika:** raport .acrepd generuje się AUTOMATYCZNIE przy `cdm process` (po udanej obróbce) — sterowane flagą `GenerateReports` z konfiguracji CDM joba (AM_ConfigurationSettings, NIE parametr CLI). Odczyt = osobny blok `cdm manifest`. Brak raportu (flaga False / awaria / nieodczytana flaga) → wyraźny status `report: {success: False, ...}` + CLI "Report: NOT CREATED — <powód>"; `success` procesu BEZ zmian (obróbka się udała).

**Implementacja (3 zadania + docs, 921 passed):**
- A: `vdb5_job_output_root.ps1` rozszerzony o `cfg.GenerateReports` (linia `generate_reports: True/False`); `cdm_db._job_config_read` (wspólny helper) + `job_generate_reports(job_name) -> bool | None` (None = odczyt/brak konfiguracji); 8 testów
- B: `application.py` — helper `_run_reports_data_collection(job_name)` (wydzielony z reports_create — DRY); `process_cdm_job` po read_job_result: generate=True → data collection (plik `<job>.acrepd`), wyjątek → report.success=False + warning; generate=False → skipped; None → "report flag read failed" + warning; `result["report"]` zawsze, `warnings` gdy niepuste; 5 nowych testów (m.in. report_save_false przez prawdziwy mock addina)
- C: `cli/cdm.py process` — "Report: OK (raport_test.acreps)" green / "Report: NOT CREATED — <powód>" yellow (exit 0); 4 testy
- D: README (proces + nowa sekcja manifest — wcześniej NIE była udokumentowana!), gateway.md (wynik process + report 3 warianty)

**E2E potwierdzony (wcześniej, dla reports create):** create → import → process → .acrepd "RaportCfg 003.acrepd" 336 KB → cdm manifest: arkusz MDF_18 2440×1220×18, części z pozycjami (x/y/rot/qty).

**Fixloop (2026-08-13, 3 rundy review, 0 blokerów, build OK):**
- Runda A: 1 medium + 4 low → naprawione: (1) data collection TYLKO przy `success=True` (przy nieudanej obróbce raport = {"success": False, "error": "process failed; report not generated"} — bez błędnych danych ze stanu sprzed obróbki!); (2) martwa linia `result["report"]`; (3) README suffix materiału; (4) puste `generate_reports:` (NULL) → False (nie mylący warning); (5) +testy (skipped_when_process_failed, assert_not_called, job_name do helpera)
- Runda B: APPROVE + 2 low + 2 nit → naprawione: (1) **`cdm_db.job_config(job_name)`** — JEDEN subprocess powershell zamiast 2 (job_output_root/job_generate_reports = cienkie wrappery; process używa job_config raz); (2) dead code `result["warnings"]`; (3) regex `\s*`→`[ \t]*` (odporność na nowe linie); (4) README doprecyzowane
- Runda C: APPROVE + 2 minor → fix: rozróżnienie 2 przyczyn `report flag read failed` (cfg nieczytelny vs flaga nieparsowalna — warning "GenerateReports missing or unparseable in job config"); **UNC edge case (cdm_db.py:472-473 — prefiks C:\ALPHACAM\ łapie też ścieżki UNC) → TASKS.md kaizen, nie naprawiany**
- Finalny sanity E2E (FinalSan 001): process → report OK (raport_test.acreps) + manifest z pozycjami → PASS; cleanup done
- Stan: **930 passed**, ruff 0, mypy 0, build OK (wheel+tar.gz), kod na maszynie zsynchronizowany (SHA1), usługa Running, 1× Acam

## RAPORTY NAKŁADANIA (.acrepd) — SKONFIGUROWANE I DZIAŁAJĄ (2026-08-13)

**Wniosek z weryfikacji:** `cdm process` (makro HeadlessProcess) NIE generuje .acrepd (makro nie robi data collection — potwierdzone: CaptureNestedPartPositions=True/False — 0 plików). Raporty generuje blok `reports create` (Add-in AcamReports) PO procesowaniu — rysunek nestingu jest wtedy aktywny.

**FIX wdrożony (`reports_create`):** core nie ładował ustawień DataOutputSettings i ignorował wynik `Save()` → generował 0 plików przy success=true. Teraz (wg oficjalnego wzorca VBA Reports.bas):
1. ładuje `.acreps` z `LICOMDIR\Reports\Settings` (candidates jak acrepd._reports_data_dir — `LicomdirPath` zwraca ROOT `C:\ALPHACAM\` nie LICOMDIR!) — na maszynie: `raport_test.acreps` (CaptureCDMData=true)
2. `CreateReportsJob(drw)` — 1 parametr (było 3)
3. `job.Settings.JobName = job_name` (opcjonalne `--job`) → nazwa pliku `"<job> - ..."?` — empirycznie: plik `"RaportCfg 003.acrepd"` (bez materiału w nazwie)
4. `Save()` → False = RuntimeError "no report data saved"
5. `CreateReports()`
Zmiana zachowania: brak aktywnego rysunku/geometrii → RuntimeError (wcześniej success=True z active_drawing=False). CLI: `reports create --job "Nazwa"`. docs/gateway.md + README zaktualizowane.

**E2E potwierdzony (2 cykle):** create → import → process (Sukces 35s) → `reports create --job` → `cdm manifest` → **total_parts: 3, arkusz MDF_18 2440×1220×18, części z pozycjami (x, y, rot, qty)** — np. `Typ Frontu 3_1 x=355 y=951 rot=180 qty=2`.

**Produkcyjny przepływ z raportami:** `cdm create` → `cdm import --job` → `cdm process` → `reports create --job "<nazwa>"` → `cdm manifest "<nazwa>"` (część→arkusz→pozycja).

## FIXLOOP (2026-08-13) — 3 iteracje, 0 issues, build OK

**Zakres:** 15 zmienionych plików (CDM audit fixes, uncommitted). Reviewer: 2 rundy (src + testy) + weryfikacja zarzutów w kodzie.

**Iteracja 1 — issues znalezione przez reviewera i naprawione (3 fixy, 1 subagent = 1 fix):**
- [x] **delete_job duplikacja** (medium): `_handler_cdm_delete_job` — pełna kopia logiki core → delegacja do `com_app.delete_cdm_job(job_name)` + `_validate_job_name` (server.py:670-681); 6 testów przepisanych na delegację
- [x] **name niespójność gateway↔core** (low×2): core stripował tylko `job` (nie `name`) → `--name " "` mylący błąd; core obcinał `name[:60]` a gateway odrzucał >60 → ujednolicenie: `name = (name or "").strip() or None` w import_cdm_csv/preview; `_cdm_job_name` bez [:60] dla explicit name i kolumny CSV (basename zachowuje [:60]); +2 testy
- [x] **CLI create/delete bez checka success** (low): defensywny `if not result.get("success")` → exit 1 (cdm.py create/delete); +2 testy

**Iteracja 2 — runda C (testy): 0 blokerów; 3 zarzuty medium → FALSE POSITIVES (zweryfikowane w kodzie):**
- fixture `server_app` patchuje modułowy `gateway.server._app` (nie CoCreateInstance) ✅ (test_gateway_server.py:18-24)
- testy delegacji importu ISTNIEJĄ: delegates:1535, full_params:1562, preview_delegates:1727, error_wrapped:1700, job_exists_wrapped:1711 ✅
- warnings przy sukcesie create są drukowane (cdm.py:62-64); testy CLI COMError istnieją (test_cli_cdm.py:214,574) ✅

**Fix docs:** `import_cdm_preview` kontrakt w docs/gateway.md — `would_create_job` (nieistniejący klucz) → rzeczywisty `{success, setting, field_map, job_name, config, material, items, rows, errors, job}` (gateway.md:241)

**Werdykt:** 0 issues — GOTOWE. `pytest 897 passed`, `ruff format/check 0`, `mypy 0`, `python -m build` OK (wheel+tar.gz).

**Kaizen/pre-existing zapisane (NIE naprawiane w pętli):**
- [ ] `_com_call`/`_sta_loop` gubi traceback wyjątku STA (putuje sam wyjątek) — dodać `with_traceback`/log na STA (low)
- [ ] fixture `server_app` bez `create_autospec` — ryzyko "phantom methods" przy literówkach w handlerach (low)
- [ ] `_handler_cdm_types` mylący komunikat "automation manager unavailable" gdy padnie iteracja `am.Jobs` (AM działał) (low)
- [ ] `_sta_loop` `start_q.get(timeout=CONNECT_TIMEOUT)` bez obsługi `queue.Empty` — goły wyjątek przy timeout connect (pre-existing, low)
- [ ] lazy-import `from alphacam_cli.gateway.server import _app` wewnątrz handlerów (styl pre-existing; przy `_app=None` komunikat "'NoneType'..." zamiast "not connected") (low)
- [ ] `_cdm_job_name`: job_name z kolumny CSV >60 znaków → twardy błąd (świadoma zmiana T3; błąd nie wskazuje wiersza CSV) — dokumentacja w README (low)
- [ ] testy delete: `failed` vs `no_delete_method` strukturalnie identyczne → parametrize (kosmetyka)
- [ ] `test_import_cdm_csv_autocreate_whitespace_name_uses_basename` — asercja pośrednia (przez błąd dup-check) — zamienić na bezpośrednią (kosmetyka)

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

## Manifest (arkusz→WO) — aktualizacja 2026-08-14 (decyzja: tylko CDM)

### KLIENT I ZAMÓWIENIE PER CZĘŚĆ — DZIAŁA E2E (2026-08-14)
- **Ustawienia importu (GUI):** "Ustawienia Importu CSV 3" (ID 18, Selected) — 8 kolumn: Style,Qty,W,H,DesignDims,Materiał,Klient(261),Zamówienie(262). "sklep CSV" (ID 3) rozszerzony przeze mnie o 261/262 (kol 9/10 — INSERT do AM_ImportSettingsParameter) — ZOSTAJE w bazie (odpowiednik zmiany GUI). Jeśli dodać kolumnę item (263) — item też wejdzie.
- **XML .acrepd ZAWIERA dane CDM** (CaptureCDMData działa, gdy detale mają dane CSV): CDMPartCSVCustomerName, CDMPartCSVCustomerOrderNumber, CDMPartCSVCustomerItemNumber, CDMPartType, CDMPartProductionComment, CDMPartCustom1..25, CDMPartNestNCFilename, CDMPartHandleName, CDMPartPressSheetName. AC_02_JOB NIE ma JobCustomerName/JobPO.
- **BUG naprawiony:** `_PART_CDM_FIELDS` miał złe nazwy kluczy — `cdmpartcsvordernumber`/`cdmpartcsvitemnumber` (XML: `cdmpartcsvcustomerordernumber`/`cdmpartcsvcustomeritemnumber`) → klient wchodził, zamówienie/item = None. Fix: poprawione nazwy + `cdmpartproductioncomment`, `cdmpartnestncfilename`, `cdmparttype`, `cdmpartcustom1..25`; `_PART_CDM_KEYS`/`_SHEET_CDM_KEYS` + `cdmpartreportid`/`cdmsheetreportid` (CDMPartReportID==PartID); testy z prawdziwymi tagami PascalCase (934 passed).
- Wzbogacanie z bazy (`_enrich_manifest_customer`) zostaje jako FALLBACK (nie nadpisuje XML).
- **E2E (Csv3Test 004):** create → import csv3 (ID 18) → process (raport auto OK) → manifest: `P003_1 → Klient 7 / PO-2026-007`, `P003_2 ×2 → Klient 8 / PO-2026-008`; scrap=81, utilization=19, type='P003'. Cleanup done.
- **Odkrycie poboczne:** zmiana w GUI "osobny raport dla każdego arkusza" → makro zamyka rysunek nestingu po procesowaniu → data collection "active drawing has no geometry"; po przywróceniu ustawień działa. Opcjonalny fallback (niedokończony): data collection na OTWARTYM rysunku nestingu z output_root (probe: geo 164/tp 29, ale CreateReportsJob failował RPC).

### Decyzja właściciela (2026-08-14)
- Automatyzacja opiera się WYŁĄCZNIE na CDM (Automation Manager). Tor ręcznego nakładania `nest run` NIE jest rozwijany.
- Tor CDM jest kompletny: `cdm process` (headless, Session 0) → automatyczny raport `.acrepd` (GenerateReports z konfiguracji joba) → `cdm manifest` (odczyt wyników: arkusze, części z pozycjami x/y, rotacją, ilościami, csv_order_number, csv_item_number, nest_nc_filename).

### Zamknięte
- [x] **M3 — CDM: wyniki nestingu** — `cdm process` + `cdm manifest` + parser `.acrepd` (core/acrepd.py). Testy 930/930, E2E na laptopie Monika: process → .acrepd automatycznie → manifest z pozycjami części.

### Anulowane (tor `nest run` nieużywany — automatyzacja tylko przez CDM)
- [x] ~~M1 — CLI `nest inspect` (odczyt wyników GetNestInformation dla nest run)~~ — anulowane 2026-08-14; core (GetNestInformation/NestPartInstance w drawing.py/nesting.py) zostaje jako warstwa API
- [x] ~~M2 — odczyt wynikowego .anl po DoNest()~~ — anulowane 2026-08-14
- [x] ~~M4 — .ard deklarowany w help nest.py:29~~ — anulowane 2026-08-14 (tor nieużywany)

### Otwarte — mostek manifest → MES (następny krok)
- [ ] **M5 — powiązanie `.acrepd` → WO**: walidacja że csv_order_number/csv_item_number z manifestu pasują do konwencji WC-<order>-<product> (konektor Woo→WO) oraz że nazwy części (Style) w CSV importowanym do CDM niosą numer WO — wspiera domykanie WO w OpenMES po M30
- [ ] **M5b — test na danych produkcyjnych**: pierwszy pełny cykl: cdm import (CSV z Woo) → cdm process → cdm manifest → walidacja powiązania z WO → raport

### Zależności (repo production-automation)
- RQ-PA-016 (co generuje CDM) — rozstrzygnięte przez .acrepd (potwierdzone E2E)
- Konektor Woo→WO (order_no = WC-<order_number>-<product_id>) — definiuje konwencję dla M5

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

## Fixloop: manifest poll w process_cdm_job (2026-08-15, code review #3 — 4 issues)

- [x] **#1 lepki `cycle_parse_error`** — `parsed_ok` per cykl (True gdy jakikolwiek kandydat sparsowany); retry tylko gdy `not parsed_ok`; raport: "content does not match" gdy był poprawny parse, "invalid XML" tylko przy samych błędach ✅
- [x] **#2 luka fallbacku** — gdy kandydaci pasujący nazwą nie przejdą weryfikacji zawartości → druga pętla po pozostałych świeżych manifestach (mtime desc, `fallback_used=True` przy matchu) ✅
- [x] **#3 stale `fallback_used`** — reset `fallback_used=False` na start każdego cyklu; warning nazwa tylko gdy FINALNY manifest z fallbacku ✅
- [x] **#4 testy** — `test_process_cdm_job_report_mixed_candidates_content_mismatch_no_retry` (1 parse-fail + 1 content-mismatch → "content does not match", 2 wywołania parse, 0 sleep) + `test_process_cdm_job_report_named_content_mismatch_uses_other_fresh` (fallback do innego świeżego → sukces z warningiem) ✅
- [x] Helper `_manifest_job_matches(parsed, job_name)` (DRY — match zawartości w obu pętlach)
- Weryfikacja: pytest **956 passed, 3 skipped** ✅ ruff ✅ mypy src/ 0 błędów ✅

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

## Production hardening — CDM 3 bloki (commit b27ddaa, 2026-08-13)
- [x] Import po restarcie: root cause = 2 procesy Acam + cache AM per-instancja → `_cdm_automation_manager` świeży AM per call (gencache + 3 retry), jeden współdzielony dispatch (sta_worker + _connect_addins)
- [x] `find_cdm_job` bez PopulateCustomersAndJobs (mutacja cache AM, duplikaty)
- [x] cli/nest.py: `raw.Nesting` z kontekstu (naprawia testy Windows, 1 sesja COM)
- [x] Watchdog STA (threading.Timer → os._exit) + scripts/scm_service_recovery.ps1
- [x] scripts/sync_to_machine.sh (SHA1 per plik)
- [x] E2E na maszynie: 2 pełne cykle create→import→process po restarcie (36.8s/35.9s Sukces) + import na świeżym Acam; pytest 871 passed

---

## ROZSZERZENIE `cdm manifest` (2026-08-15) — WYKONANE, fixloop 0 issues

- [x] **NC discovery**: `acrepd.find_nc_files` (skan depth≤4, wzorce wielowzorcowe + flagi configu, fallback pozycyjny, nc_unmatched/nc_missing), `_enrich_manifest_nc` w `manifest_read` (nc_root override > nc_output > output_root; raport > dysk; superseded → unmatched z filtrem użytych), `nc_config` realne flagi z DB.
- [x] **Ścieżki tylko z bazy**: `job_config` 1 subprocess (output_root/nc_output/generate_reports + ReplaceSpaceWithUnderscore/SplitNestedSheetDrawings/UseNameIdentifiers), `_resolve_output_path` (licomdir z COM, UNC \\ i //, normpath) — usunięty hardcode C:\ALPHACAM\.
- [x] **CLI**: --nc-root/--show-all/--by-token/--fill-threshold/--validate/--token-qty; kolumny Token/Notes; `NC: <name> [source]`; sekcje NC unmatched/missing; walidacje abs path przed COM.
- [x] **Gateway**: kwargs, _validate_job_name, abs-path (data_dir/nc_root/output_root), fill_threshold int 0-100, token_qty dict int≥0; PF2: cdm_types/cdm_jobs delegują do core (dedup).
- [x] **sheet_count_light** na evencie "end" (odporność multi-wersja); manifest_list serwer-side (bug --remote FileNotFoundError).
- [x] Weryfikacja: ruff/mypy 0, **1093 passed**, build OK, E2E job "Zamowienie 198" (NC per arkusz, by_token, validate, nc_config) — log w tasks.md.
- [ ] PF1: watchdog process default 330s (zrobione w kodzie; usługa bez restytu — sanity na maszynie wykonane).
