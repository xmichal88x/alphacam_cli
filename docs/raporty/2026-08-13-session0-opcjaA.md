# RAPORT: Procesowanie CDM w Session 0 — Test opcji A (gateway + App.Run makra)

Data: 2026-08-13
Maszyna testowa: laptop Monika (100.71.109.69, Session 0, usługa AlphaCAMGateway)
Testy: wszystkie na laptopie Monika (NIE na VM)

## Kontekst / Cel

Ustalenie z poprzednich testów (2026-08-13):
- `job.Process()` wywoływane cross-process przez COM marshal z Pythona → makro
  ApplyMachiningAfterNesting dostaje obiekty przez granicę marshal → 80004002 +
  brak obróbek (DoFeatureExtract/ApplyLayerMappingMachining nie wykonane) → brak NC.
- Makro `HeadlessProcess(JobName)` (w SysMacro, hash 20e6ff8c, late binding)
  wykonane IN-PROC w procesie Acam (`New AcamAddInsInterface.AddInsInterface` +
  `A.Process`) → pełne obróbki + NC (potwierdzone: 37s, NC 1744 B, .ard 84291 B).

Cel testu opcji A: **gateway (usługa w Session 0, stacja Service-0x0-3e7$) sam
wywołuje `App.Run("ApplyMachiningAfterNesting.Events.HeadlessProcess", job)`
przez trzymaną referencję COM** — bez VBScript, bez PsExec, bez drugiego procesu Acam.

Pytania testowe:
1. Czy `app.Run` z procesu gateway (python COM marshal → Acam) wykonuje makro
   in-proc i przechodzi bez 80004002?
2. Czy makro/Process działa w nieinteraktywnej stacji Service-0x0-3e7$
   (brak dialogów → brak UserInteractive)?
3. Jaki jest czas procesowania?
4. Czy pliki wyjściowe są kompletne (log Sukces, .nc, .ard z obróbkami)?

## Przebieg

### Krok 1 — Przygotowanie joba testowego
- Komenda: `cdm create "S0 Timing 01"` + `cdm import C:/temp/csv2_test.csv --job "S0 Timing 01"`
- CSV testowy (csv2 6-kolumnowy): `P003,1,500,500,1;18;0;0;30;45;40;90;50;3;0,MDF_18`
- Weryfikacja w bazie: job 214, JobType=1, cfg=41 (Fronty), mat=2 (MDF_18),
  detail ActiveInProcess=True, qty=1, sheet 2 (qty 100).
- Import wymagał restartu usługi gateway (pierwszy import po starcie padał na
  "System.__ComObject → AlphaCAMMill.App" — stan przejściowy COM w usłudze).

### Krok 2 — Wdrożenie tymczasowego handlera probe do gateway (server.py)
- Dodano handler `_handler_probe_run_macro` — wywołuje
  `com_app._raw_app.Run("ApplyMachiningAfterNesting.Events.HeadlessProcess", job_name)`
  na referencji COM trzymanej przez gateway (in-proc makro w procesie Acam usługi).
- Restart usługi AlphaCAMGateway po zmianie (recepta: sc stop/start).
- Uwaga: maszynowy server.py ma niecommitowane zmiany lokalne (różni się od repo
  lokalnego) — handler dodany przez patch na bazie pliku z maszyny (backup:
  /tmp/opencode/server_machine_backup.py), upload base64.

## WYNIKI TESTÓW (oba SUKCES)

### Test 1 — "S0 Timing 01" (09:52, czas od startu RPC call)
- RPC: `probe_run_macro {"job_name": "S0 Timing 01"}`
- Wynik: `success=True, elapsed_s=36.3, run_result=None`
- Pliki: log **"Status przetwarzania zadania: Sukces"**,
  `MDF_18_MDF_18.nc` **1744 B** (T08 D08 S18000, ryflowanie V-Bit),
  `S0 Timing 01_P003_1.ard` **84345 B** (z obróbkami),
  `MDF_18 MDF_18.anl` 2800 B
- **Brak 80004002, brak UserInteractive** (stacja Service-0x0-3e7$, nieinteraktywna)

### Test 2 — "S0 OptA Test 02" (10:54, nowy job create+import)
- RPC: `probe_run_macro {"job_name": "S0 OptA Test 02"}`
- Wynik: `success=True, elapsed_s=33.3, run_result=None`
- Pliki: log **"Sukces"**, `.nc` **1744 B**, `.ard` **84417 B**, `.anl` 2806 B

### Procesy Acam podczas testu
- TYLKO JEDEN proces Acam (PID 3752, Session 0, proces usługi gateway)
- Create/import (przez CLI remote → gateway COM) oraz procesowanie (App.Run makra)
  — wszystko na tym samym procesie Acam. **Brak drugiego procesu Acam.**

## WNIOSKI

1. **Opcja A działa produkcyjnie**: gateway (Session 0, Service-0x0-3e7$)
   wywołuje `App.Run("ApplyMachiningAfterNesting.Events.HeadlessProcess", job)`
   przez trzymaną referencję COM — makro wykonuje się in-proc w procesie Acam
   usługi, bez VBScript/PsExec/drugiego procesu Acam.
2. **Czas procesowania**: 33-36 s (identyczny jak ścieżka VBScript 37 s).
3. **Brak dialogów/UserInteractive** w nieinteraktywnej stacji — produkcyjne
   makro (20e6ff8c, late binding, bez MsgBox) przechodzi czysto.
4. **Wyniki kompletne**: NC + .ard z obróbkami + .anl + log Sukces.
5. **Jedyny mankament**: `_handler_probe_run_macro` to handler testowy —
   do wdrożenia jako oficjalna implementacja `process_cdm_job` (wymaga
   zastąpienia headless.py/VBScript w core/application.py + testy jednostkowe
   + E2E przez CLI `cdm process --remote`).

## REKOMENDACJA WDROŻENIOWA (opcja A jako produkcyjna)

1. Przenieść logikę `_handler_probe_run_macro` do `core/application.py` jako
   nową metodę `process_cdm_job_inproc` (App.Run makra na trzymanej referencji).
2. `process_cdm_job` → używa in-proc, zachowując fallback VBScript
   (headless.py) na wypadek błędów COM.
3. Dodać parametr RPC np. `method: "inproc" | "vbs"` (domyślnie inproc).
4. Testy: jednostkowe (mock COM), E2E przez CLI (2 joby — powtórzenie).
5. Usunąć/oznaczyć handler probe po wdrożeniu.

## OTWARTE / NOTATKI

- Pre-existing: LSP błędy w remote.py:283-285 ("No parameter named
  machine/timeout_seconds/output_root") — client.py/remote.py nie mają tych
  parametrów w sygnaturze RemoteSession (nie blokuje — procesowanie działa
  przez server.py bezpośrednio).
- `Rysunki Nestingu\MDF_18 MDF_18.ard` = 0 B (zablokowany przez Acam przy
  kopiowaniu) — plik rysunku nestingu tworzony jest pusty/otwarty w Acam;
  NC generowany jest z plików części, nie z tego pliku.
- Backup oryginalnego server.py z maszyny: /tmp/opencode/server_machine_backup.py
- Makra: SysMacro=20e6ff8c (late binding + HeadlessProcess(JobName), produkcyjne);
  desktop=9a8e4597 (early binding — rzucało 80004002 przy cross-process).


## WDROŻENIE (2026-08-13 cd.) — opcja A jako domyślna metoda procesowania

### Zmiany w kodzie (commit-ready, lokalnie + maszyna)
1. `core/application.py`:
   - `process_cdm_job_inproc(job_name, timeout_seconds=300, output_root=None)` —
     makro `HeadlessProcess` uruchamiane IN-PROC na trzymanej referencji COM
     (`self._raw_app.Run(...)`) — bez VBScript/PsExec; wynik przez
     `headless.read_job_result`; dict z `method: "inproc"`, `elapsed_s`.
   - `process_cdm_job(..., method: str = "inproc")` — dispatcher: `"inproc"`
     (default) | `"vbs"` (stara ścieżka VBScript, fallback) | inna → RuntimeError.
   - UWAGA (bug znaleziony i naprawiony w tej sesji): pierwsza wersja inproc
     uruchamiała `Run` w osobnej nici (threading.Thread) → `RPC_E_WRONG_THREAD`
     (-2147417842) — COM wymaga wywołania na wątku STA; naprawa: `Run`
     bezpośrednio w bieżącym wątku (w gateway to wątek STA usługi).
2. `gateway/server.py`: `_handler_process_cdm_job` przyjmuje `method`
   (walidacja: str + {"inproc","vbs"}); USUNIĘTY tymczasowy handler
   `_handler_probe_run_macro` (zastąpiony oficjalną ścieżką).
3. `gateway/client.py` + `gateway/remote.py`: parametr `method` w
   `process_cdm_job` (proxy + RemoteSession); naprawione pre-existing błędy
   LSP "No parameter named machine/timeout_seconds/output_root" (remote.py
   vs client.py desynchronizacja).
4. `cli/cdm.py`: opcja `--method inproc|vbs` (default inproc).
5. Testy: `test_cdm_core.py` (+5 inproc, timeout→com_error), 
   `test_gateway_server.py` (+3 method), `test_remote.py` (sync proxy).

### Weryfikacja lokalna
- ruff: All checks passed; mypy: Success (39 files); pytest: **848 passed**.

### E2E na laptopie Monika (CLI --remote, metoda inproc — domyślna)
| Job | Części | Czas | Wynik |
|---|---|---|---|
| Prod E2E 01 | 2× P003 (500×500, 400×300) | 40.7s | Sukces; NC 3690 B; 2× .ard (84319, 66192 B); .anl 3535 B |
| Prod E2E 02 | 1× P003 (500×500) | 36.1s | Sukces; NC 1744 B; .ard 84319 B; .anl 2798 B |

- Procesy podczas E2E: JEDEN Acam (PID 8484, Session 0, proces usługi) —
  create/import/process na tym samym procesie.
- Fallback `--method vbs` (test "Prod VBS Test"): GetObject err=429 —
  VBScript wymaga Acam w Session 1 (PsExec -i 1 -s); przy konfiguracji
  Session 0 (Acam tylko w usłudze) fallback NIE zadziała bez osobnego
  startu Acam w Session 1. To NIE regresja — warunek ścieżki vbs.
  Produkcyjnie: inproc (default) nie wymaga Session 1.

### Wniosek produkcyjny
- **Domyślnie: `--method inproc`** — procesowanie przez gateway na jednym
  procesie Acam (Session 0), bez PsExec, bez Session 1, ~36-41s.
- Fallback vbs zostaje tylko dla środowisk z Acam w Session 1.
