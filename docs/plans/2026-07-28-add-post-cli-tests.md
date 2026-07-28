# Add CLI Tests for `cli/post.py` Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 4 CLI tests for `cli/post.py` to increase coverage from ~39% to ~90%.

**Architecture:** The `cli/post.py` module has a `list()` command that uses `alphacam_context`, `os.path.isdir`, and `glob.glob`. The `_mock_com()` in `test_cli.py` mocks `require_platform` and `alphacam_context` for other modules but NOT for `post`. We need to add `post` patches, then create a test file with 4 test cases covering all code paths.

**Tech Stack:** Python 3.11+, pytest, typer.testing.CliRunner, unittest.mock, rich.table

---

### Task 1: Add `post` entries to `_MOCK_PATCHES` in `tests/unit/test_cli.py`

**Files:**
- Modify: `tests/unit/test_cli.py:62-76`

**Details:** Add two entries — `("alphacam_cli.cli.post", "require_platform")` and `("alphacam_cli.cli.post", "alphacam_context")` — to the `_MOCK_PATCHES` list so that `_mock_com()` also patches the `post` module.

### Task 2: Create `tests/unit/test_cli_post.py` with 4 test cases

**Files:**
- Create: `tests/unit/test_cli_post.py`

**Test cases:**
1. `test_post_list_no_posts_dir` — `licomdir_path/posts` doesn't exist, expect exit code 1 with "Posts directory not found"
2. `test_post_list_empty` — directory exists but empty, expect exit code 0 with "No post-processors found"
3. `test_post_list_with_posts` — mock glob to return .vba/.dll files, verify table output
4. `test_post_list_licomdat_fallback` — no posts in licomdir but found in licomdat, verify output

### Verification

After implementation:
1. Run: `cd /root/projects/alphacam_cli && .venv/bin/python -m pytest tests/unit/test_cli_post.py -x -v 2>&1 | tail -20`
2. Run: `cd /root/projects/alphacam_cli && .venv/bin/python -m pytest tests/ -x --tb=short 2>&1 | tail -10`
3. Run coverage: `cd /root/projects/alphacam_cli && .venv/bin/python -m pytest --cov=alphacam_cli.cli.post tests/unit/test_cli_post.py --cov-report=term-missing 2>&1 | tail -20`
