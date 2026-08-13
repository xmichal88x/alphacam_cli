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

from alphacam_cli.core import cdm_db
from alphacam_cli.core.application import _validate_due_date
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
_MACHINE_KEYS = frozenset({"psexec", "psexec_args", "cscript", "use_shell"})
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


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
    elif isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("1", "true", "yes", "on"):
            return True
        if normalized in ("0", "false", "no", "off", ""):
            return False
    if value is not None:
        logging.getLogger("alphacam.gateway").warning(
            "ambiguous boolean value %r treated as False", value
        )
    return False


_FIELD_SETTERS: dict[str, str] = {
    "door_customer_name": "CSV_CustomerName",
    "door_order_number": "CSV_OrderNumber",
    "door_item_number": "CSV_ItemNumber",
    "door_production_comment": "ProductionComment",
    "door_rotation_method": "RotationMethod",
    "door_rotation_angle": "RotationAngle",
    "door_nest_priority": "NestingPriority",
    "door_small_nest": "SmallNestPart",
}
_FIELD_SETTERS.update({f"door_custom_field_{n}": f"CustomField{n}" for n in range(1, 26)})

_DETAIL_VALUE_KEYS: dict[str, str] = dict(cdm_db.MAPPED_FIELD_TARGETS)


def _resolve_cdm_import_setting(import_setting: str | int | None) -> dict[str, Any]:
    if isinstance(import_setting, str) and import_setting.isdigit():
        import_setting = int(import_setting)
    settings = cdm_db.import_settings()
    setting = (
        cdm_db.find_import_setting(settings, import_setting) if import_setting is not None else None
    )
    if setting is None and import_setting is None:
        setting = next(
            (s for s in settings if bool(s.get("selected")) and bool(s.get("is_cdm_import"))),
            None,
        )
    if setting is None:
        if import_setting is not None:
            raise COMError(f"cdm: import settings not found: {import_setting}")
        available = ", ".join(
            f"{s.get('id')} '{s.get('name')}'" for s in settings if bool(s.get("is_cdm_import"))
        )
        raise COMError(
            "cdm: no import setting selected; pass --import-setting or select one in "
            "Automation Manager" + (f" (available: {available})" if available else "")
        )
    if not bool(setting.get("is_cdm_import")):
        name = setting.get("name") or import_setting
        raise COMError(f"cdm: import settings '{name}' is not a CDM import setting")
    return setting


def _detail_field_value(detail: dict[str, Any], field: str) -> Any:
    if field.startswith("door_custom_field_"):
        return detail.get("custom_fields", {}).get(field.removeprefix("door_custom_field_"))
    key = _DETAIL_VALUE_KEYS.get(field)
    if key is None:
        return None
    return detail.get(key)


def _cdm_material_name(details: list[dict[str, Any]], material: str | None) -> str | None:
    """Material name from the explicit arg, detail material, or job_material_id (524).

    job_material_id (524) carries the material NAME (like door_material),
    not the database id.
    """
    name = (material or "").strip() or None
    if name is not None:
        return name
    for detail in details:
        raw = detail.get("material")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    for detail in details:
        raw = detail.get("job_material_id")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _cdm_job_name(details: list[dict[str, Any]], name: str | None, csv: str) -> str:
    explicit = (name or "").strip()
    if explicit:
        return explicit[:60]
    for detail in details:
        raw = detail.get("job_name")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()[:60]
    return os.path.splitext(os.path.basename(csv))[0][:60]


def _cdm_config_name(details: list[dict[str, Any]], config: str | None) -> str | None:
    explicit = (config or "").strip()
    if explicit:
        return explicit
    for detail in details:
        raw = detail.get("job_config_id")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _cdm_apply_detail_fields(
    detail: Any, d: dict[str, Any], errors: list[str], row_no: int
) -> None:
    for field, setter in _FIELD_SETTERS.items():
        value = _detail_field_value(d, field)
        if value is None:
            continue
        try:
            setattr(detail, setter, value)
        except Exception as e:
            errors.append(f"row {row_no}: {setter} failed: {e}")


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
            from win32com.client import gencache  # type: ignore[import-untyped]

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
                    ac_app = gencache.EnsureDispatch(ac_app)
                    break
                except Exception:
                    try:
                        ac_app = gencache.EnsureDispatch(pid)
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

    def _watchdog_arm(self, seconds: float, label: str) -> threading.Timer:
        timer = threading.Timer(seconds, self._watchdog_fire, args=(label, seconds))
        timer.daemon = True
        timer.start()
        return timer

    def _watchdog_fire(self, label: str, seconds: float) -> None:
        self._logger.critical("WATCHDOG: %s exceeded %.0fs — forcing service exit", label, seconds)
        os._exit(1)

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

    def _handler_drawing_query(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        file = str(params.get("file", ""))
        if not file:
            raise COMError("file is required")
        drw = com_app.get_active_drawing()
        if drw is None:
            raise COMError("No active drawing")
        try:
            count = drw.run_query(file)
        except Exception as e:
            raise COMError(f"drawing query failed: {e}") from e
        return {"success": True, "count": int(count)}

    def _cdm_automation_manager(self) -> Any:
        import time

        import pythoncom  # type: ignore[import-untyped]
        import win32com.client as w32  # type: ignore[import-untyped]
        from win32com.client import gencache  # type: ignore[import-untyped]

        clsid = pythoncom.MakeIID("{39BFE38A-D3E4-43EA-89D0-584C776B97A9}")
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                app = gencache.EnsureDispatch("Ar5axaps.Application")
                ai = w32.Dispatch(
                    pythoncom.CoCreateInstance(
                        clsid, None, pythoncom.CLSCTX_ALL, pythoncom.IID_IDispatch
                    )
                )
                addins = ai.GetAddInsInterface(app)
                return addins.GetAutomationManagerAddInGUI()
            except Exception as e:
                last_error = e
                self._logger.warning(
                    "cdm: automation manager attempt %d failed: %s", attempt + 1, e
                )
                if attempt < 2:
                    time.sleep(3)
        raise COMError(f"cdm: automation manager unavailable: {last_error}")

    def _handler_create_cdm_job(self, params: dict[str, Any]) -> dict[str, Any]:
        job_name = str(params.get("job_name") or "").strip()
        if not job_name:
            raise COMError("cdm: job_name is required")
        config = str(params.get("config", "") or "").strip() or None
        material = str(params.get("material", "") or "").strip() or None
        customer = str(params.get("customer", "") or "").strip() or None
        po = str(params.get("po", "") or "").strip() or None
        due_date = str(params.get("due_date", "") or "").strip() or None
        description = str(params.get("description", "") or "").strip() or None
        if due_date is not None:
            try:
                _validate_due_date(due_date)
            except RuntimeError as exc:
                raise COMError(str(exc)) from None
        from alphacam_cli.gateway.server import _app as com_app

        try:
            return com_app.create_cdm_job(  # type: ignore[no-any-return]
                job_name=job_name,
                config=config,
                material=material,
                customer=customer,
                po=po,
                due_date=due_date,
                description=description,
            )
        except Exception as e:
            raise COMError(str(e)) from e

    def _handler_process_cdm_job(self, params: dict[str, Any]) -> dict[str, Any]:
        job_name = str(params.get("job_name") or "").strip() or None
        if not job_name:
            raise COMError("cdm: job_name is required")
        machine = params.get("machine")
        if machine is not None and not isinstance(machine, dict):
            raise COMError("cdm: machine must be a dict")
        if machine is not None:
            machine = {k: v for k, v in machine.items() if k in _MACHINE_KEYS}
            for key in ("psexec", "cscript"):
                if key in machine and not isinstance(machine[key], str):
                    raise COMError(f"cdm: machine.{key} must be a str")
            if "psexec_args" in machine:
                psexec_args = machine["psexec_args"]
                if not isinstance(psexec_args, list) or not all(
                    isinstance(a, str) for a in psexec_args
                ):
                    raise COMError("cdm: machine.psexec_args must be a list of str")
            machine["use_shell"] = False
        timeout_seconds = params.get("timeout_seconds")
        if timeout_seconds is not None and (
            not isinstance(timeout_seconds, int)
            or isinstance(timeout_seconds, bool)
            or timeout_seconds <= 0
        ):
            raise COMError("cdm: timeout_seconds must be a positive int")
        output_root = params.get("output_root")
        if output_root is not None and not isinstance(output_root, str):
            raise COMError("cdm: output_root must be a str")
        method = params.get("method")
        if method is not None and not isinstance(method, str):
            raise COMError("cdm: method must be a str")
        if method is not None and method not in {"inproc", "vbs"}:
            raise COMError("cdm: method must be 'inproc' or 'vbs'")
        from alphacam_cli.gateway.server import _app as com_app

        call_kwargs: dict[str, Any] = {"job_name": job_name}
        if machine is not None:
            call_kwargs["machine"] = machine
        if timeout_seconds is not None:
            call_kwargs["timeout_seconds"] = timeout_seconds
        if output_root is not None:
            call_kwargs["output_root"] = output_root
        if method is not None:
            call_kwargs["method"] = method
        watchdog = self._watchdog_arm(
            max(60.0, float(timeout_seconds or 0)) + 30.0, f"process_cdm_job({job_name})"
        )
        try:
            return com_app.process_cdm_job(**call_kwargs)  # type: ignore[no-any-return]
        except Exception as e:
            raise COMError(str(e)) from e
        finally:
            watchdog.cancel()

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
        vdb5_names, vdb5_ok = cdm_db.vdb5_door_type_names()
        return cdm_db.merge_door_types(com_names, vdb5_names, vdb5_ok)

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

    def _handler_cdm_import_csv(self, params: dict[str, Any]) -> dict[str, Any]:
        csv_path = str(params.get("csv", "")).strip()
        if not csv_path:
            raise COMError("cdm: csv path is required")
        job_param = str(params.get("job") or "").strip() or None
        name_param = str(params.get("name", "")).strip() or None
        config_param = str(params.get("config") or "").strip()
        material_param = str(params.get("material", "")).strip() or None
        if job_param and name_param:
            raise COMError("cdm: --name and --job are mutually exclusive")
        has_header = _as_bool(params.get("has_header"))
        import_setting = params.get("import_setting")
        preview = _as_bool(params.get("preview"))
        if not os.path.exists(csv_path):
            raise COMError(f"cdm: csv file not found: {csv_path}")
        if preview:
            return self._handler_cdm_import_preview(
                {
                    "csv": csv_path,
                    "import_setting": import_setting,
                    "separator": params.get("separator"),
                    "has_header": has_header,
                    "job": job_param,
                    "name": name_param,
                    "config": config_param,
                    "material": material_param,
                }
            )
        sep_param = params.get("separator")
        separator = str(sep_param or "") or None
        return self._import_cdm_csv_mapped(
            csv_path=csv_path,
            job_param=job_param,
            name_param=name_param,
            config_param=config_param,
            material_param=material_param,
            separator=separator,
            has_header=has_header,
            import_setting=import_setting,
        )

    def _import_cdm_csv_mapped(
        self,
        csv_path: str,
        job_param: str | None,
        name_param: str | None,
        config_param: str,
        material_param: str | None,
        separator: str | None,
        has_header: bool,
        import_setting: str | int | None,
    ) -> dict[str, Any]:
        setting = _resolve_cdm_import_setting(import_setting)
        setting_name = str(setting.get("name") or "")
        if job_param is None and not bool(setting.get("create_job")):
            raise COMError(
                f"cdm: job is required (import setting '{setting_name}' does not create jobs)"
            )
        eff_separator = (
            separator if separator is not None else str(setting.get("delimiter_char") or ",")
        )
        try:
            rows = cdm_db.read_cdm_csv(csv_path, eff_separator)
        except Exception as e:
            raise COMError(f"cdm: import csv failed: {e}") from e
        field_map = cdm_db.field_map_from_setting(setting)
        details, errors = cdm_db.parse_cdm_rows_mapped(
            rows, field_map, has_header or bool(setting.get("ignore_header", False))
        )
        material_name = _cdm_material_name(details, material_param)
        defaults: dict[str, Any] | None = None
        materials = cdm_db.sheet_materials()
        material_id: int | None = None
        if material_name:
            material_id = materials.get(material_name)
            if material_id is None:
                raise COMError(f"cdm: material not found: {material_name}")
        else:
            defaults = cdm_db.vdb5_job_defaults()
            material_id = defaults.get("material_id")
        material_label: str | None = material_name
        if material_label is None and material_id is not None:
            material_label = next(
                (n for n, mid in materials.items() if mid == material_id),
                None,
            )
        if not details:
            return {
                "success": False,
                "job_name": job_param or "",
                "items": 0,
                "material": material_label,
                "errors": errors,
                "import_setting": setting_name,
            }
        try:
            am = self._cdm_automation_manager()
        except Exception as e:
            raise COMError(f"cdm: automation manager unavailable: {e}") from e
        job: Any = None
        if job_param:
            try:
                job = cdm_db.find_cdm_job(am, job_param)
            except Exception as e:
                raise COMError(f"cdm: job lookup failed: {e}") from e
            if job is None:
                raise COMError(f"cdm: job not found: {job_param}")
            job_name = job_param
        else:
            config_name = _cdm_config_name(details, config_param)
            if not config_name:
                if defaults is None:
                    defaults = cdm_db.vdb5_job_defaults()
                config_name = str(defaults.get("config_name") or "").strip()
                if not config_name:
                    raise COMError("cdm: no default configuration found")
            job_name = _cdm_job_name(details, name_param, csv_path)
            try:
                job = am.NewCDMJob()
            except Exception as e:
                raise COMError(f"cdm: create job failed: {e}") from e
            job.JobName = job_name
            if config_name:
                try:
                    job.ConfigurationSetting = am.ConfigurationSettings.GetByName(config_name)
                except Exception as e:
                    raise COMError(f"cdm: config not found: {config_name}") from e
            try:
                job.SaveToDatabase()
            except Exception as e:
                raise COMError(f"cdm: create job failed: {e}") from e
        items = 0
        ok_details: list[dict[str, Any]] = []
        for d in details:
            try:
                detail = job.AddCDMOrderDetail(d["style"])
            except Exception:
                errors.append(f"row {d['row']}: door type not found: {d['style']}")
                continue
            try:
                detail.Width = d["width"]
                detail.Length = d["length"]
                detail.Quantity = d["quantity"]
                design_dims = d.get("design_dims")
                if design_dims:
                    parts = [p for p in str(design_dims).split(";") if p != ""]
                    if len(parts) < cdm_db.DESIGN_DIMS_FIELDS:
                        parts += ["0"] * (cdm_db.DESIGN_DIMS_FIELDS - len(parts))
                    detail.UserVariableString = ";".join(parts)
            except Exception as e:
                errors.append(f"row {d['row']}: save order detail failed: {e}")
                continue
            _cdm_apply_detail_fields(detail, d, errors, d["row"])
            try:
                detail.SaveToDatabase()
            except Exception as e:
                errors.append(f"row {d['row']}: save order detail failed: {e}")
                continue
            items += 1
            ok_details.append(d)
        if material_id is not None:
            if not cdm_db.set_job_material(job_name, material_id):
                errors.append(f"job {job_name}: failed to set material")
        elif material_name is None:
            errors.append(f"job {job_name}: no material set (required for processing)")
        if "door_drilling" in field_map.values() and ok_details:
            values = [bool(d.get("has_drilling") or False) for d in ok_details]
            if not cdm_db.set_has_drilling(job_name, values):
                errors.append(f"job {job_name}: failed to set has_drilling")
        if items == 0 and not job_param:
            deleted, reason = cdm_db.cleanup_created_job(
                am,
                job,
                job_name,
                log=lambda msg: self._logger.warning("cdm import: cleanup failed: %s", msg),
            )
            if deleted:
                errors.append(f"job {job_name}: no valid order details, deleted")
            elif reason == "failed":
                errors.append(f"job {job_name}: no valid order details, cleanup failed")
            else:
                errors.append(f"job {job_name}: no valid order details, cleanup unverified")
        return {
            "success": items > 0,
            "job_name": job_name,
            "items": items,
            "material": material_label,
            "errors": errors,
            "import_setting": setting_name,
        }

    def _handler_cdm_import_preview(self, params: dict[str, Any]) -> dict[str, Any]:
        csv_path = str(params.get("csv", "")).strip()
        if not csv_path:
            raise COMError("cdm: csv path is required")
        job_param = str(params.get("job") or "").strip() or None
        name_param = str(params.get("name") or "").strip() or None
        config_param = str(params.get("config") or "").strip()
        material_param = str(params.get("material") or "").strip() or None
        if job_param and name_param:
            raise COMError("cdm: --name and --job are mutually exclusive")
        sep_param = params.get("separator")
        separator = str(sep_param or "") or None
        has_header = _as_bool(params.get("has_header"))
        import_setting = params.get("import_setting")
        if not os.path.exists(csv_path):
            raise COMError(f"cdm: csv file not found: {csv_path}")
        setting = _resolve_cdm_import_setting(import_setting)
        setting_name = str(setting.get("name") or "")
        if job_param is None and not bool(setting.get("create_job")):
            raise COMError(
                f"cdm: job is required (import setting '{setting_name}' does not create jobs)"
            )
        eff_separator = (
            separator if separator is not None else str(setting.get("delimiter_char") or ",")
        )
        try:
            rows = cdm_db.read_cdm_csv(csv_path, eff_separator)
        except Exception as e:
            raise COMError(f"cdm: import csv failed: {e}") from e
        field_map = cdm_db.field_map_from_setting(setting)
        details, errors = cdm_db.parse_cdm_rows_mapped(
            rows, field_map, has_header or bool(setting.get("ignore_header", False))
        )
        defaults = cdm_db.vdb5_job_defaults()
        materials = cdm_db.sheet_materials()
        material_name = _cdm_material_name(details, material_param)
        material_id: int | None = None
        fatal_error = False
        if material_name:
            material_id = materials.get(material_name)
            if material_id is None:
                errors.append(f"cdm: material not found: {material_name}")
                fatal_error = True
        else:
            material_id = defaults.get("material_id")
        job_name = (
            job_param if job_param is not None else _cdm_job_name(details, name_param, csv_path)
        )
        if material_name is None and material_id is None:
            errors.append(f"job {job_name}: no material set (required for processing)")
        elif material_name is None and material_id is not None:
            material_name = next(
                (n for n, mid in materials.items() if mid == material_id),
                None,
            )
        config_name = None
        if not job_param:
            config_name = _cdm_config_name(details, config_param)
            if not config_name:
                config_name = str(defaults.get("config_name") or "").strip() or None
            if not config_name:
                errors.append("cdm: no default configuration found")
                fatal_error = True
        return {
            "success": bool(details) and not fatal_error,
            "setting": {
                "id": setting.get("id"),
                "name": setting.get("name"),
                "delimiter_char": setting.get("delimiter_char"),
                "sub_delimiter_char": setting.get("sub_delimiter_char"),
                "create_job": setting.get("create_job"),
                "selected": setting.get("selected"),
            },
            "field_map": cdm_db.field_map_descriptions(field_map),
            "job_name": job_name,
            "config": config_name,
            "material": material_name,
            "items": len(details),
            "rows": details,
            "errors": errors,
            "job": job_param,
        }

    def _handler_cdm_import_settings(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            settings = cdm_db.import_settings()
        except Exception as e:
            raise COMError(f"cdm: read import settings failed: {e}") from e
        out: list[dict[str, Any]] = []
        for setting in settings:
            field_map = cdm_db.field_map_from_setting(setting)
            out.append(
                {
                    "id": setting.get("id"),
                    "name": setting.get("name"),
                    "selected": setting.get("selected"),
                    "create_job": setting.get("create_job"),
                    "delimiter_char": setting.get("delimiter_char"),
                    "fields_count": len(field_map),
                    "fields": ", ".join(
                        f"{column}→{name}" for column, name in sorted(field_map.items())
                    ),
                }
            )
        return {"settings": out}

    def _handler_cdm_order_details(self, params: dict[str, Any]) -> dict[str, Any]:
        job_name = str(params.get("job_name")) if params.get("job_name") is not None else None
        try:
            return {"order_details": cdm_db.order_details(job_name), "job_name": job_name}
        except Exception as e:
            raise COMError(f"cdm: read order details failed: {e}") from e

    def _handler_cdm_door_paths(self, params: dict[str, Any]) -> dict[str, Any]:
        type_name = str(params.get("type_name")) if params.get("type_name") is not None else None
        try:
            return {"door_paths": cdm_db.door_paths(type_name), "type_name": type_name}
        except Exception as e:
            raise COMError(f"cdm: read door paths failed: {e}") from e

    def _handler_cdm_materials(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            return {"materials": cdm_db.materials()}
        except Exception as e:
            raise COMError(f"cdm: read materials failed: {e}") from e

    def _handler_cdm_configs(self, params: dict[str, Any]) -> dict[str, Any]:
        show = str(params.get("show")) if params.get("show") is not None else None
        try:
            return {"configs": cdm_db.configs(show), "show": show}
        except Exception as e:
            raise COMError(f"cdm: read configs failed: {e}") from e

    def _handler_cdm_lookups(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            return {"lookups": cdm_db.lookups()}
        except Exception as e:
            raise COMError(f"cdm: read lookups failed: {e}") from e

    def _handler_manifest_list(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        data_dir = str(params.get("data_dir")) if params.get("data_dir") else None
        try:
            return com_app.manifest_list(data_dir)  # type: ignore[no-any-return]
        except Exception as e:
            raise COMError(f"manifest: list failed: {e}") from e

    def _handler_manifest_read(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        job_name = str(params.get("job_name") or "").strip()
        if not job_name:
            raise COMError("manifest: job_name required")
        material = str(params.get("material")) if params.get("material") else None
        data_dir = str(params.get("data_dir")) if params.get("data_dir") else None
        try:
            return com_app.manifest_read(job_name, material, data_dir)  # type: ignore[no-any-return]
        except Exception as e:
            raise COMError(f"manifest: read failed: {e}") from e

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
            job = cdm_db.find_cdm_job(am, job_name)
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

        drw = com_app.create_temp_drawing()
        if drw is None:
            raise COMError("Failed to create drawing")
        outer, inner = drw.create_panel(width, height, offset, fillet)
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
        cabinets = _as_bool(params.get("cabinets"))
        if cabinets:
            com_app.set_dxf_cabinets(True)
        drw = com_app.open_cad_file(path, fmt, clear=_as_bool(params.get("clear")))
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

    def _handler_nest_inspect(self, params: dict[str, Any]) -> dict[str, Any]:
        from alphacam_cli.gateway.server import _app as com_app

        try:
            return com_app.nest_inspect()  # type: ignore[no-any-return]
        except Exception as e:
            raise COMError(str(e)) from e

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

        raw_files = params.get("files")
        if not isinstance(raw_files, list):
            raise COMError("batch: invalid files")
        files: list[str] = list(raw_files)
        output_dir = str(params.get("output_dir", ""))
        post = str(params.get("post", ""))
        continue_on_error = _as_bool(params.get("continue_on_error"))
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

        raw_parts = params.get("parts", [])
        if not isinstance(raw_parts, list) or not all(isinstance(p, dict) for p in raw_parts):
            raise COMError("nest: invalid parts")
        parts: list[dict[str, Any]] = list(raw_parts)
        try:
            part_counts = [int(p.get("count", 1)) for p in parts]
        except (TypeError, ValueError):
            raise COMError("nest: invalid part count") from None
        output_dir = str(params.get("output_dir", ""))
        try:
            sheet_width = float(params.get("sheet_width", 2440))
        except (TypeError, ValueError):
            raise COMError("nest: invalid sheet_width") from None
        try:
            sheet_height = float(params.get("sheet_height", 1220))
        except (TypeError, ValueError):
            raise COMError("nest: invalid sheet_height") from None
        sheet_name = str(params.get("sheet_name", ""))
        if not parts:
            raise COMError("parts list is required")
        advanced = _as_bool(params.get("advanced"))
        if advanced:
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
        if parts and hasattr(nd, "AddPart"):
            try:
                for part, count in zip(parts, part_counts, strict=True):
                    nd.AddPart(str(part.get("name", "")), count)  # type: ignore[attr-defined]
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
        count = sum(part_counts)
        result: dict[str, Any] = {"success": True, "count": count}
        save_ard = params.get("save_ard")
        if save_ard:
            save_path = str(save_ard)
            parent = os.path.dirname(save_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            try:
                drw.save_as(save_path)
            except Exception as e:
                raise COMError(f"nest: save_ard failed: {e}") from e
            result["save_ard"] = save_path
        try:
            inspected = com_app.nest_inspect()
            if isinstance(inspected, dict):
                result["nest"] = inspected
        except Exception as e:
            result["nest"] = {"success": False, "error": str(e)}
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
                    setattr(nl, prop, _as_bool(value))
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
            required_counts = [int(part.get("count", 1)) for part in parts]
        except (TypeError, ValueError):
            raise COMError("nest[advanced]: invalid part count") from None
        try:
            for part, required in zip(parts, required_counts, strict=True):
                nest_part = nl.AddFile(str(part.get("name", "")))
                nest_part.Required = required
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
            try:
                count = int(result.Count)
            except (TypeError, AttributeError, ValueError):
                self._logger.warning("nest[advanced]: result.Count unavailable, using count=0")
                count = 0
        except Exception as e:
            raise COMError(f"nest[advanced]: nest failed: {e}") from e
        finally:
            with contextlib.suppress(Exception):
                nesting.DeleteAllNestLists()
        out: dict[str, Any] = {"success": True, "count": count, "parts": parts}
        save_ard = params.get("save_ard")
        if save_ard:
            save_path = str(save_ard)
            parent = os.path.dirname(save_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            try:
                drw.save_as(save_path)
            except Exception as e:
                raise COMError(f"nest[advanced]: save_ard failed: {e}") from e
            out["save_ard"] = save_path
        try:
            inspected = com_app.nest_inspect()
            if isinstance(inspected, dict):
                out["nest"] = inspected
        except Exception as e:
            out["nest"] = {"success": False, "error": str(e)}
        return out

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
