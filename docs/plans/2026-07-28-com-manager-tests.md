# COM Manager Tests — keep_alive + marshal failure

> **For Claude:** Subagent-driven development in current session.

**Goal:** Add two tests to `tests/unit/test_com_manager.py` covering keep_alive and marshal failure cleanup.

**Architecture:** The `alphacam_context` context manager in `src/alphacam_cli/com/manager.py` uses an STA thread with COM marshaling. Two new tests verify (1) `keep_alive=True` prevents `Quit()` call, (2) `CoGetInterfaceAndReleaseStream` failure triggers `CoReleaseMarshalData` cleanup.

**Tech Stack:** Python, pytest, unittest.mock

---

### Task 3: Test for keep_alive

**Files:**
- Modify: `tests/unit/test_com_manager.py` (after line 105)

**Step 1: Add test**

Add after `test_alphacam_context_owned_true_calls_quit` (line 105):

```python
def test_alphacam_context_keep_alive_prevents_quit(mock_com: MagicMock) -> None:
    """When keep_alive=True and owned=True, Quit should NOT be called."""
    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        with alphacam_context(keep_alive=True):
            pass

        mock_com.return_value.Quit.assert_not_called()
```

**Step 2: Verify**

Run: `.venv/bin/python -m pytest tests/unit/test_com_manager.py::test_alphacam_context_keep_alive_prevents_quit -x -v`

Expected: PASS

### Verification

1. **Format & Lint** — `ruff check tests/unit/test_com_manager.py`
2. **Run all tests** — `.venv/bin/python -m pytest tests/unit/test_com_manager.py -x -v`

---

### Task 4: Test for marshal failure

**Files:**
- Modify: `tests/unit/test_com_manager.py` (after Task 3 test)

**Step 1: Add test**

Add after `test_alphacam_context_keep_alive_prevents_quit`:

```python
def test_alphacam_context_marshal_failure_cleanup(mock_com: MagicMock) -> None:
    """When CoGetInterfaceAndReleaseStream fails, marshal data should be released and thread stopped."""
    from unittest.mock import patch

    with mock_com:
        from alphacam_cli.com.manager import alphacam_context

        fake_stream = MagicMock()
        with (
            patch("sys.platform", "win32"),
            patch("pythoncom.CoMarshalInterThreadInterfaceInStream", return_value=fake_stream),
            patch("pythoncom.CoGetInterfaceAndReleaseStream", side_effect=Exception("Unmarshal failed")),
            patch("pythoncom.CoReleaseMarshalData") as mock_release,
        ):
            with pytest.raises(Exception, match="Unmarshal failed"):
                with alphacam_context():
                    pass

        mock_release.assert_called_once_with(fake_stream)
```

**Step 2: Verify**

Run: `.venv/bin/python -m pytest tests/unit/test_com_manager.py::test_alphacam_context_marshal_failure_cleanup -x -v`

Expected: PASS

### Verification

1. **Format & Lint** — `ruff check tests/unit/test_com_manager.py`
2. **Run all tests** — `.venv/bin/python -m pytest tests/unit/test_com_manager.py -x -v`
