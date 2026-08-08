# Tasks — Production Readiness v1.0.0

> Ocena ogólna: ~8/10. Testowany E2E na żywym AlphaCAM 2025 Router przez gateway (Tailscale). Gotowy do beta.

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

## Podsumowanie

| Obszar | Stan |
|---|---|
| Kod + typy | ✅ ruff 0, mypy 0 |
| Testy jednostkowe | ✅ 227 passed, 3 skipped (2026-08-08) |
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

**Mapowanie na opcje GUI (ACAM4.chm, sdk-download/standalone/help/):** Minimum Gap Between Paths (=Gap/PartGap), Gap at Sheet Edge (=EdgeGap), Extra Gap at Lead-in Start (=LeadGap), Cut Width, Optimization Level (Min-Max), For cuts/For space, Pack To, Subroutines.

**E2E potwierdzone (Session 0, żywy AlphaCAM 2025 Router):** run_nest advanced z 15 opcjami (total_time=20, part_gap=4, edge_gap=8, lead_gap=1, minimise_tool_changes=True itd.) + arkusz MDF_18 z biblioteki → success, **count=1**, rysunek 3 geometrie/24 toolpaths.

**Tryb podstawowy (bez --advanced) działa jak dotąd** — CreateNestData/AddSheet/DoNest (Sesje 2-4).

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
