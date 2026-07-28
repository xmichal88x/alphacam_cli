# Dopaść testy `core/application.py` — Implementation Plan

**Goal:** Add 10-12 unit tests for `Application` class methods.

**Architecture:** Each test follows the existing `mock_com` fixture pattern from `tests/conftest.py`. All tests go into the existing `tests/unit/test_application.py`.

**Tech Stack:** Python 3.11+, pytest, unittest.mock

---

### Task 1: Dodaj testy do `tests/unit/test_application.py`

**Files:**
- Modify: `tests/unit/test_application.py` (append after line 49)

**Testy do dodania (12 testów):**

1. `test_new_drawing` — sprawdza że `ac.new_drawing()` woła `raw.New()`
2. `test_quit` — sprawdza że `ac.quit()` woła `raw.Quit()`
3. `test_select_tool` — `ac.select_tool("flat_10mm.amt")` zwraca Tool z `name == "Flat - 10mm"`
4. `test_get_current_tool` — `ac.get_current_tool()` zwraca Tool z `name == "Flat - 10mm"`
5. `test_find_tool_files` — zwraca listę (pustą, bo mock paths)
6. `test_find_drawing_files` — zwraca listę (pustą)
7. `test_get_nesting` — zwraca Nesting
8. `test_select_post` — woła `raw.SelectPost("fanuc")`
9. `test_open_drawing` — zwraca Drawing, woła `raw.OpenDrawing(path)`
10. `test_open_drawing_none` — gdy OpenDrawing zwraca None → metoda zwraca None
11. `test_create_temp_drawing` — zwraca Drawing
12. `test_create_mill_data` — zwraca MillData

**Wzór każdego testu:**
```python
def test_xxx(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.application import Application

        with alphacam_context() as raw:
            ac = Application(raw)
            # ... assertions
```

**Verification:**
```bash
ruff check tests/unit/test_application.py
pytest tests/unit/test_application.py -v
```
