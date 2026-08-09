# Raport: CDM (Cabinet Door Manufacturing) uruchomiony w Session 0

> Data: 2026-08-09 | Maszyna: laptop-monika (Windows 11, AlphaCAM 2025 Router) | Dostęp: SSH + gateway RPC (Tailscale DERP)
> Wynik: **CDM działa headless przez gateway w Session 0** — nowa komenda `cdm create/jobs/types` (CLI + RPC), testy 428 passed, E2E potwierdzone.

---

## 1. Cel zadania

Uruchomić **CDM (Cabinet Door Manufacturing — dodatek AlphaDOOR do AlphaCAM)** w Session 0 na laptopie Monika, zdalnie przez gateway RPC, i rozbudować CLI o tę funkcję. Testować aż się uda. W raporcie uwzględnić wnioski dla Przemysłu 4.0.

---

## 2. Co to jest CDM

- **CDM = "Alphacam Cabinet Door Manufacturing"** — aplikacja VBA (AlphaDOOR) + dodatek .NET do produkcji **frontów meblowych (drzwi szafkowych)** z MDF: style drzwi, typy z toolpathami, zamówienia (joby), nakładanie (nesting), NC.
- **Nie mylić z CDM.dll (VB6, LICOMDAT\CDM Data\)** — to stary front-end 32-bitowy; Acam.exe jest x64, więc CDM.dll NIE ładuje się jako addin. Współczesny CDM = **Automation Manager (AcamAddIns.dll, .NET)** z funkcjami CDM.
- Komponenty na dysku:
  - `C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5` — **baza VistaDB 5** (joby, klienci, ustawienia, CDM_DoorTypes)
  - `C:\ALPHACAM\LICOMDAT\CDM Data\CDM.dll, CDM.mdb, CDM.arb` — stary AlphaDOOR (mdb = stare style/zamówienia)
  - `C:\ALPHACAM\LICOMDIR\Alphadoor User Styles\Alphadoor Included\*` — style drzwi (`.arb` + `.ini`, np. `AD_OnePanelSquare.arb`, nazwa w `.ini` → "Single Panel Square")
  - `C:\Users\48797\AppData\Local\Hexagon\Alphacam\AMSettings.acamcore` — konfiguracja Automation Manager (XML, ExtraSettingsList: ShowCDM, UseSQLServer...)
- **CDM = dodatek, nie makro** — działa przez Automation Manager (potwierdzone w dokumentacji i przez API).

---

## 3. Architektura dostępu (Session 0)

Wszystko przez **AddInsInterface** (wzorzec z sesji 7 dla NcOutputManager/AutoStyles/Reports):

```
AddInsInterface (CLSID {39BFE38A-D3E4-43EA-89D0-584C776B97A9})
  └─ GetAddInsInterface(app) → IAddIns
       └─ GetAutomationManagerAddInGUI() → IAutomationManager   ← KLUCZOWE (nie GetAutomationManagerAddIn!)
            ├─ IsCDMAuthorised() = True
            ├─ Jobs (kolekcja: .Count, .Item(i)) — joby CDM
            ├─ NewCDMJob() → IAutomationManagerJob
            │    ├─ JobName (set), SaveToDatabase()
            │    ├─ AddCDMOrderDetail(TypeName) → ICDMOrderDetail
            │    │    ├─ Width, Length, Quantity, ByPassNest (set)
            │    │    └─ SaveToDatabase()
            │    └─ Process()  ← ⚠️ WISI w Session 0 (WPF dialog)
            ├─ ConfigurationSettings (kolekcja, .Count=2)
            └─ ImportSettings (kolekcja)
```

**Handler RPC musi działać WPROST w wątku STA serwera** (jest tam wrzucany przez `_dispatch` → `_com_call`). Wewnętrzne wątki robocze / drugie `_com_call` = deadlock (błąd RPC_E_WRONG_THREAD lub zawieszenie).

---

## 4. GŁÓWNE ODKRYCIE — dlaczego GetAutomationManagerAddIn() wisi

### Objaw
`GetAutomationManagerAddIn()` nigdy nie wraca w Session 0 (testowane 45s, 90s, 300s — zero odpowiedzi). Wcześniej (sesja 7) uznano to za nieprzezwyciężalne ("addin WPF wymaga UI/licencji") — **to była błędna diagnoza**.

### Root cause (dekompilacja IL AcamAddIns.dll)
Metoda `AddIns.GetAutomationManagerAddIn()` robi `newobj AutomationManager::.ctor()` (bezargumentowy), a `GetAutomationManagerAddInGUI()` robi `ldc.i4.1; newobj .ctor(bool)`:

| Konstruktor | IL | Co robi | Session 0 |
|---|---|---|---|
| `CTOR()` (140B) | tworzy 9 kolekcji + `SetAlphacamConfigurationVariables` + **`get_AutomationManagerDB()`** + `InitialiseExtensions` | **ConnectToDatabase → modalny dialog błędu** | ❌ **WISI** |
| `CTOR(bool)` (106B) | tylko 9 kolekcji + base | nic więcej | ✅ **DZIAŁA** |

`get_AutomationManagerDB()` → `new AutomationManagerDatabase()` → `ConnectToDatabase(false,false)`:
- `ConnectExternalMaterialsLibraries` → `ConnectToWorkplanDatabase` / `ConnectToCVdatabase` → przy błędzie `QuickMessageExclamation` (**MessageBox**)
- przy braku `.con`: `UpdateAMDatabaseFromV4ToV5` / `UpdateAutomationManagerDB` (15 KB IL — migracje ALTER TABLE) → też kończy się MessageBox

**MessageBox w Session 0 = niewidzialny, czeka na kliknięcie, NIGDY nie wraca.** To jest cała przyczyna "wiszenia".

### Wniosek
**Zamiast `GetAutomationManagerAddIn()` używaj `GetAutomationManagerAddInGUI()`** — zwraca ten sam obiekt `IAutomationManager` bez inicjalizacji bazy. Dokumentacja typelibu ostrzega ("Do not use. Job and JobFile information will be incomplete") — dotyczy to tylko trybu GUI, w praktyce NewCDMJob/AddCDMOrderDetail/SaveToDatabase działają w pełni.

---

## 5. Fixy systemowe (wykonane na laptop-monika)

Session 0 = usługa AlphaCAMGateway działa jako **LocalSystem** — czyta konfigurację z profilu SYSTEM, nie użytkownika 48797. To ten sam problem co przy nestingu (reg copy HKCU→HKU\.DEFAULT).

### 5.1 Pliki w profilu SYSTEM (odpowiednik reg copy)
Skopiowano z `C:\Users\48797\AppData\Local\Hexagon\Alphacam\` do `C:\Windows\System32\config\systemprofile\AppData\Local\Hexagon\Alphacam\`:
- `AMSettings` (XML formularza)
- `AMSettings.acamcore` — **rozszerzony o**:
  ```xml
  <ExtraSettingsList>
    <string>ShowCDM|1</string>
    <string>UseSQLServer|0</string>
    <string>UseCVMaterialsLibrary|0</string>
    <string>UseWorkplan|0</string>
    <string>ShowPartProcessing|0</string>
  </ExtraSettingsList>
  ```
- `AutomationManagerForm.acamcore`, `AutomationManagerProcessingCompleteWindow.acamcore`, `AutomationManagerWizardFeatureSetupForm.acamcore`, `AutomationManagerWizardMainForm.acamcore`, `CDMDoorInfoForm.acamcore`

### 5.2 Rejestr (HKCU + HKU\.DEFAULT)
`Software\VB and VBA Program Settings\LICOM AlphaDOOR\Options`:
- `Units = 1` (DWORD) — metryczne; bez tego CDM pyta "Default Working Unit" (frmUnits — modalny → wisi w Session 0)
- `SearchResolution = 1`
- `ShowPartProcessing = 0` (na poziomie klucza Options; ustawiane też w AMSettings.acamcore)

### 5.3 Inne
- `regsvr32 /s C:\ALPHACAM\LICOMDAT\CDM Data\CDM.dll` — rejestruje ProgID-y `CDM2016R2.CVBAProject/DoorTypeData/MainFrontEnd/SplashScreen` (WOW6432Node, 32-bit). Acam.exe x64 → DLL nie ładowana jako addin, ale rejestracja nieszkodliwa.
- Ręczna rejestracja CLSID `{CC979E90-...}` (Alphacam.AddIns.AutomationManager) — **NIE rozwiązała** wiszenia (metoda robi newobj .NET, nie CoCreateInstance). Nie szkodzi, ale i nie pomaga.

---

## 6. Działająca sekwencja (recepta E2E)

```python
import pythoncom
import win32com.client as w32

# W wątku STA (u nas: handler gateway przez _com_call)
clsid = pythoncom.MakeIID("{39BFE38A-D3E4-43EA-89D0-584C776B97A9}")  # AddInsInterface
ai = w32.Dispatch(pythoncom.CoCreateInstance(clsid, None, pythoncom.CLSCTX_ALL, pythoncom.IID_IDispatch))
addins = ai.GetAddInsInterface(app)          # app = surowy CDispatch (wrapper._app)
am = addins.GetAutomationManagerAddInGUI()   # ⚠️ GUI, nie bezparametrowe!

assert am.IsCDMAuthorised() is True          # licencja CDM aktywna
job = am.NewCDMJob()
job.JobName = "Zamówienie 001"
job.SaveToDatabase()
detail = job.AddCDMOrderDetail("Typ Frontu 1")   # TypeName z tabeli CDM_DoorTypes
detail.Width = 600.0
detail.Length = 400.0
detail.Quantity = 2
detail.ByPassNest = False
detail.SaveToDatabase()
```

### Dostępne TypeName (tabela `CDM_DoorTypes` w AutomationManager.vdb5)
Odczyt przez VistaDB: `C:\Program Files\Hexagon\ALPHACAM 2025\VistaDB.5.NET40.dll`, connection `Data Source=C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5`.
Produkcyjne: `Typ Frontu 1` .. `Typ Frontu 47`, `L_B_10mm`, `L_B_32mm`, `L_C_10mm`, `M_01`, `22` (+ systemowy id=1 "Alphacam Created System Database Field - Do not delete").

---

## 7. Ograniczenia Session 0 (NIE działają headless)

| Metoda | Problem |
|---|---|
| `job.Process()` | **WISI** — okno przetwarzania WPF (ProcessingWindow). Wymaga GUI (Session 2). |
| `job.ImportCSVToJob(path, None)` | **WISI** — dialog wyboru ImportSettings. (Z obiektem ImportSettings z kolekcji też wisiał — do zbadania.) |
| `am.ImportCDMDatabase()` | Błąd `UserInteractive` ("Wyświetlenie modalnego okna... nieprawidłowe gdy aplikacja nie pracuje w trybie UserInteractive") — to WYJĄTEK, nie wisi. |
| `am.MigrateDataToSQLServer()` | Dialog TAK/NIE — nie wywoływać. |

**Praktyczny pipeline:** joby + pozycje tworzyć headless (RPC), przetwarzanie (Process → rysunki/nesting/NC) przez GUI Automation Manager na sesji użytkownika (schtasks /it).

---

## 8. Nowa funkcjonalność (wdrożona)

### CLI
```
alphacam --remote --host 100.71.109.69 cdm create JOB TYPE --width 400 --length 300 --quantity 1 [--bypass-nest]
alphacam --remote --host 100.71.109.69 cdm jobs
alphacam --remote --host 100.71.109.69 cdm types
```
- `--process` w `cdm create` — nie wywołuje Process() (GUI), wypisuje komunikat.
- Komunikaty po angielsku (konwencja repo).

### RPC (gateway/server.py)
- `_handler_run_cdm(params)` → `{success, job_name, type_name, width, length, quantity}`; czytelny błąd `cdm: door type not found: X` (mapowanie FOREIGN KEY error przez `_cdm_known_door_types`)
- `_handler_cdm_jobs()` → `{jobs: [{id, name}]}`
- `_handler_cdm_types()` → `{types: [...]}` (z jobów/CDMOrderDetails — headless ograniczone; pełna lista wymaga bezpośredniego odczytu VistaDB)
- pomocnicze: `_cdm_automation_manager()`, `_cdm_known_door_types()`

### Klienty
- `gateway/client.py`: `RemoteSession.run_cdm/cdm_jobs/cdm_types`
- `gateway/remote.py`: `RemoteApplication.*` (delegacja)
- `core/application.py`: `get_automation_manager_addin()` + `run_cdm/cdm_jobs/cdm_types` (tryb lokalny)

### Testy
428 passed (23 nowe: test_cli_cdm.py 7, test_gateway_server.py +12, test_remote.py +4), ruff 0, mypy 0.

### Commity (master, 2026-08-09)
`a601a8e` (handler flow) → `cc4c2d5` (TypeName) → `975094b` (read jobs) → `60cfe95` (Process gated) → `7fabda2` (ConfigurationSettings) → `230122a` (log) → `37af34c` (ImportCSV test) → `edad09b` (ImportSettings.Item(1)) → `7a077bd` (Feat: cdm CLI) → `f801eaf` (Docs).

---

## 9. Wnioski dla Przemysłu 4.0

1. **AddInsInterface = uniwersalna brama do wszystkich dodatków AlphaCAM w Session 0.** CLSID {39BFE38A-...} + `GetAddInsInterface(app)` + `Get*AddIn()`. Już działa: NcOutputManager, AutoStyles, NewReports (sesja 7) + **AutomationManager/CDM (ta sesja)**. Wzorzec pozwala dodawać kolejne dodatki (SheetDatabase, ToolOrdering, ParametricRules...) metodą prób i błędów.
2. **"Wariant GUI" metod addinów** (`GetXAddInGUI` zamiast `GetXAddIn`) może omijać inicjalizację z dialogami — sprawdzać IL, gdy metoda wisi.
3. **Konfiguracja per-użytkownik vs SYSTEM** — każda funkcja AlphaCAM czytająca AppData/rejestr wymaga replikacji do `systemprofile` + `HKU\.DEFAULT` (powtarzalny fix headless; odpowiednik reg copy z nestingu).
4. **Baza VistaDB (AutomationManager.vdb5) czytelna bezpośrednio** — bez COM: PowerShell + VistaDB.5.NET40.dll (SELECT z CDM_DoorTypes działa). Można budować raporty/integracje ERP bez dotykania AlphaCAM.
5. **Pipeline produkcyjny frontów:** CSV zamówień (format: `Style,Width,Height,Qty,"Material"`) → joby CDM headless (RPC) → weryfikacja w Automation Manager (GUI) → Process (rysunki + nesting + NC) → maszyna CNC. Automatyzacja planowania produkcji możliwa już teraz.
6. **Przyszłe integracje:** import CSV przez `ImportCSVToJob` z gotowym obiektem `ImportSettings` (zbudowanym przez `am.NewImportSetting()` zamiast dialogu) — kandydat do dokończenia w kolejnej sesji; `CreateJobsFromCSVFile(PathToCSV, ImportSettings)` na poziomie AM (bulk).

---

## 10. Pułapki i lekcje (dla nowej sesji)

1. **GetAutomationManagerAddIn() wisi NA ZAWSZE** — nie używać; zawsze `GetAutomationManagerAddInGUI()`.
2. **Restart usługi po zmianach kodu:** `taskkill /F /IM Acam.exe` → `sc stop AlphaCAMGateway` → `sc start AlphaCAMGateway` → czekać ~40s. **Bez taskkill Acam.exe stary proces z zablokowanym wątkiem STA wisi i nowy Dispatch podłącza się do niego** (GetActiveObject) — usługa nieodpowiadająca.
3. **Deadlock w handlerach:** handler jest już wykonywany w wątku STA przez `_dispatch`/`_com_call` — NIE tworzyć wewnątrz wątków roboczych ani drugiego `_com_call` (RPC_E_WRONG_THREAD / wiszenie).
4. **`gencache.EnsureModule` w wątku STA potrafi wisieć** — używać late binding (`w32.Dispatch(CoCreateInstance(...))`).
5. **`str()` na obiektach COM w f-stringach wywołuje default method** (błąd) — zawsze `repr()` (lekcja z nestingu, potwierdzona).
6. **PowerShell + SSH:** `head`/`Select-Object` z cmd nie działają; cudzysłowy `{}` w PowerShell przez SSH trzeba escapować; wygodniej pisać .ps1/.py do pliku i scp.
7. **CDM nie ma dostawcy Jet/ACE dla CDM.mdb** (ADODB "Nie można odnaleźć dostawcy") — CDM.mdb czytać przez VistaDB? NIE — CDM.mdb to Access; dostęp tylko przez CDM.dll (GUI) lub stare narzędzia. Główna baza to vdb5.
8. **Joby testowe** (CDM_PROBE_*, PROD_TEST_*) zostały w bazie AutomationManager.vdb5 — usunąć w GUI Automation Manager (Delete Selected), nie przez API (brak handlera delete).
9. **`_handler_cdm_probe` i `_am_probe*` w server.py** — diagnostyczne, do wyczyszczenia przy refactorze (logują do C:\temp).

---

## 11. TODO na nową sesję (kolejność proponowana)

1. **Dokończyć import CSV headless:** zbudować `ImportSettings` przez `am.NewImportSetting()` (ustawić pola: separator, kolumny, skip header) i wywołać `job.ImportCSVToJob(csv, settings)` — bez dialogu. Test: CSV z 5 kolumnami (Style,Width,Height,Qty,Material).
2. **`CreateJobsFromCSVFile(PathToCSV, ImportSettings)`** — bulk tworzenie jobów z CSV na poziomie AM (przetestować czy wisi).
3. **`cdm types` pełne:** odczyt CDM_DoorTypes bezpośrednio z vdb5 (przez skrypt PowerShell→JSON lub wbudowany odczyt VistaDB przez .NET z gateway) zamiast tylko z jobów.
4. **Handler delete job** (`cdm delete JOB_ID`) do sprzątania jobów testowych (job.DeleteFromDB() — sprawdzić czy działa headless).
5. **Sprzątanie:** usunąć `_handler_cdm_probe` + logi C:\temp; uporządkować server.py.
6. **README:** sekcja o `cdm` (jak `nest`).
7. **Ewentualnie:** próba `Process()` przez GUI z autowykonaniem (schtasks /it + makro VBA uruchamiające Automation Manager) — pełny pipeline bez ręcznej pracy.

---

## 12. Środowisko (przypomnienie dostępu)

- SSH: `ssh -i ~/.ssh/id_ed25519 48797@100.71.109.69` (Tailscale DERP wymuszony, IP 100.71.109.69)
- Usługa: `AlphaCAMGateway` (NSSM, port 8721, kod: `C:\Users\48797\Documents\PROJEKTY\alphacam_cli\alphacam_cli`)
- Cykl: git push → SSH git pull → taskkill Acam → sc stop/start
- RPC z Linuxa: `.venv/bin/alphacam --remote --host 100.71.109.69 <komenda>`
- CLI test: `.venv/bin/alphacam --remote --host 100.71.109.69 cdm create TEST "Typ Frontu 1" --width 400 --length 300 --quantity 1`
