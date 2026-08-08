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

    _POST_DIRS: ClassVar[dict[str, str]] = {
        "M": "MPosts.Alp",
        "R": "RPosts.Alp",
        "L": "LPosts.Alp",
        "W": "WPosts.Alp",
        "F": "FPosts.Alp",
    }

    def _module_dir(self, sub_dir: str) -> str:
        candidates = [
            os.path.join(self.licomdat_path, sub_dir),
            os.path.join(self.licomdat_path, "LICOMDAT", sub_dir),
        ]
        for c in candidates:
            if os.path.isdir(c):
                return c
        return candidates[0]

    def find_tool_files(self, pattern: str = "*.art") -> list[str]:
        sub_dir = type(self)._TOOL_DIRS.get(self.module_type, "mtools.alp")
        base = self._module_dir(sub_dir)
        files = glob.glob(os.path.join(base, pattern))
        if not files:
            files = glob.glob(os.path.join(base, "**", pattern), recursive=True)
        return sorted(set(files))

    def find_post_files(self, pattern: str = "*.arp") -> list[str]:
        sub_dir = type(self)._POST_DIRS.get(self.module_type, "RPosts.Alp")
        base = self._module_dir(sub_dir)
        files = glob.glob(os.path.join(base, pattern))
        if not files:
            files = glob.glob(os.path.join(base, "**", pattern), recursive=True)
        return sorted(set(files))

    def get_nesting(self) -> Nesting:
        raw = self._app.Nesting  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to get nesting")  # noqa: TRY003
        return Nesting(raw)

    def select_post(self, name: str) -> None:
        if "/" not in name and "\\" not in name and not os.path.exists(name):
            files = self.find_post_files()
            basename_lower = name.lower()
            exact = [f for f in files if os.path.basename(f).lower() == basename_lower]
            prefix = [
                f
                for f in files
                if f not in exact and os.path.basename(f).lower().startswith(basename_lower)
            ]
            substring = [
                f
                for f in files
                if f not in exact
                and f not in prefix
                and basename_lower in os.path.basename(f).lower()
            ]
            matched = exact or prefix or substring
            if not matched:
                raise RuntimeError(f"Failed to select post '{name}': no matching post file found")  # noqa: TRY003
            name = matched[0]
        try:
            self._app.SelectPost(name)  # type: ignore[attr-defined]
        except Exception as e:
            raise RuntimeError(f"Failed to select post '{name}': {e}") from e  # noqa: TRY003

    def apply_mill_style(self, style_path: str) -> None:
        try:
            styles = list(self._app.MillMachiningStyles)  # type: ignore[attr-defined]
        except Exception as e:
            raise RuntimeError(f"Failed to apply mill style '{style_path}': {e}") from e  # noqa: TRY003

        target = style_path.replace("\\", "/").lower()
        target_name = os.path.basename(target).lower()
        normalized = [
            (s, str(s.FileName).replace("\\", "/").lower())  # type: ignore[attr-defined]
            for s in styles
        ]
        style = next((s for s, fname in normalized if fname == target), None)
        if style is None:
            style = next(
                (s for s, fname in normalized if os.path.basename(fname) == target_name),
                None,
            )
        if style is None:
            available = ", ".join(fname for _, fname in normalized[:5]) or "none"
            raise RuntimeError(  # noqa: TRY003
                f"Mill style not found: {style_path}. Available styles: {available}"
            )
        try:
            style.Apply()  # type: ignore[attr-defined]
        except Exception as e:
            raise RuntimeError(f"Failed to apply mill style '{style_path}': {e}") from e  # noqa: TRY003

    def find_drawing_files(self, pattern: str = "*.amd") -> list[str]:
        base = os.path.join(self.licomdir_path, "parts")
        return sorted(glob.glob(os.path.join(base, pattern)))

    def glob_files(self, directory: str, pattern: str = "*.amd") -> list[str]:
        return sorted(glob.glob(os.path.join(directory, pattern)))
