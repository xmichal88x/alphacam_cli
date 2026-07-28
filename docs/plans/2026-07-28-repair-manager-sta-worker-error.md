# Repair: manager.py STA Worker Error Swallowing

> **For Claude:** Implement by subagent-driven-development.

**Goal:** Fix silent error swallowing in STA worker when `result_sent=True`.

**Root Cause:** `result_sent` guard (line 133) prevents error propagation when an exception occurs after the result has been sent to the main thread. The STA thread dies silently, main thread never learns about the failure.

**Recommended Approach (C):** Remove `result_sent` flag entirely, use unlimited queue, always push errors, post-mortem check in finally.

**Tech Stack:** Python, threading, queue, COM (pythoncom/win32com)

---

## Plan

### Files to modify:
- Modify: `src/alphacam_cli/com/manager.py:59,109,112,115,128-136,180-182`
- Tests: `tests/unit/test_com_manager.py` (add test for late error)

### Changes:

1. **Remove `result_sent`** (5 occurrences):
   - `result_sent = False` (line 59)
   - `result_sent = True` (lines 109, 112, 115)
   - `if not result_sent:` guard (lines 133-135)

2. **Unconditional error push** (replaces lines 133-135):
   ```python
   result_queue.put_nowait(("error", exc))
   ```

3. **Post-mortem check in main thread finally** (after line 182):
   ```python
   import logging
   logger = logging.getLogger("alphacam")
   with contextlib.suppress(queue.Empty):
       while True:
           late = result_queue.get_nowait()
           if late[0] == "error":
               logger.error("STA thread error after yield", exc_info=late[1])
   ```

4. **Add test** for late error scenario in `test_com_manager.py`.

### Verification:
- `ruff check src/`
- `mypy src/`
- `pytest tests/unit/test_com_manager.py -v`
