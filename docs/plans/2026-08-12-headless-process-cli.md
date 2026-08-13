# Headless Job Processing przez CLI — Plan wdrożenia

> **Data:** 2026-08-12 | **Maszyny:** VM 125 Win10-alphacam (192.168.100.60, AlphaCam/123456) + laptop-monika (100.71.109.69, klucz ed25519, user 48797)
> **Źródło:** sesje 2026-08-11/12 — ROOT CAUSE: job 207 "Zamowienie Test 01" miał uszkodzone powiązanie wzoru P003 (zniknęły obróbki dla wzorów) → "Zadne pliki". Po naprawie joba headless DZIAŁA identycznie jak GUI.
> **Cel:** komenda CLI uruchamiająca procesowanie joba Menadżera Automatyzacji (Automation Manager) w pełni headless — bez okna GUI, bez dialogów, z wynikiem .ard/.anl/.nc i logiem "Sukces".

---

## 1. Kontekst i stan faktyczny (potwierdzone 2026-08-12)

### 1.1 Co działa (E2E potwierdzone przez użytkownika)

| Element | Szczegóły |
|---|---|
| Makro headless | `ApplyMachiningAfterNesting.Events.HeadlessProcess` — procedura VBA: `New AcamAddInsInterface.AddInsInterface` → `GetAddInsInterface(App)` → `GetAutomationManagerAddInGUI()` → `PopulateCustomersAndJobs` → `Jobs.GetByName("<nazwa joba>")` → `PopulateJobDetails` → `Process` |
| Wywołanie | VBScript `GetObject(, "Ar5axaps.Application")` + `app.Run "ApplyMachiningAfterNesting.Events.HeadlessProcess"` — **in-proc w procesie Acam.exe** (App.Run wykonuje makro w procesie hosta, jak GUI) |
| Wymóg sesji | cscript MUSI działać w tej samej stacji co Acam (Session 1). Na VM: `PsExec64 -i 1 -u AlphaCam -p 123456 cscript ...`. Na laptopie: `PsExec64 -i 1 -s cscript ...` (Acam uruchamiany `-i 1 -s` — jako user 48797 crash 0xC0000409) |
| ProgID | `Ar5axaps.Application` (NIE `AlphaCAM.Application` — 429) |
| Czas | VM: ~102s; laptop: ~37s (jeden job, 1 część P003 500x500, nesting + NC) |
| Wynik | Katalog joba: `Rysunki Czesci\<Job>_P003_1.ard`, `<material>.anl`, `Pliki Kodu NC\<material>.nc`, log `<Job>.log` = "Status przetwarzania zadania: Sukces" |
| GUI równolegle | GUI procesuje przez TE SAME rozszerzenia SysMacro — podmiana makra w SysMacro wpływa na GUI (dlatego AMA_final3 z For Each + AddExtensionData był potrzebny do GUI) |

### 1.2 Architektura blokowa (zgodnie z AGENTS.md §9)

CLI = narzędzie z niezależnych bloków. Sekwencję składa aplikacja zewnętrzna. Bloki:

1. **Przygotowanie joba** (czytanie/aktualizacja bazy) — istniejące komendy CDM (cdm import, order-details, doorpaths, materials, config, setups...)
2. **Weryfikacja joba** (NOWY blok): czy job ma JobFiles / powiązanie wzoru poprawne, zanim Process. Zapobiega "Zadne pliki" z niejasnym błędem.
3. **Uruchomienie headless process** (NOWY blok, cel tego raportu): świeża sesja COM + makro HeadlessProcess dla wskazanego joba.
4. **Odczyt wyników** (NOWY/rozszerzony): status z logu joba, lista plików wyjściowych, exit code.

### 1.3 Znane ograniczenia (muszą być w docs komendy)

- **Job musi być poprawny** (wzór z biblioteki z obróbkami). Uszkodzony job → "Zadne pliki" — NIE jest to błąd COM ani makra. Diagnoza: `populate` → sprawdź `JobFiles.Count` / dane CDM_OrderDetails w bazie.
- **Cross-process COM Process() zawsze wisi** (Dispatch, GetActiveObject, Session 0 i 1). Jedyna droga: App.Run in-proc (makro w SysMacro).
- **Wymagana interaktywna stacja** — Session 1 z zalogowanym userem (VM: AutoAdminLogon AlphaCam; laptop: user 48797). Session 0 (usługa gateway) NIE nadaje się do job processingu (nie ma interaktywnego desktopu).
- **Makro HeadlessProcess musi istnieć w SysMacro** (`ApplyMachiningAfterNesting.Events.HeadlessProcess`). Obecne makro testowe: AMA_byname2.arb (laptop) / AMA_byname.arb (VM). Po wdrożeniu CLI: jedno wspólne makro produkcyjne (patrz §4).
- **Podmiana makra w SysMacro wpływa na GUI** — makro produkcyjne musi zachować GUI-compat: `AutomationManagerExtensionSetProcessingData`, `AutomationManagerExtensionInitialise` + AddExtensionData (for each), `AutomationManagerAfterNestingMaterial`, `AutomationManagerBeforeOutputNc` (patrz AMA_final3 = czysty oryginał Hexagon 3bd8060d + osobna procedura HeadlessProcess dobudowana — tak zbudowano AMA_byname).

---

## 2. Zadania (sekwencyjnie; po każdym: ruff + mypy + pytest + commit)

### T1: RESEARCH — dokumentacja referencji API AM do raportu
**Cel:** pełne sygnatury obiektów AutomationManager (Jobs, Job, Process, PopulateJobDetails, AddExtensionData) z typelibu / przykładów Hexagon — jako sekcja w `docs/api_docs/` (nowy plik 11_AutomationManager.md lub rozszerzenie).
**Wykonawca:** subagent explore/general (lokalnie: `docs/alphacam-ecosystem/alphacam-provided-examples/API/...`, `Alphacam_Nesting.py` to TYLKO nesting — AM szukać w przykładach AutomationManager + help-unpacked). Bez E2E. Wynik: raport sygnatur do sesji.

### T2: Makro produkcyjne AMA_prod.arb (z HeadlessProcess)
**Cel:** jedno makro łączące GUI-compat (oryginał Hexagon AMA_final3: SetProcessingData/Initialise/AfterNestingMaterial/BeforeOutputNc/ReadLanguageFile) + procedura `HeadlessProcess` (late binding jak AMA_byname).
**Pliki:** `/tmp/opencode/events_byname2.bas` (baza — ma HeadlessProcess z GetByName; nazwa joba: parametr — sprawdzić czy App.Run przekazuje parametry do makra; jeśli nie: stała/konfigurowalny plik `C:\temp\ama_jobname.txt` odczytywany przez makro przy starcie — DECYZJA w T2).
- Rekompilacja: `vba_build.py <template AMA_final3.arb> <out> <bas> 4750` (UWAGA: template AMA_byname.arb failuje "incorrect last sector index" — slot 6613 vs nowy stream; AMA_final3 ma slot 6580 == nowy stream OK).
- Test: wgrywa na VM + laptop, GUI i headless (patrz T7).
**Wykonawca:** subagent implementujący (main agent dostarcza .bas i kompresor).

### T3: Moduł `core/am_process.py` — czysta logika (bez COM)
**Cel:** funkcje:
- `check_job(job_name) -> dict` — czy job istnieje w bazie (VistaDB przez ps1 — wzorzec cdm_db.py), stan: liczba CDM_OrderDetails, liczba JobFiles, ActiveInProcess, ostatni log.
- `run_headless(job_name, machine_config) -> dict` — generuje VBScript (GetObject Ar5axaps.Application + App.Run HeadlessProcess), uruchamia przez PsExec (konfigurowalne: `-i 1 -u <user> -p <pass>` dla VM / `-i 1 -s` dla laptopa), timeout, zbiera stdout.
- `read_result(job_name, output_root) -> dict` — parse logu joba (status), lista plików wyjściowych, czasy.
**Pliki:** Create `src/alphacam_cli/core/am_process.py`, `tests/unit/test_am_process.py` (mock subprocess/PsExec — bez prawdziwego Acam).
**Wykonawca:** subagent implementujący (wzorzec: cdm_db.py + existing unit tests).

### T4: CLI `am process <job_name>` (+ `am status <job_name>`, `am check <job_name>`)
**Cel:** komendy blokowe:
- `alphacam am check <job>` — weryfikacja joba (T3.check_job) z czytelnym komunikatem: OK / brak wzoru / brak obróbek / job nie istnieje.
- `alphacam am process <job> [--timeout]` — uruchomienie headless (T3.run_headless), potem status. Zwraca JSON (--json) lub rich table. Exit code: 0 sukces, 1 nieudane, 2 job nie istnieje, 3 timeout, 4 Acam nie działa.
- `alphacam am status <job>` — odczyt wyników (T3.read_result).
**Pliki:** Create `src/alphacam_cli/cli/am.py`, Modify `src/alphacam_cli/main.py` (rejestracja grupy), `tests/unit/test_cli_am.py`.
**Wykonawca:** subagent implementujący (wzorzec: cdm.py + main.py).

### T5: Aplikacja `application/am.py` + gateway
**Cel:** jeśli ma działać przez gateway RPC (jak reszta CLI na laptopie — Session 0): handler gateway `am.process` — UWAGA: na VM/Laptop Session 0 NIE ma interaktywnej stacji, więc gateway może uruchomić PsExec zdalnie. Alternatywnie: komendy lokalne (VM z RDP/SSH) — DECYZJA: najpierw lokalnie (T4), gateway po potwierdzeniu E2E.
**Pliki:** wg wzorca application/drawing.py + gateway (jeśli zdecydujemy RPC).

### T6: Naprawa biblioteki wzorów na VM 125 (osobny wątek, blokuje produkcję)
**Cel:** przywrócić obróbki wzorów na VM. Stan: CDM.mdb IDENTYCZNY na obu maszynach (0be800b0), Front.arb identyczny (9a2fd8da), VBMacros identyczne. Podejrzane: AM_UserStyles (265), CDM_ConfigurationSettings, AM_ConfigurationSettings, `sheet_database_v2.db`, AutomationManager.vdb5 (baza AM — 33 DataRow vs 66 na laptopie, cfg 41 ma ID 21-28 vs 11-20).
**Zadania:**
- T6a: porównanie AutomationManager.vdb5 VM vs laptop (tabele AM_UserStyles, AM_ConfigurationSettings, CDM_ConfigurationSettings, AM_Setups, AM_LayerMapping) — różnice.
- T6b: przywrócenie/uzupełnienie różnic na VM (kopiowanie z laptopa przez SSH, zgodnie z backupem C:\temp\AutomationManager_vm_before_laptop.vdb5).
- T6c: test: GUI process joba z P003 na VM → Sukces z plikami.
**Wykonawca:** subagenci implementujący (po researchu T6a).

### T7: E2E (weryfikacja pełna)
**Cel:** na VM 125: `alphacam am check "Zamowienie Test 01"` → OK; `alphacam am process "Zamowienie Test 01"` → Sukces, pliki .ard/.anl/.nc; `alphacam am status` → raport. Powtórka na laptopie (job "Zamowienie Test 02"). GUI po T2: dalej przetwarza (regresja makra).
**Wykonawca:** main agent (E2E przez SSH) + subagent debugger gdy fail.

### T8: Dokumentacja komend w README/docs
**Cel:** sekcja w README: `alphacam am check/process/status`, wymagania (Session 1, PsExec, makro AMA_prod), ograniczenia (uszkodzony job ≠ błąd COM, Session 0 NIE działa, podmiana SysMacro wpływa na GUI).

---

## 3. Recepty E2E (zweryfikowane 2026-08-12)

### VM 125 (192.168.100.60, AlphaCam/123456)
```bash
# 1. Acam w Session 1 (interaktywna stacja — wymóg!)
sshpass -p "123456" ssh AlphaCam@192.168.100.60 "C:\temp\pstools\PsExec64.exe -accepteula -i 1 -u AlphaCam -p 123456 -d \"C:\Program Files\Hexagon\ALPHACAM 2025\Acam.exe\""
# 2. Headless process (cscript w Session 1!)
sshpass -p "123456" ssh AlphaCam@192.168.100.60 "C:\temp\pstools\PsExec64.exe -accepteula -i 1 -u AlphaCam -p 123456 cscript //nologo C:\temp\vbs_hp_now.vbs"
# 3. Wynik
sshpass -p "123456" ssh AlphaCam@192.168.100.60 'type "C:\ALPHACAM\Automatyzacja\Przetworzone Pliki Menadzera Automatyzacji\Zamowienie Test 01\Zamowienie Test 01.log"'
# → "Status przetwarzania zadania: Sukces"
```

### Laptop Monika (100.71.109.69, klucz ed25519, user 48797)
```bash
# 1. Acam jako SYSTEM (user 48797 crash 0xC0000409 bez pełnego kontekstu interaktywnego)
ssh -i ~/.ssh/id_ed25519 48797@100.71.109.69 "C:\temp\PsExec64.exe -accepteula -i 1 -s -d \"C:\Program Files\Hexagon\ALPHACAM 2025\Acam.exe\""
# 2. Headless (cscript też jako SYSTEM!)
ssh -i ~/.ssh/id_ed25519 48797@100.71.109.69 "C:\temp\PsExec64.exe -accepteula -i 1 -s cscript //nologo C:\temp\vbs_hp_laptop.vbs"
# 3. Wynik (log joba)
# → "Status przetwarzania zadania: Sukces" (36.9s, .ard+.anl+.nc)
```

### VBScript szablon (generowany przez CLI)
```vbs
Option Explicit
On Error Resume Next
Dim fso, f, app, t0
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.CreateTextFile("C:\temp\vbs_hp_out.txt", True)
Set app = GetObject(, "Ar5axaps.Application")
f.WriteLine "GetObject err=" & Err.Number & " " & Err.Description
Err.Clear
t0 = Timer
app.Run "ApplyMachiningAfterNesting.Events.HeadlessProcess"
f.WriteLine "Run HeadlessProcess: err=" & Err.Number & " " & Err.Description & " in " & Round(Timer - t0, 1) & "s"
f.Close
WScript.Echo "done"
```

---

## 4. Decyzje otwarte (rozstrzygnąć PRZED T2/T4)

1. **Nazwa joba w makrze**: App.Run przekazuje parametry (Run(MacroName, Parm1..8)) — sprawdzić czy makro może przyjąć `Sub HeadlessProcess(JobName As String)` i `app.Run "...", "<job>"`. Jeśli nie: plik `C:\temp\ama_jobname.txt` odczytywany przy starcie makra (czyszczony po).
2. **Gateway czy lokalnie**: na VM nie ma gateway (usługa nie zainstalowana) — komendy lokalne przez SSH/PsExec. Na laptopie jest gateway (Session 0) — ale Session 0 nie ma interaktywnej stacji → headless przez gateway NIE zadziała bezpośrednio; gateway musiałby wywołać PsExec na Session 1. Pierwsza wersja: lokalnie (maszyny z RDP/SSH).
3. **Jedno makro produkcyjne**: AMA_prod.arb = oryginał Hexagon (GUI-compat) + HeadlessProcess (late binding). Wgranie na obie maszyny (SysMacro) — GUI i headless korzystają z tego samego pliku.
4. **Timeout / monitorowanie**: Process trwa 37-102s na job; CLI musi mieć timeout + log postępu (makro loguje do C:\temp\ama_macro_log.txt: 1,2,3,4,got,PS,r — można czytać w trakcie).

---

## 5. Artefakty (stan 2026-08-12)

| Lokalizacja | Zawartość |
|---|---|
| `/tmp/opencode/AMA_byname2.arb` (ce7ac45a) | Makro z HeadlessProcess GetByName "Zamowienie Test 02" (laptop) |
| `/tmp/opencode/AMA_byname.arb` (bfd59cbb) | Makro z HeadlessProcess GetByName "Zamowienie Test 01" (VM) |
| `/tmp/opencode/AMA_final3.arb` (3bd8060d) | Czysty oryginał Hexagon (GUI-compat) — template build |
| `/tmp/opencode/AMA_orig.arb` / `AMA_orig_backup_vm.arb` (984e4f98) | Oryginał VM (identyczny z laptopa C:\temp\AMA_orig_laptop.arb) |
| `/tmp/opencode/events_byname2.bas`, `events_byname_src.bas` | Źródła makr |
| `/tmp/opencode/vba_build.py`, `vba_compress.py` | Kompresor MS-OVBA LZ77 + builder ARB |
| VM: `C:\temp\vbs_hp_now.vbs`, laptop: `C:\temp\vbs_hp_laptop.vbs` | Skrypty testowe |
| VM: `C:\temp\AutomationManager_vm_before_laptop.vdb5` (6a2f5a91) | Backup bazy AM VM (oryginał) |
| `docs/plans/2026-08-09-cdm-faza2-audyt.md` | Wzorzec planu/konwencji (T1-T8, recepty, wzorce kodu) |

---

## 6. Ryzyka

- **Podmiana makra w SysMacro = zmiana GUI**: makro produkcyjne MUSI mieć pełny GUI-compat (procedury Hexagon). Test regresji GUI po T2.
- **Session 0 nie działa**: usługa gateway nie może wykonać Process bez interaktywnej stacji — komunikaty CLI muszą to jasno mówić (lub CLI automatycznie używa PsExec -i 1).
- **Uszkodzony job ≠ błąd CLI**: "Zadne pliki" może oznaczać zepsuty wzór (jak job 207) — `am check` ma to wykrywać (JobFiles.Count, CDM_OrderDetails, obróbki).
- **Acam restart** przy podmianie makra: plik zablokowany gdy Acam działa — taskkill + copy /Y + restart (recepta w tasks.md).
- **CDM.arb nie kompiluje się na VM** (brak SSTree.ocx — Infragistics ActiveTreeView, {1C203F10-95AD-11D0-A84B-00A0247B735B}, brak pliku+CLSID+TypeLib) — blokuje IMPORT CDM, nie procesowanie istniejących jobów. Osobny wątek (opcjonalnie T6d).
