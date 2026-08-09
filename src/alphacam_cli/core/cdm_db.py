from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
import subprocess
import sys
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

DESIGN_DIMS_FIELDS = 50


def _scripts_dir() -> str:
    """Directory with helper scripts (sheet_materials.py + vdb5 *.ps1), PyInstaller-safe."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "scripts")
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "..",
        "..",
        "scripts",
    )


def read_cdm_csv(path: str, separator: str) -> list[list[str]]:
    """Read CSV with BOM and encoding handling (utf-8-sig → cp1250)."""
    if not isinstance(separator, str) or len(separator) != 1:
        raise RuntimeError("cdm: separator must be a single character")  # noqa: TRY003
    with open(path, "rb") as fh:
        data = fh.read()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1250")
    return list(csv.reader(io.StringIO(text), delimiter=separator))


def parse_cdm_rows(
    rows: list[list[str]], has_header: bool
) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse CSV rows into (details, errors); only valid rows become details."""
    details: list[dict[str, Any]] = []
    errors: list[str] = []
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
        if quantity <= 0:
            errors.append(f"row {n}: quantity must be positive")
            continue
        try:
            width = float(str(row[2]).strip())
        except ValueError:
            errors.append(f"row {n}: invalid width: {row[2]!r}")
            continue
        if width <= 0:
            errors.append(f"row {n}: width must be positive")
            continue
        try:
            length = float(str(row[3]).strip())
        except ValueError:
            errors.append(f"row {n}: invalid length: {row[3]!r}")
            continue
        if length <= 0:
            errors.append(f"row {n}: length must be positive")
            continue
        details.append(
            {
                "row": n,
                "style": style,
                "quantity": quantity,
                "width": width,
                "length": length,
                "design_dims": str(row[4]).strip(),
            }
        )
    return details, errors


def sheet_materials() -> dict[str, int]:
    """Material name -> sheet/material ID from SQLite sheet database."""
    script_path = os.path.join(_scripts_dir(), "sheet_materials.py")
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
        logger.warning("cdm materials: sheet db read failed: %r", e)
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


def vdb5_job_defaults() -> dict[str, Any]:
    """Read default config name and material id from the Automation Manager database."""
    script_path = os.path.join(_scripts_dir(), "vdb5_job_defaults.ps1")
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
            return {"config_name": None, "material_id": None}
        data = json.loads(proc.stdout)
    except Exception as e:
        logger.warning("cdm defaults: vdb5 read failed: %r", e)
        return {"config_name": None, "material_id": None}
    if isinstance(data, dict) and "value" in data:
        data = data["value"]
    if not isinstance(data, dict):
        return {"config_name": None, "material_id": None}
    config_name = data.get("config_name")
    material_id = data.get("material_id")
    if not isinstance(config_name, str):
        config_name = None
    if material_id is not None:
        try:
            material_id = int(material_id)
        except (TypeError, ValueError):
            material_id = None
    return {"config_name": config_name, "material_id": material_id}


def set_job_material(job_name: str, material_id: int) -> bool:
    """Set AM_JobDetails.fkMaterialID for a job by name; True when rows updated."""
    script_path = os.path.join(_scripts_dir(), "vdb5_set_job_material.ps1")
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
        logger.warning("cdm material: vdb5 update failed: %r", e)
        return False
    if proc.returncode != 0:
        logger.warning("cdm material: vdb5 update failed: %s", proc.stdout.strip())
        return False
    match = re.search(r"(?m)^rows:\s*(\d+)", proc.stdout)
    return bool(match and int(match.group(1)) > 0)


def job_count(job_name: str) -> int | None:
    """Count AM_JobDetails rows for a job by name; None when the read fails."""
    script_path = os.path.join(_scripts_dir(), "vdb5_job_count.ps1")
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
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
    except Exception as e:
        logger.warning("cdm count: vdb5 read failed: %r", e)
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    match = re.search(r"count:\s*(\d+)", proc.stdout)
    if match is None:
        return None
    return int(match.group(1))


def _door_type_name(row: dict[str, Any]) -> str:
    for key in ("TypeName", "Name", "DoorTypeName"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for value in row.values():
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def vdb5_door_type_names() -> tuple[list[str], bool]:
    """Read door type names from the vdb5 database; (names, ok) or ([], False)."""
    script_path = os.path.join(_scripts_dir(), "vdb5_door_types.ps1")
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
        logger.warning("cdm types: vdb5 read failed: %r", e)
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
        name = _door_type_name(row)
        if name and "do not delete" not in name.lower():
            names.append(name)
    return names, True


def merge_door_types(
    com_names: list[str],
    vdb5_names: list[str],
    vdb5_ok: bool,
) -> dict[str, Any]:
    """Merge COM + vdb5 door type names into the API result dict (dedupe casefold)."""
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


def find_cdm_job(am: Any, name: str) -> Any | None:
    """Find a CDM job by name via the Automation Manager COM interface."""
    jobs = am.Jobs
    for i in range(1, int(jobs.Count) + 1):
        try:
            jj = jobs.Item(i)
        except Exception:
            continue
        if str(jj.JobName) == name:
            return jj
    return None


def cleanup_created_job(
    am: Any,
    job: Any,
    job_name: str,
    log: Callable[[str], None] | None = None,
) -> tuple[bool, str]:
    """Best-effort delete of a just-created CDM job (direct, then via collection lookup).

    Returns ``(deleted, reason)`` where ``reason`` is ``""`` when the DB row is
    gone (verified via VistaDB job_count), ``"failed"`` when an exception
    occurred or the job is still present, and ``"unverified"`` when the
    job_count read returned None (VistaDB unavailable).
    """
    try:
        if hasattr(job, "DeleteFromDB"):
            job.DeleteFromDB()
        found = find_cdm_job(am, job_name)
        if found is not None and hasattr(found, "DeleteFromDB"):
            found.DeleteFromDB()
        count = job_count(job_name)
    except Exception as e:
        if log is not None:
            log(f"{e!r}")
        return False, "failed"
    if count == 0:
        return True, ""
    if count is None:
        return False, "unverified"
    return False, "failed"
