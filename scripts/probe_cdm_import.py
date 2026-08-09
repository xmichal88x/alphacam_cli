"""Probe harness for AlphaCAM CDM CSV import (ImportCSVToJob / CreateJobsFromCSVFile).

Runs in Session 0 as SYSTEM via a scheduled task - separate process with its own
watchdog, so it can never block the gateway service. A threading watchdog calls
os._exit(2) on hang; a missing "call_returned" key in the JSON output is the hang
signal (the process was killed mid-call).

Usage (machine):
    python C:/temp/probe_cdm_import.py --csv C:/temp/test.csv --settings-id 1 --method both

Via schtasks (Session 0, SYSTEM), one command (^ = line continuation):
    schtasks /create /tn cdm_probe /tr "python C:/temp/probe_cdm_import.py --csv C:/temp/t.csv" ^
        /sc once /st 23:59 /ru SYSTEM /f
    schtasks /run /tn cdm_probe

Outputs:
    C:/temp/probe_cdm_import_out.json  overwritten, UTF-8
    C:/temp/probe_cdm_import.log       appended, timestamp + PID
"""

import argparse
import json
import logging
import os
import threading
import time
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


def probe_settings(am: Any, settings_id: int, out: dict[str, Any]) -> Any:
    out["settings"] = {}
    try:
        count = int(am.ImportSettings.Count)
        out["settings"]["count"] = count
        logger.info("ImportSettings.Count=%d", count)
    except Exception as e:
        out["settings"]["count"] = f"FAIL: {e!r}"
        logger.exception("ImportSettings.Count FAIL")
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


def probe_import(am: Any, s: Any, csv: str, job_name: str, out: dict[str, Any]) -> None:
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


def probe_bulk(am: Any, s: Any, csv: str, out: dict[str, Any]) -> None:
    entry: dict[str, Any] = {"call_started": datetime.now().isoformat(timespec="seconds")}
    out["bulk"] = entry
    dump(out)
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe AlphaCAM CDM CSV import in Session 0")
    parser.add_argument("--csv", required=True, help="path to the CSV file on the machine")
    parser.add_argument(
        "--settings-id",
        type=int,
        default=1,
        help="ImportSettings index 1..N to use (default: 1)",
    )
    parser.add_argument(
        "--method",
        choices=("import", "bulk", "both"),
        default="both",
        help="which call to probe (default: both)",
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
    args = parser.parse_args()

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
        "method": args.method,
        "job_name": job_name,
    }
    logger.info(
        "start variant=probe_cdm_import csv=%s settings_id=%d method=%s",
        args.csv,
        args.settings_id,
        args.method,
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
        s = probe_settings(am, args.settings_id, out)
        dump(out)
        if s is not None:
            if args.method in ("import", "both"):
                probe_import(am, s, args.csv, job_name, out)
                dump(out)
            if args.method in ("bulk", "both"):
                probe_bulk(am, s, args.csv, out)
                dump(out)

    dump(out)
    logger.info("finished")


if __name__ == "__main__":
    main()
