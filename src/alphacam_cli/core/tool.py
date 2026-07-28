from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import win32com.client as win32  # type: ignore[import-untyped]


class Tool:
    """Typed wrapper around AlphaCAM MillTool COM object."""

    def __init__(self, dispatch: win32.CDispatch) -> None:
        if dispatch is None:
            raise ValueError("Tool dispatch object is None")  # noqa: TRY003
        self._tool = dispatch

    @property
    def diameter(self) -> float:
        return float(self._tool.Diameter)  # type: ignore[attr-defined]

    @property
    def name(self) -> str:
        return str(self._tool.Name)  # type: ignore[attr-defined]

    @property
    def number(self) -> int:
        return int(self._tool.Number)  # type: ignore[attr-defined]

    @property
    def tool_length(self) -> float:
        return float(self._tool.Length)  # type: ignore[attr-defined]

    @property
    def tool_type(self) -> int:
        return int(self._tool.Type)  # type: ignore[attr-defined]

    @property
    def feed_per_tooth(self) -> float:
        return float(self._tool.FeedPerTooth)  # type: ignore[attr-defined]

    @property
    def file_name(self) -> str:
        return str(self._tool.FileName)  # type: ignore[attr-defined]

    @property
    def units(self) -> int:
        return int(self._tool.Units)  # type: ignore[attr-defined]

    @property
    def corner_radius(self) -> float:
        return float(self._tool.CornerRadius)  # type: ignore[attr-defined]

    @property
    def note(self) -> str:
        return str(self._tool.Note)  # type: ignore[attr-defined]

    @property
    def number_of_teeth(self) -> int:
        return int(self._tool.NumberOfTeeth)  # type: ignore[attr-defined]
