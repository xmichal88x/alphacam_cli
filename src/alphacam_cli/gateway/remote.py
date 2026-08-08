from __future__ import annotations

import os
from typing import Any

from alphacam_cli.gateway.client import RemoteSession


class _ToolProxy:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @property
    def name(self) -> str:
        return str(self._data["name"])

    @property
    def diameter(self) -> float:
        return float(self._data["diameter"])

    @property
    def number(self) -> int:
        return int(self._data["number"])

    @property
    def tool_length(self) -> float:
        return float(self._data["length"])

    @property
    def tool_type(self) -> int:
        return int(self._data["tool_type"])


def _ensure_dict(obj: dict[str, Any] | None) -> dict[str, Any]:
    return {} if obj is None else obj


def _basename(path: str) -> str:
    normalized = path.replace("\\", "/")
    return normalized.rsplit("/", 1)[-1]


class _DrawingProxy:
    def __init__(self, session: RemoteSession, info: dict[str, Any]) -> None:
        self._session = session
        self._info = info

    @property
    def geometries_count(self) -> int:
        return int(self._info["geometries_count"])

    @property
    def tool_paths_count(self) -> int:
        return int(self._info.get("tool_paths_count", 0))

    def save_as(self, path: str) -> None:
        self._session.save_active_drawing(path)

    def output_nc(self, path: str) -> dict[str, Any]:
        return self._session.output_nc(path)

    def zoom_all(self) -> None:
        self._session.zoom_all()

    def select_all_geometries(self) -> None:
        pass

    def geometries(self) -> list[Any]:
        return []

    def create_rectangle(self, x1: float, y1: float, x2: float, y2: float) -> Any:
        return None

    def create_text(self, text: str, x: float, y: float, height: float) -> Any:
        return None


class RemoteApplication:
    def __init__(self, session: RemoteSession) -> None:
        self._session = session
        self._info: dict[str, Any] | None = None

    def _ensure_info(self) -> dict[str, Any]:
        if self._info is None:
            self._info = self._session.get_info()
        return self._info

    @property
    def version(self) -> str:
        return str(self._ensure_info()["version"])

    @property
    def name(self) -> str:
        return str(self._ensure_info()["name"])

    @property
    def full_name(self) -> str:
        return str(self._ensure_info()["full_name"])

    @property
    def module_type(self) -> str:
        return str(self._ensure_info()["module_type"])

    @property
    def program_level(self) -> int:
        return int(self._ensure_info()["program_level"])

    @property
    def api_version(self) -> int:
        return int(self._ensure_info()["api_version"])

    @property
    def licomdat_path(self) -> str:
        return str(self._ensure_info()["licomdat_path"])

    @property
    def licomdir_path(self) -> str:
        return str(self._ensure_info()["licomdir_path"])

    @property
    def post_file_name(self) -> str:
        return str(self._ensure_info()["post_file_name"])

    @property
    def program_letter(self) -> int:
        return ord(self.module_type) if len(self.module_type) == 1 else 0

    @property
    def is_mill(self) -> bool:
        return self.program_letter == 77

    @property
    def is_router(self) -> bool:
        return self.program_letter == 82

    def get_active_drawing(self) -> _DrawingProxy | None:
        info = self._session.get_active_drawing()
        if info is None:
            return None
        return _DrawingProxy(self._session, info)

    def create_temp_drawing(self) -> _DrawingProxy | None:
        info = self._session.create_temp_drawing()
        if info is None:
            return None
        return _DrawingProxy(self._session, info)

    def open_drawing(self, path: str) -> _DrawingProxy | None:
        info = self._session.open_drawing(path)
        if info is None:
            return None
        return _DrawingProxy(self._session, info)

    def select_tool(self, path: str) -> _ToolProxy | None:
        data = self._session.select_tool(path)
        if data is None:
            return None
        return _ToolProxy(data)

    def get_current_tool(self) -> _ToolProxy | None:
        data = self._session.get_current_tool()
        if data is None:
            return None
        return _ToolProxy(data)

    def find_tool_files(self, pattern: str = "*.art") -> list[str]:
        return self._session.list_tools(pattern)  # type: ignore[no-any-return]

    def find_drawing_files(self, pattern: str = "*.amd") -> list[str]:
        return self._session.find_drawing_files(pattern)  # type: ignore[no-any-return]

    def glob_files(self, directory: str, pattern: str = "*.amd") -> list[str]:
        return self._session.glob_files(directory, pattern)  # type: ignore[no-any-return]

    def create_mill_data(self) -> Any:
        return _RemoteMillData(self._session)

    def select_post(self, name: str) -> None:
        self._session.select_post(name)

    def apply_mill_style(self, style_path: str) -> None:
        self._session.apply_style(style_path)

    def get_nesting(self) -> Any:
        return _RemoteNesting(self._session)

    def new_drawing(
        self,
        width: float = 100,
        height: float = 50,
        fillet: float = 0,
        text: str = "",
    ) -> _DrawingProxy | None:
        info = self._session.new_drawing(width, height, fillet, text)
        if info is None:
            return None
        return _DrawingProxy(self._session, info)


class _RemoteMillData:
    def __init__(self, session: RemoteSession) -> None:
        self._session = session
        self._params: dict[str, Any] = {}

    def _set(self, key: str, value: Any) -> None:
        self._params[key] = value

    @property
    def safe_rapid_level(self) -> float:
        return float(self._params.get("rapid", 10))

    @safe_rapid_level.setter
    def safe_rapid_level(self, value: float) -> None:
        self._set("rapid", value)

    @property
    def rapid_down_to(self) -> float:
        return float(self._params.get("rapid_down_to", 2))

    @rapid_down_to.setter
    def rapid_down_to(self, value: float) -> None:
        pass

    @property
    def material_top(self) -> float:
        return float(self._params.get("material_top", 0))

    @material_top.setter
    def material_top(self, value: float) -> None:
        self._set("material_top", value)

    @property
    def final_depth(self) -> float:
        return float(self._params.get("depth", -10))

    @final_depth.setter
    def final_depth(self, value: float) -> None:
        self._set("depth", value)

    @property
    def spindle_speed(self) -> int:
        return int(self._params.get("spindle", 12000))

    @spindle_speed.setter
    def spindle_speed(self, value: int) -> None:
        self._set("spindle", value)

    @property
    def down_feed(self) -> float:
        return float(self._params.get("down_feed", 2000))

    @down_feed.setter
    def down_feed(self, value: float) -> None:
        self._set("down_feed", value)

    @property
    def cut_feed(self) -> float:
        return float(self._params.get("feed", 3000))

    @cut_feed.setter
    def cut_feed(self, value: float) -> None:
        self._set("feed", value)

    @property
    def max_depth_per_cut(self) -> float:
        return float(self._params.get("max_depth_per_cut", 2.5))

    @max_depth_per_cut.setter
    def max_depth_per_cut(self, value: float) -> None:
        self._set("max_depth_per_cut", value)

    @property
    def width_of_cut(self) -> float:
        return float(self._params.get("width_of_cut", 5))

    @width_of_cut.setter
    def width_of_cut(self, value: float) -> None:
        self._set("width_of_cut", value)

    @property
    def stock(self) -> float:
        return float(self._params.get("stock", 0.5))

    @stock.setter
    def stock(self, value: float) -> None:
        self._set("stock", value)

    @property
    def process_type(self) -> int:
        return 2

    @process_type.setter
    def process_type(self, value: int) -> None:
        pass

    @property
    def pocket_type(self) -> int:
        return 0

    @pocket_type.setter
    def pocket_type(self, value: int) -> None:
        self._set("pocket_type", value)

    @property
    def xy_corners(self) -> int:
        return int(self._params.get("xy_corners", 0))

    @xy_corners.setter
    def xy_corners(self, value: int) -> None:
        self._set("xy_corners", value)

    @property
    def start_x(self) -> float:
        return float(self._params.get("start_x", 0.0))

    @start_x.setter
    def start_x(self, value: float) -> None:
        self._set("start_x", value)

    @property
    def start_y(self) -> float:
        return float(self._params.get("start_y", 0.0))

    @start_y.setter
    def start_y(self, value: float) -> None:
        self._set("start_y", value)

    @property
    def drill_type(self) -> int:
        return 0

    @drill_type.setter
    def drill_type(self, value: int) -> None:
        pass

    @property
    def bottom_of_hole(self) -> float:
        return float(self._params.get("depth", -15))

    @bottom_of_hole.setter
    def bottom_of_hole(self, value: float) -> None:
        self._set("depth", value)

    def rough_finish(self) -> None:
        self._session.mill_rough(**self._params)

    def pocket(self) -> None:
        self._session.mill_pocket(**self._params)

    def drill_tap(self) -> None:
        d_type = self._params.get("drill_type", "drill")
        self._session.mill_drill(
            depth=self._params.get("depth", -15),
            drill_type=d_type,
            spindle=self._params.get("spindle", 12000),
        )


class _RemoteNesting:
    def __init__(self, session: RemoteSession) -> None:
        self._session = session

    @property
    def suppress_dialogs(self) -> bool:
        return True

    @suppress_dialogs.setter
    def suppress_dialogs(self, value: bool) -> None:
        pass

    def new_nest_list(self, path: str) -> Any:
        return _RemoteNestList(self._session, path)

    def new_sheet_list(self) -> Any:
        return _RemoteSheetList(self._session)

    def nest(self, nl: Any, sl: Any, sheet_name: str = "") -> Any:
        parts = nl.get_parts() if hasattr(nl, "get_parts") else []
        result = self._session.run_nest(
            parts=parts,
            output_dir=nl.output_dir if hasattr(nl, "output_dir") else "",
            sheet_width=sl.width if hasattr(sl, "width") else 2440,
            sheet_height=sl.height if hasattr(sl, "height") else 1220,
            sheet_name=sheet_name,
        )
        return _RemoteNestResult(result)


class _RemoteNestList:
    def __init__(self, session: RemoteSession, path: str) -> None:
        self._session = session
        self._path = path
        self._parts: list[dict[str, Any]] = []
        self.output_dir = os.path.dirname(path)

    def add_file(self, filename: str) -> Any:
        part = {"name": filename, "count": 1}
        self._parts.append(part)
        return _RemoteNestPart(part)

    def save(self, filename: str | None = None) -> None:
        pass

    def get_parts(self) -> list[dict[str, Any]]:
        return self._parts


class _RemoteNestPart:
    def __init__(self, part: dict[str, Any]) -> None:
        self._part = part

    @property
    def required(self) -> int:
        return int(self._part.get("count", 1))

    @required.setter
    def required(self, value: int) -> None:
        self._part["count"] = value


class _RemoteSheetList:
    def __init__(self, session: RemoteSession) -> None:
        self._session = session
        self.width = 2440.0
        self.height = 1220.0

    def add(self, geometry: Any) -> Any:
        return _RemoteNestSheet(self)


class _RemoteNestSheet:
    def __init__(self, sl: _RemoteSheetList) -> None:
        self._sl = sl
        self._thickness = 18.0
        self._required = 1

    @property
    def thickness(self) -> float:
        return self._thickness

    @thickness.setter
    def thickness(self, value: float) -> None:
        self._thickness = value

    @property
    def required(self) -> int:
        return self._required

    @required.setter
    def required(self, value: int) -> None:
        self._required = value


class _RemoteNestResult:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @property
    def count(self) -> int:
        return int(self._data.get("count", 0))
