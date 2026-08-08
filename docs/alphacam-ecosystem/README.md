# AlphaCAM — Dokumentacja i zasoby SDK

Mapa katalogu `docs/alphacam-ecosystem/`: dokumentacja API AlphaCAM, oficjalne przykłady od Hexagon oraz pliki SDK (.NET wrapper + CHM + DLL-ki). Katalog jest lokalnym zapasem materiałów, z których czerpią narzędzia `alphacam_cli`.

## Struktura

| Ścieżka | Zawartość | Uwagi |
|---|---|---|
| `docs/chm-files/` | Wyciągnięte CHM → `.md`: `Nesting.md`, `acamapi.md`, `AEDITAPI.md`, `ConstraintsAPI.md`, `Feature.md`, `Primitives.md` | Najszybsze źródło sygnatur API bez rozpakowywania CHM |
| `docs/api-reference/` | README.md (placeholder) | Rezerwowane pod referencję API |
| `docs/guides/` | README.md (placeholder) | Rezerwowane pod poradniki |
| `alphacam-provided-examples/API/AcamAddInsAPI/` | Oficjalne addiny VBA: `SplitNest.bas`, `ReverseSideNesting.bas` | Przykłady integracji z API nestingu |
| `alphacam-provided-examples/API/VBMacros/` | `Nest.arb` — makro nesticowe | VBA/ARB, nie Python |
| `alphacam-provided-examples/API/Python/PyCharm Examples/NestingFromCSV/` | `Alphacam_Nesting.py` (pełny typelib Nesting v3.0 w Pythonie), `NestingFromCSV.py` (oficjalny przykład pełnego flow nestingu) | **Główne źródło sygnatur API nestingu** |
| `sdk-download/` | README.md + `docs/` (`HELP_FILES_STRUCTURE.md`, `HELP_SYSTEM.md` — po rosyjsku) | Opis SDK pobranego z portalu Hexagon |
| `sdk-download/AlphacamSDK/` | Wrapper .NET: `src/AlphacamSDK.cs`, `LibraryManager.cs`, `Interfaces/` (IAlphacamCore, IAlphacamGeometry, IAlphacamAutomation), `sdk_config.json`, `docs/` (AUDIT_REPORT, INSTALLATION_GUIDE, PORTABLE_*, ROADMAP, TASKS) | **Uwaga: NIE zawiera nestingu** — tylko Core/Geometry/Automation (potwierdzone) |
| `sdk-download/standalone/help/` | Pełne CHM: `ACAM4.chm` (80 MB), `ACAMAPI.chm`, `AEDITAPI.chm`, `ConstraintsAPI.chm`, `AcamReports.chm`, `Feature.chm`, `primitives.chm`, `R2V.chm`, `ACAM4LK.chm`, `AEdit3.chm`, `ModuleWorks_-_Documentation.chm` (149 MB) | Pełna dokumentacja w formie źródłowej |
| `sdk-download/standalone/lib/` | DLL-ki AlphaCAM + `Interop.AlphaCAM*.dll`, `NestUtilities.dll` | Biblioteki dla integracji .NET |

## Jak korzystać

- **Sygnatury API nestingu** → `alphacam-provided-examples/API/Python/PyCharm Examples/NestingFromCSV/Alphacam_Nesting.py` (pełny typelib v3.0). Szukaj np. `class INestList`, `class ISheetDatabase`, `"TotalTime"`.
- **Oficjalne przykłady** → `alphacam-provided-examples/API/...` (addiny VBA, makro `Nest.arb`, przykładowy flow w `NestingFromCSV.py`).
- **Opisy GUI (opcje dialogów nestingu: sheet database, nest parts)** → rozpakuj `sdk-download/standalone/help/ACAM4.chm` (`7z x`) i czytaj `menus/nesting/sheet_database.htm`, `menus/utils/nest_parts.htm`.
- **Ogólne API** → `docs/chm-files/*.md` (już wyciągnięte z CHM) albo `sdk-download/standalone/help/` (pełne CHM).
- **SDK .NET** → `sdk-download/AlphacamSDK/`. Tylko Core/Geometry/Automation — do pracy z nestingiem użyj typeliba Pythona albo Interop z `standalone/lib/`.

## Narzędzia

- **Rozpakowanie CHM na Linuxie**: `7z x plik.chm` (wymaga `p7zip-full`). Wystarczające, choć można też użyć `extract_chm.py`/`chm.py` — patrz skrypty w repo.
- **Czytanie plików .htm po rozpakowaniu**: grep/cat — `grep -ri "sheet database" menus/` albo `cat menus/nesting/sheet_database.htm` (surowy HTML, pomijaj znaczniki).

## Co NIE jest w tym katalogu

- Pełna dokumentacja VBA (tylko wyciągi API i przykłady).
- Aktywne pliki instalacyjne AlphaCAM — `standalone/` to pobrane SDK + CHM, nie instalator.
- Dokumentacja programistyczna w języku polskim — `sdk-download/docs/HELP_SYSTEM.md` i `HELP_FILES_STRUCTURE.md` są po rosyjsku.
