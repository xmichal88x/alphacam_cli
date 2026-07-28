# PE-02: NcEventHandler nc_path Bug Fix

**Goal:** Fix `TypeError` when `DispatchWithEvents` instantiates `NcEventHandler` without `nc_path` argument.

**Architecture:** Make `nc_path` optional with default `""` in `NcEventHandler.__init__`, then set it after construction in `Drawing.output_nc_with_events`.

**Tech Stack:** Python, pywin32

---

### Task 1: Fix nc_path in events.py and drawing.py

**Files:**
- Modify: `src/alphacam_cli/core/events.py:10`
- Modify: `src/alphacam_cli/core/drawing.py:68-73`

**Step 1: Make nc_path optional in NcEventHandler**

In `events.py:10`, change:
```python
def __init__(self, nc_path: str) -> None:
```
to:
```python
def __init__(self, nc_path: str = "") -> None:
```

**Step 2: Set nc_path on handler after DispatchWithEvents**

In `drawing.py:73`, change:
```python
_ = DispatchWithEvents(app_dispatch, NcEventHandler)
```
to:
```python
handler = DispatchWithEvents(app_dispatch, NcEventHandler)
handler.nc_path = path
```

**Step 3: Run lint and tests**

```bash
ruff check src/alphacam_cli/core/events.py src/alphacam_cli/core/drawing.py
pytest tests/unit/test_drawing.py -v
```
