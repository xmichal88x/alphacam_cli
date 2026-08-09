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

    def export(self, path: str, fmt: str) -> dict[str, Any]:
        return self._session.export_drawing(path, fmt)

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

    def create_layer(self, name: str) -> dict[str, Any]:
        return self._session.create_layer(name)  # type: ignore[no-any-return]


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

    def open_cad_file(
        self,
        path: str,
        fmt: str,
        clear: bool = False,
        cabinets: bool = False,
    ) -> _DrawingProxy | None:
        info = self._session.open_cad_file(path, fmt, clear=clear, cabinets=cabinets)
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

    def find_style_files(self) -> list[str]:
        result = self._session.list_styles()
        return [str(s["path"]) for s in result.get("styles", [])]

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

    def reports_create(self) -> dict[str, Any]:
        return self._session.reports_create()  # type: ignore[no-any-return]

    def nc_configs(self) -> dict[str, Any]:
        return self._session.nc_configs()  # type: ignore[no-any-return]

    def auto_style_apply(self, file: str) -> dict[str, Any]:
        return self._session.auto_style_apply(file)  # type: ignore[no-any-return]

    def create_layer(self, name: str) -> dict[str, Any]:
        return self._session.create_layer(name)  # type: ignore[no-any-return]

    def machining_pipeline(
        self,
        agq: str | None = None,
        ara: str | None = None,
        layer_map: str | None = None,
    ) -> dict[str, Any]:
        return self._session.machining_pipeline(  # type: ignore[no-any-return]
            agq=agq, ara=ara, layer_map=layer_map
        )

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

    def drawing_parametric(
        self,
        width: float,
        height: float,
        offset: float = 50,
        fillet: float = 5,
        depth: float | None = None,
        tool: str | None = None,
        spindle: int | None = None,
        feed: float | None = None,
        down_feed: float | None = None,
    ) -> dict[str, Any]:
        return self._session.drawing_parametric(
            width,
            height,
            offset=offset,
            fillet=fillet,
            depth=depth,
            tool=tool,
            spindle=spindle,
            feed=feed,
            down_feed=down_feed,
        )

    def run_cdm(
        self,
        job_name: str,
        type_name: str,
        width: float = 400,
        length: float = 300,
        quantity: int = 1,
        bypass_nest: bool = False,
    ) -> dict[str, Any]:
        return self._session.run_cdm(  # type: ignore[no-any-return]
            job_name=job_name,
            type_name=type_name,
            width=width,
            length=length,
            quantity=quantity,
            bypass_nest=bypass_nest,
        )

    def cdm_types(self) -> dict[str, Any]:
        return self._session.cdm_types()  # type: ignore[no-any-return]

    def cdm_jobs(self) -> dict[str, Any]:
        return self._session.cdm_jobs()  # type: ignore[no-any-return]


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

    @property
    def saw_angle(self) -> float:
        return float(self._params.get("saw_angle", 0))

    @saw_angle.setter
    def saw_angle(self, value: float) -> None:
        self._set("saw_angle", value)

    @property
    def saw_external_corners(self) -> int:
        return int(self._params.get("external_corners", 1))

    @saw_external_corners.setter
    def saw_external_corners(self, value: int) -> None:
        self._set("external_corners", value)

    @property
    def saw_internal_corners(self) -> int:
        return int(self._params.get("internal_corners", 1))

    @saw_internal_corners.setter
    def saw_internal_corners(self, value: int) -> None:
        self._set("internal_corners", value)

    @property
    def saw_open_ends(self) -> int:
        return int(self._params.get("open_ends", 1))

    @saw_open_ends.setter
    def saw_open_ends(self, value: int) -> None:
        self._set("open_ends", value)

    @property
    def saw_head_position(self) -> int:
        return int(self._params.get("head_position", 0))

    @saw_head_position.setter
    def saw_head_position(self, value: int) -> None:
        self._set("head_position", value)

    @property
    def engrave_type(self) -> int:
        return int(self._params.get("engrave_type", 0))

    @engrave_type.setter
    def engrave_type(self, value: int) -> None:
        self._set("engrave_type", value)

    @property
    def step_length(self) -> float:
        return float(self._params.get("step_length", 0.1))

    @step_length.setter
    def step_length(self, value: float) -> None:
        self._set("step_length", value)

    @property
    def chord_error(self) -> float:
        return float(self._params.get("chord_error", 0.01))

    @chord_error.setter
    def chord_error(self, value: float) -> None:
        self._set("chord_error", value)

    @property
    def engrave_corner_angle_limit(self) -> float:
        return float(self._params.get("engrave_corner_angle_limit", 90))

    @engrave_corner_angle_limit.setter
    def engrave_corner_angle_limit(self, value: float) -> None:
        self._set("engrave_corner_angle_limit", value)

    def rough_finish(self) -> None:
        self._session.mill_rough(**self._params)

    def pocket(self) -> None:
        self._session.mill_pocket(**self._params)

    def saw(self) -> None:
        self._session.mill_saw(**self._params)

    def engrave(self) -> None:
        self._session.mill_engrave(**self._params)

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

    def nest(
        self,
        nl: Any,
        sl: Any,
        sheet_name: str = "",
        gap: float | None = None,
        edge_gap: float | None = None,
        lead_gap: float | None = None,
        advanced: bool = False,
        total_time: float | None = None,
        optimise_level: int | None = None,
        part_gap: float | None = None,
        cut_width: float | None = None,
        nesting_method: int | None = None,
        optimise_for_cuts: int | None = None,
        cut_direction: int | None = None,
        use_subroutines: bool | None = None,
        prevent_aperture_nest: bool | None = None,
        order_by_part: bool | None = None,
        inner_first: bool | None = None,
        repeat_first_row: bool | None = None,
        preserve_sheet_edge: bool | None = None,
        minimise_tool_changes: bool | None = None,
        strict_priorities: bool | None = None,
        allow_solid_parts: bool | None = None,
        select_best_sheet: int | None = None,
        sheet_order: int | None = None,
        time_per_sheet: float | None = None,
        resolution: float | None = None,
    ) -> Any:
        parts = nl.get_parts() if hasattr(nl, "get_parts") else []
        result = self._session.run_nest(
            parts=parts,
            output_dir=nl.output_dir if hasattr(nl, "output_dir") else "",
            sheet_width=sl.width if hasattr(sl, "width") else 2440,
            sheet_height=sl.height if hasattr(sl, "height") else 1220,
            sheet_name=sheet_name,
            gap=gap,
            edge_gap=edge_gap,
            lead_gap=lead_gap,
            advanced=advanced,
            total_time=total_time,
            optimise_level=optimise_level,
            part_gap=part_gap,
            cut_width=cut_width,
            nesting_method=nesting_method,
            optimise_for_cuts=optimise_for_cuts,
            cut_direction=cut_direction,
            use_subroutines=use_subroutines,
            prevent_aperture_nest=prevent_aperture_nest,
            order_by_part=order_by_part,
            inner_first=inner_first,
            repeat_first_row=repeat_first_row,
            preserve_sheet_edge=preserve_sheet_edge,
            minimise_tool_changes=minimise_tool_changes,
            strict_priorities=strict_priorities,
            allow_solid_parts=allow_solid_parts,
            select_best_sheet=select_best_sheet,
            sheet_order=sheet_order,
            time_per_sheet=time_per_sheet,
            resolution=resolution,
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
