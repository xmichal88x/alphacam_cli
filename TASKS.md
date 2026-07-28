# TASKS.md — Alphacam CLI

## Pre-existing errors found during code review (not fixed in this session)

### tools/test_alphacam_com.py
1. **Multiple CoInitialize()** (lines 41, 172, 285) — wołany 3x w głównym wątku. pywin32 robi to automatycznie. Do poprawy przy refactoringu testów.
2. **COM collection iteration** (line 174) — `for geo in drw.Geometries` może nie działać dla niektórych COM kolekcji. Lepszy wzorzec: `coll(1)`.
3. **getattr z domyślnym stringiem** (lines 156-157) — `getattr(tool, 'ToolNumber', 'N/A')` zwraca string zamiast int. Powinno być `-1`.

### tools/chm-reader/search_chm.py
4. **Dead code** (lines 110-114) — nieużywane zmienne `pattern`, `content_lower`, `query_lower`.

### tools/diagnostic.py (w tej sesji, ale ulepszenia na później)
5. **Brak CoUninitialize** — proces kończy się zaraz, więc nie szkodzi, ale niepoprawne.
6. **win32com.__version__ nie istnieje** — `getattr` zawsze zwróci "unknown".

## Minor code review notes (do rozważenia, nie blokują)
- `_lazy_typer` nie jest faktycznie lazy — importuje na starcie. Zmienić nazwę lub zaimplementować prawdziwe lazy.
- `cli/common.py` mutable global state — rozważyć Context object dla testowalności.
- Testy `require_platform()` — na Windows failują. Dodać `mock.patch("sys.platform")`.

## Planowana architektura
Patrz: `docs/plans/` — pełny plan implementacji.
