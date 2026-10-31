from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

from rich.console import Console

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "alphacam_cli"

_FORBIDDEN = re.compile(r"console\s*\.\s*print\s*\(\s*json\s*\.\s*dumps\s*\(")


def test_no_console_print_json_dumps() -> None:
    violations: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        for match in _FORBIDDEN.finditer(source):
            line_no = source.count("\n", 0, match.start()) + 1
            rel = path.relative_to(SRC_ROOT.parent)
            violations.append(f"{rel}:{line_no}: {match.group(0)}")

    assert not violations, (
        "console.print(json.dumps(...)) can wrap lines and corrupt JSON output; "
        "use typer.echo(json.dumps(...)) instead:\n" + "\n".join(violations)
    )


def _payload() -> dict[str, Any]:
    long_value = "x" * 350
    return {
        "success": True,
        "note": long_value,
        "records": [{"index": i, "description": f"record-{i}-{long_value}"} for i in range(5)],
    }


def test_rich_print_json_survives_long_values_and_narrow_buffers() -> None:
    payload = _payload()
    for width in (80, 120):
        buffer = io.StringIO()
        console = Console(file=buffer, width=width, force_terminal=False, color_system=None)
        console.print_json(data=payload)
        output = buffer.getvalue()

        assert json.loads(output) == payload, f"invalid JSON output at width={width}"
