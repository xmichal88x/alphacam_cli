# ruff: noqa: TRY003

from __future__ import annotations

import contextlib
import logging
import socket
from typing import Any, cast

from alphacam_cli.gateway.protocol import (
    COM_ERROR,
    make_request,
    pack_message,
    read_frame,
)


class RemoteConnectionError(Exception):
    """Connection-level errors."""


class RemoteComError(Exception):
    """COM errors on the server."""


class RemoteSession:
    def __init__(self, host: str = "127.0.0.1", port: int = 8721, timeout: float = 180.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._msg_id: int = 0
        self._logger = logging.getLogger("alphacam.remote")

    def connect(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(self.timeout)
        self._sock.connect((self.host, self.port))
        self._logger.info("Connected to %s:%s", self.host, self.port)

    def _call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._msg_id += 1
        msg_id = self._msg_id
        request = make_request(method, params or {}, msg_id)
        packed = pack_message(request)
        if self._sock is None:
            raise RemoteConnectionError("Not connected")
        self._sock.sendall(packed)
        raw = read_frame(self._sock)
        if raw is None:
            raise RemoteConnectionError("Connection closed by server")
        response = cast(dict[str, Any], raw)
        if "error" in response:
            error = cast(dict[str, Any], response["error"])
            code = error.get("code")
            message = error.get("message", "Unknown error")
            if code == COM_ERROR:
                raise RemoteComError(str(message))
            raise RemoteConnectionError(f"JSON-RPC error ({code}): {message}")
        return response["result"]

    def close(self) -> None:
        if self._sock is not None:
            with contextlib.suppress(Exception):
                self._sock.close()
            self._sock = None
            self._logger.debug("Connection closed")

    def __enter__(self) -> RemoteSession:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def ping(self) -> dict[str, Any]:
        return self._call("ping")  # type: ignore[no-any-return]

    def get_info(self) -> dict[str, Any]:
        return self._call("get_info")  # type: ignore[no-any-return]

    def new_drawing(
        self, width: float = 100, height: float = 50, fillet: float = 0, text: str = ""
    ) -> dict[str, Any]:
        return self._call(  # type: ignore[no-any-return]
            "new_drawing", {"width": width, "height": height, "fillet": fillet, "text": text}
        )

    def create_temp_drawing(self) -> dict[str, Any]:
        return self._call("create_temp_drawing")  # type: ignore[no-any-return]

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
        params: dict[str, Any] = {
            "width": width,
            "height": height,
            "offset": offset,
            "fillet": fillet,
        }
        if depth is not None:
            params["depth"] = depth
        if tool is not None:
            params["tool"] = tool
        if spindle is not None:
            params["spindle"] = spindle
        if feed is not None:
            params["feed"] = feed
        if down_feed is not None:
            params["down_feed"] = down_feed
        return self._call("drawing_parametric", params)  # type: ignore[no-any-return]

    def zoom_all(self) -> dict[str, Any]:
        return self._call("zoom_all")  # type: ignore[no-any-return]

    def open_drawing(self, path: str) -> dict[str, Any]:
        return self._call("open_drawing", {"path": path})  # type: ignore[no-any-return]

    def open_cad_file(
        self,
        path: str,
        fmt: str,
        clear: bool = False,
        cabinets: bool = False,
    ) -> dict[str, Any]:
        return self._call(  # type: ignore[no-any-return]
            "open_cad_file",
            {"path": path, "fmt": fmt, "clear": clear, "cabinets": cabinets},
        )

    def export_drawing(self, path: str, fmt: str) -> dict[str, Any]:
        return self._call(  # type: ignore[no-any-return]
            "export_drawing", {"path": path, "fmt": fmt}
        )

    def save_active_drawing(self, path: str) -> dict[str, Any]:
        return self._call("save_active_drawing", {"path": path})  # type: ignore[no-any-return]

    def get_active_drawing(self) -> dict[str, Any] | None:
        return self._call("get_active_drawing")  # type: ignore[no-any-return]

    def list_tools(self, pattern: str = "*.art") -> list[str]:
        return self._call("list_tools", {"pattern": pattern})  # type: ignore[no-any-return]

    def select_tool(self, name: str) -> dict[str, Any]:
        return self._call("select_tool", {"name": name})  # type: ignore[no-any-return]

    def get_current_tool(self) -> dict[str, Any] | None:
        return self._call("get_current_tool")  # type: ignore[no-any-return]

    def mill_rough(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("mill_rough", kwargs)  # type: ignore[no-any-return]

    def mill_pocket(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("mill_pocket", kwargs)  # type: ignore[no-any-return]

    def mill_drill(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("mill_drill", kwargs)  # type: ignore[no-any-return]

    def mill_saw(self, **kwargs: Any) -> dict[str, Any]:
        params = {key: value for key, value in kwargs.items() if value is not None}
        return self._call("mill_saw", params)  # type: ignore[no-any-return]

    def mill_engrave(self, **kwargs: Any) -> dict[str, Any]:
        params = {key: value for key, value in kwargs.items() if value is not None}
        return self._call("mill_engrave", params)  # type: ignore[no-any-return]

    def output_nc(self, path: str, post: str = "") -> dict[str, Any]:
        return self._call("output_nc", {"path": path, "post": post})  # type: ignore[no-any-return]

    def apply_style(self, style: str, tool: str = "") -> dict[str, Any]:
        return self._call("apply_style", {"style": style, "tool": tool})  # type: ignore[no-any-return]

    def list_styles(self) -> dict[str, Any]:
        return self._call("list_styles")  # type: ignore[no-any-return]

    def reports_create(self) -> dict[str, Any]:
        return self._call("reports_create")  # type: ignore[no-any-return]

    def nc_configs(self) -> dict[str, Any]:
        return self._call("nc_configs")  # type: ignore[no-any-return]

    def auto_style_apply(self, file: str) -> dict[str, Any]:
        return self._call("auto_style_apply", {"file": file})  # type: ignore[no-any-return]

    def create_layer(self, name: str) -> dict[str, Any]:
        return self._call("create_layer", {"name": name})  # type: ignore[no-any-return]

    def machining_pipeline(
        self,
        agq: str | None = None,
        ara: str | None = None,
        layer_map: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if agq is not None:
            params["agq"] = agq
        if ara is not None:
            params["ara"] = ara
        if layer_map is not None:
            params["layer_map"] = layer_map
        return self._call("machining_pipeline", params)  # type: ignore[no-any-return]

    def batch_process(
        self,
        files: list[str],
        output_dir: str = "",
        post: str = "",
        continue_on_error: bool = False,
    ) -> list[dict[str, Any]]:
        return self._call(  # type: ignore[no-any-return]
            "batch_process",
            {
                "files": files,
                "output_dir": output_dir,
                "post": post,
                "continue_on_error": continue_on_error,
            },
        )

    def list_posts(self) -> list[dict[str, Any]]:
        return self._call("list_posts")  # type: ignore[no-any-return]

    def select_post(self, name: str) -> dict[str, Any]:
        return self._call("select_post", {"name": name})  # type: ignore[no-any-return]

    def run_nest(
        self,
        parts: list[dict[str, Any]],
        output_dir: str = "",
        sheet_width: float = 2440,
        sheet_height: float = 1220,
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
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "parts": parts,
            "output_dir": output_dir,
            "sheet_width": sheet_width,
            "sheet_height": sheet_height,
            "sheet_name": sheet_name,
            "advanced": advanced,
        }
        if gap is not None:
            params["gap"] = gap
        if edge_gap is not None:
            params["edge_gap"] = edge_gap
        if lead_gap is not None:
            params["lead_gap"] = lead_gap
        nest_opts: dict[str, Any] = {
            "total_time": total_time,
            "optimise_level": optimise_level,
            "part_gap": part_gap,
            "cut_width": cut_width,
            "nesting_method": nesting_method,
            "optimise_for_cuts": optimise_for_cuts,
            "cut_direction": cut_direction,
            "use_subroutines": use_subroutines,
            "prevent_aperture_nest": prevent_aperture_nest,
            "order_by_part": order_by_part,
            "inner_first": inner_first,
            "repeat_first_row": repeat_first_row,
            "preserve_sheet_edge": preserve_sheet_edge,
            "minimise_tool_changes": minimise_tool_changes,
            "strict_priorities": strict_priorities,
            "allow_solid_parts": allow_solid_parts,
            "select_best_sheet": select_best_sheet,
            "sheet_order": sheet_order,
            "time_per_sheet": time_per_sheet,
            "resolution": resolution,
        }
        for key, value in nest_opts.items():
            if value is not None:
                params[key] = value
        return self._call("run_nest", params)  # type: ignore[no-any-return]

    def run_cdm(
        self,
        job_name: str,
        type_name: str,
        width: float = 400,
        length: float = 300,
        quantity: int = 1,
        bypass_nest: bool = False,
        material: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "job_name": job_name,
            "type_name": type_name,
            "width": width,
            "length": length,
            "quantity": quantity,
            "bypass_nest": bypass_nest,
        }
        if material is not None:
            params["material"] = material
        return self._call("run_cdm", params)  # type: ignore[no-any-return]

    def cdm_types(self) -> dict[str, Any]:
        return self._call("cdm_types")  # type: ignore[no-any-return]

    def cdm_jobs(self) -> dict[str, Any]:
        return self._call("cdm_jobs")  # type: ignore[no-any-return]

    def import_cdm_csv(
        self,
        csv: str,
        job: str | None = None,
        name: str | None = None,
        config: str | None = None,
        separator: str | None = None,
        has_header: bool = False,
        material: str | None = None,
        import_setting: str | int | None = None,
        preview: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"csv": csv, "has_header": has_header}
        if separator is not None:
            params["separator"] = separator
        if job is not None:
            params["job"] = job
        if name is not None:
            params["name"] = name
        if config is not None:
            params["config"] = config
        if material is not None:
            params["material"] = material
        if import_setting is not None:
            params["import_setting"] = (
                int(import_setting) if str(import_setting).isdigit() else import_setting
            )
        if preview:
            params["preview"] = True
        return self._call("cdm_import_csv", params)  # type: ignore[no-any-return]

    def import_cdm_preview(
        self,
        csv: str,
        import_setting: str | int | None = None,
        separator: str | None = None,
        has_header: bool = False,
        job: str | None = None,
        name: str | None = None,
        config: str | None = None,
        material: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"csv": csv, "has_header": has_header}
        if import_setting is not None:
            params["import_setting"] = (
                int(import_setting) if str(import_setting).isdigit() else import_setting
            )
        if separator is not None:
            params["separator"] = separator
        if job is not None:
            params["job"] = job
        if name is not None:
            params["name"] = name
        if config is not None:
            params["config"] = config
        if material is not None:
            params["material"] = material
        return self._call("cdm_import_preview", params)  # type: ignore[no-any-return]

    def cdm_import_settings(self) -> dict[str, Any]:
        return self._call("cdm_import_settings")  # type: ignore[no-any-return]

    def delete_cdm_job(self, job_name: str) -> dict[str, Any]:
        return self._call("cdm_delete_job", {"job_name": job_name})  # type: ignore[no-any-return]

    def find_drawing_files(self, pattern: str = "*.amd") -> list[str]:
        return self._call("find_drawing_files", {"pattern": pattern})  # type: ignore[no-any-return]

    def glob_files(self, directory: str, pattern: str = "*.amd") -> list[str]:
        return self._call("glob_files", {"directory": directory, "pattern": pattern})  # type: ignore[no-any-return]
