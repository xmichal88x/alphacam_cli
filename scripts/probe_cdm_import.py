"""Probe harness for AlphaCAM CDM CSV import (ImportCSVToJob / CreateJobsFromCSVFile).

Runs in Session 0 as SYSTEM via a scheduled task - separate process with its own
watchdog, so it can never block the gateway service. A threading watchdog calls
os._exit(2) on hang; a missing "call_returned" key in the JSON output is the hang
signal (the process was killed mid-call).

Usage (machine):
    python C:/temp/probe_cdm_import.py --csv C:/temp/test.csv --settings-id 1 --method both
    python C:/temp/probe_cdm_import.py --csv C:/temp/test.csv --settings-name NAME --method both
    python C:/temp/probe_cdm_import.py --method build-settings --settings-id 3 \
        --fields "256,259,257,258,264,512,513,524"

The ImportSettings collection may be selected by index (--settings-id, default 1)
or by exact name (--settings-name; mutually exclusive). The output always includes
a settings_list section (index/name/selected/id) for diagnostics.

--method build-settings edits an existing ImportSettings via the COM API
(NewImportSettingField + FieldsOrder.Add + SaveToDatabase), no GUI. --fields is a
comma-separated list of field types appended after the existing FieldsOrder;
new columns continue from FieldsOrder.Count + 1. No import/bulk runs after a build.

Via schtasks (Session 0, SYSTEM), one command (^ = line continuation):
    schtasks /create /tn cdm_probe /tr "python C:/temp/probe_cdm_import.py --csv C:/temp/t.csv" ^
        /sc once /st 23:59 /ru SYSTEM /f
    schtasks /run /tn cdm_probe

Outputs:
    C:/temp/probe_cdm_import_out.json  overwritten, UTF-8
    C:/temp/probe_cdm_import.log       appended, timestamp + PID
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
LOG_PATH = Path(r"C:/temp/probe_cdm_import.log")
OUT_PATH = Path(r"C:/temp/probe_cdm_import_out.json")

logger = logging.getLogger("probe_cdm_import")


def convert(value: Any) -> Any:
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


def dump_fields_order(fo: Any) -> Any:
    try:
        count = int(fo.Count)
    except Exception as e:
        return f"FAIL(Count): {e!r}"
    fields: list[dict[str, Any]] = []
    for i in range(1, count + 1):
        field: dict[str, Any] = {}
        try:
            f = fo.Item(i)
        except Exception as e:
            field["item"] = f"FAIL: {e!r}"
            fields.append(field)
            continue
        for prop in ("ColumnNumber", "Type", "FieldID"):
            try:
                field[prop] = convert(getattr(f, prop))
            except Exception as e:
                field[prop] = f"FAIL: {e!r}"
        fields.append(field)
    return fields


def dump_setting(s: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for prop in (
        "Name",
        "IsCDMImport",
        "IgnoreHeader",
        "DelimiterChar",
        "SubDelimiterChar",
        "Selected",
    ):
        try:
            data[prop] = convert(getattr(s, prop))
        except Exception as e:
            data[prop] = f"FAIL: {e!r}"
    try:
        data["FieldsOrder"] = dump_fields_order(s.FieldsOrder)
    except Exception as e:
        data["FieldsOrder"] = f"FAIL: {e!r}"
    return data


def dump_settings_list(am: Any, out: dict[str, Any]) -> None:
    try:
        count = int(am.ImportSettings.Count)
    except Exception as e:
        out["settings_list"] = f"FAIL(Count): {e!r}"
        logger.exception("settings_list Count FAIL")
        return
    settings_list: list[dict[str, Any]] = []
    for i in range(1, count + 1):
        entry: dict[str, Any] = {"index": i}
        try:
            s = am.ImportSettings.Item(i)
        except Exception as e:
            entry["item"] = f"FAIL: {e!r}"
            logger.exception("settings_list Item(%d) FAIL", i)
            settings_list.append(entry)
            continue
        try:
            entry["name"] = str(s.Name)
        except Exception as e:
            entry["name"] = f"FAIL: {e!r}"
            logger.exception("settings_list Name(%d) FAIL", i)
        try:
            entry["selected"] = bool(s.Selected)
        except Exception as e:
            entry["selected"] = f"FAIL: {e!r}"
            logger.exception("settings_list Selected(%d) FAIL", i)
        try:
            entry["id"] = int(s.ImportSettingID)
        except Exception as e:
            entry["id"] = f"FAIL: {e!r}"
            logger.exception("settings_list ImportSettingID(%d) FAIL", i)
        settings_list.append(entry)
    out["settings_list"] = settings_list


def probe_settings(
    am: Any, settings_id: int, settings_name: str | None, out: dict[str, Any]
) -> Any:
    out["settings"] = {}
    try:
        count = int(am.ImportSettings.Count)
        out["settings"]["count"] = count
        logger.info("ImportSettings.Count=%d", count)
    except Exception as e:
        out["settings"]["count"] = f"FAIL: {e!r}"
        logger.exception("ImportSettings.Count FAIL")
        return None
    dump_settings_list(am, out)
    if settings_name is not None:
        for i in range(1, count + 1):
            try:
                s = am.ImportSettings.Item(i)
            except Exception as e:
                logger.warning("ImportSettings.Item(%d) FAIL during name scan: %r", i, e)
                continue
            try:
                name = str(s.Name)
            except Exception as e:
                logger.warning("ImportSettings.Name(%d) FAIL during name scan: %r", i, e)
                continue
            if name == settings_name:
                out["settings"]["item"] = dump_setting(s)
                logger.info("ImportSettings name=%r matched at index %d", settings_name, i)
                return s
        out["error"] = f"settings name not found: {settings_name}"
        logger.error("settings name not found: %s", settings_name)
        return None
    if settings_id > count:
        out["settings"]["error"] = f"settings_id {settings_id} out of range (Count={count})"
        logger.error("settings_id %d out of range (Count=%d)", settings_id, count)
        return None
    try:
        s = am.ImportSettings.Item(settings_id)
    except Exception as e:
        out["settings"]["item"] = f"FAIL: {e!r}"
        logger.exception("ImportSettings.Item(%d) FAIL", settings_id)
        return None
    out["settings"]["item"] = dump_setting(s)
    logger.info("ImportSettings.Item(%d) OK", settings_id)
    return s


def probe_build_settings(s: Any, field_types: list[int], out: dict[str, Any]) -> None:
    entry: dict[str, Any] = {}
    out["build_settings"] = entry
    try:
        s.UpdateFromDB()
        entry["update_from_db"] = True
        logger.info("UpdateFromDB OK")
    except Exception as e:
        entry["update_from_db"] = f"FAIL: {e!r}"
        logger.exception("UpdateFromDB FAIL")

    existing_count = 0
    try:
        existing_count = int(s.FieldsOrder.Count)
        entry["existing_fields_count"] = existing_count
        logger.info("FieldsOrder.Count=%d before build", existing_count)
    except Exception as e:
        entry["existing_fields_count"] = f"FAIL: {e!r}"
        logger.exception("FieldsOrder.Count before build FAIL")

    added: list[dict[str, Any]] = []
    for idx, typ in enumerate(field_types, start=1):
        col = existing_count + idx
        step: dict[str, Any] = {"type": typ, "column_number": col}
        try:
            field = s.NewImportSettingField()
            step["new_field"] = "OK"
        except Exception as e:
            step["new_field"] = f"FAIL: {e!r}"
            added.append(step)
            logger.exception("NewImportSettingField FAIL (type=%d)", typ)
            continue
        try:
            field.Type = typ
            step["type_set"] = "OK"
        except Exception as e:
            step["type_set"] = f"FAIL: {e!r}"
            logger.exception("field.Type=%d FAIL", typ)
        try:
            field.ColumnNumber = col
            step["column_set"] = "OK"
        except Exception as e:
            step["column_set"] = f"FAIL: {e!r}"
            logger.exception("field.ColumnNumber=%d FAIL", col)
        try:
            s.FieldsOrder.Add(field)
            step["add"] = "OK"
            logger.info("field added type=%d column=%d", typ, col)
        except Exception as e:
            step["add"] = f"FAIL: {e!r}"
            logger.exception("FieldsOrder.Add FAIL (type=%d)", typ)
        added.append(step)
    entry["added"] = added

    try:
        s.SaveToDatabase(True)
        entry["save_to_db"] = True
        logger.info("SaveToDatabase(True) OK")
    except Exception as e:
        entry["save_to_db"] = f"FAIL: {e!r}"
        logger.exception("SaveToDatabase(True) FAIL")
    try:
        entry["fields_order_count_after"] = int(s.FieldsOrder.Count)
        logger.info("FieldsOrder.Count=%d after build", entry["fields_order_count_after"])
    except Exception as e:
        entry["fields_order_count_after"] = f"FAIL: {e!r}"
        logger.exception("FieldsOrder.Count after build FAIL")
    try:
        entry["name"] = str(s.Name)
    except Exception as e:
        entry["name"] = f"FAIL: {e!r}"
        logger.exception("Name FAIL")


def probe_import(
    am: Any,
    s: Any,
    csv: str,
    job_name: str,
    out: dict[str, Any],
    watch_windows: bool = False,
) -> None:
    job: Any = None
    try:
        job = am.NewCDMJob()
        out["import_job_created"] = True
        logger.info("NewCDMJob OK")
    except Exception as e:
        out["import_job_created"] = f"FAIL: {e!r}"
        logger.exception("NewCDMJob FAIL")
    if job is not None:
        try:
            job.JobName = job_name
            logger.info("JobName=%s", job_name)
        except Exception as e:
            out["import_job_name"] = f"FAIL: {e!r}"
            logger.exception("JobName FAIL")
        try:
            job.SaveToDatabase()
            out["import_job_saved"] = True
            logger.info("SaveToDatabase OK")
        except Exception as e:
            out["import_job_saved"] = f"FAIL: {e!r}"
            logger.exception("SaveToDatabase FAIL")
    if job is None:
        out["import"] = {"error": "NewCDMJob failed - cannot call ImportCSVToJob"}
        logger.error("ImportCSVToJob skipped: job is None")
        return
    entry: dict[str, Any] = {"call_started": datetime.now().isoformat(timespec="seconds")}
    out["import"] = entry
    dump(out)
    watcher_started = False
    if watch_windows:
        watcher_started = _watch_acam_windows()
    started = time.monotonic()
    logger.info("ImportCSVToJob started (csv=%s)", csv)
    try:
        ok = job.ImportCSVToJob(csv, s)
        entry["call_returned"] = datetime.now().isoformat(timespec="seconds")
        entry["duration_s"] = round(time.monotonic() - started, 3)
        entry["result"] = convert(ok)
        logger.info("ImportCSVToJob returned %r", ok)
    except Exception as e:
        entry["call_returned"] = datetime.now().isoformat(timespec="seconds")
        entry["duration_s"] = round(time.monotonic() - started, 3)
        entry["error"] = f"{type(e).__name__}: {e}"
        logger.exception("ImportCSVToJob FAIL")
    finally:
        if watcher_started:
            logger.info("WATCH STOP")


def probe_bulk(
    am: Any,
    s: Any,
    csv: str,
    out: dict[str, Any],
    watch_windows: bool = False,
) -> None:
    entry: dict[str, Any] = {"call_started": datetime.now().isoformat(timespec="seconds")}
    out["bulk"] = entry
    dump(out)
    watcher_started = False
    if watch_windows:
        watcher_started = _watch_acam_windows()
    started = time.monotonic()
    logger.info("CreateJobsFromCSVFile started (csv=%s)", csv)
    try:
        coll = am.CreateJobsFromCSVFile(csv, s)
        entry["call_returned"] = datetime.now().isoformat(timespec="seconds")
        entry["duration_s"] = round(time.monotonic() - started, 3)
        logger.info("CreateJobsFromCSVFile returned")
    except Exception as e:
        entry["call_returned"] = datetime.now().isoformat(timespec="seconds")
        entry["duration_s"] = round(time.monotonic() - started, 3)
        entry["error"] = f"{type(e).__name__}: {e}"
        logger.exception("CreateJobsFromCSVFile FAIL")
        return
    finally:
        if watcher_started:
            logger.info("WATCH STOP")
    try:
        count = int(coll.Count)
        entry["count"] = count
        logger.info("collection Count=%d", count)
    except Exception as e:
        entry["count"] = f"FAIL: {e!r}"
        logger.exception("collection Count FAIL")
        return
    jobs: list[dict[str, Any]] = []
    for i in range(1, count + 1):
        job: dict[str, Any] = {"index": i}
        try:
            j = coll.Item(i)
        except Exception as e:
            job["item"] = f"FAIL: {e!r}"
            logger.exception("Item(%d) FAIL", i)
            jobs.append(job)
            continue
        try:
            job["job_name"] = str(j.JobName)
        except Exception as e:
            job["job_name"] = f"FAIL: {e!r}"
            logger.exception("JobName(%d) FAIL", i)
        try:
            j.SaveToDatabase()
            job["saved"] = True
            logger.info("bulk job %d saved", i)
        except Exception as e:
            job["saved"] = False
            job["save_error"] = f"{type(e).__name__}: {e}"
            logger.exception("bulk job %d SaveToDatabase FAIL", i)
        jobs.append(job)
    entry["jobs"] = jobs


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
    user32 = ctypes.windll.user32
    titles: list[str] = []

    def _cb(hwnd: int, lparam: int) -> bool:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value != target_pid:
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            titles.append(buf.value)
        return True

    callback = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(_cb)
    while True:
        time.sleep(3)
        titles.clear()
        user32.EnumWindows(callback, 0)
        logger.info("WINDOWS: n=%d titles=%r", len(titles), titles)


def _watch_acam_windows() -> bool:
    pid = _get_acam_pid()
    if pid is None:
        logger.info("WINDOW WATCH: Acam.exe PID not found")
        return False
    logger.info("WINDOW WATCH start (pid=%d)", pid)
    threading.Thread(target=_window_watcher, args=(pid,), daemon=True).start()
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe AlphaCAM CDM CSV import in Session 0")
    parser.add_argument(
        "--csv",
        default=None,
        help="path to the CSV file on the machine (not needed for build-settings)",
    )
    settings_group = parser.add_mutually_exclusive_group()
    settings_group.add_argument(
        "--settings-id",
        type=int,
        default=1,
        help="ImportSettings index 1..N to use (default: 1)",
    )
    settings_group.add_argument(
        "--settings-name",
        default=None,
        help="ImportSettings exact name to use (mutually exclusive with --settings-id)",
    )
    parser.add_argument(
        "--method",
        choices=("import", "bulk", "both", "build-settings"),
        default="both",
        help="which call to probe (default: both)",
    )
    parser.add_argument(
        "--fields",
        default=None,
        help="comma-separated field types for --method build-settings "
        '(e.g. "256,259,257,258,264,512,513,524"); required for build-settings',
    )
    parser.add_argument(
        "--job-name",
        default="",
        help="job name for method=import (default: PROBE_IMPORT_<ts>)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="watchdog timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--watch-windows",
        action="store_true",
        help="log visible Acam.exe window titles every 3s during import/bulk COM calls",
    )
    args = parser.parse_args()

    if args.method == "build-settings":
        if not args.fields:
            parser.error("--fields is required for --method build-settings")
    elif args.csv is None:
        parser.error(f"--csv is required for --method {args.method}")

    logging.basicConfig(
        filename=LOG_PATH,
        filemode="a",
        level=logging.INFO,
        format="%(asctime)s PID=%(process)d %(message)s",
        encoding="utf-8",
    )

    job_name = args.job_name or f"PROBE_IMPORT_{datetime.now():%Y%m%d_%H%M%S}"
    out: dict[str, Any] = {
        "variant": "probe_cdm_import",
        "csv": args.csv,
        "settings_id": args.settings_id,
        "settings_name": args.settings_name,
        "method": args.method,
        "job_name": job_name,
        "fields": args.fields,
        "watch_windows": args.watch_windows,
    }
    logger.info(
        "start variant=probe_cdm_import csv=%s settings_id=%d settings_name=%s method=%s fields=%s",
        args.csv,
        args.settings_id,
        args.settings_name,
        args.method,
        args.fields,
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

    if am is not None:
        try:
            out["cdm_authorised"] = bool(am.IsCDMAuthorised())
            logger.info("IsCDMAuthorised=%s", out["cdm_authorised"])
        except Exception as e:
            out["cdm_authorised"] = f"FAIL: {e!r}"
            logger.exception("IsCDMAuthorised FAIL")
        dump(out)
        s = probe_settings(am, args.settings_id, args.settings_name, out)
        dump(out)
        if s is not None:
            if args.method == "build-settings":
                try:
                    field_types = [int(x) for x in args.fields.split(",") if x.strip()]
                    probe_build_settings(s, field_types, out)
                    dump(out)
                except ValueError as e:
                    out["build_settings"] = {"fields_parse": f"FAIL: {e!r}"}
                    logger.exception("--fields parse FAIL: %s", args.fields)
            else:
                if args.method in ("import", "both"):
                    probe_import(
                        am,
                        s,
                        args.csv,
                        job_name,
                        out,
                        watch_windows=args.watch_windows,
                    )
                    dump(out)
                if args.method in ("bulk", "both"):
                    probe_bulk(
                        am,
                        s,
                        args.csv,
                        out,
                        watch_windows=args.watch_windows,
                    )
                    dump(out)

    dump(out)
    logger.info("finished")


if __name__ == "__main__":
    main()
