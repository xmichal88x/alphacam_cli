from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"


def _ruff_lint_config() -> dict[str, Any]:
    with PYPROJECT.open("rb") as handle:
        config = tomllib.load(handle)
    return config["tool"]["ruff"]["lint"]  # type: ignore[no-any-return]


def test_src_has_no_file_level_ruff_noqa() -> None:
    offenders = [
        str(path.relative_to(PROJECT_ROOT))
        for path in SRC_DIR.rglob("*.py")
        if "# ruff: noqa:" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_server_per_file_ignore_is_exactly_try003() -> None:
    per_file_ignores = _ruff_lint_config()["per-file-ignores"]
    assert per_file_ignores["src/alphacam_cli/gateway/server.py"] == ["TRY003"]
    server_entries = [path for path in per_file_ignores if Path(path).name == "server.py"]
    assert server_entries == ["src/alphacam_cli/gateway/server.py"]


def test_try003_is_not_globally_ignored() -> None:
    ignore = _ruff_lint_config().get("ignore", [])
    assert "TRY003" not in ignore
