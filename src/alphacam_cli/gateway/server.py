# ruff: noqa: TRY003

from __future__ import annotations

import contextlib
import csv
import glob as glob_module
import io
import json
import logging
import os
import queue
import re
import socket
import subprocess
import sys
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
_NEST_TYPELIB_GUID = "{6702E3DF-142C-4627-8EA2-4C47EBC78441}"

_NEST_OPT_PROPERTIES: dict[str, str] = {
    "total_time": "TotalTime",
    "optimise_level": "OptimiseLevel",
    "part_gap": "PartGap",
    "edge_gap": "EdgeGap",
    "lead_gap": "LeadInGap",
    "cut_width": "CutWidth",
    "nesting_method": "NestingMethod",
    "optimise_for_cuts": "OptimiseForCuts",
    "cut_direction": "CutDirection",
    "use_subroutines": "UseSubroutines",
    "prevent_aperture_nest": "PreventApertureNest",
    "order_by_part": "OrderByPart",
    "inner_first": "InnerFirst",
    "repeat_first_row": "RepeatFirstRow",
    "preserve_sheet_edge": "PreserveSheetEdge",
    "minimise_tool_changes": "MinimiseToolChanges",
    "strict_priorities": "StrictPriorities",
    "allow_solid_parts": "AllowSolidParts",
    "select_best_sheet": "SelectBestSheet",
    "sheet_order": "SheetOrder",
    "time_per_sheet": "TimePerSheet",
    "resolution": "Resolution",
}
_NEST_FLOAT_OPTS = frozenset(
    {"total_time", "time_per_sheet", "part_gap", "edge_gap", "lead_gap", "cut_width", "resolution"}
)
_NEST_INT_OPTS = frozenset(
    {
        "optimise_level",
        "nesting_method",
        "optimise_for_cuts",
        "cut_direction",
        "select_best_sheet",
        "sheet_order",
    }
)
_NEST_BOOL_OPTS = frozenset(
    {
        "use_subroutines",
        "prevent_aperture_nest",
        "order_by_part",
        "inner_first",
        "repeat_first_row",
        "preserve_sheet_edge",
        "minimise_tool_changes",
        "strict_priorities",
        "allow_solid_parts",
    }
)


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

    def _handler_reports_create(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        try:
            return com_app.reports_create()  # type: ignore[no-any-return]
        except Exception as e:
            raise COMError(f"reports: create failed: {e}") from e

    def _handler_nc_configs(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        try:
            return com_app.nc_configs()  # type: ignore[no-any-return]
        except Exception as e:
            raise COMError(f"nc configs failed: {e}") from e

    def _handler_auto_style_apply(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        file = str(params.get("file", ""))
        if not file:
            raise COMError("file is required")
        try:
            return com_app.auto_style_apply(file)  # type: ignore[no-any-return]
        except Exception as e:
            raise COMError(str(e)) from e

    def _handler_create_layer(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        name = str(params.get("name", ""))
        if not name:
            raise COMError("name is required")
        drw = com_app.get_active_drawing()
        if drw is None:
            raise COMError("No active drawing")
        try:
            drw.create_layer(name)
        except Exception as e:
            raise COMError(f"create_layer failed: {e}") from e
        return {"success": True, "layer": name}

    def _handler_machining_pipeline(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        ara = str(params.get("ara", ""))
        if not ara:
            raise COMError("ara is required")
        agq = str(params.get("agq", "")) or None
        layer_map = str(params.get("layer_map", "")) or None
        try:
            return com_app.machining_pipeline(  # type: ignore[no-any-return]
                agq=agq, ara=ara, layer_map=layer_map
            )
        except Exception as e:
            raise COMError(f"machining pipeline failed: {e}") from e

    def _handler_probe_nest(self, params: dict[str, Any]) -> dict[str, str]:
        from alphacam_cli.gateway.server import _app as com_app

        out: dict[str, str] = {}
        d = None
        try:
            d = com_app.get_active_drawing()
            out["active_drawing"] = "OK" if d else "None"
        except Exception as e:
            out["active_drawing"] = f"FAIL: {e!r}"
        if d is not None:
            try:
                nd = d.create_nest_data(str(params.get("path", r"C:\temp\nest_out\nest.anl")))
                out["create_nest_data"] = f"OK: {nd}"
            except Exception as e:
                out["create_nest_data"] = f"FAIL: {e!r}"
        try:
            raw = com_app._app.Nesting  # type: ignore[attr-defined]
            out["app_nesting"] = f"OK: {raw}"
        except Exception as e:
            out["app_nesting"] = f"FAIL: {e!r}"
        try:
            import win32com.client as w32  # type: ignore[import-untyped]

            raw = w32.Dispatch("AcamNest.Nesting")
            out["dispatch_acamnest"] = f"OK: {raw}"
        except Exception as e:
            out["dispatch_acamnest"] = f"FAIL: {e!r}"
        try:
            import win32com.client.gencache as gencache  # type: ignore[import-untyped]

            app2 = gencache.EnsureDispatch("Ar5axaps.Application")
            out["gencache_app"] = f"OK: {app2}"
            members = [
                m for m in dir(app2) if any(s in m.lower() for s in ("nest", "level", "addin"))
            ]
            out["app2_members"] = f"{members}"
            try:
                n3 = app2.Nesting
                out["gencache_nesting"] = f"OK: {n3}"
            except Exception as e:
                out["gencache_nesting"] = f"FAIL: {e!r}"
            for addin_name in (
                r"C:\Program Files\Hexagon\ALPHACAM 2025\Add-Ins\Nesting\AcamRadNest.dll",
            ):
                try:
                    r2 = app2.LoadAddIn(addin_name)
                    out["load_addin_fullpath"] = f"OK: {r2}"
                    n4 = app2.Nesting
                    out["nesting_after_load_fullpath"] = f"OK: {n4}"
                except Exception as e:
                    out["load_addin_fullpath"] = f"FAIL: {e!r}"
            try:
                r5 = app2.EnableAddIn(
                    r"C:\Program Files\Hexagon\ALPHACAM 2025\Add-Ins\Nesting\AcamRadNest.dll",
                    True,
                )
                out["enable_addin_fullpath"] = f"OK: {r5}"
                n6 = app2.Nesting
                out["nesting_after_enable"] = f"OK: {n6}"
            except Exception as e:
                out["enable_addin_fullpath"] = f"FAIL: {e!r}"
            for fn, args in (
                ("EnableAddIn", ("Nesting",)),
                ("EnableAddIn", ("AcamRadNest",)),
                ("EnableAddIn", ("AcamNest",)),
            ):
                try:
                    r5 = getattr(app2, fn)(*args)
                    out[f"{fn}{args}"] = f"OK: {r5}"
                except Exception as e:
                    out[f"{fn}{args}"] = f"FAIL: {e!r}"
            try:
                out["IsAlphaNest_value"] = f"OK: {app2.IsAlphaNest}"
            except Exception as e:
                out["IsAlphaNest_value"] = f"FAIL: {e!r}"
            try:
                out["LoadAddIn_sig"] = f"OK: {app2.LoadAddIn.__doc__}"
            except Exception as e:
                out["LoadAddIn_sig"] = f"FAIL: {e!r}"
            try:
                out["EnableAddIn_sig"] = f"OK: {app2.EnableAddIn.__doc__}"
            except Exception as e:
                out["EnableAddIn_sig"] = f"FAIL: {e!r}"
        except Exception as e:
            out["gencache_app"] = f"FAIL: {e!r}"
        try:
            com_app.get_active_drawing()
            out["materials"] = "n/a"
        except Exception as e:
            out["materials"] = f"FAIL: {e!r}"
        try:
            import win32com.client.gencache as gencache  # type: ignore[import-untyped]

            mod = gencache.EnsureModule("{6702E3DF-142C-4627-8EA2-4C47EBC78441}", 0, 1, 3)
            out["ensuremodule"] = f"OK: {mod!r}"
        except Exception as e:
            out["ensuremodule"] = f"FAIL: {e!r}"
        app3: Any = None
        n: Any = None
        try:
            import win32com.client.gencache as gencache  # type: ignore[import-untyped]

            app3 = gencache.EnsureDispatch("Ar5axaps.Application")
            n = app3.Nesting
            out["nesting_after_ensure"] = f"OK: {n!r}"
        except Exception as e:
            out["nesting_after_ensure"] = f"FAIL: {e!r}"
        if n is not None:
            db: Any = None
            try:
                db = n.SheetDatabase
                out["sheetdatabase"] = f"OK: {db!r}"
            except Exception as e:
                out["sheetdatabase"] = f"FAIL: {e!r}"
            mat_coll: Any = None
            try:
                mat_coll = db.Materials
                out["materials"] = f"OK count={mat_coll.Count}"
            except Exception as e:
                out["materials"] = f"FAIL: {e!r}"
            mat0: Any = None
            if mat_coll is not None:
                try:
                    mat0 = mat_coll.Item(1)
                    out["material0"] = f"OK: {mat0.Name}"
                except Exception as e:
                    out["material0"] = f"FAIL: {e!r}"
            mat: Any = None
            if mat0 is not None:
                try:
                    mat = mat0.FindMaterial(mat0.Name)
                    out["findmaterial"] = f"OK: {mat!r}"
                except Exception as e:
                    out["findmaterial"] = f"FAIL: {e!r}"
            thick: Any = None
            if mat is not None:
                try:
                    thick = mat.FindThickness(18.0, "mm")
                    out["thickness18"] = f"OK: {thick!r}"
                except Exception as e:
                    out["thickness18"] = f"FAIL: {e!r}"
            if thick is not None:
                try:
                    ws = thick.WholeSheets
                    wcount = ws.Count
                    sheet_names: list[str] = []
                    for i in range(1, wcount + 1):
                        if len(sheet_names) >= 5:
                            break
                        try:
                            s = ws.Item(i)
                            sheet_names.append(f"{s.Name} {s.Width}x{s.Height}x{s.Quantity}")
                        except Exception as e:
                            sheet_names.append(f"item{i} FAIL: {e!r}")
                    out["wholesheets"] = f"OK count={wcount} first={sheet_names}"
                except Exception as e:
                    out["wholesheets"] = f"FAIL: {e!r}"
            try:
                sheet = db.FindSheet("MDF_18")
                out["findsheet"] = (
                    f"OK: {sheet.Name} {sheet.Width}x{sheet.Height}x{sheet.Quantity} "
                    f"mat={sheet.Material.Name}"
                )
            except Exception as e:
                out["findsheet"] = f"FAIL: {e!r}"
            sheet2: Any = None
            paths2: Any = None
            try:
                sheet2 = db.FindSheet("MDF_18")
                paths2 = sheet2.InsertInActiveDrawingAtPoint(0.0, 0.0)
                out["sheet_insert_paths"] = f"OK: {paths2!r} type={type(paths2).__name__}"
            except Exception as e:
                out["sheet_insert_paths"] = f"FAIL: {e!r}"
            try:
                drw2 = com_app.get_active_drawing()
                out["drawing_after_sheet_insert"] = (
                    f"OK geometries={drw2.geometries_count} tool_paths={drw2.tool_paths_count}"
                )
            except Exception as e:
                out["drawing_after_sheet_insert"] = f"FAIL: {e!r}"
            nd2: Any = None
            try:
                drw2b = com_app.get_active_drawing()
                nd2 = drw2b.create_nest_data(r"C:\temp\nest_out\nest.anl")
                out["nd2"] = f"OK: {nd2!r}"
            except Exception as e:
                out["nd2"] = f"FAIL: {e!r}"
            if nd2 is not None:
                try:
                    r = nd2.AddSheet(paths2.Item(1), sheet2.Material.Name, 18, sheet2.Quantity)
                    out["addsheet_item1"] = f"OK: {r!r}"
                except Exception as e:
                    out["addsheet_item1"] = f"FAIL: {e!r}"
                try:
                    r = nd2.DoNest()
                    out["donest_item1"] = f"OK: {r!r}"
                except Exception as e:
                    out["donest_item1"] = f"FAIL: {e!r}"
                try:
                    drw3 = com_app.get_active_drawing()
                    out["drawing_after_nest_item1"] = (
                        f"OK geometries={drw3.geometries_count} tool_paths={drw3.tool_paths_count}"
                    )
                except Exception as e:
                    out["drawing_after_nest_item1"] = f"FAIL: {e!r}"
                if out.get("addsheet_item1", "").startswith("FAIL"):
                    try:
                        r = nd2.AddSheet(paths2, sheet2.Material.Name, 18, sheet2.Quantity)
                        out["addsheet_collection"] = f"OK: {r!r}"
                    except Exception as e:
                        out["addsheet_collection"] = f"FAIL: {e!r}"
                    try:
                        r = nd2.DoNest()
                        out["donest_collection"] = f"OK: {r!r}"
                    except Exception as e:
                        out["donest_collection"] = f"FAIL: {e!r}"
                nst: Any = None
                try:
                    nst = n
                    out["nestlist_nesting"] = f"OK: {nst!r}"
                except Exception as e:
                    out["nestlist_nesting"] = f"FAIL: {e!r}"
                if nst is not None:
                    try:
                        nst.SuppressDialogs = True
                        out["nestlist_suppress"] = f"OK: {nst.SuppressDialogs!r}"
                    except Exception as e:
                        out["nestlist_suppress"] = f"FAIL: {e!r}"
                    nl: Any = None
                    try:
                        nl = nst.NewNestList(r"C:\temp\nest_out\nest_full.anl")
                        out["nestlist_new"] = f"OK: {nl!r}"
                    except Exception as e:
                        out["nestlist_new"] = f"FAIL: {e!r}"
                    np: Any = None
                    if nl is not None:
                        try:
                            np = nl.AddFile(r"C:\Users\48797\Documents\Kmil elementy\cz1.ard")
                            out["nestlist_addfile"] = f"OK: {np!r}"
                        except Exception as e:
                            out["nestlist_addfile"] = f"FAIL: {e!r}"
                        try:
                            np.Required = 2
                            out["nestlist_required"] = f"OK: {np.Required!r}"
                        except Exception as e:
                            out["nestlist_required"] = f"FAIL: {e!r}"
                        for attr_name, key, value in (
                            ("TotalTime", "nestlist_total_time", 15),
                            ("OptimiseLevel", "nestlist_opt_level", 1),
                            ("PartGap", "nestlist_part_gap", 5.0),
                            ("EdgeGap", "nestlist_edge_gap", 10.0),
                            ("LeadInGap", "nestlist_lead_gap", 1.5),
                            ("CutWidth", "nestlist_cut_width", 0.0),
                            ("NestingMethod", "nestlist_method", 0),
                            ("OptimiseForCuts", "nestlist_opt_cuts", 0),
                            ("UseSubroutines", "nestlist_subroutines", False),
                            ("PreventApertureNest", "nestlist_no_aperture", True),
                            ("OrderByPart", "nestlist_order_part", False),
                            ("SelectBestSheet", "nestlist_best_sheet", 0),
                        ):
                            try:
                                setattr(nl, attr_name, value)
                                out[key] = f"OK: {getattr(nl, attr_name)!r}"
                            except Exception as e:
                                out[key] = f"FAIL: {e!r}"
                        sl: Any = None
                        try:
                            sl = nst.NewSheetList()
                            out["nestlist_sheetlist"] = f"OK: {sl!r}"
                        except Exception as e:
                            out["nestlist_sheetlist"] = f"FAIL: {e!r}"
                        ns: Any = None
                        if sl is not None:
                            try:
                                ns = sl.Add(paths2.Item(1))
                                out["nestlist_sheet_add"] = f"OK: {ns!r}"
                            except Exception as e:
                                out["nestlist_sheet_add"] = f"FAIL: {e!r}"
                            try:
                                ns.Required = 1
                                ns.Thickness = 18.0
                                out["nestlist_sheet_params"] = (
                                    f"OK: required={ns.Required!r} thickness={ns.Thickness!r}"
                                )
                            except Exception as e:
                                out["nestlist_sheet_params"] = f"FAIL: {e!r}"
                            result: Any = None
                            try:
                                result = nst.Nest(nl, sl)
                                out["nestlist_nest"] = f"OK: {result!r}"
                            except Exception as e:
                                out["nestlist_nest"] = f"FAIL: {e!r}"
                            try:
                                out["nestlist_result_count"] = f"OK: {result.Count}"
                            except Exception as e:
                                out["nestlist_result_count"] = f"FAIL: {e!r}"
                            try:
                                drw4 = com_app.get_active_drawing()
                                out["drawing_after_nestlist"] = (
                                    "OK geometries="
                                    f"{drw4.geometries_count} tool_paths={drw4.tool_paths_count}"
                                )
                            except Exception as e:
                                out["drawing_after_nestlist"] = f"FAIL: {e!r}"
                    try:
                        nst.DeleteAllNestLists()
                        out["nestlist_cleanup"] = "OK"
                    except Exception as e:
                        out["nestlist_cleanup"] = f"FAIL: {e!r}"
        elif app3 is not None:
            n2: Any = None
            try:
                n2 = app3.GetNestInformation()
                out["nest_information"] = f"OK: {n2!r}"
            except Exception as e:
                out["nest_information"] = f"FAIL: {e!r}"
            try:
                sdb = n2.SheetDB
                out["sheetdb_legacy"] = f"OK: {sdb!r}"
                paths = sdb.InsertSheet(0)
                out["sheetdb_insert0"] = f"OK: {paths!r} type={type(paths).__name__}"
            except Exception as e:
                out["sheetdb_insert0"] = f"FAIL: {e!r}"
        else:
            out["sheetdb_insert0"] = "SKIP: nesting and app3 unavailable"
        stl_d: Any = None
        try:
            stl_d = com_app.open_cad_file(r"C:\temp\nest_out\slotted_disk.stl", "stl")
            out["stl_import"] = (
                f"OK geometries={stl_d.geometries_count}" if stl_d else "OK drawing=None"
            )
        except Exception as e:
            out["stl_import"] = f"FAIL: {e!r}"
        if stl_d is not None:
            try:
                stl_d._drw.SetGeosSelected(True)  # type: ignore[attr-defined]
                out["stl_select"] = "OK"
            except Exception as e:
                out["stl_select"] = f"FAIL: {e!r}"
            for stl_type in (0, 1, 2):
                try:
                    stl_d._drw.SaveStlFile(  # type: ignore[attr-defined]
                        rf"C:\temp\nest_out\stl_t{stl_type}.stl", stl_type, 0.1
                    )
                    out[f"stl_export_t{stl_type}"] = "OK"
                except Exception as e:
                    out[f"stl_export_t{stl_type}"] = f"FAIL: {e!r}"
            try:
                stl_d._drw.SetGeosSelected(False)  # type: ignore[attr-defined]
                out["stl_deselect"] = "OK"
            except Exception as e:
                out["stl_deselect"] = f"FAIL: {e!r}"

        return out

    def _cdm_automation_manager(self) -> Any:
        """Return the IAutomationManager via GetAutomationManagerAddInGUI (headless-safe)."""
        import pythoncom  # type: ignore[import-untyped]
        import win32com.client as w32  # type: ignore[import-untyped]

        from alphacam_cli.gateway.server import _app as com_app

        clsid = pythoncom.MakeIID("{39BFE38A-D3E4-43EA-89D0-584C776B97A9}")
        ai = w32.Dispatch(
            pythoncom.CoCreateInstance(clsid, None, pythoncom.CLSCTX_ALL, pythoncom.IID_IDispatch)
        )
        raw = getattr(com_app, "_app", None) or getattr(com_app, "raw_dispatch", None)
        addins = ai.GetAddInsInterface(raw)
        return addins.GetAutomationManagerAddInGUI()

    def _cdm_known_door_types(self, am: Any) -> set[str]:
        types: set[str] = set()
        try:
            jobs = am.Jobs
            for i in range(1, int(jobs.Count) + 1):
                try:
                    details = jobs.Item(i).CDMOrderDetails
                except Exception:
                    continue
                for di in range(1, int(details.Count) + 1):
                    try:
                        types.add(str(details.Item(di).TypeName))
                    except Exception:
                        continue
        except Exception:
            pass
        return types

    def _handler_run_cdm(self, params: dict[str, Any]) -> dict[str, Any]:
        job_name = str(params.get("job_name", "")).strip()
        if not job_name:
            raise COMError("cdm: job_name is required")
        type_name = str(params.get("type_name", "")).strip()
        if not type_name:
            raise COMError("cdm: type_name is required")
        width = float(params.get("width", 400))
        length = float(params.get("length", 300))
        quantity = int(params.get("quantity", 1))
        bypass_nest = bool(params.get("bypass_nest", False))
        try:
            am = self._cdm_automation_manager()
        except Exception as e:
            raise COMError(f"cdm: automation manager unavailable: {e}") from e
        try:
            job = am.NewCDMJob()
            job.JobName = job_name
            job.SaveToDatabase()
        except Exception as e:
            raise COMError(f"cdm: create job failed: {e}") from e
        try:
            detail = job.AddCDMOrderDetail(type_name)
        except Exception as e:
            if type_name not in self._cdm_known_door_types(am):
                raise COMError(f"cdm: door type not found: {type_name}") from e
            raise COMError(f"cdm: add order detail failed: {e}") from e
        try:
            detail.Width = width
            detail.Length = length
            detail.Quantity = quantity
            detail.ByPassNest = bypass_nest
            detail.SaveToDatabase()
        except Exception as e:
            raise COMError(f"cdm: save order detail failed: {e}") from e
        return {
            "success": True,
            "job_name": job_name,
            "type_name": type_name,
            "width": width,
            "length": length,
            "quantity": quantity,
        }

    def _door_type_name(self, row: dict[str, Any]) -> str:
        for key in ("TypeName", "Name", "DoorTypeName"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for value in row.values():
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _vdb5_door_type_names(self) -> tuple[list[str], bool]:
        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "..",
            "..",
            "scripts",
            "vdb5_door_types.ps1",
        )
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                return [], False
            rows = json.loads(proc.stdout)
        except Exception as e:
            self._logger.warning("cdm types: vdb5 read failed: %r", e)
            return [], False
        if not isinstance(rows, list):
            if isinstance(rows, dict) and isinstance(rows.get("value"), list):
                rows = rows["value"]
            elif isinstance(rows, dict):
                rows = [rows]
            else:
                return [], False
        names: list[str] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = self._door_type_name(row)
            if name and "do not delete" not in name.lower():
                names.append(name)
        return names, True

    def _handler_cdm_types(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            am = self._cdm_automation_manager()
        except Exception as e:
            raise COMError(f"cdm: automation manager unavailable: {e}") from e
        com_names: list[str] = []
        seen: set[str] = set()
        try:
            jobs = am.Jobs
            for i in range(1, int(jobs.Count) + 1):
                try:
                    details = jobs.Item(i).CDMOrderDetails
                except Exception:
                    continue
                for di in range(1, int(details.Count) + 1):
                    try:
                        name = str(details.Item(di).TypeName)
                    except Exception:
                        continue
                    if name and name.casefold() not in seen:
                        seen.add(name.casefold())
                        com_names.append(name)
        except Exception as e:
            raise COMError(f"cdm: read door types failed: {e}") from e
        vdb5_names, vdb5_ok = self._vdb5_door_type_names()
        if not vdb5_ok:
            if not com_names:
                return {"types": [], "note": "no CDM door types found"}
            return {
                "types": [{"id": i, "name": name} for i, name in enumerate(com_names, 1)],
                "note": "vdb5 read failed; types from jobs only",
                "source": "com",
            }
        merged: list[str] = []
        merged_seen: set[str] = set()
        for name in [*vdb5_names, *com_names]:
            if name and name.casefold() not in merged_seen:
                merged_seen.add(name.casefold())
                merged.append(name)
        if not merged:
            return {"types": [], "note": "no CDM door types found"}
        return {
            "types": [{"id": i, "name": name} for i, name in enumerate(merged, 1)],
            "source": "vdb5+com",
        }

    def _handler_cdm_jobs(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            am = self._cdm_automation_manager()
        except Exception as e:
            raise COMError(f"cdm: automation manager unavailable: {e}") from e
        jobs_out: list[dict[str, Any]] = []
        try:
            jobs = am.Jobs
            for i in range(1, int(jobs.Count) + 1):
                try:
                    jj = jobs.Item(i)
                    jobs_out.append({"id": i, "name": str(jj.JobName)})
                except Exception:
                    continue
        except Exception as e:
            raise COMError(f"cdm: list jobs failed: {e}") from e
        return {"jobs": jobs_out}

    def _sheet_materials(self) -> dict[str, int]:
        """Material name -> sheet/material ID from SQLite sheet database."""
        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "..",
            "..",
            "scripts",
            "sheet_materials.py",
        )
        try:
            proc = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                return {}
            data = json.loads(proc.stdout)
        except Exception as e:
            self._logger.warning("cdm materials: sheet db read failed: %r", e)
            return {}
        if isinstance(data, dict) and "value" in data:
            data = data["value"]
        if not isinstance(data, dict):
            return {}
        materials: dict[str, int] = {}
        for key in ("sheets", "materials"):
            rows = data.get(key)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = row.get("name")
                mid = row.get("id")
                if not isinstance(name, str) or not name.strip():
                    continue
                if mid is None:
                    continue
                try:
                    mid_int = int(mid)
                except (TypeError, ValueError):
                    continue
                name_key = name.strip()
                if name_key not in materials:
                    materials[name_key] = mid_int
        return materials

    def _vdb5_set_job_material(self, job_name: str, material_id: int) -> bool:
        """Set AM_JobDetails.fkMaterialID for a job by name; True when rows updated."""
        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "..",
            "..",
            "scripts",
            "vdb5_set_job_material.ps1",
        )
        try:
            proc = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    script_path,
                    "-JobName",
                    job_name,
                    "-MaterialID",
                    str(material_id),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
        except Exception as e:
            self._logger.warning("cdm material: vdb5 update failed: %r", e)
            return False
        if proc.returncode != 0:
            self._logger.warning("cdm material: vdb5 update failed: %s", proc.stdout.strip())
            return False
        match = re.search(r"rows:\s*(\d+)", proc.stdout)
        return bool(match and int(match.group(1)) > 0)

    def _handler_cdm_import_csv(self, params: dict[str, Any]) -> dict[str, Any]:
        csv_path = str(params.get("csv", "")).strip()
        if not csv_path:
            raise COMError("cdm: csv path is required")
        job_param = str(params.get("job", "")).strip() or None
        name_param = str(params.get("name", "")).strip() or None
        config_param = str(params.get("config") or "Fronty").strip()
        material_param = str(params.get("material", "")).strip() or None
        if job_param and name_param:
            raise COMError("cdm: --name and --job are mutually exclusive")
        separator = str(params.get("separator", ","))
        has_header = bool(params.get("has_header", False))
        if not os.path.exists(csv_path):
            raise COMError(f"cdm: csv file not found: {csv_path}")
        try:
            with open(csv_path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except UnicodeDecodeError:
            with open(csv_path, encoding="cp1250", errors="replace") as fh:
                text = fh.read()
        rows = list(csv.reader(io.StringIO(text), delimiter=separator))
        material_name = material_param
        if material_name is None:
            for n, row in enumerate(rows, start=1):
                if has_header and n == 1:
                    continue
                if not any(str(cell).strip() for cell in row):
                    continue
                if len(row) > 5 and str(row[5]).strip():
                    material_name = str(row[5]).strip()
                    break
        materials: dict[str, int] = {}
        material_id: int | None = None
        if material_name:
            materials = self._sheet_materials()
            material_id = materials.get(material_name)
            if material_id is None:
                raise COMError(f"cdm: material not found: {material_name}")
        try:
            am = self._cdm_automation_manager()
        except Exception as e:
            raise COMError(f"cdm: automation manager unavailable: {e}") from e
        job: Any = None
        if job_param:
            try:
                jobs = am.Jobs
                for i in range(1, int(jobs.Count) + 1):
                    try:
                        jj = jobs.Item(i)
                    except Exception:
                        continue
                    if str(jj.JobName) == job_param:
                        job = jj
                        break
            except Exception as e:
                raise COMError(f"cdm: import csv failed: {e}") from e
            if job is None:
                raise COMError(f"cdm: job not found: {job_param}")
            job_name = job_param
        else:
            default_job_name = os.path.splitext(os.path.basename(csv_path))[0]
            job_name = (name_param or default_job_name)[:60]
            try:
                job = am.NewCDMJob()
            except Exception as e:
                raise COMError(f"cdm: create job failed: {e}") from e
            job.JobName = job_name
            if config_param:
                try:
                    job.ConfigurationSetting = am.ConfigurationSettings.GetByName(config_param)
                except Exception as e:
                    raise COMError(f"cdm: config not found: {config_param}") from e
            try:
                job.SaveToDatabase()
            except Exception as e:
                raise COMError(f"cdm: create job failed: {e}") from e
        errors: list[str] = []
        if (
            material_name
            and material_id is not None
            and not self._vdb5_set_job_material(job_name, material_id)
        ):
            errors.append(f"job {job_name}: failed to set material")
        items = 0
        for n, row in enumerate(rows, start=1):
            if has_header and n == 1:
                continue
            if not any(str(cell).strip() for cell in row):
                continue
            if len(row) < 5:
                errors.append(f"row {n}: expected at least 5 columns, got {len(row)}")
                continue
            style = str(row[0]).strip()
            if not style:
                errors.append(f"row {n}: style is required")
                continue
            try:
                quantity = int(str(row[1]).strip())
            except ValueError:
                errors.append(f"row {n}: invalid quantity: {row[1]!r}")
                continue
            try:
                width = float(str(row[2]).strip())
            except ValueError:
                errors.append(f"row {n}: invalid width: {row[2]!r}")
                continue
            try:
                length = float(str(row[3]).strip())
            except ValueError:
                errors.append(f"row {n}: invalid length: {row[3]!r}")
                continue
            design_dims = str(row[4]).strip()
            try:
                detail = job.AddCDMOrderDetail(style)
            except Exception:
                errors.append(f"row {n}: door type not found: {style}")
                continue
            detail.Width = width
            detail.Length = length
            detail.Quantity = quantity
            if design_dims:
                parts = [p for p in design_dims.split(";") if p != ""]
                if len(parts) < 50:
                    parts += ["0"] * (50 - len(parts))
                detail.UserVariableString = ";".join(parts)
            try:
                detail.SaveToDatabase()
            except Exception as e:
                errors.append(f"row {n}: save order detail failed: {e}")
                continue
            items += 1
        if material_name is None:
            errors.append(f"job {job_name}: no material set (required for processing)")
        return {
            "success": items > 0,
            "job_name": job_name,
            "items": items,
            "material": material_name,
            "errors": errors,
        }

    def _handler_cdm_delete_job(self, params: dict[str, Any]) -> dict[str, Any]:
        job_name = str(params.get("job_name", "")).strip()
        if not job_name:
            raise COMError("cdm: job_name is required")
        try:
            am = self._cdm_automation_manager()
        except Exception as e:
            raise COMError(f"cdm: automation manager unavailable: {e}") from e
        job: Any = None
        try:
            jobs = am.Jobs
            for i in range(1, int(jobs.Count) + 1):
                try:
                    jj = jobs.Item(i)
                except Exception:
                    continue
                if str(jj.JobName) == job_name:
                    job = jj
                    break
        except Exception as e:
            raise COMError(f"cdm: delete job failed: {e}") from e
        if job is None:
            raise COMError(f"cdm: job not found: {job_name}")
        if not hasattr(job, "DeleteFromDB"):
            raise COMError("cdm: DeleteFromDB unavailable on job")
        try:
            job.DeleteFromDB()
        except Exception as e:
            raise COMError(f"cdm: delete job failed: {e}") from e
        return {"success": True, "job_name": job_name}

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

    def _handler_drawing_parametric(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        width = float(params.get("width", 0))
        height = float(params.get("height", 0))
        if width <= 0 or height <= 0:
            raise COMError("width and height must be positive numbers")
        offset = float(params.get("offset", 50))
        fillet = float(params.get("fillet", 5))
        depth = params.get("depth")
        depth_val = float(depth) if depth is not None else None
        if depth_val is not None and depth_val >= 0:
            raise COMError("depth must be negative")
        tool = params.get("tool")
        tool_val = str(tool) if tool else None
        spindle = params.get("spindle")
        spindle_val = int(spindle) if spindle is not None else None
        feed = params.get("feed")
        feed_val = float(feed) if feed is not None else None
        down_feed = params.get("down_feed")
        down_feed_val = float(down_feed) if down_feed is not None else None

        drw = com_app.create_temp_drawing()
        if drw is None:
            raise COMError("Failed to create drawing")
        outer, inner = drw.create_panel(width, height, offset, fillet)
        if depth_val is not None:
            if tool_val:
                com_app.select_tool(tool_val)
            md = com_app.create_mill_data()
            md.safe_rapid_level = 10.0
            md.rapid_down_to = 2.0
            md.material_top = 0.0
            md.final_depth = depth_val
            if spindle_val is not None:
                md.spindle_speed = spindle_val
            if feed_val is not None:
                md.cut_feed = feed_val
            if down_feed_val is not None:
                md.down_feed = down_feed_val
            for path in (outer, inner):
                path.selected = True
                md.rough_finish()
                path.selected = False
        drw.zoom_all()
        return {
            "success": True,
            "geometries_count": drw.geometries_count,
            "tool_paths_count": drw.tool_paths_count,
            "outer": {"tool_in_out": outer.tool_in_out},
            "inner": {"tool_in_out": inner.tool_in_out},
        }

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

    def _handler_open_cad_file(self, params: dict[str, Any]) -> dict[str, int]:
        from alphacam_cli.gateway.server import _app as com_app

        path = str(params.get("path", ""))
        fmt = str(params.get("fmt", "")).lower()
        if not path:
            raise COMError("path is required")
        if not fmt:
            raise COMError("fmt is required")
        if bool(params.get("cabinets", False)):
            com_app.set_dxf_cabinets(True)
        drw = com_app.open_cad_file(path, fmt, clear=bool(params.get("clear", False)))
        if drw is None:
            raise COMError(f"Failed to open CAD file: {path}")
        return {"geometries_count": drw.geometries_count, "tool_paths_count": drw.tool_paths_count}

    def _handler_export_drawing(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        path = str(params.get("path", ""))
        fmt = str(params.get("fmt", "")).lower()
        if not path:
            raise COMError("path is required")
        if not fmt:
            raise COMError("fmt is required")
        drw = com_app.get_active_drawing()
        if drw is None:
            raise COMError("No active drawing")
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        drw.export(path, fmt)
        return {"success": True, "path": path}

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

    def _handler_mill_saw(self, params: dict[str, Any]) -> dict[str, int]:
        from alphacam_cli.gateway.server import _app as com_app

        drw = com_app.get_active_drawing()
        if drw is None:
            raise COMError("No active drawing")
        if drw.geometries_count == 0:
            raise COMError("No geometries to machine")
        tool = str(params.get("tool", ""))
        if tool:
            if os.path.exists(tool):
                if com_app.select_tool(tool) is None:
                    raise COMError(f"Failed to select tool: {os.path.basename(tool)}")
            else:
                self._handler_select_tool({"name": tool})
        drw.select_all_geometries()
        md = com_app.create_mill_data()
        md.safe_rapid_level = 20.0
        md.rapid_down_to = 2.0
        md.final_depth = float(params.get("depth", -10))
        md.spindle_speed = int(params.get("spindle", 12000))
        md.down_feed = float(params.get("down_feed", 2000))
        md.cut_feed = float(params.get("feed", 3000))
        md.saw_angle = float(params.get("saw_angle", 0))
        md.saw_internal_corners = int(params.get("internal_corners", 1))
        md.saw_external_corners = int(params.get("external_corners", 1))
        md.saw_head_position = int(params.get("head_position", 0))
        md.saw()
        drw.zoom_all()
        return {"tool_paths_count": drw.tool_paths_count}

    def _handler_mill_engrave(self, params: dict[str, Any]) -> dict[str, int]:
        from alphacam_cli.gateway.server import _app as com_app

        drw = com_app.get_active_drawing()
        if drw is None:
            raise COMError("No active drawing")
        if drw.geometries_count == 0:
            raise COMError("No geometries to machine")
        tool = str(params.get("tool", ""))
        if tool:
            if os.path.exists(tool):
                if com_app.select_tool(tool) is None:
                    raise COMError(f"Failed to select tool: {os.path.basename(tool)}")
            else:
                self._handler_select_tool({"name": tool})
        drw.select_all_geometries()
        md = com_app.create_mill_data()
        md.safe_rapid_level = 20.0
        md.rapid_down_to = 2.0
        md.final_depth = float(params.get("depth", -1))
        md.spindle_speed = int(params.get("spindle", 12000))
        md.down_feed = float(params.get("down_feed", 2000))
        md.cut_feed = float(params.get("feed", 3000))
        md.engrave_type = int(params.get("engrave_type", 0))
        md.step_length = float(params.get("step_length", 0.1))
        md.chord_error = float(params.get("chord_error", 0.01))
        md.engrave()
        drw.zoom_all()
        return {"tool_paths_count": drw.tool_paths_count}

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

    def _handler_list_styles(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        styles: list[dict[str, Any]] = []
        styles_dir = os.path.join(com_app.licomdir_path, "Styles")
        for fp in com_app.find_style_files():
            directory = os.path.dirname(fp)
            try:
                rel_dir = os.path.relpath(directory, styles_dir)
            except ValueError:
                rel_dir = "."
            directory_label = "Styles" if rel_dir == "." else os.path.join("Styles", rel_dir)
            size = 0
            with contextlib.suppress(OSError):
                size = int(os.path.getsize(fp))
            styles.append(
                {
                    "name": os.path.basename(fp),
                    "directory": directory_label.replace("\\", "/"),
                    "size": size,
                    "path": fp,
                }
            )
        styles.sort(key=lambda s: (str(s["name"]).lower(), str(s["path"])))
        return {"styles": styles}

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
        sheet_name = str(params.get("sheet_name", ""))
        if not parts:
            raise COMError("parts list is required")
        if bool(params.get("advanced", False)):
            return self._run_nest_advanced(
                params, parts, output_dir, sheet_name, sheet_width, sheet_height
            )
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        drw = com_app.create_temp_drawing()
        if drw is None:
            raise COMError("Failed to create temporary drawing")
        nest_path = os.path.join(output_dir, "nest.anl") if output_dir else "nest.anl"
        try:
            nd = drw.create_nest_data(nest_path)
        except Exception as e:
            raise COMError(f"nest: create_nest_data failed: {e}") from e
        if parts:
            print(f"nest: parts not added via nest list (diagnostic): {parts}")
        if parts and hasattr(nd, "AddPart"):
            try:
                for part in parts:
                    nd.AddPart(str(part.get("name", "")), int(part.get("count", 1)))  # type: ignore[attr-defined]
            except Exception as e:
                raise COMError(f"nest: add_part failed: {e}") from e
        try:
            if sheet_name:
                import win32com.client.gencache as gencache  # type: ignore[import-untyped]

                gencache.EnsureModule("{6702E3DF-142C-4627-8EA2-4C47EBC78441}", 0, 1, 3)
                app = gencache.EnsureDispatch("Ar5axaps.Application")
                try:
                    sheet = app.Nesting.SheetDatabase.FindSheet(sheet_name)
                except Exception as e:
                    raise COMError(f"nest: sheet from library not found: {sheet_name}") from e
                if sheet is None:
                    raise COMError(f"nest: sheet from library not found: {sheet_name}")  # noqa: TRY301
                paths = sheet.InsertInActiveDrawingAtPoint(0.0, 0.0)
                try:
                    thickness = sheet.Thickness.Thickness
                except Exception:
                    thickness = 18.0
                nd.AddSheet(  # type: ignore[attr-defined]
                    paths.Item(1), sheet.Material.Name, thickness, sheet.Quantity
                )
            else:
                sheet_geo = drw.create_rectangle(0, 0, sheet_width, sheet_height)
                nd.AddSheet(sheet_geo.raw_dispatch, "MDF", 18, 1)  # type: ignore[attr-defined]
        except COMError:
            raise
        except Exception as e:
            raise COMError(f"nest: add_sheet failed: {e}") from e
        gap = params.get("gap")
        edge_gap = params.get("edge_gap")
        lead_gap = params.get("lead_gap")
        try:
            if gap is not None:
                nd.Gap = float(gap)  # type: ignore[attr-defined]
            if edge_gap is not None:
                nd.EdgeGap = float(edge_gap)  # type: ignore[attr-defined]
            if lead_gap is not None:
                nd.LeadGap = float(lead_gap)  # type: ignore[attr-defined]
        except Exception as e:
            raise COMError(f"nest: set gaps failed: {e}") from e
        try:
            nd.DoNest()  # type: ignore[attr-defined]
        except Exception as e:
            raise COMError(f"nest: do_nest failed: {e}") from e
        result: dict[str, Any] = {"success": True, "count": 1}
        if parts and not hasattr(nd, "AddPart"):
            result["parts"] = parts
        return result

    def _set_nest_list_options(self, nl: Any, params: dict[str, Any]) -> None:
        gap = params.get("gap")
        for name, prop in _NEST_OPT_PROPERTIES.items():
            value = params.get(name)
            if name == "part_gap" and value is None:
                value = gap
            if value is None:
                continue
            try:
                if name in _NEST_FLOAT_OPTS:
                    setattr(nl, prop, float(value))
                elif name in _NEST_INT_OPTS:
                    setattr(nl, prop, int(value))
                elif name in _NEST_BOOL_OPTS:
                    setattr(nl, prop, bool(value))
            except Exception as e:
                raise COMError(f"nest[advanced]: set option failed ({name}): {e}") from e

    def _run_nest_advanced(
        self,
        params: dict[str, Any],
        parts: list[dict[str, Any]],
        output_dir: str,
        sheet_name: str,
        sheet_width: float,
        sheet_height: float,
    ) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        nest_path = os.path.join(output_dir, "nest_full.anl") if output_dir else "nest_full.anl"
        drw = com_app.create_temp_drawing()
        if drw is None:
            raise COMError("Failed to create temporary drawing")
        import win32com.client.gencache as gencache  # type: ignore[import-untyped]

        try:
            gencache.EnsureModule(_NEST_TYPELIB_GUID, 0, 1, 3)
            app = gencache.EnsureDispatch("Ar5axaps.Application")
            nesting = app.Nesting
        except Exception as e:
            raise COMError(f"nest[advanced]: dispatch failed: {e}") from e
        with contextlib.suppress(Exception):
            nesting.SuppressDialogs = True
        try:
            nl = nesting.NewNestList(nest_path)
        except Exception as e:
            raise COMError(f"nest[advanced]: new_nest_list failed: {e}") from e
        try:
            for part in parts:
                nest_part = nl.AddFile(str(part.get("name", "")))
                nest_part.Required = int(part.get("count", 1))
        except Exception as e:
            raise COMError(f"nest[advanced]: add_file failed: {e}") from e
        self._set_nest_list_options(nl, params)
        try:
            sl = nesting.NewSheetList()
            if sheet_name:
                sheet = nesting.SheetDatabase.FindSheet(sheet_name)
                if sheet is None:
                    raise COMError(  # noqa: TRY301
                        f"nest[advanced]: sheet from library not found: {sheet_name}"
                    )
                paths = sheet.InsertInActiveDrawingAtPoint(0.0, 0.0)
                nest_sheet = sl.Add(paths.Item(1))
                try:
                    nest_sheet.Thickness = float(sheet.Thickness.Thickness)
                except Exception:
                    nest_sheet.Thickness = 18.0
            else:
                sheet_geo = drw.create_rectangle(0, 0, sheet_width, sheet_height)
                nest_sheet = sl.Add(sheet_geo.raw_dispatch)
                nest_sheet.Thickness = 18.0
            nest_sheet.Required = 1
        except COMError:
            raise
        except Exception as e:
            raise COMError(f"nest[advanced]: add_sheet failed: {e}") from e
        try:
            result = nesting.Nest(nl, sl)
        except Exception as e:
            raise COMError(f"nest[advanced]: nest failed: {e}") from e
        finally:
            with contextlib.suppress(Exception):
                nesting.DeleteAllNestLists()
        return {"success": True, "count": int(result.Count), "parts": parts}

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
