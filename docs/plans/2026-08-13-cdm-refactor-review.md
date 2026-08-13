# PLAN NAPRAWY — źródło dla agenta code review

**Cel**: kod produkcyjny 3 bloków CDM (create/import/process) po refaktorze — zweryfikowany przez agenta review przed uznaniem za gotowy. Agent ma ocenić **czy zmiany realizują architekturę docelową i czy nie wprowadziły regresji**, a nie tylko stylistykę.

---

## 1. Zakres (pliki objęte review)

| Obszar | Pliki |
|---|---|
| Sesja COM (nowa) | `src/alphacam_cli/core/session.py` (nowy) |
| Core CDM | `core/application.py`, `core/cdm_db.py`, `core/headless.py` |
| Gateway | `gateway/server.py`, `gateway/client.py`, `gateway/remote.py` |
| CLI | `cli/cdm.py`, `cli/nest.py` |
| Skrypty | `scripts/scm_service_recovery.ps1`, `scripts/sync_to_machine.sh`, `scripts/e2e_cdm.sh` (nowy) |
| Testy | `tests/unit/test_*.py` (zmienione), `tests/conftest.py` |
| Docs | `docs/gateway.md`, `tasks.md`, `TASKS.md` |

Porównaj z `git diff b27ddaa..HEAD` (albo odpowiednim zakresem refaktoru).

---

## 2. Architektura docelowa (co ma być spełnione)

### A. Jedna sesja COM — `core/session.py`
- [ ] **JEDEN proces Acam**: `AcamSession` używa `gencache.EnsureDispatch` (silne typy) — NIE late-bound `win32.Dispatch` (to powodowało `System.__ComObject → AlphaCAMMill.App`)
- [ ] **Dedicated STA thread** z message pump; marshal przez `CoMarshalInterThreadInterfaceInStream`
- [ ] **Health-check** (`AlphacamVersion`) + **retry 3× z backoff** przy świeżo startującym Acam
- [ ] `sta_worker` (server.py) i `_connect_addins` (application.py) **używają tego samego AcamSession** — zakaz dwóch niezależnych połączeń
- [ ] **Świeży AM per wywołanie** w operacjach CDM (cache AM per-instancja nie widzi świeżych jobów — udokumentowany bug)
- [ ] NIE wywoływać `PopulateCustomersAndJobs` (mutuje cache, duplikaty kluczy)

### B. Kontrakt bloków
- [ ] Każdy blok: samodzielny, jednoznaczne wejście/wyjście (dict), świeża sesja COM per wywołanie (AGENTS.md §9)
- [ ] **Walidacja na brzegu** (handler RPC): job_name (zakaz `/`, `\`, `.`, `..`), timeout (`int > 0`, nie bool), method (`inproc|vbs`), machine (whitelist, `use_shell` zawsze False)
- [ ] **Server deleguje do core** — zakaz duplikacji logiki (była duplikacja importu CSV: server vs core)
- [ ] Jednolity format wyników: `{success, status, detail, method, elapsed_s, log, ...}`

### C. Procesowanie
- [ ] **Tylko in-proc makro** przez `App.Run("ApplyMachiningAfterNesting.Events.HeadlessProcess")` — `job.Process()` cross-process = 80004002 (udokumentowane)
- [ ] **Run na wątku STA** (RPC_E_WRONG_THREAD) — zakaz osobnego wątku dla Run
- [ ] **Watchdog**: `threading.Timer(timeout+30) → os._exit(1)` + `cancel()` w finally + skrypt SCM Recovery
- [ ] **`min_mtime` z zegara ściennego** (`time.time()`, NIE `time.monotonic()`) w `read_job_result`
- [ ] VBS (fallback): bez BOM, unikalne nazwy plików (PID+timestamp), cleanup w `finally`

### D. Testy
- [ ] **conftest.py mockuje win32com ZAWSZE** (usunięty `if sys.platform != "win32"`) — testy CLI nigdy nie łączą się z prawdziwym COM
- [ ] Testy platform-agnostic: `pytest.skip` zamiast `assert len(candidates) == 2`
- [ ] Pokrycie: walidacja brzegów, retry, watchdog, min_mtime stale/fresh, idempotencja importu, rollback create

### E. Operacyjność
- [ ] `sync_to_machine.sh`: weryfikacja SHA1 per plik, exit 1 przy DIFF
- [ ] `scm_service_recovery.ps1`: restart po awarii (5s→10s→1 dzień)
- [ ] `docs/gateway.md` zgodna z kodem (parametry, wyniki, Session 0 vs 1)

---

## 3. Checklist review — pytania kontrolne per obszar

### Bezpieczeństwo (krytyczne)
- [ ] Czy `machine` z RPC jest sanitizowany? `use_shell` może być kiedykolwiek True? (RCE jako SYSTEM)
- [ ] Czy job_name nie ucieka z output_root (`../`)? Walidacja PRZED `os.path.join`?
- [ ] Czy timeout/method/bool są walidowane typowo (bool to int w Pythonie)?

### COM (krytyczne)
- [ ] Czy istnieje **tylko jeden** punkt tworzenia połączenia Acam? (grep `EnsureDispatch` / `win32.Dispatch` / `GetActiveObject`)
- [ ] Czy `App.Run` jest wywoływany na wątku STA? (żadnego `threading.Thread` dla Run)
- [ ] Czy `_cdm_automation_manager` tworzy świeży AM per call? (cache = martwy import)
- [ ] Czy retry łapie właściwe wyjątki (com_error) i nie maskuje błędów trwałych?
- [ ] Czy brakuje `gencache.EnsureModule` typelibów przed `EnsureDispatch`?

### Niezawodność
- [ ] Watchdog: czy `cancel()` jest w `finally`? Czy `os._exit` loguje critical przed wyjściem?
- [ ] `min_mtime`: czy porównanie jest z zegarem ściennym? Czy stale log daje `success=False` a nie fałszywy Sukces?
- [ ] Timeout klienta: `max(timeout, timeout_seconds+30)` w try/finally?
- [ ] Czy procesowanie z wieloma częściami (2+ joby) przechodzi bez timeoutu?

### Architektura bloków
- [ ] Czy żaden blok nie wykonuje całego pipeline'u (create+import+process w jednej komendzie)? (ZAKAZ z AGENTS.md §9)
- [ ] Czy server.py nie powiela logiki core (import CSV, AM connection)?
- [ ] Czy wynik każdego bloku jest jednoznaczny (maszynowy dict)?

### Testy
- [ ] Czy conftest nie ma `sys.platform` warunku dla mocków COM?
- [ ] Czy testy przechodzą na Linux (CI) i są platform-agnostic?
- [ ] Czy istnieje test E2E skryptowy (`scripts/e2e_cdm.sh`) — restart usługi → create → import → process → weryfikacja NC/ard/log?
- [ ] Czy testy pokrywają: retry AM, watchdog, walidację brzegów, idempotencję, rollback?

### Regresje (historyczne bugi — NIE mogą wrócić)
- [ ] Brak drugiego procesu Acam (create na A, import na B)
- [ ] Brak `System.__ComObject → AlphaCAMMill.App` (late-bound raw w GetAddInsInterface)
- [ ] Brak `RPC_E_WRONG_THREAD` (Run w osobnym wątku)
- [ ] Brak fałszywego "Sukces" ze stale logu
- [ ] Brak 8 faili test_cli_nest na Windows (drugie połączenie COM w cli/nest.py — ma używać `raw.Nesting` z kontekstu)
- [ ] Brak deadlocka usługi bez SCM Recovery

---

## 4. Definicja "0 issues" (akceptacja)

Review kończy się **0 issues** tylko gdy:
1. Wszystkie pozycje z sekcji 3 są ✅ (każda potwierdzona w kodzie, nie na słowo)
2. `pytest tests/unit` — 100% pass (liczba zależna od zakresu refaktoru)
3. `ruff check src/ tests/` — 0 błędów
4. `mypy src/alphacam_cli/` — 0 błędów
5. `python -m build` — wheel buduje się
6. `bash -n scripts/*.sh` — składnia OK
7. **E2E na maszynie** (jeśli wykonane): restart usługi → 1 proces Acam → pełny cykl create/import/process → "Sukces" + NC + .ard — potwierdzone w raporcie

## 5. Format raportu review

```
### Sekcja 2 — Architektura (A-E): status per punkt (OK / BRAK / CZĘŚCIOWO + file:line)
### Sekcja 3 — Checklist: tabela (pytanie | status | file:line | dowód)
### Nowe issue: file:line | opis | severity (critical/high/medium/low) | proponowany fix
### Pre-existing (poza zakresem): file:line | opis | severity
### Werdykt: "0 issues — GOTOWE" lub lista blokerów
```

**NIE pisz kodu** — tylko raport. Używaj Read/Grep do weryfikacji każdego punktu.
