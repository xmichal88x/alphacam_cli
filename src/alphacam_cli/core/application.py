from __future__ import annotations

import glob
import os
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    import win32com.client as win32  # type: ignore[import-untyped]

    from alphacam_cli.core.drawing import Drawing
    from alphacam_cli.core.machining import MillData
    from alphacam_cli.core.nesting import Nesting
    from alphacam_cli.core.tool import Tool

from alphacam_cli.com.constants import MODULE_MILL, MODULE_ROUTER
from alphacam_cli.core.drawing import Drawing
from alphacam_cli.core.machining import MillData
from alphacam_cli.core.nesting import Nesting
from alphacam_cli.core.tool import Tool


class Application:
    """Typed wrapper around AlphaCAM Application COM object."""

    def __init__(self, dispatch: win32.CDispatch) -> None:
        self._app = dispatch

    @property
    def _raw_app(self) -> Any:
        """Return the raw COM dispatch object (for event sink registration)."""
        return self._app

    @property
    def visible(self) -> bool:
        return bool(self._app.Visible)  # type: ignore[attr-defined]

    @visible.setter
    def visible(self, value: bool) -> None:
        self._app.Visible = value  # type: ignore[attr-defined]

    @property
    def version(self) -> str:
        return str(self._app.AlphacamVersion)  # type: ignore[attr-defined]

    @property
    def full_name(self) -> str:
        return str(self._app.FullName)  # type: ignore[attr-defined]

    @property
    def name(self) -> str:
        return str(self._app.Name)  # type: ignore[attr-defined]

    @property
    def program_level(self) -> int:
        return int(self._app.ProgramLevel)  # type: ignore[attr-defined]

    @property
    def program_letter(self) -> int:
        return int(self._app.ProgramLetter)  # type: ignore[attr-defined]

    @property
    def licomdat_path(self) -> str:
        return str(self._app.LicomdatPath)  # type: ignore[attr-defined]

    @property
    def licomdir_path(self) -> str:
        return str(self._app.LicomdirPath)  # type: ignore[attr-defined]

    @property
    def post_file_name(self) -> str:
        return str(self._app.PostFileName)  # type: ignore[attr-defined]

    @property
    def api_version(self) -> int:
        return int(self._app.ApiVersion)  # type: ignore[attr-defined]

    @property
    def module_type(self) -> str:
        letter = self.program_letter
        if 32 < letter < 127:
            return chr(letter)
        return "?"

    @property
    def is_mill(self) -> bool:
        return self.program_letter == MODULE_MILL

    @property
    def is_router(self) -> bool:
        return self.program_letter == MODULE_ROUTER

    def get_active_drawing(self) -> Drawing | None:
        raw = self._app.ActiveDrawing  # type: ignore[attr-defined]
        if raw is None:
            return None
        return Drawing(raw)

    def create_temp_drawing(self) -> Drawing | None:
        self._app.New()  # type: ignore[attr-defined]
        raw = self._app.ActiveDrawing  # type: ignore[attr-defined]
        if raw is None:
            return None
        return Drawing(raw)

    def open_drawing(self, path: str) -> Drawing | None:
        raw = self._app.OpenDrawing(path)  # type: ignore[attr-defined]
        if raw is None:
            return None
        return Drawing(raw)

    def select_tool(self, path: str) -> Tool | None:
        raw = self._app.SelectTool(path)  # type: ignore[attr-defined]
        if raw is None:
            return None
        return Tool(raw)

    def get_current_tool(self) -> Tool | None:
        raw = self._app.GetCurrentTool()  # type: ignore[attr-defined]
        if raw is None:
            return None
        return Tool(raw)

    def create_mill_data(self) -> MillData:
        raw = self._app.CreateMillData()  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to create mill data")  # noqa: TRY003
        return MillData(raw)

    def new_drawing(
        self,
        width: float = 100,
        height: float = 50,
        fillet: float = 0,
        text: str = "",
    ) -> Drawing | None:
        try:
            self._app.New()  # type: ignore[attr-defined]
        except Exception as e:
            raise RuntimeError(f"Failed to create new drawing: {e}") from e  # noqa: TRY003
        drw = self.get_active_drawing()
        if drw is None:
            return None
        rect = drw.create_rectangle(0, 0, width, height)
        if fillet > 0:
            rect.fillet(fillet)
        if text:
            drw.create_text(text, 5, height / 2, 4)
        drw.zoom_all()
        return drw

    def quit(self) -> None:
        try:
            self._app.Quit()  # type: ignore[attr-defined]
        except Exception as e:
            raise RuntimeError(f"Failed to quit application: {e}") from e  # noqa: TRY003

    _TOOL_DIRS: ClassVar[dict[str, str]] = {
        "M": "mtools.alp",
        "R": "rtools.alp",
        "L": "ltools.alp",
        "W": "wtools.alp",
        "F": "ftools.alp",
    }

    def find_tool_files(self, pattern: str = "*.art") -> list[str]:
        sub_dir = type(self)._TOOL_DIRS.get(self.module_type, "mtools.alp")
        base = os.path.join(self.licomdat_path, sub_dir)
        files = glob.glob(os.path.join(base, pattern))
        if not files:
            files = glob.glob(os.path.join(self.licomdat_path, "**", pattern), recursive=True)
        return sorted(set(files))

    def get_nesting(self) -> Nesting:
        raw = self._app.Nesting  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to get nesting")  # noqa: TRY003
        return Nesting(raw)

    def select_post(self, name: str) -> None:
        try:
            self._app.SelectPost(name)  # type: ignore[attr-defined]
        except Exception as e:
            raise RuntimeError(f"Failed to select post '{name}': {e}") from e  # noqa: TRY003

    def apply_mill_style(self, style_path: str) -> None:
        try:
            style = self._app.CreateMillStyle()  # type: ignore[attr-defined]
            style.FileName = style_path  # type: ignore[attr-defined]
            style.Apply()  # type: ignore[attr-defined]
        except Exception as e:
            raise RuntimeError(f"Failed to apply mill style '{style_path}': {e}") from e  # noqa: TRY003

    def find_drawing_files(self, pattern: str = "*.amd") -> list[str]:
        base = os.path.join(self.licomdir_path, "parts")
        return sorted(glob.glob(os.path.join(base, pattern)))
