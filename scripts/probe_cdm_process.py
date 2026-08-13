"""Probe harness for AlphaCAM Automation Manager job.Process() hang diagnosis.

Runs in Session 0 as SYSTEM via a scheduled task - separate process with its own
watchdog, so it can never block the gateway service. A threading watchdog calls
os._exit(2) on hang; a missing "call_returned" key in the JSON output is the hang
signal (the process was killed mid-call).

The probe does NOT create a new job - it reads an existing CDM job from the
Automation Manager database (default name "Zamowienie Test 01") and dumps it
before/after each call: job properties, ConfigurationSetting, Customer,
JobFiles, CDMOrderDetails and NestMaterialDatabaseSheet(s). A nesting_diag
section probes app.Nesting / SheetDatabase / FindSheet("MDF_18") reachability
(requires gencache.EnsureModule of the Nesting typelib first). --watch-windows
logs Acam.exe top-level window titles every 3s plus NEW WINDOW / WINDOW GONE
transitions (Session 0 windows are invisible, so no IsWindowVisible filter) -
a modal WPF processing dialog would show up as a NEW WINDOW line while
Process() raises.

Usage (machine):
    python C:/temp/probe_cdm_process.py --job "Zamowienie Test 01" --method all --watch-windows
    python C:/temp/probe_cdm_process.py --method process --timeout 120 --watch-windows
    python C:/temp/probe_cdm_process.py --method populate

--method sequence (each call is timed separately and dumped to JSON):
    populate          job.PopulateJobDetails() - fully populates Job/JobFiles data
    run               am.Run() - Automation Manager "process all" entry point
    process           job.Process() - raises the UserInteractive modal-dialog
                      InvalidOperationException in Session 0
    process-flags     config.DisableScreenUpdates=True and
                      config.ReportsSilentReportGeneration=True before Process()
                      (memory only, no SaveToDatabase), originals restored
    process-material  job.NestMaterialDatabaseSheet = SheetDatabase.FindSheet(
                      "MDF_18") before Process() (Nesting typelib via gencache;
                      falls back to NestMaterialDatabaseSheets)
    process-vba       config.CustomVBAMacro = first .bas/.dvb found under
                      C:/ALPHACAM/LICOMDIR or C:/temp before Process(); aborts
                      with "no macro file found" when no macro file exists
                      (a macro file is never created)
    populate-process  populate then process (recommended first diagnostic run)
    all               populate -> process-flags -> process-material (safest
                      variants first; run/process/process-vba stay explicit;
                      default)

Via schtasks (Session 0, SYSTEM), one command (^ = line continuation):
    schtasks /create /tn cdm_process_probe /tr "python C:/temp/probe_cdm_process.py ^
        --job \"Zamowienie Test 01\" --watch-windows" /sc once /st 23:59 /ru SYSTEM /f
    schtasks /run /tn cdm_process_probe

Outputs:
    C:/temp/probe_cdm_process_out.json  overwritten, UTF-8
    C:/temp/probe_cdm_process.log       appended, timestamp + PID
"""

import argparse
import ctypes
import json
import logging
import os
import subprocess
import threading
import time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from typing import Any

ADDINS_CLSID = "{39BFE38A-D3E4-43EA-89D0-584C776B97A9}"
NESTING_TYPELIB = "{6702E3DF-142C-4627-8EA2-4C47EBC78441}"
SHEET_NAME = "MDF_18"
MACRO_DIRS = (r"C:/ALPHACAM/LICOMDIR", r"C:/temp")
LOG_PATH = Path(r"C:/temp/probe_cdm_process.log")
OUT_PATH = Path(r"C:/temp/probe_cdm_process_out.json")

logger = logging.getLogger("probe_cdm_process")

JOB_PROPS = (
    "JobName",
    "JobDetailID",
    "JobType",
    "IsCDMJob",
    "IsMultipleProcessJob",
    "IsSubProcess",
    "JobSequentialName",
    "JobSequentialNumber",
    "FkCustomerID",
    "FkMachiningOrderID",
    "ProgrammerName",
    "PurchaseOrderNumber",
    "WorkOrderNumber",
    "OrderDate",
    "DueDate",
    "JobDescription",
)

CONFIG_PROPS = (
    "ConfigurationSettingName",
    "ConfigurationSettingID",
    "PostProcessor",
    "DrawingFileOutputLocation",
    "NCFileOutputLocation",
    "ReportFileOutputLocation",
    "NCFileExtension",
    "GenerateNC",
    "GenerateReports",
    "DisableScreenUpdates",
    "CustomVBAMacro",
    "NestingMethod",
    "ReportsSilentReportGeneration",
    "ClearOutputFolders",
    "ReplaceSpaceWithUnderscore",
)

CUSTOMER_PROPS = (
    "CustomerName",
    "CustomerID",
    "ContactName",
    "EmailAddress",
    "TelephoneNumber",
)

JOBFILE_PROPS = (
    "FileName",
    "ActiveInProcess",
    "DoNotMachine",
    "AutoAssociateMaterialName",
    "FkMaterialID",
)

DETAIL_PROPS = (
    "TypeName",
    "TypeID",
    "Quantity",
    "Length",
    "Width",
    "DoorThickness",
    "ActiveInProcess",
    "ByPassNest",
    "NestingPriority",
    "RotationMethod",
    "RotationAngle",
    "ProcessedDate",
    "ProcessedFileFullName",
    "SmallNestPart",
    "HotJob",
    "IgnoreOuterGeometry",
    "CDMOrderDetailID",
    "CDMOrderID",
    "DetailID",
    "FkParentOrderDetailID",
    "UserVariableString",
    "UserVariableDescriptionString",
    "UserStyleName",
    "StyleNumber",
    "CustomerName",
    "OrderDate",
    "DueDate",
    "ReverseMachiningFilename",
)


def convert(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: convert(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [convert(val) for val in value]
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    return str(value)


def dump(out: dict[str, Any]) -> None:
    OUT_PATH.write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )


def dump_props(obj: Any, props: tuple[str, ...]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for prop in props:
        try:
            data[prop] = convert(getattr(obj, prop))
        except Exception as e:
            data[prop] = f"FAIL: {e!r}"
    return data


def dump_configuration_setting(job: Any) -> Any:
    try:
        cs = job.ConfigurationSetting
    except Exception as e:
        return f"FAIL: {e!r}"
    return dump_props(cs, CONFIG_PROPS)


def dump_customer(job: Any) -> Any:
    try:
        customer = job.Customer
    except Exception as e:
        return f"FAIL: {e!r}"
    return dump_props(customer, CUSTOMER_PROPS)


def dump_job_files(job: Any) -> Any:
    try:
        coll = job.JobFiles
        count = int(coll.Count)
    except Exception as e:
        return f"FAIL: {e!r}"
    files: list[dict[str, Any]] = []
    for i in range(1, count + 1):
        entry: dict[str, Any] = {"index": i}
        try:
            f = coll.Item(i)
        except Exception as e:
            entry["item"] = f"FAIL: {e!r}"
            files.append(entry)
            continue
        entry.update(dump_props(f, JOBFILE_PROPS))
        files.append(entry)
    return {"count": count, "files": files}


def dump_cdm_order_details(job: Any) -> Any:
    try:
        coll = job.CDMOrderDetails
        count = int(coll.Count)
    except Exception as e:
        return f"FAIL: {e!r}"
    details: list[dict[str, Any]] = []
    for i in range(1, count + 1):
        entry: dict[str, Any] = {"index": i}
        try:
            d = coll.Item(i)
        except Exception as e:
            entry["item"] = f"FAIL: {e!r}"
            details.append(entry)
            continue
        entry.update(dump_props(d, DETAIL_PROPS))
        details.append(entry)
    return {"count": count, "details": details}


def dump_material_sheets(job: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for prop in ("NestMaterialDatabaseSheet", "NestMaterialDatabaseSheets"):
        try:
            value = getattr(job, prop)
        except Exception as e:
            data[prop] = f"FAIL: {e!r}"
            continue
        if value is None:
            data[prop] = None
            continue
        entry: dict[str, Any] = {"com": repr(value)}
        try:
            entry["name"] = convert(value.Name)
        except Exception as e:
            entry["name"] = f"FAIL: {e!r}"
        try:
            entry["id"] = convert(value.Id)
        except Exception as e:
            entry["id"] = f"FAIL: {e!r}"
        data[prop] = entry
    return data


def dump_job(job: Any) -> dict[str, Any]:
    data = dump_props(job, JOB_PROPS)
    data["configuration_setting"] = dump_configuration_setting(job)
    data["customer"] = dump_customer(job)
    data["job_files"] = dump_job_files(job)
    data["cdm_order_details"] = dump_cdm_order_details(job)
    data["material_sheets"] = dump_material_sheets(job)
    return data


def dump_jobs_list(am: Any, out: dict[str, Any]) -> int | None:
    try:
        count = int(am.Jobs.Count)
        out["jobs_count"] = count
        logger.info("Jobs.Count=%d", count)
    except Exception as e:
        out["jobs_count"] = f"FAIL: {e!r}"
        logger.exception("Jobs.Count FAIL")
        return None
    jobs_list: list[dict[str, Any]] = []
    for i in range(1, count + 1):
        entry: dict[str, Any] = {"index": i}
        try:
            j = am.Jobs.Item(i)
        except Exception as e:
            entry["item"] = f"FAIL: {e!r}"
            logger.exception("Jobs.Item(%d) FAIL", i)
            jobs_list.append(entry)
            continue
        try:
            entry["job_name"] = convert(j.JobName)
        except Exception as e:
            entry["job_name"] = f"FAIL: {e!r}"
            logger.exception("Jobs.JobName(%d) FAIL", i)
        try:
            entry["job_detail_id"] = convert(j.JobDetailID)
        except Exception as e:
            entry["job_detail_id"] = f"FAIL: {e!r}"
            logger.exception("Jobs.JobDetailID(%d) FAIL", i)
        try:
            entry["is_cdm_job"] = convert(j.IsCDMJob)
        except Exception as e:
            entry["is_cdm_job"] = f"FAIL: {e!r}"
        jobs_list.append(entry)
    out["jobs_list"] = jobs_list
    return count


def find_job(am: Any, count: int, job_name: str) -> Any:
    target = job_name.casefold()
    for i in range(1, count + 1):
        try:
            j = am.Jobs.Item(i)
        except Exception as e:
            logger.warning("Jobs.Item(%d) FAIL during name scan: %r", i, e)
            continue
        try:
            name = convert(j.JobName)
        except Exception as e:
            logger.warning("Jobs.JobName(%d) FAIL during name scan: %r", i, e)
            continue
        if name.casefold() == target:
            logger.info("job %r matched at index %d", job_name, i)
            return j
    return None


def dump_nesting_diag(app: Any, out: dict[str, Any]) -> None:
    out["nesting_diag"] = {}
    try:
        from win32com.client import gencache

        gencache.EnsureModule(NESTING_TYPELIB, 0, 1, 3)
        out["nesting_diag"]["ensure_module"] = "OK"
    except Exception as e:
        out["nesting_diag"]["ensure_module"] = f"FAIL: {e!r}"
        logger.exception("nesting_diag EnsureModule FAIL")
        return
    try:
        nesting = app.Nesting
        out["nesting_diag"]["nesting"] = repr(nesting)
    except Exception as e:
        out["nesting_diag"]["nesting"] = f"FAIL: {e!r}"
        logger.exception("nesting_diag app.Nesting FAIL")
        return
    try:
        sheet_db = nesting.SheetDatabase
        out["nesting_diag"]["sheet_db"] = repr(sheet_db)
    except Exception as e:
        out["nesting_diag"]["sheet_db"] = f"FAIL: {e!r}"
        logger.exception("nesting_diag SheetDatabase FAIL")
        return
    try:
        sheet = sheet_db.FindSheet(SHEET_NAME)
    except Exception as e:
        out["nesting_diag"]["find_sheet_mdf18"] = f"FAIL: {e!r}"
        logger.exception("nesting_diag FindSheet FAIL")
        return
    if sheet is None:
        out["nesting_diag"]["find_sheet_mdf18"] = None
        return
    entry: dict[str, Any] = {"com": repr(sheet)}
    try:
        entry["name"] = convert(sheet.Name)
    except Exception as e:
        entry["name"] = f"FAIL: {e!r}"
    try:
        entry["id"] = convert(sheet.Id)
    except Exception as e:
        entry["id"] = f"FAIL: {e!r}"
    out["nesting_diag"]["find_sheet_mdf18"] = entry


def _find_macro_files() -> list[str]:
    found: list[str] = []
    for directory in MACRO_DIRS:
        root = Path(directory)
        if not root.is_dir():
            continue
        for pattern in ("*.bas", "*.dvb"):
            for path in sorted(root.glob(pattern)):
                found.append(str(path))
    return found


def _process_with_flags(job: Any) -> dict[str, Any]:
    steps: dict[str, Any] = {}
    try:
        config = job.ConfigurationSetting
        steps["configuration_setting"] = "OK"
    except Exception as e:
        steps["configuration_setting"] = f"FAIL: {e!r}"
        steps["error"] = "ConfigurationSetting unavailable - Process() not attempted"
        return steps
    old_values: dict[str, Any] = {}
    for prop in ("DisableScreenUpdates", "ReportsSilentReportGeneration"):
        try:
            old_values[prop] = convert(getattr(config, prop))
            steps[f"old_{prop}"] = old_values[prop]
        except Exception as e:
            old_values[prop] = None
            steps[f"old_{prop}"] = f"FAIL: {e!r}"
    for prop in ("DisableScreenUpdates", "ReportsSilentReportGeneration"):
        try:
            setattr(config, prop, True)
            steps[f"set_{prop}"] = True
        except Exception as e:
            steps[f"set_{prop}"] = f"FAIL: {e!r}"
    try:
        job.Process()
        steps["process"] = "OK"
    except Exception as e:
        steps["process"] = f"FAIL: {e!r}"
        logger.exception("Process() FAIL (process-flags)")
    for prop, value in old_values.items():
        try:
            setattr(config, prop, value)
            steps[f"restore_{prop}"] = True
        except Exception as e:
            steps[f"restore_{prop}"] = f"FAIL: {e!r}"
            logger.exception("config.%s restore FAIL", prop)
    return steps


def _process_with_material(job: Any, app: Any) -> dict[str, Any]:
    steps: dict[str, Any] = {}
    try:
        from win32com.client import gencache

        gencache.EnsureModule(NESTING_TYPELIB, 0, 1, 3)
        steps["ensure_module"] = "OK"
    except Exception as e:
        steps["ensure_module"] = f"FAIL: {e!r}"
        steps["error"] = "gencache.EnsureModule failed - Process() not attempted"
        return steps
    try:
        nesting = app.Nesting
        steps["nesting"] = "OK"
    except Exception as e:
        steps["nesting"] = f"FAIL: {e!r}"
        steps["error"] = "app.Nesting unavailable - Process() not attempted"
        return steps
    try:
        sheet_db = nesting.SheetDatabase
        steps["sheet_db"] = "OK"
    except Exception as e:
        steps["sheet_db"] = f"FAIL: {e!r}"
        steps["error"] = "SheetDatabase unavailable - Process() not attempted"
        return steps
    try:
        sheet = sheet_db.FindSheet(SHEET_NAME)
        steps["find_sheet"] = "OK" if sheet is not None else "not found (None)"
    except Exception as e:
        sheet = None
        steps["find_sheet"] = f"FAIL: {e!r}"
    if sheet is None:
        steps["error"] = f"sheet not found in database: {SHEET_NAME} - Process() not attempted"
        return steps
    assigned = False
    for prop in ("NestMaterialDatabaseSheet", "NestMaterialDatabaseSheets"):
        try:
            setattr(job, prop, sheet)
            steps[f"set_{prop}"] = "OK"
            assigned = True
            break
        except Exception as e:
            steps[f"set_{prop}"] = f"FAIL: {e!r}"
            logger.exception("job.%s set FAIL", prop)
    if not assigned:
        steps["error"] = "could not assign material sheet - Process() not attempted"
        return steps
    try:
        job.Process()
        steps["process"] = "OK"
    except Exception as e:
        steps["process"] = f"FAIL: {e!r}"
        logger.exception("Process() FAIL (process-material)")
    return steps


def _process_with_vba(job: Any) -> dict[str, Any]:
    steps: dict[str, Any] = {}
    macros = _find_macro_files()
    steps["macro_files_found"] = macros
    if not macros:
        steps["error"] = "no macro file found"
        logger.warning("no .bas/.dvb macro file found - Process() not attempted")
        return steps
    macro_path = macros[0]
    try:
        config = job.ConfigurationSetting
        steps["configuration_setting"] = "OK"
    except Exception as e:
        steps["configuration_setting"] = f"FAIL: {e!r}"
        steps["error"] = "ConfigurationSetting unavailable - Process() not attempted"
        return steps
    old_macro: Any = ""
    try:
        old_macro = convert(config.CustomVBAMacro)
        steps["old_custom_vba_macro"] = old_macro
    except Exception as e:
        steps["old_custom_vba_macro"] = f"FAIL: {e!r}"
    try:
        config.CustomVBAMacro = macro_path
        steps["set_custom_vba_macro"] = macro_path
    except Exception as e:
        steps["set_custom_vba_macro"] = f"FAIL: {e!r}"
        steps["error"] = "CustomVBAMacro set failed - Process() not attempted"
        return steps
    try:
        job.Process()
        steps["process"] = "OK"
    except Exception as e:
        steps["process"] = f"FAIL: {e!r}"
        logger.exception("Process() FAIL (process-vba)")
    try:
        config.CustomVBAMacro = old_macro
        steps["restore_custom_vba_macro"] = True
    except Exception as e:
        steps["restore_custom_vba_macro"] = f"FAIL: {e!r}"
    return steps


def probe_call(name: str, fn: Any, out: dict[str, Any], watch_windows: bool = False) -> None:
    entry: dict[str, Any] = {"call_started": datetime.now().isoformat(timespec="seconds")}
    out["calls"][name] = entry
    dump(out)
    watcher_started = False
    if watch_windows:
        watcher_started = _watch_acam_windows()
    started = time.monotonic()
    logger.info("%s started", name)
    try:
        result = fn()
        entry["call_returned"] = datetime.now().isoformat(timespec="seconds")
        entry["duration_s"] = round(time.monotonic() - started, 3)
        entry["result"] = convert(result)
        logger.info("%s returned (duration_s=%s)", name, entry["duration_s"])
    except Exception as e:
        entry["call_returned"] = datetime.now().isoformat(timespec="seconds")
        entry["duration_s"] = round(time.monotonic() - started, 3)
        entry["error"] = f"{type(e).__name__}: {e}"
        logger.exception("%s FAIL", name)
    finally:
        if watcher_started:
            logger.info("WATCH STOP")


def _get_acam_pid() -> int | None:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Acam.exe", "/FO", "CSV"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return None
    pids: list[int] = []
    for line in result.stdout.splitlines()[1:]:
        fields = line.split(",")
        if len(fields) < 2:
            continue
        try:
            pids.append(int(fields[1].strip('"')))
        except ValueError:
            continue
    return max(pids) if pids else None


def _window_watcher(target_pid: int) -> None:
    # Windows-only API; absent from ctypes stubs on non-Windows
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    windows: list[tuple[int, str, str]] = []
    prev_windows: list[tuple[int, str, str]] = []
    prev_hwnds: set[int] = set()

    def _cb(hwnd: int, lparam: int) -> bool:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value != target_pid:
            return True
        cls_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls_buf, 256)
        length = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
        windows.append((hwnd, cls_buf.value, title))
        return True

    callback = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(_cb)  # type: ignore[attr-defined]  # Windows-only API
    while True:
        time.sleep(3)
        windows.clear()
        user32.EnumWindows(callback, 0)
        current_hwnds = {hwnd for hwnd, _, _ in windows}
        for hwnd, cls, title in windows:
            if hwnd not in prev_hwnds:
                logger.info("NEW WINDOW: hwnd=%d class=%r title=%r", hwnd, cls, title)
        for hwnd, cls, title in prev_windows:
            if hwnd not in current_hwnds:
                logger.info("WINDOW GONE: hwnd=%d class=%r title=%r", hwnd, cls, title)
        prev_windows = list(windows)
        prev_hwnds = current_hwnds
        logger.info("WINDOWS: n=%d titles=%r", len(windows), windows)


def _watch_acam_windows() -> bool:
    pid = _get_acam_pid()
    if pid is None:
        logger.info("WINDOW WATCH: Acam.exe PID not found")
        return False
    logger.info("WINDOW WATCH start (pid=%d)", pid)
    threading.Thread(target=_window_watcher, args=(pid,), daemon=True).start()
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe AlphaCAM Automation Manager job.Process() hang in Session 0"
    )
    parser.add_argument(
        "--job",
        default="Zamowienie Test 01",
        help="existing job name to find in the Automation Manager database (default: "
        "Zamowienie Test 01)",
    )
    parser.add_argument(
        "--method",
        choices=(
            "populate",
            "run",
            "process",
            "process-flags",
            "process-material",
            "process-vba",
            "populate-process",
            "all",
        ),
        default="all",
        help="which calls to probe: populate | run | process | process-flags | "
        "process-material | process-vba | populate-process | all (default: all "
        "= populate -> process-flags -> process-material; run/process/process-"
        "vba run only when requested)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=90,
        help="watchdog timeout in seconds (default: 90)",
    )
    parser.add_argument(
        "--watch-windows",
        action="store_true",
        help="log Acam.exe window titles every 3s plus NEW WINDOW/WINDOW GONE "
        "transitions during the COM calls",
    )
    args = parser.parse_args()

    logging.basicConfig(
        filename=LOG_PATH,
        filemode="a",
        level=logging.INFO,
        format="%(asctime)s PID=%(process)d %(message)s",
        encoding="utf-8",
    )

    out: dict[str, Any] = {
        "variant": "probe_cdm_process",
        "job_name": args.job,
        "method": args.method,
        "timeout": args.timeout,
        "watch_windows": args.watch_windows,
    }
    logger.info(
        "start variant=probe_cdm_process job=%s method=%s timeout=%d watch_windows=%s",
        args.job,
        args.method,
        args.timeout,
        args.watch_windows,
    )
    dump(out)

    import pythoncom
    import win32com.client as w32

    try:
        pythoncom.CoInitialize()
        out["coinitialize"] = True
        logger.info("CoInitialize OK")
    except Exception as e:
        out["coinitialize"] = f"FAIL: {e!r}"
        logger.exception("CoInitialize FAIL")

    watchdog = threading.Timer(args.timeout, lambda: os._exit(2))
    watchdog.daemon = True
    watchdog.start()
    logger.info("watchdog armed (%ds)", args.timeout)

    app: Any = None
    try:
        app = w32.Dispatch("Ar5axaps.Application")
        out["alphacam_app"] = "OK"
        logger.info("Dispatch Ar5axaps.Application OK")
    except Exception as e:
        out["alphacam_app"] = f"FAIL: {e!r}"
        logger.exception("Dispatch Ar5axaps.Application FAIL")
    dump(out)

    if app is not None:
        dump_nesting_diag(app, out)
        dump(out)

    ai: Any = None
    if app is not None:
        try:
            clsid = pythoncom.MakeIID(ADDINS_CLSID)
            raw = pythoncom.CoCreateInstance(
                clsid, None, pythoncom.CLSCTX_ALL, pythoncom.IID_IDispatch
            )
            ai = w32.Dispatch(raw)
            out["addins_interface"] = "OK"
            logger.info("AddInsInterface OK")
        except Exception as e:
            out["addins_interface"] = f"FAIL: {e!r}"
            logger.exception("AddInsInterface FAIL")
    dump(out)

    addins: Any = None
    if ai is not None:
        try:
            addins = ai.GetAddInsInterface(app)
            out["get_addins"] = "OK"
            logger.info("GetAddInsInterface OK")
        except Exception as e:
            out["get_addins"] = f"FAIL: {e!r}"
            logger.exception("GetAddInsInterface FAIL")
    dump(out)

    am: Any = None
    if addins is not None:
        try:
            am = addins.GetAutomationManagerAddInGUI()
            out["automation_manager"] = "OK"
            logger.info("GetAutomationManagerAddInGUI OK")
        except Exception as e:
            out["automation_manager"] = f"FAIL: {e!r}"
            logger.exception("GetAutomationManagerAddInGUI FAIL")
    dump(out)

    if am is None:
        out["error"] = "Automation Manager not available - cannot proceed"
        logger.error("Automation Manager not available - cannot proceed")
        dump(out)
        logger.info("finished with error")
        return

    try:
        out["cdm_authorised"] = bool(am.IsCDMAuthorised())
        logger.info("IsCDMAuthorised=%s", out["cdm_authorised"])
    except Exception as e:
        out["cdm_authorised"] = f"FAIL: {e!r}"
        logger.exception("IsCDMAuthorised FAIL")
    dump(out)

    count = dump_jobs_list(am, out)
    dump(out)
    if count is None:
        out["error"] = "Jobs collection unavailable - cannot proceed"
        dump(out)
        logger.info("finished with error")
        return

    job = find_job(am, count, args.job)
    if job is None:
        out["error"] = f"job not found by name: {args.job}"
        logger.error("job not found by name: %s", args.job)
        dump(out)
        logger.info("finished with error")
        return

    out["job_found"] = True
    out["job_before"] = dump_job(job)
    dump(out)
    logger.info("job dump (before) written")

    out["calls"] = {}
    dump(out)

    if args.method in ("populate", "populate-process", "all"):
        probe_call("populate", lambda: job.PopulateJobDetails(), out)
        out["job_after_populate"] = dump_job(job)
        dump(out)
        logger.info("job dump (after populate) written")

    if args.method == "run":
        probe_call("run", lambda: am.Run(), out, watch_windows=args.watch_windows)
        out["job_after_run"] = dump_job(job)
        dump(out)
        logger.info("job dump (after run) written")

    if args.method in ("process", "populate-process"):
        probe_call("process", lambda: job.Process(), out, watch_windows=args.watch_windows)
        out["job_after_process"] = dump_job(job)
        dump(out)
        logger.info("job dump (after process) written")

    if args.method in ("process-flags", "all"):
        probe_call(
            "process-flags",
            lambda: _process_with_flags(job),
            out,
            watch_windows=args.watch_windows,
        )
        out["job_after_process-flags"] = dump_job(job)
        dump(out)
        logger.info("job dump (after process-flags) written")

    if args.method in ("process-material", "all"):
        probe_call(
            "process-material",
            lambda: _process_with_material(job, app),
            out,
            watch_windows=args.watch_windows,
        )
        out["job_after_process-material"] = dump_job(job)
        dump(out)
        logger.info("job dump (after process-material) written")

    if args.method == "process-vba":
        probe_call(
            "process-vba",
            lambda: _process_with_vba(job),
            out,
            watch_windows=args.watch_windows,
        )
        out["job_after_process-vba"] = dump_job(job)
        dump(out)
        logger.info("job dump (after process-vba) written")

    dump(out)
    logger.info("finished")


if __name__ == "__main__":
    main()
