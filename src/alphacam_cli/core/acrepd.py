from __future__ import annotations

import glob
import logging
import os
from collections.abc import Callable
from typing import Any
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import ParseError

logger = logging.getLogger(__name__)

_JOB_FIELDS: dict[str, str] = {
    "jobname": "job_name",
    "jobcustomername": "customer_name",
    "jobmaterial_automationmanager": "material",
    "jobpo": "po_number",
    "jobduedate": "due_date",
    "joborderdate": "order_date",
    "jobprocesseddate": "processed_date",
    "jobefficiencyratepercentage": "efficiency_rate",
}

_DRAWING_FIELDS: dict[str, str] = {
    "drawingname": "name",
    "drawingfilename": "file_name",
}

_SHEET_FIELDS: dict[str, str] = {
    "sheetid": "id",
    "sheetname": "name",
    "sheetdatabasename": "database_name",
    "sheetwidth": "width",
    "sheetlength": "length",
    "sheetthickness": "thickness",
    "sheetpartcount": "part_count",
    "sheetuniquepartcount": "unique_part_count",
    "sheetquantity": "quantity",
    "sheetscrap": "scrap",
}

_SHEET_CDM_FIELDS: dict[str, str] = {
    "cdmsheetnestncfilename": "nest_nc_filename",
    "cdmsheetpressname": "press_name",
}

_SHEET_CDM_KEYS = ("cdmsheetid", "cdmsheetreportid", "sheetid")

_PART_FIELDS: dict[str, str] = {
    "partid": "id",
    "partsheetid": "sheet_id",
    "partdrawingid": "drawing_id",
    "partjobid": "job_id",
    "partname": "name",
    "partdrawingfilename": "drawing_file_name",
    "partitemnumber": "item_number",
    "partquantity": "quantity",
    "partquantityonsheet": "quantity_on_sheet",
    "partlocationonsheetx": "x",
    "partlocationonsheety": "y",
    "partrotationonsheet": "rotation",
    "partwidth": "width",
    "partlength": "length",
    "partthickness": "thickness",
    "partmaterial": "material",
    "partnestkitnumber": "nest_kit_number",
}

_PART_CDM_FIELDS: dict[str, str] = {
    "cdmparthandlename": "handle_name",
    "cdmpartcsvcustomername": "csv_customer_name",
    "cdmpartcsvcustomerordernumber": "csv_order_number",
    "cdmpartcsvcustomeritemnumber": "csv_item_number",
    "cdmpartproductioncomment": "production_comment",
    "cdmpartnestncfilename": "nest_nc_filename",
    "cdmparttype": "type",
    "cdmpartpresssheetname": "press_sheet_name",
}
_PART_CDM_FIELDS.update({f"cdmpartcustom{n}": f"custom_field_{n}" for n in range(1, 26)})

_PART_CDM_KEYS = ("cdmpartid", "cdmpartreportid", "partid")

_SHEET_NUMERIC: dict[str, Callable[..., Any]] = {
    "id": int,
    "width": float,
    "length": float,
    "thickness": float,
    "part_count": int,
    "unique_part_count": int,
    "quantity": int,
    "scrap": int,
}

_PART_NUMERIC: dict[str, Callable[..., Any]] = {
    "id": int,
    "sheet_id": int,
    "drawing_id": int,
    "job_id": int,
    "quantity": int,
    "quantity_on_sheet": int,
    "x": float,
    "y": float,
    "rotation": int,
    "width": float,
    "length": float,
    "thickness": float,
}

_IMAGE_TAGS = frozenset({"sheetimage", "partimage"})

_MAX_ACREPD_SIZE = 64 * 1024 * 1024


def _num(value: str | None, cast: Callable[..., Any]) -> Any:
    """Convert a string value via ``cast``; return None on missing or invalid input."""
    if value is None:
        return None
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def _reports_data_dir(licomdir_path: str, override: str | None = None) -> str:
    """Resolve the reports data directory; ``override`` wins, else probe standard layouts."""
    if override and override.strip():
        return override.strip()
    candidates = [
        os.path.join(licomdir_path, "LICOMDIR", "Reports", "Data"),
        os.path.join(licomdir_path, "Reports", "Data"),
    ]
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return candidates[0]


def _name_parts(path: str) -> tuple[str, str | None]:
    """Split "<JobName> - <Material>.acrepd" into (job_name, material)."""
    base = os.path.splitext(os.path.basename(path))[0]
    parts = base.rsplit(" - ", 1)
    job_name = parts[0].strip()
    material: str | None = None
    if len(parts) > 1 and parts[1].strip():
        material = parts[1].strip()
    return job_name, material


def manifest_files(data_dir: str) -> list[dict[str, Any]]:
    """List .acrepd manifest files with job/material metadata from filenames."""
    manifests: list[dict[str, Any]] = []
    for path in sorted(glob.glob(os.path.join(data_dir, "*.acrepd"))):
        job_name, material = _name_parts(path)
        try:
            stat = os.stat(path)
        except OSError:
            logger.warning("acrepd: skipping manifest file %s (stat failed)", path)
            continue
        manifests.append(
            {
                "path": path,
                "job_name": job_name,
                "material": material,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            }
        )
    return manifests


def _local_name(tag: str) -> str:
    """Strip an XML namespace prefix from a tag name."""
    return tag.rsplit("}", 1)[-1]


_TREE_WRAPPER_TAGS = frozenset({"diffgram", "newdataset", "document"})
_TREE_SKIP_TAGS = frozenset({"before", "after"})


def _children(root: ET.Element, name: str) -> list[ET.Element]:
    result: list[ET.Element] = []
    target = name.lower()
    for el in root:
        local = _local_name(el.tag).lower()
        if local in _TREE_SKIP_TAGS:
            continue
        if local == target:
            result.append(el)
        elif local in _TREE_WRAPPER_TAGS:
            result.extend(_children(el, name))
    return result


def _rows(root: ET.Element, table: str) -> list[dict[str, str]]:
    """Parse table rows as {tag: value}; image values are reduced to has_image."""
    rows: list[dict[str, str]] = []
    for row_el in _children(root, table):
        row: dict[str, str] = {}
        for child in row_el:
            tag = _local_name(child.tag).lower()
            if tag in _IMAGE_TAGS:
                if child.text and child.text.strip():
                    row["has_image"] = "1"
                continue
            if child.text and child.text.strip():
                row[tag] = child.text.strip()
        rows.append(row)
    return rows


def _mapped(row: dict[str, str], mapping: dict[str, str]) -> dict[str, Any]:
    """Map row tags to output keys; missing fields become None."""
    out: dict[str, Any] = {key: None for key in mapping.values()}
    for tag, key in mapping.items():
        if tag in row:
            out[key] = row[tag]
    return out


def _attach_part_cdm(parts: list[dict[str, Any]], cdm_rows: list[dict[str, str]]) -> None:
    """Defensively attach AC_PART_CDM fields by PartID value or by row index."""
    if not parts or not cdm_rows:
        return
    part_id_key = next((k for row in cdm_rows for k in _PART_CDM_KEYS if row.get(k)), None)
    if part_id_key is not None:
        by_id = {str(p["id"]): p for p in parts}
        matched = 0
        for row in cdm_rows:
            raw = row.get(part_id_key)
            if raw is None:
                continue
            target = by_id.get(str(raw))
            if target is not None:
                matched += 1
                mapped = _mapped(row, _PART_CDM_FIELDS)
                target.update({k: v for k, v in mapped.items() if v is not None})
        if matched:
            if matched < len(cdm_rows):
                logger.warning(
                    "acrepd: %d of %d CDM rows matched by %s", matched, len(cdm_rows), part_id_key
                )
            return
        logger.warning(
            "acrepd: no parts matched by %s, falling back to positional attach", part_id_key
        )
    logger.warning(
        "acrepd: no CDM part ID key found, attaching %d rows positionally", len(cdm_rows)
    )
    for index, target in enumerate(parts):
        if index < len(cdm_rows):
            target.update(_mapped(cdm_rows[index], _PART_CDM_FIELDS))


def _attach_sheet_cdm(sheets: list[dict[str, Any]], cdm_rows: list[dict[str, str]]) -> None:
    """Defensively attach AC_SHEET_CDM fields by SheetID value or by row index."""
    if not sheets or not cdm_rows:
        return
    sheet_id_key = next((k for row in cdm_rows for k in _SHEET_CDM_KEYS if row.get(k)), None)
    if sheet_id_key is not None:
        by_id = {str(s["id"]): s for s in sheets}
        matched = 0
        for row in cdm_rows:
            raw = row.get(sheet_id_key)
            if raw is None:
                continue
            target = by_id.get(str(raw))
            if target is not None:
                matched += 1
                mapped = _mapped(row, _SHEET_CDM_FIELDS)
                target.update({k: v for k, v in mapped.items() if v is not None})
        if matched:
            if matched < len(cdm_rows):
                logger.warning(
                    "acrepd: %d of %d CDM rows matched by %s", matched, len(cdm_rows), sheet_id_key
                )
            return
        logger.warning(
            "acrepd: no sheets matched by %s, falling back to positional attach", sheet_id_key
        )
    logger.warning(
        "acrepd: no CDM sheet ID key found, attaching %d rows positionally", len(cdm_rows)
    )
    for index, target in enumerate(sheets):
        if index < len(cdm_rows):
            target.update(_mapped(cdm_rows[index], _SHEET_CDM_FIELDS))


def parse_manifest(path: str) -> dict[str, Any]:
    """Parse an .acrepd nesting results manifest (VistaDB DataSet XML)."""
    size = os.path.getsize(path)
    if size > _MAX_ACREPD_SIZE:
        raise RuntimeError(  # noqa: TRY003
            f"manifest: file too large: {size} bytes (max {_MAX_ACREPD_SIZE})"
        )
    try:
        root = ET.parse(path).getroot()
    except ParseError as e:
        raise RuntimeError(f"manifest: invalid XML in {path}: {e}") from e  # noqa: TRY003

    job_name, material = _name_parts(path)

    job: dict[str, Any] = {key: None for key in _JOB_FIELDS.values()}
    job_rows = _rows(root, "AC_02_JOB")
    if job_rows:
        job.update(_mapped(job_rows[0], _JOB_FIELDS))

    drawings = [_mapped(row, _DRAWING_FIELDS) for row in _rows(root, "AC_03_DRAWINGS")]

    sheet_cdm_rows = _rows(root, "AC_SHEET_CDM")
    sheets: list[dict[str, Any]] = []
    for row in _rows(root, "AC_04_SHEETS"):
        sheet = _mapped(row, _SHEET_FIELDS)
        sheet["has_image"] = row.pop("has_image", None) == "1"
        sheet["nest_nc_filename"] = None
        sheet["press_name"] = None
        sheet["parts"] = []
        for key, cast in _SHEET_NUMERIC.items():
            sheet[key] = _num(sheet[key], cast)
        sheet["utilization"] = None if sheet["scrap"] is None else max(0, 100 - int(sheet["scrap"]))
        sheets.append(sheet)
    _attach_sheet_cdm(sheets, sheet_cdm_rows)

    part_cdm_rows = _rows(root, "AC_PART_CDM")
    parts: list[dict[str, Any]] = []
    for row in _rows(root, "AC_05_PARTS"):
        part = _mapped(row, _PART_FIELDS)
        part["has_image"] = row.pop("has_image", None) == "1"
        for key in _PART_CDM_FIELDS.values():
            part[key] = None
        for key, cast in _PART_NUMERIC.items():
            part[key] = _num(part[key], cast)
        parts.append(part)
    _attach_part_cdm(parts, part_cdm_rows)

    unmatched_parts: list[dict[str, Any]] = []
    for part in parts:
        found = _find_sheet(sheets, part.get("sheet_id"))
        if found is not None:
            found["parts"].append(part)
        else:
            unmatched_parts.append(part)

    return {
        "job_name": job_name,
        "material": material,
        "job": job,
        "drawings": drawings,
        "sheets": sheets,
        "total_parts": sum(len(sheet["parts"]) for sheet in sheets) + len(unmatched_parts),
        "unmatched_parts": unmatched_parts,
        "path": path,
    }


def _find_sheet(sheets: list[dict[str, Any]], sheet_id: Any) -> dict[str, Any] | None:
    if sheet_id is None:
        return None
    for sheet in sheets:
        if sheet.get("id") == sheet_id:
            return sheet
    return None


def find_manifest(data_dir: str, job_name: str, material: str | None = None) -> str | None:
    """Find a manifest path by job name (case-insensitive) and optional material."""
    target = job_name.casefold()
    material_folded = material.casefold() if material else None
    for manifest in manifest_files(data_dir):
        path = manifest["path"]
        if not isinstance(path, str):
            continue
        m_job = manifest["job_name"]
        if isinstance(m_job, str) and m_job.casefold() == target:
            if material_folded is None:
                return path
            m_material = manifest["material"]
            if isinstance(m_material, str) and m_material.casefold() == material_folded:
                return path
    return None
