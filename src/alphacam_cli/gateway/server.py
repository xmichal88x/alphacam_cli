# ruff: noqa: TRY003

from __future__ import annotations

import contextlib
import glob as glob_module
import logging
import os
import queue
import socket
import threading
from collections.abc import Callable
from typing import Any, cast

from alphacam_cli.gateway.protocol import (
    COM_ERROR,
    INTERNAL_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    make_error,
    make_response,
    pack_message,
    read_frame,
)

CONNECT_TIMEOUT = 180
_RPC_E_CHANGED_MODE = -2147417850
_DRILL_MAP: dict[str, int] = {"drill": 0, "tap": 1, "peck": 3}


class COMError(Exception):
    pass


# Module-level Application instance, created and used exclusively on the STA thread.
_app: Any = None


class GatewayServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8721) -> None:
        self._host = host
        self._port = port
        self._logger = logging.getLogger("alphacam.gateway")
        self._server: socket.socket | None = None
        self._running = threading.Event()
        self._owned: bool = False
        self._sta_thread: threading.Thread | None = None
        self._call_queue: queue.Queue[Any] = queue.Queue()

    def start(self) -> None:
        self._logger.info("Starting AlphaCAM gateway server...")
        self._running.set()
        self._sta_loop()
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self._host, self._port))
        self._server.listen(1)
        self._server.settimeout(1.0)
        self._logger.info("Gateway server listening on %s:%s", self._host, self._port)
        while self._running.is_set():
            try:
                client, addr = self._server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            self._logger.info("Client connected: %s:%s", *addr)
            t = threading.Thread(target=self._handle_client, args=(client,), daemon=True)
            t.start()

    def _com_call(self, fn: Callable[[], Any], desc: str = "") -> Any:
        """Queue a lambda on the STA call queue and block for the result."""
        result_q: queue.Queue[Any] = queue.Queue()
        self._call_queue.put((fn, result_q, desc))
        result = result_q.get()
        if isinstance(result, Exception):
            raise result
        return result

    def _sta_loop(self) -> None:
        import pythoncom  # type: ignore[import-untyped]
        import win32com.client as win32  # type: ignore[import-untyped]

        start_q: queue.Queue[Any] = queue.Queue()

        def sta_worker() -> None:
            from alphacam_cli.com.constants import PROG_IDS

            com_ok = False
            ac_app = None
            owned = False
            try:
                pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
                com_ok = True
            except pythoncom.com_error as e:  # type: ignore[attr-defined]
                if e.hresult != _RPC_E_CHANGED_MODE:  # type: ignore[attr-defined]
                    start_q.put(("error", f"CoInitializeEx failed: {e}"))
                    return

            for pid in PROG_IDS:
                try:
                    ac_app = win32.GetActiveObject(pid)
                    break
                except Exception:
                    try:
                        ac_app = win32.Dispatch(pid)
                        owned = True
                        break
                    except Exception:
                        pass

            if ac_app is None:
                start_q.put(
                    (
                        "error",
                        f"Cannot connect to AlphaCAM. Tried ProgIDs: {PROG_IDS}\n"
                        "Check: (1) AlphaCAM installed, (2) license active, "
                        "(3) another process not blocking",
                    )
                )
                return

            with contextlib.suppress(Exception):
                ac_app.Visible = True  # type: ignore[attr-defined]

            from alphacam_cli.core.application import Application

            global _app
            _app = Application(ac_app)  # type: ignore[arg-type]
            start_q.put(("ok", owned))
            self._logger.info("AlphaCAM COM connected (owned=%s)", owned)

            while self._running.is_set():
                try:
                    item = self._call_queue.get(timeout=0.05)
                except queue.Empty:
                    pythoncom.PumpWaitingMessages()
                    continue

                fn, result_q, desc = item
                try:
                    r = fn()
                    result_q.put(r)
                except Exception as exc:
                    result_q.put(exc)
                pythoncom.PumpWaitingMessages()

            if owned:
                with contextlib.suppress(Exception):
                    ac_app.Quit()
            if com_ok:
                pythoncom.CoUninitialize()  # type: ignore[attr-defined]

        self._sta_thread = threading.Thread(target=sta_worker, daemon=True)
        self._sta_thread.start()

        status = start_q.get(timeout=CONNECT_TIMEOUT)
        if status[0] == "error":
            raise RuntimeError(status[1])
        self._owned = bool(status[1])

    def _handle_client(self, client_socket: socket.socket) -> None:
        try:
            while self._running.is_set():
                raw = read_frame(client_socket)
                if raw is None:
                    break
                msg = cast(dict[str, Any], raw)
                if not isinstance(msg, dict) or "method" not in msg:
                    err_resp = make_error(
                        INVALID_REQUEST,
                        "Invalid request",
                        msg.get("id"),
                    )
                    client_socket.sendall(pack_message(err_resp))
                    continue
                req_id = msg.get("id")
                method = str(msg["method"])
                params_raw = msg.get("params", {})
                params = cast(dict[str, Any], params_raw) if isinstance(params_raw, dict) else {}
                response = self._dispatch(method, params, req_id)
                if response is not None:
                    client_socket.sendall(pack_message(response))
        except Exception:
            self._logger.exception("Client handler error")
        finally:
            client_socket.close()
            self._logger.info("Client disconnected")

    def _dispatch(
        self, method: str, params: dict[str, Any], msg_id: int | None
    ) -> dict[str, Any] | None:
        if msg_id is None:
            return None
        handler_name = f"_handler_{method}"
        handler = getattr(self, handler_name, None)
        if handler is None:
            return make_error(METHOD_NOT_FOUND, f"Method not found: {method}", msg_id)
        try:
            result = self._com_call(lambda: handler(params), method)
        except COMError as e:
            self._logger.exception("COM error handling '%s'", method)
            return make_error(COM_ERROR, str(e), msg_id)
        except Exception as e:
            self._logger.exception("Error handling '%s'", method)
            return make_error(INTERNAL_ERROR, str(e), msg_id)
        return make_response(result, msg_id)

    def stop(self) -> None:
        self._logger.info("Gateway server stopping...")
        self._running.clear()
        if self._server is not None:
            with contextlib.suppress(OSError):
                self._server.close()
        if self._sta_thread is not None and self._sta_thread.is_alive():
            self._call_queue.put((lambda: None, queue.Queue(), "stop"))
            self._sta_thread.join(timeout=10)

    def _handler_ping(self, params: dict[str, Any]) -> dict[str, bool]:
        return {"pong": True}

    def _handler_get_info(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        return {
            "version": com_app.version,
            "name": com_app.name,
            "full_name": com_app.full_name,
            "module_type": com_app.module_type,
            "program_level": com_app.program_level,
            "api_version": com_app.api_version,
            "licomdat_path": com_app.licomdat_path,
            "licomdir_path": com_app.licomdir_path,
            "post_file_name": com_app.post_file_name,
        }

    def _handler_new_drawing(self, params: dict[str, Any]) -> dict[str, int]:
        from alphacam_cli.gateway.server import _app as com_app

        width = float(params.get("width", 100))
        height = float(params.get("height", 50))
        fillet = float(params.get("fillet", 0))
        text = str(params.get("text", ""))
        drw = com_app.create_temp_drawing()
        if drw is None:
            raise COMError("Failed to create temporary drawing")
        rect = drw.create_rectangle(0, 0, width, height)
        if fillet > 0:
            rect.fillet(fillet)
        if text:
            drw.create_text(text, 5, height / 2, 4)
        drw.zoom_all()
        return {"geometries_count": drw.geometries_count}

    def _handler_create_temp_drawing(self, params: dict[str, Any]) -> dict[str, int]:
        from alphacam_cli.gateway.server import _app as com_app

        drw = com_app.create_temp_drawing()
        if drw is None:
            raise COMError("Failed to create temporary drawing")
        return {"geometries_count": drw.geometries_count, "tool_paths_count": drw.tool_paths_count}

    def _handler_zoom_all(self, params: dict[str, Any]) -> dict[str, bool]:
        from alphacam_cli.gateway.server import _app as com_app

        drw = com_app.get_active_drawing()
        if drw is None:
            raise COMError("No active drawing")
        drw.zoom_all()
        return {"success": True}

    def _handler_open_drawing(self, params: dict[str, Any]) -> dict[str, int]:
        from alphacam_cli.gateway.server import _app as com_app

        path = str(params.get("path", ""))
        if not path:
            raise COMError("path is required")
        drw = com_app.open_drawing(path)
        if drw is None:
            raise COMError(f"Failed to open drawing: {path}")
        return {"geometries_count": drw.geometries_count, "tool_paths_count": drw.tool_paths_count}

    def _handler_save_active_drawing(self, params: dict[str, Any]) -> dict[str, bool]:
        from alphacam_cli.gateway.server import _app as com_app

        path = str(params.get("path", ""))
        if not path:
            raise COMError("path is required")
        drw = com_app.get_active_drawing()
        if drw is None:
            raise COMError("No active drawing")
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        drw.save_as(path)
        return {"success": True}

    def _handler_get_active_drawing(self, params: dict[str, Any]) -> dict[str, int] | None:
        from alphacam_cli.gateway.server import _app as com_app

        drw = com_app.get_active_drawing()
        if drw is None:
            return None
        return {"geometries_count": drw.geometries_count, "tool_paths_count": drw.tool_paths_count}

    def _handler_list_tools(self, params: dict[str, Any]) -> list[str]:
        from alphacam_cli.gateway.server import _app as com_app

        pattern = str(params.get("pattern", "*.art"))
        return com_app.find_tool_files(pattern)  # type: ignore[no-any-return]

    def _handler_select_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        name = str(params.get("name", ""))
        if not name:
            raise COMError("name is required")
        files = com_app.find_tool_files()
        name_norm = name.replace("\\", "/").lower()
        basename_lower = name.lower()
        exact_path = [f for f in files if f.replace("\\", "/").lower() == name_norm]
        exact = [
            f
            for f in files
            if f not in exact_path and os.path.basename(f).lower() == basename_lower
        ]
        path_substring: list[str] = []
        if "/" in name or "\\" in name:
            path_substring = [
                f
                for f in files
                if f not in exact_path
                and f not in exact
                and name_norm in f.replace("\\", "/").lower()
            ]
        prefix = [
            f
            for f in files
            if f not in exact_path
            and f not in exact
            and f not in path_substring
            and os.path.basename(f).lower().startswith(basename_lower)
        ]
        substring = [
            f
            for f in files
            if f not in exact_path
            and f not in exact
            and f not in path_substring
            and f not in prefix
            and basename_lower in os.path.basename(f).lower()
        ]
        matched = exact_path or exact or path_substring or prefix or substring
        if not matched:
            raise COMError(f"No tool matching '{name}'")
        if len(matched) > 1:
            names = [os.path.basename(m) for m in matched]
            raise COMError(f"Multiple tools matched: {', '.join(names)}. Use a more specific name.")
        tool = com_app.select_tool(matched[0])
        if tool is None:
            raise COMError(f"Failed to select tool: {os.path.basename(matched[0])}")
        return {
            "name": tool.name,
            "diameter": tool.diameter,
            "number": tool.number,
            "length": tool.tool_length,
            "tool_type": tool.tool_type,
        }

    def _handler_get_current_tool(self, params: dict[str, Any]) -> dict[str, Any] | None:
        from alphacam_cli.gateway.server import _app as com_app

        tool = com_app.get_current_tool()
        if tool is None:
            return None
        return {
            "name": tool.name,
            "diameter": tool.diameter,
            "number": tool.number,
            "length": tool.tool_length,
            "tool_type": tool.tool_type,
        }

    def _handler_mill_rough(self, params: dict[str, Any]) -> dict[str, int]:
        from alphacam_cli.gateway.server import _app as com_app

        drw = com_app.get_active_drawing()
        if drw is None:
            raise COMError("No active drawing")
        if drw.geometries_count == 0:
            raise COMError("No geometries to machine")
        tool_side = str(params.get("tool_side", "outside")).lower()
        if tool_side not in ("outside", "inside"):
            raise COMError(f"Invalid tool side: '{tool_side}'. Use 'outside' or 'inside'")
        side = -1 if tool_side == "outside" else 1
        start_x = float(params.get("start_x", 0.0))
        start_y = float(params.get("start_y", 0.0))
        for geo in drw.geometries():
            geo.tool_in_out = side
            geo.set_start_point(start_x, start_y)
        drw.select_all_geometries()
        md = com_app.create_mill_data()
        md.safe_rapid_level = float(params.get("rapid", 10))
        md.rapid_down_to = 2.0
        md.material_top = float(params.get("material_top", 0))
        md.final_depth = float(params.get("depth", -10))
        md.spindle_speed = int(params.get("spindle", 12000))
        md.down_feed = float(params.get("down_feed", 2000))
        md.cut_feed = float(params.get("feed", 3000))
        md.max_depth_per_cut = float(params.get("max_depth_per_cut", 2.5))
        md.width_of_cut = float(params.get("width_of_cut", 5))
        md.stock = float(params.get("stock", 0.5))
        md.xy_corners = 1
        md.rough_finish()
        drw.zoom_all()
        return {"tool_paths_count": drw.tool_paths_count}

    def _handler_mill_pocket(self, params: dict[str, Any]) -> dict[str, bool]:
        from alphacam_cli.com.constants import ACAM_POCKET_CONTOUR
        from alphacam_cli.gateway.server import _app as com_app

        drw = com_app.get_active_drawing()
        if drw is None:
            raise COMError("No active drawing")
        drw.select_all_geometries()
        md = com_app.create_mill_data()
        md.pocket_type = ACAM_POCKET_CONTOUR
        md.safe_rapid_level = 20.0
        md.rapid_down_to = 2.0
        md.final_depth = float(params.get("depth", -8))
        md.spindle_speed = int(params.get("spindle", 12000))
        md.cut_feed = float(params.get("feed", 3000))
        md.width_of_cut = float(params.get("width_of_cut", 7.5))
        md.stock = 1.0
        md.pocket()
        drw.zoom_all()
        return {"success": True}

    def _handler_mill_drill(self, params: dict[str, Any]) -> dict[str, bool]:
        from alphacam_cli.gateway.server import _app as com_app

        drw = com_app.get_active_drawing()
        if drw is None:
            raise COMError("No active drawing")
        drw.select_all_geometries()
        drill_type_str = str(params.get("drill_type", "drill")).lower()
        d_type = _DRILL_MAP.get(drill_type_str)
        if d_type is None:
            raise COMError(f"Invalid drill type: '{drill_type_str}'. Use drill/tap/peck")
        md = com_app.create_mill_data()
        md.drill_type = d_type
        md.safe_rapid_level = 20.0
        md.rapid_down_to = 2.0
        md.bottom_of_hole = float(params.get("depth", -15))
        md.spindle_speed = int(params.get("spindle", 12000))
        md.drill_tap()
        drw.zoom_all()
        return {"success": True}

    def _handler_apply_style(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        style = str(params.get("style", ""))
        if not style:
            raise COMError("style is required")
        tool = str(params.get("tool", ""))
        if tool:
            if os.path.exists(tool):
                if com_app.select_tool(tool) is None:
                    raise COMError(f"Failed to select tool: {os.path.basename(tool)}")
            else:
                self._handler_select_tool({"name": tool})
        drw = com_app.get_active_drawing()
        if drw is None:
            raise COMError("No active drawing")
        if drw.geometries_count == 0:
            raise COMError("No geometries to machine")
        for geo in drw.geometries():
            geo.selected = True
        com_app.apply_mill_style(style)
        drw.zoom_all()
        return {"success": True, "tool_paths_count": drw.tool_paths_count}

    def _handler_output_nc(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        path = str(params.get("path", ""))
        if not path:
            raise COMError("path is required")
        post = str(params.get("post", ""))
        if post:
            com_app.select_post(post)
        drw = com_app.get_active_drawing()
        if drw is None:
            raise COMError("No active drawing")
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        drw.output_nc(path)
        if os.path.exists(path):
            return {"success": True, "size": int(os.path.getsize(path)), "path": path}
        raise COMError(f"NC file not created: {path}")

    def _handler_batch_process(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        from alphacam_cli.gateway.server import _app as com_app

        files: list[str] = list(params.get("files", []))
        output_dir = str(params.get("output_dir", ""))
        post = str(params.get("post", ""))
        continue_on_error = bool(params.get("continue_on_error", False))
        if not files:
            raise COMError("files list is required")
        if post:
            com_app.select_post(post)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        results: list[dict[str, Any]] = []
        for f in files:
            result: dict[str, Any] = {"file": f, "status": "OK", "error": ""}
            try:
                drw = com_app.open_drawing(f)
                if drw is None:
                    result.update(status="FAIL", error=f"Could not open drawing: {f}")
                    if not continue_on_error:
                        results.append(result)
                        break
                    results.append(result)
                    continue
                if output_dir:
                    basename = os.path.splitext(os.path.basename(f))[0]
                    nc_path = os.path.join(output_dir, f"{basename}.nc")
                    drw.output_nc(nc_path)
            except Exception as e:
                result.update(status="FAIL", error=str(e))
                if not continue_on_error:
                    results.append(result)
                    break
            results.append(result)
        return results

    def _handler_list_posts(self, params: dict[str, Any]) -> list[dict[str, str]]:
        from alphacam_cli.gateway.server import _app as com_app

        posts: list[dict[str, str]] = []
        seen: set[str] = set()
        for fp in com_app.find_post_files("*.arp"):
            if fp not in seen:
                seen.add(fp)
                posts.append({"name": os.path.basename(fp), "path": fp})
        for base_dir in (com_app.licomdir_path, com_app.licomdat_path):
            posts_dir = os.path.join(base_dir, "posts")
            if not os.path.isdir(posts_dir):
                continue
            for ext in ("*.vba", "*.dll"):
                for fp in sorted(glob_module.glob(os.path.join(posts_dir, ext))):
                    if fp not in seen:
                        seen.add(fp)
                        posts.append({"name": os.path.basename(fp), "path": fp})
        return sorted(posts, key=lambda p: (p["name"].lower(), p["path"]))

    def _handler_select_post(self, params: dict[str, Any]) -> dict[str, bool]:
        from alphacam_cli.gateway.server import _app as com_app

        name = str(params.get("name", ""))
        if not name:
            raise COMError("name is required")
        if not os.path.exists(name):
            files = com_app.find_post_files("*.arp")
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
                raise COMError(f"No post matching '{name}'")
            if len(matched) > 1:
                names = [os.path.basename(m) for m in matched]
                raise COMError(
                    f"Multiple posts matched: {', '.join(names)}. Use a more specific name."
                )
            name = matched[0]
        com_app.select_post(name)
        return {"success": True}

    def _handler_run_nest(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        parts: list[dict[str, Any]] = list(params.get("parts", []))
        output_dir = str(params.get("output_dir", ""))
        sheet_width = float(params.get("sheet_width", 2440))
        sheet_height = float(params.get("sheet_height", 1220))
        if not parts:
            raise COMError("parts list is required")
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        drw = com_app.create_temp_drawing()
        if drw is None:
            raise COMError("Failed to create temporary drawing")
        sheet_geo = drw.create_rectangle(0, 0, sheet_width, sheet_height)
        try:
            nesting = com_app.get_nesting()
        except Exception as e:
            raise COMError(f"nest: get_nesting failed: {e}") from e
        try:
            nesting.suppress_dialogs = True
        except Exception as e:
            raise COMError(f"nest: suppress_dialogs failed: {e}") from e
        try:
            nesting.delete_all_nest_lists()
        except Exception as e:
            raise COMError(f"nest: delete_all_nest_lists failed: {e}") from e
        nest_path = os.path.join(output_dir, "nest.anl") if output_dir else "nest.anl"
        try:
            nl = nesting.new_nest_list(nest_path)
        except Exception as e:
            raise COMError(f"nest: new_nest_list failed: {e}") from e
        nl.total_time = 10
        for part in parts:
            try:
                np_pt = nl.add_file(str(part.get("name", "")))
            except Exception as e:
                raise COMError(f"nest: add_file failed: {e}") from e
            np_pt.required = int(part.get("count", 1))
            np_pt.rotation_angle = 90
        try:
            sl = nesting.new_sheet_list()
        except Exception as e:
            raise COMError(f"nest: new_sheet_list failed: {e}") from e
        try:
            ss = sl.add(sheet_geo)
        except Exception as e:
            raise COMError(f"nest: add failed: {e}") from e
        ss.thickness = 18.0
        ss.required = 1
        try:
            nest_result = nesting.nest(nl, sl)
        except Exception as e:
            raise COMError(f"nest: nest failed: {e}") from e
        nl.save()
        return {"count": nest_result.count if nest_result else 0, "success": True}

    def _handler_find_drawing_files(self, params: dict[str, Any]) -> list[str]:
        from alphacam_cli.gateway.server import _app as com_app

        pattern = str(params.get("pattern", "*.amd"))
        return com_app.find_drawing_files(pattern)  # type: ignore[no-any-return]

    def _handler_glob_files(self, params: dict[str, Any]) -> list[str]:
        directory = str(params.get("directory", ""))
        pattern = str(params.get("pattern", "*.amd"))
        if not directory:
            raise COMError("directory is required")
        if not os.path.isdir(directory):
            return []
        return sorted(glob_module.glob(os.path.join(directory, pattern)))
