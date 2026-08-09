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
                f"-JobName:{job_name}",
                f"-MaterialID:{material_id}",
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


def set_has_drilling(job_name: str, values: list[bool]) -> bool:
    """Set CDM_OrderDetails.HasDrilling per detail for a job; True when rows updated."""
    script_path = os.path.join(_scripts_dir(), "vdb5_set_has_drilling.ps1")
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script_path,
                f"-JobName:{job_name}",
                f"-Values:{';'.join('1' if v else '0' for v in values)}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
    except Exception as e:
        logger.warning("cdm drilling: vdb5 update failed: %r", e)
        return False
    if proc.returncode != 0:
        logger.warning("cdm drilling: vdb5 update failed: %s", proc.stdout.strip())
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
                f"-JobName:{job_name}",
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


# 268-270, 273 removed from the vendor enum; 271=rotation_method, 272=rotation_angle, 274=nest_priority  # noqa: E501
IMPORT_FIELD_NAMES: dict[int, str] = {
    256: "door_type",
    257: "door_width",
    258: "door_height",
    259: "door_quantity",
    260: "door_material",
    261: "door_customer_name",
    262: "door_order_number",
    263: "door_item_number",
    264: "door_design_dimensions",
    265: "door_production_comment",
    266: "door_custom_field_1",
    267: "door_custom_field_2",
    271: "door_rotation_method",
    272: "door_rotation_angle",
    274: "door_nest_priority",
    298: "door_drilling",
    299: "door_small_nest",
    512: "job_name",
    513: "job_config_id",
    514: "job_setup_id",
    515: "job_tool_order_id",
    516: "job_purchase_order_number",
    517: "job_work_order_number",
    518: "job_description",
    519: "job_programmer_name",
    520: "job_order_date",
    521: "job_due_date",
    522: "job_customer",
    523: "job_parent_job",
    524: "job_material_id",
}
IMPORT_FIELD_NAMES.update({n: f"door_custom_field_{n - 272}" for n in range(275, 298)})

REQUIRED_IMPORT_FIELDS = ("door_type", "door_quantity", "door_width", "door_height")

_MAPPED_DETAIL_KEYS = (
    "style",
    "quantity",
    "width",
    "length",
    "design_dims",
    "material",
    "customer_name",
    "order_number",
    "item_number",
    "production_comment",
    "oversize_x",
    "oversize_y",
    "corner_radius",
    "rotation_method",
    "rotation_angle",
    "nest_priority",
    "ignore_outer_geometry",
    "small_nest_part",
    "has_drilling",
    "job_name",
    "job_config_id",
    "job_setup_id",
    "job_tool_order_id",
    "job_purchase_order_number",
    "job_work_order_number",
    "job_description",
    "job_programmer_name",
    "job_order_date",
    "job_due_date",
    "job_customer",
    "job_parent_job",
    "job_material_id",
)

MAPPED_FIELD_TARGETS: dict[str, str] = {
    "door_type": "style",
    "door_quantity": "quantity",
    "door_width": "width",
    "door_height": "length",
    "door_design_dimensions": "design_dims",
    "door_material": "material",
    "door_customer_name": "customer_name",
    "door_order_number": "order_number",
    "door_item_number": "item_number",
    "door_production_comment": "production_comment",
    "door_rotation_method": "rotation_method",
    "door_rotation_angle": "rotation_angle",
    "door_nest_priority": "nest_priority",
    "door_drilling": "has_drilling",
    "door_small_nest": "small_nest_part",
    "job_name": "job_name",
    "job_config_id": "job_config_id",
    "job_setup_id": "job_setup_id",
    "job_tool_order_id": "job_tool_order_id",
    "job_purchase_order_number": "job_purchase_order_number",
    "job_work_order_number": "job_work_order_number",
    "job_description": "job_description",
    "job_programmer_name": "job_programmer_name",
    "job_order_date": "job_order_date",
    "job_due_date": "job_due_date",
    "job_customer": "job_customer",
    "job_parent_job": "job_parent_job",
    "job_material_id": "job_material_id",
}


def import_field_name(parameter_type: int) -> str | None:
    """Field name for an AM_ImportSettingsParameter type; None when unknown."""
    return IMPORT_FIELD_NAMES.get(parameter_type)


def import_settings() -> list[dict[str, Any]]:
    """Read AM_ImportSettings (id/name/delimiters/flags/fields) from the vdb5 database."""
    script_path = os.path.join(_scripts_dir(), "vdb5_import_settings.ps1")
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
            return []
        data = json.loads(proc.stdout)
    except Exception as e:
        logger.warning("cdm import settings: vdb5 read failed: %r", e)
        return []
    if isinstance(data, dict) and "value" in data:
        data = data["value"]
    if not isinstance(data, list):
        return []
    settings: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if not all(key in item for key in ("id", "name", "delimiter_char", "fields")):
            continue
        fields = item.get("fields")
        if not isinstance(fields, list):
            continue
        item["fields"] = [
            field
            for field in fields
            if isinstance(field, dict) and "column_number" in field and "parameter_type" in field
        ]
        settings.append(item)
    return settings


def order_details(job_name: str | None = None) -> list[dict[str, Any]]:
    """Read CDM_OrderDetails rows (joined with AM_JobDetails) from the vdb5 database."""
    script_path = os.path.join(_scripts_dir(), "vdb5_order_details.ps1")
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path]
    if job_name:
        cmd += [f"-JobName:{job_name}"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []
        data = json.loads(proc.stdout)
    except Exception as e:
        logger.warning("cdm order details: vdb5 read failed: %r", e)
        return []
    if isinstance(data, dict) and "value" in data:
        data = data["value"]
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def door_paths(type_name: str | None = None) -> list[dict[str, Any]]:
    """Read CDM_DoorPaths rows (joined with CDM_DoorTypes) from the vdb5 database."""
    script_path = os.path.join(_scripts_dir(), "vdb5_door_paths.ps1")
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path]
    if type_name:
        cmd += [f"-TypeName:{type_name}"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []
        data = json.loads(proc.stdout)
    except Exception as e:
        logger.warning("cdm door paths: vdb5 read failed: %r", e)
        return []
    if isinstance(data, dict) and "value" in data:
        data = data["value"]
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def materials() -> list[dict[str, Any]]:
    """Read AM_Materials rows (ids, names, sheet sizes) from the vdb5 database."""
    script_path = os.path.join(_scripts_dir(), "vdb5_materials.ps1")
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
            return []
        data = json.loads(proc.stdout)
    except Exception as e:
        logger.warning("cdm materials: vdb5 read failed: %r", e)
        return []
    if isinstance(data, dict) and "value" in data:
        data = data["value"]
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def configs(show: str | None = None) -> list[dict[str, Any]]:
    """Read AM_ConfigurationSettings with merged CDM_ConfigurationSettings per config.

    Each config gets a ``cdm`` dict key (merged CDM rows by
    ``fk_configuration_setting_id``, last row wins on conflicts; ``{}`` when
    none). ``show`` filters by config name (casefold); no match -> [].
    """
    script_path = os.path.join(_scripts_dir(), "vdb5_configs.ps1")
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
            return []
        data = json.loads(proc.stdout)
    except Exception as e:
        logger.warning("cdm configs: vdb5 read failed: %r", e)
        return []
    if isinstance(data, dict) and "value" in data:
        data = data["value"]
    if not isinstance(data, dict):
        return []
    rows = data.get("configs")
    if not isinstance(rows, list):
        return []
    cdm_by_fk: dict[int, dict[str, Any]] = {}
    cdm_rows = data.get("cdm")
    if isinstance(cdm_rows, list):
        for item in cdm_rows:
            if not isinstance(item, dict):
                continue
            fk_raw = item.get("fk_configuration_setting_id")
            if fk_raw is None:
                continue
            try:
                fk_id = int(fk_raw)
            except (TypeError, ValueError):
                continue
            merged = dict(cdm_by_fk.get(fk_id, {}))
            merged.update(item)
            cdm_by_fk[fk_id] = merged
    result: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        cfg_id = item.get("id")
        if cfg_id is not None:
            try:
                cfg_id = int(cfg_id)
            except (TypeError, ValueError):
                cfg_id = None
        merged = dict(item)
        merged["cdm"] = cdm_by_fk.get(cfg_id, {}) if cfg_id is not None else {}
        result.append(merged)
    if show:
        wanted = show.strip().casefold()
        if wanted:
            result = [
                cfg
                for cfg in result
                if isinstance(cfg.get("name"), str) and cfg["name"].strip().casefold() == wanted
            ]
    return result


LOOKUP_KEYS = (
    "setups",
    "customers",
    "machining_orders",
    "doorstyles",
    "multidrill",
    "fittings",
    "layers_mapping",
)


def lookups() -> dict[str, list[dict[str, Any]]]:
    """Read lookup tables (setups/customers/styles/multidrill/...) from the vdb5 database.

    Missing or invalid sections become empty lists; total failure returns
    ``{key: [] for key in LOOKUP_KEYS}``.
    """
    script_path = os.path.join(_scripts_dir(), "vdb5_lookups.ps1")
    fallback: dict[str, list[dict[str, Any]]] = {key: [] for key in LOOKUP_KEYS}
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
            return fallback
        data = json.loads(proc.stdout)
    except Exception as e:
        logger.warning("cdm lookups: vdb5 read failed: %r", e)
        return fallback
    if isinstance(data, dict) and "value" in data:
        data = data["value"]
    if not isinstance(data, dict):
        return fallback
    result: dict[str, list[dict[str, Any]]] = {}
    for key in LOOKUP_KEYS:
        rows = data.get(key)
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list):
            result[key] = []
            continue
        result[key] = [row for row in rows if isinstance(row, dict)]
    return result


def find_import_setting(settings: list[dict[str, Any]], key: str | int) -> dict[str, Any] | None:
    """Find an import setting by id (int) or name (str, casefold); None when absent."""
    if isinstance(key, int):
        for setting in settings:
            raw_id = setting.get("id")
            if raw_id is None:
                continue
            try:
                if int(raw_id) == key:
                    return setting
            except (TypeError, ValueError):
                continue
        return None
    wanted = key.strip().casefold()
    for setting in settings:
        name = setting.get("name")
        if isinstance(name, str) and name.strip().casefold() == wanted:
            return setting
    return None


def field_map_from_setting(setting: dict[str, Any]) -> dict[int, str]:
    """Column number -> field name from an import setting's fields list."""
    fields = setting.get("fields")
    if not isinstance(fields, list):
        return {}
    entries: list[tuple[int, str]] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        parameter_type = field.get("parameter_type")
        column_raw = field.get("column_number")
        if parameter_type is None or column_raw is None:
            continue
        try:
            ptype = int(parameter_type)
            column = int(column_raw)
        except (TypeError, ValueError):
            continue
        if ptype in (0, 1):
            continue
        entries.append((column, IMPORT_FIELD_NAMES.get(ptype, f"unknown_{ptype}")))
    entries.sort(key=lambda entry: entry[0])
    return dict(entries)


def _parse_bool_value(raw: str) -> tuple[bool | None, bool]:
    """Parse a CSV bool-ish string into (value, ok); empty -> (None, True)."""
    value = raw.casefold()
    if value in ("1", "true", "yes"):
        return True, True
    if value in ("0", "false", "no"):
        return False, True
    if not value:
        return None, True
    return None, False


def parse_cdm_rows_mapped(
    rows: list[list[str]],
    field_map: dict[int, str],
    has_header: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse CSV rows into (details, errors) using an import settings column map.

    Every row without all required fields mapped raises an error; only valid
    rows become details. Values are converted by field type (bool/int/float).
    """
    details: list[dict[str, Any]] = []
    errors: list[str] = []
    missing_required = [name for name in REQUIRED_IMPORT_FIELDS if name not in field_map.values()]
    if missing_required:
        errors.append(
            "import settings map is missing required field(s): " + ", ".join(missing_required)
        )
    for n, row in enumerate(rows, start=1):
        if has_header and n == 1:
            continue
        if not any(str(cell).strip() for cell in row):
            continue
        if missing_required:
            continue
        detail: dict[str, Any] = {key: None for key in _MAPPED_DETAIL_KEYS}
        detail["row"] = n
        detail["custom_fields"] = {}
        invalid: str | None = None
        for column in sorted(field_map):
            if column < 1:
                continue
            name = field_map[column]
            if name.startswith("unknown_"):
                continue
            if column - 1 >= len(row):
                invalid = f"row {n}: expected at least {column} columns, got {len(row)}"
                break
            raw = str(row[column - 1]).strip()
            if name == "door_type":
                if not raw:
                    invalid = f"row {n}: style is required"
                    break
                detail["style"] = raw
            elif name == "door_quantity":
                try:
                    quantity = int(raw)
                except ValueError:
                    invalid = f"row {n}: invalid quantity: {row[column - 1]!r}"
                    break
                if quantity <= 0:
                    invalid = f"row {n}: quantity must be positive"
                    break
                detail["quantity"] = quantity
            elif name == "door_width":
                try:
                    width = float(raw)
                except ValueError:
                    invalid = f"row {n}: invalid width: {row[column - 1]!r}"
                    break
                if width <= 0:
                    invalid = f"row {n}: width must be positive"
                    break
                detail["width"] = width
            elif name == "door_height":
                try:
                    length = float(raw)
                except ValueError:
                    invalid = f"row {n}: invalid length: {row[column - 1]!r}"
                    break
                if length <= 0:
                    invalid = f"row {n}: length must be positive"
                    break
                detail["length"] = length
            elif name in ("door_drilling", "door_small_nest"):
                bool_value, ok = _parse_bool_value(raw)
                if not ok:
                    invalid = f"row {n}: invalid value for {name}: {raw}"
                    break
                detail[MAPPED_FIELD_TARGETS[name]] = bool_value
            elif name == "door_rotation_angle":
                if not raw:
                    continue
                try:
                    angle = float(raw)
                except ValueError:
                    invalid = f"row {n}: invalid value for {name}: {raw}"
                    break
                detail["rotation_angle"] = angle
            elif name in ("door_rotation_method", "door_nest_priority"):
                if not raw:
                    continue
                try:
                    parsed_int = int(raw)
                except ValueError:
                    invalid = f"row {n}: invalid value for {name}: {raw}"
                    break
                detail[MAPPED_FIELD_TARGETS[name]] = parsed_int
            elif name.startswith("door_custom_field_"):
                if raw:
                    detail["custom_fields"][name.removeprefix("door_custom_field_")] = raw
            else:
                target = MAPPED_FIELD_TARGETS.get(name)
                if raw and target is not None:
                    detail[target] = raw
        if invalid is not None:
            errors.append(invalid)
            continue
        details.append(detail)
    return details, errors


def field_map_descriptions(field_map: dict[int, str]) -> list[dict[str, Any]]:
    """Human-readable descriptions of a column map for preview/CLI output."""
    return [
        {
            "column": column,
            "field": name,
            "required": name in REQUIRED_IMPORT_FIELDS,
        }
        for column, name in sorted(field_map.items())
    ]
