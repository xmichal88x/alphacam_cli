# AlphaCAM — Dokumentacja i zasoby SDK

Lokalny zapas materiałów AlphaCAM: dokumentacja API (wyciągi CHM → .md oraz pełne pliki pomocy), oficjalne przykłady od Hexagon oraz SDK (wrapper .NET, typeliby COM). Z tych materiałów czerpią narzędzia `alphacam_cli`.

## Struktura

| Ścieżka | Zawartość | Uwagi |
|---|---|---|
| `docs/chm-files/` | Wyciągnięte CHM → `.md`: `acamapi.md` (core API), `Nesting.md`, `AEDITAPI.md`, `ConstraintsAPI.md`, `Feature.md`, `Primitives.md` (+ źródła `.chm`) | Szybki przegląd sygnatur API bez rozpakowywania CHM |
| `docs/api-reference/` | README (placeholder) | Rezerwowane |
| `docs/guides/` | README (placeholder) | Rezerwowane |
| `alphacam-provided-examples/API/` | Oficjalne przykłady Hexagon: `Python/`, `CSharp.Net/`, `VB.Net/`, `VBMacros/`, `AcamAddInsAPI/`, `DotNetAddIns/`, `DotNetPosts/`, `Multidrill/`, `CutWithDisk/`, `AutoGeometryBridge/`, `CSVFileUtility/`, `Delphi/`, `Documents/`, `EditableAddInOps/`, `PolyLinesToLayer/`, `RibbonBarExample/`, `ScaleGeoZLevels/`, `VBATrainingGuide/`, `VisualCPP/`, `WordVBA/`, `ZlevelPreview/` | Wzorce oficjalnego użycia API (automatyzacja, posty, addiny); w `Python/PyCharm Examples/NestingFromCSV/Alphacam_Nesting.py` pełny typelib Nesting v3.0 |
| `sdk-download/AlphacamSDK/` | Wrapper .NET: `src/` (`AlphacamSDK.cs`, `HelpManager.cs`, `LibraryManager.cs`), `Interfaces/` (IAlphacamCore, IAlphacamGeometry, IAlphacamAutomation), `sdk_config.json`, `docs/` (AUDIT_REPORT, INSTALLATION_GUIDE, PORTABLE_*, ROADMAP, TASKS), `examples/BasicExample.cs` | Uwaga: NIE zawiera nestingu (potwierdzone) |
| `sdk-download/standalone/help/` | Pełne CHM: `ACAMAPI.chm` (API), `ACAM4.chm` (80 MB, GUI), `AcamReports.chm` (raporty), `ModuleWorks_-_Documentation.chm` (149 MB, frezowanie), `AEDITAPI.chm`, `ConstraintsAPI.chm`, `Feature.chm`, `primitives.chm`, `R2V.chm`, `ACAM4LK.chm`, `AEdit3.chm` | Pełna dokumentacja w formie źródłowej (po rozpakowaniu: menu, okna dialogowe) |
| `sdk-download/standalone/lib/` | DLL-ki AlphaCAM + `Interop.AlphaCAM*.dll`, `NestUtilities.dll`, pliki `.tlb` | Typeliby COM i interop .NET |

## Jak korzystać

- **Sygnatury API core** (Application, Drawing, Geometry, MillData...) → `docs/chm-files/acamapi.md` lub `docs/api_docs/` (osobny katalog, dokumentacja po polsku).
- **Sygnatury API nestingu** (INesting, INestList, ISheetDatabase...) → `alphacam-provided-examples/API/Python/PyCharm Examples/NestingFromCSV/Alphacam_Nesting.py` (pełny typelib Nesting v3.0).
- **Opisy GUI** (okna dialogowe, menu) → rozpakuj `sdk-download/standalone/help/ACAM4.chm` (`7z x`) i czytaj pliki `.htm` (np. `menus/nesting/...`).
- **Przykłady użycia API** → `alphacam-provided-examples/API/` — wybierz język/katalog (Python, CSharp.Net, VB.Net, VBMacros, addiny...).
- **SDK .NET** → `sdk-download/AlphacamSDK/` (Core/Geometry/Automation; nie zawiera nestingu — do nestingu użyj typeliba Pythona lub Interop z `standalone/lib/`).

## Narzędzia

- **Rozpakowanie CHM na Linuxie**: `sudo apt install p7zip-full`, następnie `7z x plik.chm -oKatalogWynikowy`.
- **Czytanie plików .htm po rozpakowaniu**: `grep -ri "fraza" katalog/` lub `cat plik.htm` (surowy HTML — pomijaj znaczniki).

## Uwagi

- Katalog zajmuje ~500 MB — nie wgrywaj go do git (wykluczony w `.gitignore`).
- `sdk-download/` zawiera też `docs/HELP_FILES_STRUCTURE.md` i `docs/HELP_SYSTEM.md` — opis SDK pobranego z portalu Hexagon (po rosyjsku).
