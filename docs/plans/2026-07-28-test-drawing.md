# Drawing Tests Implementation Plan

> **For Claude:** 1 task — add 14 tests to existing `tests/unit/test_drawing.py`

**Goal:** Achieve comprehensive test coverage for `alphacam_cli/core/drawing.py` (Drawing, CamPath, Geo2D, Text classes)

**Architecture:** Tests follow existing pattern: `mock_com` fixture → `alphacam_context()` → create wrapper → assert behavior on mock dispatch

**Tech Stack:** Python 3.11+, pytest, MagicMock

---

### Task 1: Add tests to tests/unit/test_drawing.py

**Files:**
- Modify: `tests/unit/test_drawing.py` — append 14 new tests after existing tests
- Reference: `src/alphacam_cli/core/drawing.py` — source under test

**Tests to add (14 total, plus import):**

1. `test_create_circle` — Drawing.create_circle() returns CamPath
2. `test_create_text` — Drawing.create_text() returns Text with correct properties
3. `test_create_2d_geometry` — Drawing.create_2d_geometry() returns Geo2D
4. `test_create_polygon` — Drawing.create_polygon() returns CamPath
5. `test_save_as` — Drawing.save_as(path) calls SaveAs on dispatch
6. `test_output_nc` — Drawing.output_nc(path) calls OutputNC on dispatch
7. `test_clear` — Drawing.clear() calls Clear with default params
8. `test_select_all_geometries` — Drawing.select_all_geometries() selects all
9. `test_cam_path_properties` — CamPath.selected getter/setter, tool_in_out
10. `test_cam_path_fillet` — CamPath.fillet() calls Fillet
11. `test_cam_path_set_start_point` — CamPath.set_start_point() calls SetStartPoint
12. `test_geo2d_add_line_close` — Geo2D: add_line → close_and_finish_line → CamPath
13. `test_text_properties` — Text.height, text_string, font_name getters/setters
14. `test_drawing_init_none` — Drawing(None) → ValueError

**Pattern to follow for each test:**
```python
def test_xxx(mock_com: MagicMock) -> None:
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.drawing import Drawing, ...

        with alphacam_context() as raw:
            drw = Drawing(raw.CreateTempDrawing())
            # set up mock, call method, assert
```

**Mocking notes:**
- `drw._drw` is the drawing mock from conftest (returned by `raw.CreateTempDrawing()`)
- For Geo2D/Text: create a `MagicMock()` for the raw COM object and set it as return_value on the appropriate method
- Use `pytest.raises` for the ValueError test (add `import pytest`)

### Verification

```bash
ruff check tests/unit/test_drawing.py
pytest tests/unit/test_drawing.py -v
```
