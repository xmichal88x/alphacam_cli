# AGENTS.md — Alphacam CLI

Obowiązują **globalne reguły** z `~/.config/opencode/AGENTS.md`. Główny agent tylko analizuje i deleguje, nigdy nie pisze kodu.

---

## 1. Technologie

- Framework: Python + click/typer
- Język: Python 3.11+
- COM bridge: pywin32
- Packaging: pyinstaller → .exe
- MCP server: fastmcp (opcjonalnie)

## 2. Komendy

```bash
alphacam connect
alphacam drawing create --w 100 --h 50
alphacam drawing save test.amd
alphacam tool list
alphacam tool select "Flat - 10mm"
alphacam mill rough --depth -10 --spindle 12000
alphacam nc output test.nc
alphacam batch ./parts/ --post fanuc
```

## 3. Agent Architecture — Reguły Postępowania

### 3.1 Główny agent

Główny agent **NIGDY** nie pisze kodu ani nie edytuje plików. Jego rola:
1. **Analizuje** — rozumie zadanie, czyta kod, identyfikuje co trzeba zrobić
2. **Dzieli** — rozbija pracę na niezależne, atomowe zadania (1 zadanie = 1 konkretna zmiana)
3. **Zapisuje** — tworzy listę zadań przez `todowrite` (status: pending)
4. **Deleguje** — KAŻDE zadanie do osobnego subagenta przez `Task` tool
5. **Weryfikuje** — odbiera wyniki, sprawdza jakość, aktualizuje `todowrite` na `completed`

### 3.2 Subagenci

- **1 subagent = 1 atomowe zadanie.** Nigdy więcej.
- Jeśli zadanie wymaga 10 kroków → to znaczy, że wymaga 10 subagentów.
- **Implementacja ≠ Debugowanie:**
  - **Implementacja** — zadania wykonuj SEKWENCYJNIE (1 subagent naraz), bo zmiany w tej samej bazie kodu konfliktują.
  - **Debugowanie/testy** — niezależne problemy badaj RÓWNOLEGLE (wielu subagentów naraz).
- Subagent wykonuje zadanie i zwraca wynik. Główny agent przekazuje subagentowi tylko jego zadanie + kontekst (subagent NIE ma dostępu do todo głównego agenta).

### 3.3 Workflow dla kodu

1. Subagent czyta istniejący kod, rozumie kontekst
2. Subagent wprowadza zmianę (edytuje lub tworzy pliki)
3. Subagent uruchamia: linter → type checker → testy (jeśli dostępne)
4. Subagent zgłasza wynik agentowi głównemu
5. Agent główny weryfikuje (`verification-before-completion`), aktualizuje `todowrite`
6. Po wszystkich zadaniach → `code-reviewer` dla całościowego przeglądu

## 4. System śledzenia zadań

**`todowrite`** — główny system śledzenia zadań podczas sesji.

**`TASKS.md`** — persistent storage między sesjami. Na początku sesji odczytaj TASKS.md i przenieś do `todowrite`. Na koniec sesji zaktualizuj TASKS.md na podstawie stanu z `todowrite`.

Stany: `pending` → `in_progress` → `completed` / `cancelled`.

## 5. Kaizen — Oportunistyczna Poprawa Kodu

Podczas pracy zawsze wypatruj okazji do poprawy jakości kodu:
- Każda znaleziona okazja → OSOBNE zadanie na `todowrite`
- Poprawki deleguj przez `code-refactoring-refactor-clean`
- **1 zadanie = 1 poprawka.** Nie łącz poprawy jakości z głównym zadaniem.
- Subagent widzący okazję zgłasza ją agentowi głównemu (nie robi tego sam).

## 6. Skills Activation

Przy każdej sesji aktywuj skille pasujące do zadania:

**Obowiązkowe:**
- `writing-plans` — plan przed implementacją
- `subagent-driven-development` — wykonanie przez subagentów
- `verification-before-completion` — weryfikacja przed zakończeniem
- `kaizen` — ciągłe ulepszanie

**Opcjonalne (gdy pasują):**
- `code-reviewer` — przegląd kodu
- `debugger` / `systematic-debugging` — debugowanie
- `dispatching-parallel-agents` — wielu subagentów równolegle dla debugowania/testów
- `code-refactoring-refactor-clean` — poprawa jakości kodu przez subagenta
- `executing-plans` — wykonanie planu w osobnej sesji

## 7. Verification Gate

Przed uznaniem zadania za zakończone:
1. Uruchom linter
2. Uruchom type checker (jeśli dostępny dla języka)
3. Uruchom testy (jednostkowe i integracyjne)
4. Sprawdź czy nie ma regresji
5. **DOPIERO WTEDY** zmień status `todowrite` na `completed`

## 8. Dokumentacja — gdzie szukać

Najpierw przeczytaj `tasks.md` (stan projektu, logi, recepty E2E).

| Lokalizacja | Co zawiera | Kiedy użyć |
|---|---|---|
| `tasks.md` | Stan projektu, logi sesji, recepty E2E (np. Session 0 nesting: reg copy HKCU→HKU\.DEFAULT, `gencache.EnsureModule` typelibu przed `App.Nesting`, `--advanced`) | **Początek każdej sesji** |
| `docs/api_docs/` | Podzielona dokumentacja API core (01_Events, 02_Application, 04_Drawing, 05_Geometry, 06_Tools, 07_Machining, 08_Styles, 09_PostProcessor, 10_Utilities; README.md) — POLSKA | Ogólny opis obiektów core API (Drawing, Geometry, Tools, MillData, PostProcessor...) |
| `docs/alphacam-ecosystem/docs/chm-files/` | CHM wyciągnięte do .md: acamapi.md, Nesting.md, AEDITAPI.md, ConstraintsAPI.md, Feature.md, Primitives.md | Szybki przegląd ogólny bez rozpakowywania CHM |
| `docs/alphacam-ecosystem/alphacam-provided-examples/API/` | OFICJALNE przykłady Hexagon (Python, CSharp.Net, VB.Net, VBMacros, AcamAddInsAPI, DotNetPosts, Multidrill, AutoGeometryBridge, WordVBA, Delphi...) | Wzorce oficjalnego użycia API (automatyzacja, posty, addiny) |
| `docs/alphacam-ecosystem/alphacam-provided-examples/API/Python/PyCharm Examples/NestingFromCSV/Alphacam_Nesting.py` | PEŁNY typelib Nesting v3.0 w Pythonie — sygnatury INesting, INestList, INestData, ISheetDatabase itd. | **Szukanie sygnatur API nestingu** |
| `docs/alphacam-ecosystem/sdk-download/standalone/help/` | PEŁNE CHM: ACAMAPI.chm (API), ACAM4.chm (~80MB GUI docs), AcamReports.chm, Feature.chm, primitives.chm, R2V.chm, ModuleWorks_-_Documentation.chm | Opisy GUI i szczegóły (po rozpakowaniu 7z): `menus/...`, okna dialogowe |
| `docs/alphacam-ecosystem/sdk-download/standalone/lib/` | DLL-ki + Interop.AlphaCAM*.dll, .tlb | Typeliby COM, interop .NET |
| `docs/alphacam-ecosystem/sdk-download/AlphacamSDK/` | Wrapper .NET (IAlphacamCore/Geometry/Automation, LibraryManager.cs) — NIE zawiera nestingu | Automatyzacja .NET, nie do nestingu |
| `docs/gateway.md` | Dokumentacja gateway RPC (handlery, protokół) | Komunikacja z usługą AlphaCAM Gateway (Session 0) |
| `C:/temp/...` (katalog w repo) | Skrypty probe (probe_gui.py itd.) | Debugowanie na Windows |
| `/root/projects/_infra/dostepy-serwer.md` | Dostęp do laptopa z AlphaCAM: SSH 48797@100.71.109.69, usługa AlphaCAMGateway Session 0, port 8721, reg copy | **Dostęp do maszyny** (SSH/zdalne wykonanie) |

**Rozpakowanie CHM na Linuxie** (wymaga `p7zip-full`):

```bash
sudo apt install p7zip-full
7z x plik.chm -oWynikowyKatalog
```

**Wskazówki:**
- Sygnatury API core (Application, Drawing, Geometry, MillData...): `docs/api_docs/` (podzielone) lub wygenerowany moduł gen_py na Windowsie — typelib Router jest embedded w Acam.exe.
- Sygnatury API nestingu: `Alphacam_Nesting.py` (pełny typelib Nesting v3.0).
- Opisów GUI (opcje, okna dialogowe) szukaj w rozpakowanym `ACAM4.chm` (`menus/...`).
- Recepty E2E są w `tasks.md` — **czytaj `tasks.md` na początku sesji**.
- Wzorce oficjalnego użycia API: `alphacam-provided-examples/API/`.
