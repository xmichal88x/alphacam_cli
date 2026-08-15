from __future__ import annotations

import glob
import logging
import os
import re
from collections.abc import Callable
from typing import Any
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import ParseError

logger = logging.getLogger(__name__)

_NC_MAX_DEPTH = 4
_NC_TOKEN_DIRS = ("nc", "nesting", "kod")

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


def fill_class(utilization: int | float | None, threshold: int | None = 70) -> str:
    if not isinstance(threshold, int) or not 0 <= threshold <= 100:
        threshold = 70
    if utilization is None or utilization <= 0:
        return "empty"
    if utilization >= threshold:
        return "full"
    return "partial"


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


def sheet_count_light(path: str) -> tuple[int, int | None]:
    """Stream-scan a manifest for sheet count and first-sheet utilization.

    Parses incrementally (no full tree) and skips ``before``/``after``
    diffgram sections; returns ``(0, None)`` on any error.
    """
    count = 0
    utilization: int | None = None
    skip_depth = 0
    recorded = False
    in_first_sheet = False
    root: ET.Element | None = None
    try:
        for event, elem in ET.iterparse(path, events=("start", "end")):
            if root is None:
                root = elem
            local = _local_name(elem.tag).lower()
            if event == "start":
                if skip_depth:
                    skip_depth += 1
                elif local in _TREE_SKIP_TAGS:
                    skip_depth = 1
                elif local == "ac_04_sheets":
                    if count == 0:
                        in_first_sheet = True
                    count += 1
                continue
            if skip_depth:
                skip_depth -= 1
            elif local == "ac_04_sheets" and not recorded:
                utilization = _first_sheet_utilization(elem)
                recorded = True
                in_first_sheet = False
            if in_first_sheet:
                continue
            elem.clear()
            if root is not None:
                root.clear()
    except (OSError, ParseError) as exc:
        logger.warning("acrepd: sheet_count_light failed for %s: %r", path, exc)
        return 0, None
    return count, utilization


def _first_sheet_utilization(sheet_el: ET.Element) -> int | None:
    for child in sheet_el:
        if _local_name(child.tag).lower() == "sheetscrap":
            try:
                return max(0, 100 - int(child.text or ""))
            except (TypeError, ValueError):
                return None
    return None


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


def _nc_normalize(name: str, replace_space: bool) -> str:
    """Normalize an NC basename for matching: casefold, optional space->underscore."""
    stem = os.path.splitext(name)[0]
    folded = stem.casefold()
    if replace_space:
        folded = folded.replace(" ", "_")
    return folded


def _nc_is_preferred(dirname: str) -> bool:
    """Return whether a directory name carries an NC token (nc/nesting/kod)."""
    words = re.split(r"[_\-\s]+", dirname.casefold())
    return any(token in words for token in _NC_TOKEN_DIRS)


def _nc_scan(job_root: str) -> list[dict[str, Any]]:
    """Recursively collect ``*.nc`` files under ``job_root`` (depth <= 4, no symlinks).

    Candidates from directories carrying an NC token come first; access errors
    only log a warning. Each candidate is
    ``{"path", "filename", "stem", "preferred"}``.
    """
    found: list[dict[str, Any]] = []

    def walk(directory: str, depth: int, preferred: bool) -> None:
        try:
            entries = list(os.scandir(directory))
        except OSError as e:
            logger.warning("acrepd: nc scan failed for %s: %r", directory, e)
            return
        for entry in entries:
            try:
                is_file = entry.is_file(follow_symlinks=False)
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError as e:
                logger.warning("acrepd: nc scan entry failed for %s: %r", entry.path, e)
                continue
            if is_file and entry.name.casefold().endswith(".nc"):
                found.append(
                    {
                        "path": entry.path,
                        "filename": entry.name,
                        "stem": os.path.splitext(entry.name)[0],
                        "preferred": preferred,
                    }
                )
            elif is_dir and depth < _NC_MAX_DEPTH:
                walk(entry.path, depth + 1, preferred or _nc_is_preferred(entry.name))

    walk(job_root, 0, False)
    found.sort(key=lambda c: (not c["preferred"], c["path"].casefold()))
    return found


def find_nc_path(
    job_root: str,
    filename: str,
    candidates: list[dict[str, Any]] | None = None,
) -> str | None:
    """Locate a named ``*.nc`` file under ``job_root``; None when not found.

    ``candidates`` (from :func:`find_nc_files`) skips a fresh disk scan.
    """
    if candidates is None:
        candidates = _nc_scan(job_root)
    target = filename.casefold()
    for candidate in candidates:
        if candidate["filename"].casefold() == target:
            return str(candidate["path"])
    target_stem = _nc_normalize(filename, True)
    for candidate in candidates:
        if _nc_normalize(candidate["stem"], True) == target_stem:
            return str(candidate["path"])
    return None


def find_nc_files(
    job_root: str,
    sheets: list[dict[str, Any]],
    material: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Discover ``*.nc`` nesting outputs under ``job_root`` and match them to sheets.

    Sheets are matched by normalized name stems (casefold, optional
    space->underscore) in priority order: sheet stem, ``<material>_<sheet>``,
    ``<sheet>_<material>``, and (when ``config.use_name_identifiers``) stems
    with a numeric suffix. ``config.split_nested_sheet_drawings=False``
    expects one shared NC file (material/sheet stem patterns) with a
    positional fallback. When ``config`` is None all stem patterns are
    active. A remaining positional fallback pairs unmatched sheets with
    unassigned files when the counts are equal.

    Returns ``{"nc_by_sheet", "nc_matched_by_order", "nc_unmatched",
    "nc_missing", "nc_candidates"}`` where ``nc_by_sheet`` maps sheet
    indexes to ``{"nc_filename", "nc_path", "nc_source": "disk"}`` and
    ``nc_candidates`` is the raw scan list (reusable via
    :func:`find_nc_path`).
    """
    if not os.path.isdir(job_root):
        return {
            "nc_by_sheet": {},
            "nc_matched_by_order": [],
            "nc_unmatched": [],
            "nc_missing": [
                sheet["name"]
                for sheet in sheets
                if isinstance(sheet, dict) and isinstance(sheet.get("name"), str)
            ],
            "nc_candidates": [],
        }

    replace_space = True
    split_sheets = True
    use_suffix = False
    if config:
        replace_space = config.get("replace_space_with_underscore", True)
        if replace_space is None:
            replace_space = True
        split_sheets = config.get("split_nested_sheet_drawings", True)
        split_sheets = True if split_sheets is None else bool(split_sheets)
        use_suffix = bool(config.get("use_name_identifiers", False))

    candidates = _nc_scan(job_root)
    material_stem = _nc_normalize(material, replace_space) if material else None

    stems: list[tuple[int, list[str], list[str]]] = []
    for index, sheet in enumerate(sheets):
        if not isinstance(sheet, dict):
            continue
        name = sheet.get("name")
        if not isinstance(name, str) or not name:
            continue
        sheet_stem = _nc_normalize(name, replace_space)
        plain: list[str] = [sheet_stem]
        if material_stem:
            plain.append(f"{material_stem}_{sheet_stem}")
            plain.append(f"{sheet_stem}_{material_stem}")
        if not split_sheets and material_stem:
            plain = [f"{material_stem}_{sheet_stem}", f"{sheet_stem}_{material_stem}"]
        stems.append((index, plain, plain))

    used: set[str] = set()
    by_sheet: dict[int, dict[str, Any]] = {}
    matched_order: list[int] = []

    def match_patterns(index: int, plain: list[str], bases: list[str]) -> bool:
        for pattern in plain:
            for candidate in candidates:
                if candidate["path"] in used:
                    continue
                if _nc_normalize(candidate["stem"], replace_space) == pattern:
                    used.add(candidate["path"])
                    by_sheet[index] = candidate
                    return True
        if not use_suffix:
            return False
        for base in bases:
            for candidate in candidates:
                if candidate["path"] in used:
                    continue
                match = re.fullmatch(r"(.+)_(\d+)", _nc_normalize(candidate["stem"], replace_space))
                if match is not None and match.group(1) == base:
                    used.add(candidate["path"])
                    by_sheet[index] = candidate
                    return True
        return False

    if not split_sheets:
        shared: dict[str, Any] | None = None
        for candidate in candidates:
            nc_stem = _nc_normalize(candidate["stem"], replace_space)
            if stems and all(nc_stem in plain for _, plain, _ in stems):
                shared = candidate
                break
        if shared is not None:
            used.add(shared["path"])
            for index, _, _ in stems:
                by_sheet[index] = shared
    else:
        for index, plain, bases in stems:
            match_patterns(index, plain, bases)

    unmatched_sheets = [
        index
        for index, sheet in enumerate(sheets)
        if isinstance(sheet, dict) and index not in by_sheet
    ]
    unassigned = [candidate for candidate in candidates if candidate["path"] not in used]
    if unmatched_sheets and len(unmatched_sheets) == len(unassigned):

        def sheet_key(index: int) -> str:
            name = sheets[index].get("name")
            if isinstance(name, str):
                return _nc_normalize(name, replace_space)
            return ""

        for index, candidate in zip(
            sorted(unmatched_sheets, key=sheet_key),
            sorted(unassigned, key=lambda c: _nc_normalize(c["stem"], replace_space)),
            strict=True,
        ):
            by_sheet[index] = candidate
            used.add(candidate["path"])
            matched_order.append(index)

    nc_by_sheet = {
        index: {"nc_filename": c["filename"], "nc_path": c["path"], "nc_source": "disk"}
        for index, c in sorted(by_sheet.items())
    }
    nc_unmatched = [candidate["path"] for candidate in candidates if candidate["path"] not in used]
    nc_missing = [
        sheets[index]["name"]
        for index, sheet in enumerate(sheets)
        if isinstance(sheet, dict) and isinstance(sheet.get("name"), str) and index not in by_sheet
    ]
    return {
        "nc_by_sheet": nc_by_sheet,
        "nc_matched_by_order": matched_order,
        "nc_unmatched": nc_unmatched,
        "nc_missing": nc_missing,
        "nc_candidates": candidates,
    }


def _manifest_token(part: dict[str, Any]) -> str | None:
    value = part.get("custom_field_1")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _part_qty(part: dict[str, Any]) -> int:
    value = part.get("quantity_on_sheet")
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _part_order_number(part: dict[str, Any]) -> str | None:
    value = part.get("csv_order_number")
    if value is None or not str(value).strip():
        return None
    return str(value).strip()


def aggregate_by_token(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    groups: dict[str | None, list[tuple[str, dict[str, Any]]]] = {}
    for sheet in manifest.get("sheets") or []:
        if not isinstance(sheet, dict):
            continue
        name = sheet.get("name")
        sheet_name = name if isinstance(name, str) and name else "?"
        for part in sheet.get("parts") or []:
            if isinstance(part, dict):
                groups.setdefault(_manifest_token(part), []).append((sheet_name, part))
    for part in manifest.get("unmatched_parts") or []:
        if isinstance(part, dict):
            groups.setdefault(_manifest_token(part), []).append(("?", part))
    result: list[dict[str, Any]] = []
    for token, items in groups.items():
        sheet_qtys: dict[str, int] = {}
        total_qty = 0
        order_number: str | None = None
        for sheet_name, part in items:
            qty = _part_qty(part)
            total_qty += qty
            sheet_qtys[sheet_name] = sheet_qtys.get(sheet_name, 0) + qty
            if order_number is None:
                order_number = _part_order_number(part)
        result.append(
            {
                "token": token,
                "total_qty": total_qty,
                "sheets": [
                    {"sheet": sheet_name, "qty": qty} for sheet_name, qty in sheet_qtys.items()
                ],
                "csv_order_number": order_number,
            }
        )
    result.sort(
        key=lambda item: (
            item["token"] is None,
            (item["token"] or "").casefold(),
            item["token"] or "",
        )
    )
    return result


def validate_manifest(
    manifest: dict[str, Any],
    expected_qty: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Validate manifest consistency; return {"valid", "warnings", "errors"}."""
    errors: list[str] = []
    warnings: list[str] = []

    token_qtys: dict[str, int] = {}
    for group in aggregate_by_token(manifest):
        token = group.get("token")
        if isinstance(token, str):
            token_qtys[token] = int(group.get("total_qty", 0))
    for token, expected in (expected_qty or {}).items():
        got = token_qtys.get(token, 0)
        if got != expected:
            errors.append(f'token "{token}": expected {expected}, got {got}')

    part_count = sum(len(sheet.get("parts") or []) for sheet in manifest.get("sheets") or []) + len(
        manifest.get("unmatched_parts") or []
    )
    total_parts = manifest.get("total_parts")
    if isinstance(total_parts, int) and part_count != total_parts:
        errors.append(f"total_parts mismatch: expected {total_parts}, got {part_count}")

    missing = 0
    for sheet in manifest.get("sheets") or []:
        for part in sheet.get("parts") or []:
            if _part_order_number(part) is None and _manifest_token(part) is None:
                missing += 1
    for part in manifest.get("unmatched_parts") or []:
        if _part_order_number(part) is None and _manifest_token(part) is None:
            missing += 1
    if missing:
        warnings.append(f"{missing} parts without csv_order_number and custom_field_1")

    return {"valid": not errors, "warnings": warnings, "errors": errors}
