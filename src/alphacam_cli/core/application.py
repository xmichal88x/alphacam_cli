from __future__ import annotations

import glob
import os
import time
from collections.abc import Iterator
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    import win32com.client as win32  # type: ignore[import-untyped]

    from alphacam_cli.core.drawing import Drawing
    from alphacam_cli.core.machining import MillData
    from alphacam_cli.core.nesting import Nesting
    from alphacam_cli.core.tool import Tool

from alphacam_cli.com.constants import MODULE_MILL, MODULE_ROUTER
from alphacam_cli.core import acrepd, cdm_db, headless
from alphacam_cli.core.drawing import Drawing
from alphacam_cli.core.logger import logger
from alphacam_cli.core.machining import MillData
from alphacam_cli.core.nesting import Nesting
from alphacam_cli.core.tool import Tool

_ADDINS_INTERFACE_TYPELIB = "{D216BAAC-A717-4793-92D3-1AE37AE3AC2E}"
_ADDINS_TYPELIB = "{A87DD4DB-67C9-4F1B-BC79-A71EE8C7D1E5}"
_ADDINS_INTERFACE_CLSID = "{39BFE38A-D3E4-43EA-89D0-584C776B97A9}"

_MANIFEST_FRESH_TOLERANCE = 0.0
_MANIFEST_POLL_ATTEMPTS = 3
_MANIFEST_POLL_INTERVAL = 0.5


def _try_com_job_setter(job: Any, candidates: tuple[str, ...], value: Any) -> bool:
    """Try a guessed COM property setter on the job object; True when it worked."""
    for name in candidates:
        try:
            if not hasattr(job, name):
                continue
        except Exception:
            continue
        try:
            setattr(job, name, value)
        except Exception:
            return False
        return True
    return False


def _validate_due_date(date_str: str) -> None:
    """Raise RuntimeError unless ``date_str`` is a valid YYYY-MM-DD date."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise RuntimeError(  # noqa: TRY003
            f"cdm: invalid due date: {date_str!r} (expected YYYY-MM-DD)"
        ) from None


_JOB_NAME_MAX_LENGTH = 60
_JOB_NAME_FORBIDDEN_CHARS = '/\\:*?"<>|`'
_JOB_NAME_CONTROL_CHARS = tuple(chr(i) for i in range(32))


def _validate_job_name(name: str) -> str:
    """Validate a CDM job name at the edge and return the stripped name.

    Rejects empty names, names longer than ``_JOB_NAME_MAX_LENGTH``
    characters, ``.``/``..``, Windows path-forbidden characters
    (``/ \\ : * ? " < > |``), backtick (PowerShell escape) and control
    characters (VBA/macro safety).
    Unicode letters (including Polish diacritics), digits, spaces, ``_``,
    ``-`` and similar are allowed.
    """
    name = name.strip()
    if not name:
        raise RuntimeError("cdm: job_name is required")  # noqa: TRY003
    if len(name) > _JOB_NAME_MAX_LENGTH:
        raise RuntimeError(  # noqa: TRY003
            f"cdm: invalid job name: {name!r} "
            f"(max {_JOB_NAME_MAX_LENGTH} characters, got {len(name)})"
        )
    if name in (".", ".."):
        raise RuntimeError(  # noqa: TRY003
            f"cdm: invalid job name: {name!r} (forbidden characters: . ..)"
        )
    found = sorted({c for c in _JOB_NAME_FORBIDDEN_CHARS if c in name})
    if found:
        raise RuntimeError(  # noqa: TRY003
            f"cdm: invalid job name: {name!r} (forbidden characters: {' '.join(found)})"
        )
    if any(c in _JOB_NAME_CONTROL_CHARS for c in name):
        raise RuntimeError(  # noqa: TRY003
            f"cdm: invalid job name: {name!r} (control characters are not allowed)"
        )
    return name


def _manifest_job_matches(parsed: Any, job_name: str) -> bool:
    """Return whether a parsed .acrepd manifest embeds ``job_name``."""
    parsed_job = parsed.get("job") if isinstance(parsed, dict) else None
    parsed_job_name = parsed_job.get("job_name") if isinstance(parsed_job, dict) else None
    return isinstance(parsed_job_name, str) and parsed_job_name.casefold() == job_name.casefold()


class Application:
    """Typed wrapper around AlphaCAM Application COM object."""

    def __init__(self, dispatch: win32.CDispatch) -> None:
        self._app = dispatch
        self._addins: Any | None = None

    @property
    def _raw_app(self) -> Any:
        """Return the raw COM dispatch object (for event sink registration)."""
        return self._app

    @property
    def visible(self) -> bool:
        return bool(self._app.Visible)  # type: ignore[attr-defined]

    @visible.setter
    def visible(self, value: bool) -> None:
        self._app.Visible = value  # type: ignore[attr-defined]

    @property
    def version(self) -> str:
        return str(self._app.AlphacamVersion)  # type: ignore[attr-defined]

    @property
    def full_name(self) -> str:
        return str(self._app.FullName)  # type: ignore[attr-defined]

    @property
    def name(self) -> str:
        return str(self._app.Name)  # type: ignore[attr-defined]

    @property
    def program_level(self) -> int:
        return int(self._app.ProgramLevel)  # type: ignore[attr-defined]

    @property
    def program_letter(self) -> int:
        return int(self._app.ProgramLetter)  # type: ignore[attr-defined]

    @property
    def licomdat_path(self) -> str:
        return str(self._app.LicomdatPath)  # type: ignore[attr-defined]

    @property
    def licomdir_path(self) -> str:
        return str(self._app.LicomdirPath)  # type: ignore[attr-defined]

    @property
    def post_file_name(self) -> str:
        return str(self._app.PostFileName)  # type: ignore[attr-defined]

    @property
    def api_version(self) -> int:
        return int(self._app.ApiVersion)  # type: ignore[attr-defined]

    @property
    def module_type(self) -> str:
        letter = self.program_letter
        if 32 < letter < 127:
            return chr(letter)
        return "?"

    @property
    def is_mill(self) -> bool:
        return self.program_letter == MODULE_MILL

    @property
    def is_router(self) -> bool:
        return self.program_letter == MODULE_ROUTER

    def get_active_drawing(self) -> Drawing | None:
        raw = self._app.ActiveDrawing  # type: ignore[attr-defined]
        if raw is None:
            return None
        return Drawing(raw)

    def create_temp_drawing(self) -> Drawing | None:
        self._app.New()  # type: ignore[attr-defined]
        raw = self._app.ActiveDrawing  # type: ignore[attr-defined]
        if raw is None:
            return None
        return Drawing(raw)

    def open_drawing(self, path: str) -> Drawing | None:
        raw = self._app.OpenDrawing(path)  # type: ignore[attr-defined]
        if raw is None:
            return None
        return Drawing(raw)

    def open_cad_file(self, path: str, fmt: str, clear: bool = False) -> Drawing | None:
        """Open a CAD file (DXF/DWG, IGES, STEP, STL, VDA, CADL) and return the drawing."""
        try:
            self._open_cad(path, fmt, clear)
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to open CAD file '{path}' ({fmt}): {e}") from e  # noqa: TRY003
        return self.get_active_drawing()

    def _open_cad(self, path: str, fmt: str, clear: bool) -> None:
        from alphacam_cli.com.constants import (
            ACAM_IGES_STD,
            ACAM_STEP_SURFACES,
        )

        if fmt in ("dxf", "dwg"):
            self._app.OpenDxfFile(path, clear)  # type: ignore[attr-defined]
        elif fmt in ("igs", "iges"):
            self._app.OpenIgesFile(path, clear, ACAM_IGES_STD)  # type: ignore[attr-defined]
        elif fmt in ("stp", "step"):
            try:
                self._app.OpenStepFileEx(  # type: ignore[attr-defined]
                    path, clear, ACAM_STEP_SURFACES
                )
            except Exception:
                self._app.OpenStepFile(path, clear)  # type: ignore[attr-defined]
        elif fmt == "stl":
            self._app.OpenStlFile(path, clear)  # type: ignore[attr-defined]
        elif fmt == "vda":
            self._app.OpenVdaFile(path, clear)  # type: ignore[attr-defined]
        elif fmt == "cadl":
            self._app.OpenCadlFile(path, clear)  # type: ignore[attr-defined]
        else:
            raise ValueError(f"Unsupported CAD format: {fmt}")  # noqa: TRY003

    def set_dxf_cabinets(self, enabled: bool) -> None:
        """Enable/disable DXF cabinets input (CadInputSettings.DxfSpecial)."""
        from alphacam_cli.com.constants import (
            ACAM_DXF_SPECIAL_CABINETS,
            ACAM_DXF_SPECIAL_STANDARD,
        )

        try:
            settings = self._app.CadInputSettings  # type: ignore[attr-defined]
            settings.DxfSpecial = (  # type: ignore[attr-defined]
                ACAM_DXF_SPECIAL_CABINETS if enabled else ACAM_DXF_SPECIAL_STANDARD
            )
        except Exception as e:
            raise RuntimeError(f"Failed to set DXF cabinets input: {e}") from e  # noqa: TRY003

    def select_tool(self, path: str) -> Tool | None:
        raw = self._app.SelectTool(path)  # type: ignore[attr-defined]
        if raw is None:
            return None
        return Tool(raw)

    def get_current_tool(self) -> Tool | None:
        raw = self._app.GetCurrentTool()  # type: ignore[attr-defined]
        if raw is None:
            return None
        return Tool(raw)

    def create_mill_data(self) -> MillData:
        raw = self._app.CreateMillData()  # type: ignore[attr-defined]
        if raw is None:
            raise RuntimeError("Failed to create mill data")  # noqa: TRY003
        return MillData(raw)

    def new_drawing(
        self,
        width: float = 100,
        height: float = 50,
        fillet: float = 0,
        text: str = "",
    ) -> Drawing | None:
        try:
            self._app.New()  # type: ignore[attr-defined]
        except Exception as e:
            raise RuntimeError(f"Failed to create new drawing: {e}") from e  # noqa: TRY003
        drw = self.get_active_drawing()
        if drw is None:
            return None
        rect = drw.create_rectangle(0, 0, width, height)
        if fillet > 0:
            rect.fillet(fillet)
        if text:
            drw.create_text(text, 5, height / 2, 4)
        drw.zoom_all()
        return drw

    def drawing_parametric(
        self,
        width: float,
        height: float,
        offset: float = 50,
        fillet: float = 5,
    ) -> dict[str, Any]:
        """Create a parametric door/frame panel geometry.

        Outer filleted rectangle + inner arched contour.
        """
        drw = self.create_temp_drawing()
        if drw is None:
            raise RuntimeError("Failed to create drawing")  # noqa: TRY003
        outer, inner = drw.create_panel(width, height, offset, fillet)
        drw.zoom_all()
        return {
            "success": True,
            "geometries_count": drw.geometries_count,
            "tool_paths_count": drw.tool_paths_count,
            "outer": {"tool_in_out": outer.tool_in_out},
            "inner": {"tool_in_out": inner.tool_in_out},
        }

    def quit(self) -> None:
        try:
            self._app.Quit()  # type: ignore[attr-defined]
        except Exception as e:
            raise RuntimeError(f"Failed to quit application: {e}") from e  # noqa: TRY003

    _TOOL_DIRS: ClassVar[dict[str, str]] = {
        "M": "mtools.alp",
        "R": "rtools.alp",
        "L": "ltools.alp",
        "W": "wtools.alp",
        "F": "ftools.alp",
    }

    _POST_DIRS: ClassVar[dict[str, str]] = {
        "M": "MPosts.Alp",
        "R": "RPosts.Alp",
        "L": "LPosts.Alp",
        "W": "WPosts.Alp",
        "F": "FPosts.Alp",
    }

    def _module_dir(self, sub_dir: str) -> str:
        candidates = [
            os.path.join(self.licomdat_path, sub_dir),
            os.path.join(self.licomdat_path, "LICOMDAT", sub_dir),
        ]
        for c in candidates:
            if os.path.isdir(c):
                return c
        return candidates[0]

    def find_tool_files(self, pattern: str = "*.art") -> list[str]:
        sub_dir = type(self)._TOOL_DIRS.get(self.module_type, "mtools.alp")
        base = self._module_dir(sub_dir)
        files = glob.glob(os.path.join(base, pattern))
        files += glob.glob(os.path.join(base, "**", pattern), recursive=True)
        return sorted(set(files))

    def find_post_files(self, pattern: str = "*.arp") -> list[str]:
        sub_dir = type(self)._POST_DIRS.get(self.module_type, "RPosts.Alp")
        base = self._module_dir(sub_dir)
        files = glob.glob(os.path.join(base, pattern))
        files += glob.glob(os.path.join(base, "**", pattern), recursive=True)
        return sorted(set(files))

    def find_style_files(self) -> list[str]:
        base = os.path.join(self.licomdir_path, "Styles")
        files: list[str] = []
        for pattern in ("*.ary", "*.ara"):
            files += glob.glob(os.path.join(base, pattern))
            files += glob.glob(os.path.join(base, "**", pattern), recursive=True)
        return sorted(set(files))

    def get_nesting(self) -> Nesting:
        raw = self._get_nesting_raw()
        if raw is None:
            raise RuntimeError("Failed to get nesting")  # noqa: TRY003
        return Nesting(raw)

    def _get_nesting_raw(self) -> Any:
        try:
            return self._app.Nesting  # type: ignore[attr-defined]
        except Exception:
            import win32com.client as win32  # type: ignore[import-untyped]

            try:
                return win32.Dispatch("AcamNest.Nesting")
            except Exception as e2:
                msg = f"Failed to get nesting (App.Nesting and AcamNest.Nesting failed): {e2}"
                raise RuntimeError(msg) from e2

    def nest_inspect(self) -> dict[str, Any]:
        """Inspect the nesting results of the active drawing (sheets + part placements)."""
        drw = self.get_active_drawing()
        if drw is None:
            raise RuntimeError("No active drawing")  # noqa: TRY003
        try:
            result = drw.get_nest_information().to_dict()
            total_parts = sum(len(sheet["parts"]) for sheet in result["sheets"])
            return {
                "success": True,
                "sheets": result["sheets"],
                "total_parts": total_parts,
            }
        except Exception as e:
            raise RuntimeError(f"nest: inspect failed: {e}") from e  # noqa: TRY003

    def select_post(self, name: str) -> None:
        if "/" not in name and "\\" not in name and not os.path.exists(name):
            files = self.find_post_files()
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
                raise RuntimeError(f"Failed to select post '{name}': no matching post file found")  # noqa: TRY003
            name = matched[0]
        try:
            self._app.SelectPost(name)  # type: ignore[attr-defined]
        except Exception as e:
            raise RuntimeError(f"Failed to select post '{name}': {e}") from e  # noqa: TRY003

    def apply_mill_style(self, style_path: str) -> None:
        try:
            styles = list(self._app.MillMachiningStyles)  # type: ignore[attr-defined]
        except Exception as e:
            raise RuntimeError(f"Failed to apply mill style '{style_path}': {e}") from e  # noqa: TRY003

        target = style_path.replace("\\", "/").lower()
        target_name = os.path.basename(target).lower()
        normalized = [
            (s, str(s.FileName).replace("\\", "/").lower())  # type: ignore[attr-defined]
            for s in styles
        ]
        style = next((s for s, fname in normalized if fname == target), None)
        if style is None:
            style = next(
                (s for s, fname in normalized if os.path.basename(fname) == target_name),
                None,
            )
        if style is None:
            available = ", ".join(fname for _, fname in normalized[:5]) or "none"
            raise RuntimeError(  # noqa: TRY003
                f"Mill style not found: {style_path}. Available styles: {available}"
            )
        try:
            style.Apply()  # type: ignore[attr-defined]
        except Exception as e:
            raise RuntimeError(f"Failed to apply mill style '{style_path}': {e}") from e  # noqa: TRY003

    def find_drawing_files(self, pattern: str = "*.amd") -> list[str]:
        base = os.path.join(self.licomdir_path, "parts")
        return sorted(glob.glob(os.path.join(base, pattern)))

    def glob_files(self, directory: str, pattern: str = "*.amd") -> list[str]:
        return sorted(glob.glob(os.path.join(directory, pattern)))

    # --- Add-ins interface (Reports, NcOutputManager, AutoStyles) ---

    def get_addins(self) -> Any:
        """Return the IAddIns interface for add-in automation (cached)."""
        if self._addins is None:
            self._addins = self._connect_addins()
        return self._addins

    def _connect_addins(self) -> Any:
        try:
            import pythoncom  # type: ignore[import-untyped]
            import win32com.client as w32  # type: ignore[import-untyped]
            from win32com.client import gencache  # type: ignore[import-untyped]
        except ImportError as e:
            raise RuntimeError("Add-ins interface requires pywin32 (Windows only)") from e  # noqa: TRY003
        try:
            gencache.EnsureModule(_ADDINS_INTERFACE_TYPELIB, 0, 1, 0)
            gencache.EnsureModule(_ADDINS_TYPELIB, 0, 1, 0)
            app = self._app
            if app is None:
                app = gencache.EnsureDispatch("Ar5axaps.Application")
            clsid = pythoncom.MakeIID(_ADDINS_INTERFACE_CLSID)
            ai = w32.Dispatch(
                pythoncom.CoCreateInstance(
                    clsid, None, pythoncom.CLSCTX_ALL, pythoncom.IID_IDispatch
                )
            )
            try:
                return ai.GetAddInsInterface(app)
            except Exception:
                return ai.GetAddInsInterface(gencache.EnsureDispatch("Ar5axaps.Application"))
        except Exception as e:
            raise RuntimeError(f"Failed to connect to AlphaCAM add-ins: {e}") from e  # noqa: TRY003

    def get_reports_addin(self) -> Any:
        addins = self.get_addins()
        if addins is None:
            raise RuntimeError("Add-ins interface unavailable")  # noqa: TRY003
        return addins.GetNewReportsAddIn()

    def get_nc_output_manager_addin(self) -> Any:
        addins = self.get_addins()
        if addins is None:
            raise RuntimeError("Add-ins interface unavailable")  # noqa: TRY003
        return addins.GetNcOutputManagerAddIn()

    def get_auto_styles_addin(self) -> Any:
        addins = self.get_addins()
        if addins is None:
            raise RuntimeError("Add-ins interface unavailable")  # noqa: TRY003
        return addins.GetAutoStylesAddIn()

    def _run_reports_data_collection(self, job_name: str | None = None) -> dict[str, Any]:
        """Run the reports add-in data collection for the active drawing.

        Shared by ``reports_create`` and the cdm process flow: resolves the
        data output settings (.acreps), checks the active drawing, creates
        the reports job, saves the manifest and creates the reports. Raises
        RuntimeError when the settings are missing, the drawing is empty or
        Save() reports no data.
        """
        reports = self.get_reports_addin()
        job_name = (job_name or "").strip() or None
        settings_candidates = [
            os.path.join(self.licomdir_path, "LICOMDIR", "Reports", "Settings"),
            os.path.join(self.licomdir_path, "Reports", "Settings"),
        ]
        settings_dir = next(
            (c for c in settings_candidates if os.path.isdir(c)), settings_candidates[0]
        )
        settings_files = sorted(glob.glob(os.path.join(settings_dir, "*.acreps")))
        if not settings_files:
            raise RuntimeError(  # noqa: TRY003
                "reports: no data output settings found "
                "(install .acreps in LICOMDIR\\Reports\\Settings)"
            )
        settings_path = settings_files[0]
        try:
            reports.Settings.SetDataOutputSettingsFromFile(settings_path)
        except Exception as e:
            raise RuntimeError(  # noqa: TRY003
                f"reports: failed to load data output settings: {e}"
            ) from e
        drw = self.get_active_drawing()
        if drw is None or (drw.geometries_count + drw.tool_paths_count == 0):
            raise RuntimeError("reports: active drawing has no geometry or tool paths")  # noqa: TRY003
        job = reports.CreateReportsJob(drw.raw_dispatch)
        if job_name:
            try:
                job.Settings.JobName = job_name
            except Exception as e:
                logger.warning("reports: failed to set job name %r: %s", job_name, e)
        if not job.Save():
            raise RuntimeError("reports: no report data saved (drawing empty?)")  # noqa: TRY003
        job.CreateReports()
        return {
            "success": True,
            "active_drawing": True,
            "settings_file": os.path.basename(settings_path),
        }

    def reports_create(self, job_name: str | None = None) -> dict[str, Any]:
        """Create production reports for the active drawing (headless, no dialogs).

        Data output settings (.acreps) are loaded from
        ``LICOMDIR\\Reports\\Settings`` before the job is created; ``job_name``
        (optional) sets the manifest filename prefix (e.g. for the cdm
        manifest). Save() is honored: False means no report data was written.
        """
        result = self._run_reports_data_collection(job_name)
        result["job"] = "ok"
        return result

    def nc_configs(self) -> dict[str, Any]:
        """List NC output configurations (read-only, no dialogs)."""
        ncman = self.get_nc_output_manager_addin()
        coll = ncman.GetOutputConfigurationsCollection()
        count = int(coll.Count)
        configs: list[str] = []
        for i in range(1, count + 1):
            try:
                configs.append(str(coll.Item(i).Name))
            except Exception:
                configs.append(f"config_{i}")
        return {"count": count, "configs": configs}

    def auto_style_apply(self, file: str) -> dict[str, Any]:
        """Apply an auto-style file to the active drawing (no dialogs)."""
        astyles = self.get_auto_styles_addin()
        try:
            astyles.Apply(file)
        except Exception as e:
            msg = (
                f"failed to apply auto-style '{file}': invalid or unrecognized "
                "AutoStyles file (check format .ara)"
            )
            raise RuntimeError(msg) from e  # noqa: TRY003
        return {"success": True, "file": file}

    def get_automation_manager_addin(self) -> Any:
        """Return the CDM Automation Manager (headless-safe: GetAutomationManagerAddInGUI)."""
        addins = self.get_addins()
        if addins is None:
            raise RuntimeError("Add-ins interface unavailable")  # noqa: TRY003
        return addins.GetAutomationManagerAddInGUI()

    def get_cdm_automation_manager(self) -> Any:
        """Return a fresh CDM Automation Manager (headless-safe).

        Uses a fresh EnsureDispatch connection (same pattern as the gateway
        server) so newly created CDM jobs are visible in am.Jobs; the
        marshalled app reference used by get_addins does not see them.
        """
        try:
            import pythoncom  # type: ignore[import-untyped]
            import win32com.client as w32  # type: ignore[import-untyped]
            from win32com.client import gencache  # type: ignore[import-untyped]
        except ImportError as e:
            raise RuntimeError(  # noqa: TRY003
                "cdm: automation manager requires pywin32 (Windows only)"
            ) from e
        clsid = pythoncom.MakeIID(_ADDINS_INTERFACE_CLSID)
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
                logger.warning("cdm: automation manager attempt %d failed: %s", attempt + 1, e)
                if attempt < 2:
                    time.sleep(3)
        raise RuntimeError(  # noqa: TRY003
            f"cdm: automation manager unavailable: {last_error}"
        ) from last_error

    def create_cdm_job(
        self,
        job_name: str,
        config: str | None = None,
        material: str | None = None,
        customer: str | None = None,
        po: str | None = None,
        due_date: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create an empty CDM job (headless, no dialogs; no order details).

        Config and material are required at creation: explicit arguments win,
        otherwise the database defaults (AM_Settings); when neither exists the
        job is not created (fail-fast). Metadata (customer/po/due date/
        description) is best-effort: a COM setter on the job object is tried
        first (before the single DB save), then a VistaDB UPDATE; failures
        become warnings, never abort the creation.         Material is stored via a
        VistaDB UPDATE after the save; when it fails the job is removed and
        the creation aborts. The job is finalized (JobType + default sheets)
        via a VistaDB UPDATE afterwards; when it fails the job is removed and
        the creation aborts.
        """
        job_name = _validate_job_name(job_name)
        if due_date is not None:
            _validate_due_date(due_date)
        am = self.get_cdm_automation_manager()
        count = cdm_db.job_count(job_name)
        if count is None:
            raise RuntimeError(  # noqa: TRY003
                f"cdm: job existence check failed: {job_name}"
            )
        if count > 0:
            raise RuntimeError(f"cdm: job already exists: {job_name}")  # noqa: TRY003
        defaults: dict[str, Any] | None = None
        config_name = (config or "").strip()
        if not config_name:
            if defaults is None:
                defaults = cdm_db.vdb5_job_defaults()
            config_name = str(defaults.get("config_name") or "").strip()
            if not config_name:
                raise RuntimeError("cdm: no default configuration found")  # noqa: TRY003
        materials = cdm_db.sheet_materials()
        material_name = (material or "").strip()
        material_id: int | None = None
        if material_name:
            material_id = materials.get(material_name)
            if material_id is None:
                raise RuntimeError(f"cdm: material not found: {material_name}")  # noqa: TRY003
        else:
            if defaults is None:
                defaults = cdm_db.vdb5_job_defaults()
            material_id = defaults.get("material_id")
            if material_id is None:
                raise RuntimeError("cdm: no default material found")  # noqa: TRY003
        material_label: str | None = material_name or None
        if material_label is None and material_id is not None:
            material_label = next(
                (n for n, mid in materials.items() if mid == material_id),
                f"id:{material_id}",
            )
        try:
            job = am.NewCDMJob()
            job.JobName = job_name
        except Exception as e:
            raise RuntimeError(f"cdm: create job failed: {e}") from e  # noqa: TRY003
        try:
            job.ConfigurationSetting = am.ConfigurationSettings.GetByName(config_name)
        except Exception as e:
            raise RuntimeError(f"cdm: config not found: {config_name}") from e  # noqa: TRY003
        warnings: list[str] = []
        customer_name: str | None = None
        customer_id: int | None = None
        if customer is not None:
            customer_name = customer.strip()
            if not customer_name:
                warnings.append("cdm: customer name is empty; ignored")
            else:
                customers_map = cdm_db.customers()
                if not customers_map:
                    warnings.append("cdm: customer database unavailable; customer not set")
                else:
                    customer_id = customers_map.get(customer_name)
                    if customer_id is None:
                        warnings.append(f"cdm: customer not found: {customer_name}")
        com_set: set[str] = set()
        if customer_id is not None and _try_com_job_setter(
            job, ("Customer", "CustomerName"), customer_name
        ):
            com_set.add("customer")
        if po is not None and _try_com_job_setter(job, ("PurchaseOrderNumber", "PO"), po):
            com_set.add("po")
        if due_date is not None and _try_com_job_setter(job, ("DueDate",), due_date):
            com_set.add("due_date")
        if description is not None and _try_com_job_setter(
            job, ("JobDescription", "Description"), description
        ):
            com_set.add("description")
        try:
            job.SaveToDatabase()
        except Exception as e:
            raise RuntimeError(f"cdm: create job failed: {e}") from e  # noqa: TRY003
        if not cdm_db.set_job_material(job_name, material_id):
            deleted, reason = cdm_db.cleanup_created_job(
                am,
                job,
                job_name,
                log=lambda msg: logger.warning("cdm: cleanup failed: %s", msg),
            )
            note = "job removed" if deleted else f"cleanup failed: {reason}"
            raise RuntimeError(  # noqa: TRY003
                f"cdm: failed to set material for job {job_name} ({note})"
            )
        if not cdm_db.finalize_cdm_job(job_name):
            deleted, reason = cdm_db.cleanup_created_job(
                am,
                job,
                job_name,
                log=lambda msg: logger.warning("cdm: cleanup failed: %s", msg),
            )
            note = "job removed" if deleted else f"cleanup failed: {reason}"
            raise RuntimeError(  # noqa: TRY003
                f"cdm: failed to finalize job {job_name} ({note})"
            )
        if (
            customer_id is not None
            and "customer" not in com_set
            and not _try_com_job_setter(job, ("Customer", "CustomerName"), customer_name)
            and not cdm_db.set_job_customer(job_name, customer_id)
        ):
            warnings.append("failed to set customer")
        if (
            po is not None
            and "po" not in com_set
            and not _try_com_job_setter(job, ("PurchaseOrderNumber", "PO"), po)
            and not cdm_db.set_job_po(job_name, po)
        ):
            warnings.append("failed to set purchase order number")
        if (
            due_date is not None
            and "due_date" not in com_set
            and not _try_com_job_setter(job, ("DueDate",), due_date)
            and not cdm_db.set_job_due_date(job_name, due_date)
        ):
            warnings.append("failed to set due date")
        if (
            description is not None
            and "description" not in com_set
            and not _try_com_job_setter(job, ("JobDescription", "Description"), description)
            and not cdm_db.set_job_description(job_name, description)
        ):
            warnings.append("failed to set job description")
        return {
            "success": True,
            "job_name": job_name,
            "config": config_name,
            "material": material_label,
            "warnings": warnings,
        }

    def process_cdm_job(
        self,
        job_name: str,
        timeout_seconds: int | None = None,
        output_root: str | None = None,
    ) -> dict[str, Any]:
        """Process a CDM job in-process via the held COM reference.

        The ``ApplyMachiningAfterNesting.Events.HeadlessProcess`` macro runs
        synchronously on ``self._raw_app`` inside the AlphaCAM process
        (~33-41s), so no VBScript/PsExec is needed. ``timeout_seconds`` is
        accepted for API compatibility; the macro is synchronous and
        terminates on its own, and the client-side RPC timeout protects the
        caller. Results come from the Automation Manager job log via
        ``headless.read_job_result``. When the job configuration enables
        ``GenerateReports`` and processing succeeded, the Automation Manager
        generates the report manifest (.acrepd) itself after processing,
        writing it to ``LICOMDIR\\Reports\\Data``. The CLI only verifies that
        a fresh manifest (mtime at or after the process start time) was
        created in the reports data directory and returns its filename in
        ``report.manifest_file``. When several fresh manifests exist for the
        job (multi-material), the newest one by mtime is reported; the
        manifest's embedded job name is verified against ``job_name`` before
        success is reported. Report failures never invalidate a successful
        process run, and reports are never generated for a failed process.
        """
        job_name = _validate_job_name(job_name)
        count = cdm_db.job_count(job_name)
        if count is None:
            raise RuntimeError(  # noqa: TRY003
                f"cdm: job existence check failed: {job_name}"
            )
        if count < 1:
            raise RuntimeError(f"cdm: job not found: {job_name}")  # noqa: TRY003
        cfg = cdm_db.job_config(job_name)
        if output_root is None:
            root = cfg.get("output_root") if cfg else None
            output_root = root if isinstance(root, str) else None
        if not output_root:
            raise RuntimeError(f"cdm: output root not found: {job_name}")  # noqa: TRY003
        t0 = time.monotonic()
        t0_wall = time.time()
        try:
            self._raw_app.Run(headless._HEADLESS_MACRO, job_name)
        except Exception as e:
            raise RuntimeError(  # noqa: TRY003
                f"cdm: process job failed: {e}"
            ) from e
        elapsed_s = round(time.monotonic() - t0, 1)
        result = headless.read_job_result(job_name, output_root, min_mtime=t0_wall)
        success = bool(result.get("success"))
        warnings: list[str] = []
        report: dict[str, Any] = {
            "success": False,
            "skipped": True,
            "error": "reports disabled for job configuration (GenerateReports=False)",
        }
        if cfg is None:
            report = {"success": False, "error": "report flag read failed"}
            warnings.append("cdm: report flag read failed (job config not readable)")
        elif cfg.get("generate_reports") is None:
            report = {"success": False, "error": "report flag read failed"}
            warnings.append(
                "cdm: report flag read failed "
                "(GenerateReports missing or unparseable in job config)"
            )
        elif cfg["generate_reports"] and success:
            try:
                data_dir = acrepd._reports_data_dir(self.licomdir_path)
                manifest: dict[str, Any] | None = None
                fallback_used = False
                last_candidate: dict[str, Any] | None = None
                last_mismatch: dict[str, Any] | None = None
                last_parse_error: Exception | None = None
                parsed_ok = False
                for _attempt in range(_MANIFEST_POLL_ATTEMPTS):
                    manifests = [
                        m
                        for m in acrepd.manifest_files(data_dir)
                        if m.get("mtime") is not None
                        and float(m["mtime"]) >= t0_wall - _MANIFEST_FRESH_TOLERANCE
                    ]
                    fallback_used = False
                    named = sorted(
                        [
                            m
                            for m in manifests
                            if isinstance(m.get("job_name"), str)
                            and m["job_name"].casefold() == job_name.casefold()
                        ],
                        key=lambda m: float(m["mtime"]),
                        reverse=True,
                    )
                    candidates = (
                        named
                        if named
                        else sorted(manifests, key=lambda m: float(m["mtime"]), reverse=True)
                    )
                    if not named and candidates:
                        fallback_used = True
                    parsed_ok = False
                    cycle_parse_error: Exception | None = None
                    for m in candidates:
                        last_candidate = m
                        try:
                            parsed = acrepd.parse_manifest(m["path"])
                        except Exception as e:
                            cycle_parse_error = e
                            continue
                        parsed_ok = True
                        if _manifest_job_matches(parsed, job_name):
                            manifest = m
                            break
                        last_mismatch = m
                    if manifest is not None:
                        break
                    if named:
                        named_paths = {m["path"] for m in named}
                        for m in sorted(
                            [x for x in manifests if x["path"] not in named_paths],
                            key=lambda x: float(x["mtime"]),
                            reverse=True,
                        ):
                            last_candidate = m
                            try:
                                parsed = acrepd.parse_manifest(m["path"])
                            except Exception as e:
                                cycle_parse_error = e
                                continue
                            parsed_ok = True
                            if _manifest_job_matches(parsed, job_name):
                                manifest = m
                                fallback_used = True
                                break
                            last_mismatch = m
                        if manifest is not None:
                            break
                    if parsed_ok:
                        break
                    if cycle_parse_error is not None:
                        last_parse_error = cycle_parse_error
                    if _attempt < _MANIFEST_POLL_ATTEMPTS - 1:
                        time.sleep(_MANIFEST_POLL_INTERVAL)
                if manifest is not None:
                    if fallback_used:
                        warnings.append(
                            f'cdm: manifest name does not match job "{job_name}", '
                            f"using {os.path.basename(manifest['path'])}"
                        )
                    report = {
                        "success": True,
                        "manifest_file": os.path.basename(manifest["path"]),
                        "manifest_path": manifest["path"],
                        "manifest_size": manifest.get("size"),
                    }
                elif last_candidate is not None and parsed_ok and last_mismatch is not None:
                    report = {
                        "success": False,
                        "error": "manifest content does not match job",
                    }
                    if fallback_used:
                        warnings.append(
                            f'cdm: manifest name does not match job "{job_name}", '
                            f"using {os.path.basename(last_mismatch['path'])}"
                        )
                    warnings.append(
                        f'cdm: manifest content does not match job "{job_name}" '
                        f"in {last_mismatch['path']}"
                    )
                elif last_parse_error is not None:
                    report = {"success": False, "error": str(last_parse_error)}
                    warnings.append(f"cdm: report manifest check failed: {last_parse_error}")
                else:
                    report = {
                        "success": False,
                        "error": "no .acrepd manifest found after processing",
                    }
                    warnings.append(
                        f"cdm: report manifest not found after processing in {data_dir}"
                    )
            except Exception as e:
                report = {"success": False, "error": str(e)}
                warnings.append(f"cdm: report manifest check failed: {e}")
        elif not success:
            report = {"success": False, "error": "process failed; report not generated"}
        returned = {
            "success": success,
            "job_name": job_name,
            "status": result.get("status"),
            "processed": success,
            "method": "inproc",
            "elapsed_s": elapsed_s,
            "log": result.get("log"),
            "detail": result.get("detail"),
            "report": report,
        }
        if warnings:
            returned["warnings"] = warnings
        return returned

    def cdm_types(self) -> dict[str, Any]:
        """List CDM door types from the vdb5 database + existing jobs (headless-safe)."""
        am = self.get_cdm_automation_manager()
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
            raise RuntimeError(f"cdm: read door types failed: {e}") from e  # noqa: TRY003
        vdb5_names, vdb5_ok = cdm_db.vdb5_door_type_names()
        return cdm_db.merge_door_types(com_names, vdb5_names, vdb5_ok)

    def cdm_jobs(self) -> dict[str, Any]:
        """List existing CDM jobs (headless-safe)."""
        am = self.get_cdm_automation_manager()
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
            raise RuntimeError(f"cdm: list jobs failed: {e}") from e  # noqa: TRY003
        return {"jobs": jobs_out}

    def import_cdm_csv(
        self,
        csv: str,
        job: str | None = None,
        name: str | None = None,
        config: str | None = None,
        separator: str | None = None,
        has_header: bool = False,
        material: str | None = None,
        import_setting: str | int | None = None,
        preview: bool = False,
    ) -> dict[str, Any]:
        """Import a CSV door order into a single CDM job (headless, no dialogs).

        The column map (and separator/header flag) always come from
        AM_ImportSettings: ``import_setting`` selects one by id or name, and
        without it the setting marked ``Selected`` in the database is used
        (error when none is selected). Extra detail fields
        (customer/order/item/comment/rotation/custom fields) are set on each
        order detail, and the job name/config/material may come from mapped
        job columns. With ``preview`` nothing touches COM: the result is the
        import preview. With --job the rows are added to an existing job;
        otherwise a new job is created only when the setting has
        CreateJob=Yes (name from --name, the mapped job name or the CSV
        basename, max 60 chars) — when CreateJob=No ``job`` is required.
        """
        job = (job or "").strip() or None
        name = (name or "").strip() or None
        if job and name:
            raise RuntimeError("cdm: --name and --job are mutually exclusive")  # noqa: TRY003
        if not csv.strip():
            raise RuntimeError("cdm: csv path is required")  # noqa: TRY003
        if not os.path.exists(csv):
            raise RuntimeError(f"cdm: csv file not found: {csv}")  # noqa: TRY003
        if preview:
            return self.import_cdm_preview(
                csv=csv,
                import_setting=import_setting,
                separator=separator,
                has_header=has_header,
                job=job,
                name=name,
                config=config,
                material=material,
            )
        return self._import_cdm_csv_mapped(
            csv=csv,
            job=job,
            name=name,
            config=config,
            separator=separator,
            has_header=has_header,
            material=material,
            import_setting=import_setting,
        )

    def _import_cdm_csv_mapped(
        self,
        csv: str,
        job: str | None,
        name: str | None,
        config: str | None,
        separator: str | None,
        has_header: bool,
        material: str | None,
        import_setting: str | int | None,
    ) -> dict[str, Any]:
        setting = _resolve_import_setting(import_setting)
        setting_name = str(setting.get("name") or "")
        if job is None and not bool(setting.get("create_job")):
            raise RuntimeError(  # noqa: TRY003
                f"cdm: job is required (import setting '{setting_name}' does not create jobs)"
            )
        eff_separator = separator or str(setting.get("delimiter_char") or ",")
        try:
            rows = cdm_db.read_cdm_csv(csv, eff_separator)
        except Exception as e:
            raise RuntimeError(f"cdm: import csv failed: {e}") from e  # noqa: TRY003
        field_map = cdm_db.field_map_from_setting(setting)
        details, errors = cdm_db.parse_cdm_rows_mapped(
            rows, field_map, has_header or bool(setting.get("ignore_header", False))
        )
        material_name = _cdm_material_name(details, material)
        defaults: dict[str, Any] | None = None
        materials = cdm_db.sheet_materials()
        material_id: int | None = None
        if material_name:
            material_id = materials.get(material_name)
            if material_id is None:
                raise RuntimeError(f"cdm: material not found: {material_name}")  # noqa: TRY003
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
                "job_name": job or "",
                "items": 0,
                "material": material_label,
                "errors": errors,
                "import_setting": setting_name,
            }
        am = self.get_cdm_automation_manager()
        cdm_job: Any = None
        if job:
            try:
                cdm_job = cdm_db.find_cdm_job(am, job)
            except Exception as e:
                raise RuntimeError(f"cdm: job lookup failed: {e}") from e  # noqa: TRY003
            if cdm_job is None:
                count = cdm_db.job_count(job)
                if count is None:
                    raise RuntimeError(  # noqa: TRY003
                        f"cdm: job existence check failed: {job}"
                    )
                if count > 0:
                    raise RuntimeError(  # noqa: TRY003
                        "cdm: job not found via Automation Manager but exists in "
                        f"database (AM cache issue): {job}"
                    )
                raise RuntimeError(f"cdm: job not found: {job}")  # noqa: TRY003
            job_name = job
        else:
            config_name = _cdm_config_name(details, config)
            if not config_name:
                if defaults is None:
                    defaults = cdm_db.vdb5_job_defaults()
                config_name = str(defaults.get("config_name") or "").strip()
                if not config_name:
                    raise RuntimeError("cdm: no default configuration found")  # noqa: TRY003
            job_name = _validate_job_name(_cdm_job_name(details, name, csv))
            count = cdm_db.job_count(job_name)
            if count is None:
                raise RuntimeError(  # noqa: TRY003
                    f"cdm: job existence check failed: {job_name}"
                )
            if count > 0:
                raise RuntimeError(  # noqa: TRY003
                    f"cdm: job already exists: {job_name} "
                    "(use --job to import into the existing job)"
                )
            try:
                cdm_job = am.NewCDMJob()
            except Exception as e:
                raise RuntimeError(f"cdm: create job failed: {e}") from e  # noqa: TRY003
            cdm_job.JobName = job_name
            if config_name:
                try:
                    cdm_job.ConfigurationSetting = am.ConfigurationSettings.GetByName(config_name)
                except Exception as e:
                    raise RuntimeError(f"cdm: config not found: {config_name}") from e  # noqa: TRY003
            try:
                cdm_job.SaveToDatabase()
            except Exception as e:
                raise RuntimeError(f"cdm: create job failed: {e}") from e  # noqa: TRY003
        items = 0
        ok_details: list[dict[str, Any]] = []
        com_active_failed = False
        for d in details:
            try:
                detail = cdm_job.AddCDMOrderDetail(d["style"])
            except Exception:
                errors.append(f"row {d['row']}: door type not found: {d['style']}")
                continue
            try:
                detail.ActiveInProcess = True
            except Exception:
                com_active_failed = True
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
            for field, setter in _FIELD_SETTERS.items():
                value = _detail_field_value(d, field)
                if value is None:
                    continue
                try:
                    setattr(detail, setter, value)
                except Exception as e:
                    errors.append(f"row {d['row']}: {setter} failed: {e}")
            try:
                detail.SaveToDatabase()
            except Exception as e:
                errors.append(f"row {d['row']}: save order detail failed: {e}")
                continue
            items += 1
            ok_details.append(d)
        if com_active_failed and not cdm_db.set_order_details_active(job_name):
            errors.append(f"job {job_name}: failed to set order details active")
        if material_id is not None:
            if not cdm_db.set_job_material(job_name, material_id):
                errors.append(f"job {job_name}: failed to set material")
            if not cdm_db.set_order_detail_material(job_name, material_id):
                errors.append(f"job {job_name}: failed to set order detail material")
        elif material_name is None:
            errors.append(f"job {job_name}: no material set (required for processing)")
        if "door_drilling" in field_map.values() and ok_details:
            values = [bool(d.get("has_drilling") or False) for d in ok_details]
            if not cdm_db.set_has_drilling(job_name, values):
                errors.append(f"job {job_name}: failed to set has_drilling")
        if items == 0 and not job:
            deleted, reason = cdm_db.cleanup_created_job(
                am,
                cdm_job,
                job_name,
                log=lambda msg: logger.warning("cdm import: cleanup failed: %s", msg),
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

    def import_cdm_preview(
        self,
        csv: str,
        import_setting: str | int | None = None,
        separator: str | None = None,
        has_header: bool = False,
        job: str | None = None,
        name: str | None = None,
        config: str | None = None,
        material: str | None = None,
    ) -> dict[str, Any]:
        """Dry-run import preview without touching COM (read, parse, map only).

        Mirrors the real import: the setting is resolved the same way
        (``--import-setting`` or the Selected one) and CreateJob=No requires
        ``job``.
        """
        job = (job or "").strip() or None
        name = (name or "").strip() or None
        if job and name:
            raise RuntimeError("cdm: --name and --job are mutually exclusive")  # noqa: TRY003
        if not csv.strip():
            raise RuntimeError("cdm: csv path is required")  # noqa: TRY003
        if not os.path.exists(csv):
            raise RuntimeError(f"cdm: csv file not found: {csv}")  # noqa: TRY003
        setting = _resolve_import_setting(import_setting)
        setting_name = str(setting.get("name") or "")
        if job is None and not bool(setting.get("create_job")):
            raise RuntimeError(  # noqa: TRY003
                f"cdm: job is required (import setting '{setting_name}' does not create jobs)"
            )
        eff_separator = separator or str(setting.get("delimiter_char") or ",")
        try:
            rows = cdm_db.read_cdm_csv(csv, eff_separator)
        except Exception as e:
            raise RuntimeError(f"cdm: import csv failed: {e}") from e  # noqa: TRY003
        field_map = cdm_db.field_map_from_setting(setting)
        details, errors = cdm_db.parse_cdm_rows_mapped(
            rows, field_map, has_header or bool(setting.get("ignore_header", False))
        )
        defaults = cdm_db.vdb5_job_defaults()
        materials = cdm_db.sheet_materials()
        material_name = _cdm_material_name(details, material)
        material_id: int | None = None
        fatal_error = False
        if material_name:
            material_id = materials.get(material_name)
            if material_id is None:
                errors.append(f"cdm: material not found: {material_name}")
                fatal_error = True
        else:
            material_id = defaults.get("material_id")
        job_name = job if job is not None else _cdm_job_name(details, name, csv)
        if material_name is None and material_id is None:
            errors.append(f"job {job_name}: no material set (required for processing)")
        elif material_name is None and material_id is not None:
            material_name = next(
                (n for n, mid in materials.items() if mid == material_id),
                None,
            )
        config_name = None
        if not job:
            config_name = _cdm_config_name(details, config)
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
            "job": job,
        }

    def cdm_import_settings(self) -> dict[str, Any]:
        """List CDM import settings from the vdb5 database (headless-safe)."""
        settings = cdm_db.import_settings()
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
                    "fields": ", ".join(
                        f"{column}→{name}" for column, name in sorted(field_map.items())
                    ),
                    "fields_count": len(field_map),
                }
            )
        return {"settings": out}

    def cdm_order_details(self, job_name: str | None = None) -> dict[str, Any]:
        """Read CDM order details from the vdb5 database (headless-safe)."""
        return {"order_details": cdm_db.order_details(job_name), "job_name": job_name}

    def cdm_door_paths(self, type_name: str | None = None) -> dict[str, Any]:
        """Read CDM door paths from the vdb5 database (headless-safe)."""
        return {"door_paths": cdm_db.door_paths(type_name), "type_name": type_name}

    def cdm_materials(self) -> dict[str, Any]:
        """Read material definitions from the vdb5 database (headless-safe)."""
        return {"materials": cdm_db.materials()}

    def cdm_configs(self, show: str | None = None) -> dict[str, Any]:
        """Read job configurations from the vdb5 database (headless-safe)."""
        return {"configs": cdm_db.configs(show), "show": show}

    def cdm_lookups(self) -> dict[str, Any]:
        """Read CDM lookup tables from the vdb5 database (headless-safe)."""
        return {"lookups": cdm_db.lookups()}

    def manifest_list(self, data_dir: str | None = None) -> dict[str, Any]:
        """List nesting results manifests (.acrepd) from the reports data directory."""
        data_dir = acrepd._reports_data_dir(self.licomdir_path, data_dir)
        if not os.path.isdir(data_dir):
            raise RuntimeError(  # noqa: TRY003
                f"manifest: reports data directory not found: {data_dir}"
            )
        return {
            "success": True,
            "directory": data_dir,
            "manifests": acrepd.manifest_files(data_dir),
        }

    def manifest_read(
        self,
        job_name: str | None = None,
        material: str | None = None,
        data_dir: str | None = None,
    ) -> dict[str, Any]:
        """Read a nesting results manifest (.acrepd) for a job and optional material."""
        if job_name is None:
            return self.manifest_list(data_dir)
        job_name = _validate_job_name(job_name)
        data_dir = acrepd._reports_data_dir(self.licomdir_path, data_dir)
        if not os.path.isdir(data_dir):
            raise RuntimeError(  # noqa: TRY003
                f"manifest: reports data directory not found: {data_dir}"
            )
        path = acrepd.find_manifest(data_dir, job_name, material)
        if path is None:
            raise RuntimeError(f"manifest: not found: {job_name}")  # noqa: TRY003
        manifest = acrepd.parse_manifest(path)
        _enrich_manifest_customer(manifest, job_name)
        return {"success": True, "manifest": manifest}

    def delete_cdm_job(self, job_name: str) -> dict[str, Any]:
        """Delete a CDM job from the database (headless, no dialogs)."""
        am = self.get_cdm_automation_manager()
        job: Any = None
        try:
            job = cdm_db.find_cdm_job(am, job_name)
        except Exception as e:
            raise RuntimeError(f"cdm: delete job failed: {e}") from e  # noqa: TRY003
        if job is None:
            raise RuntimeError(f"cdm: job not found: {job_name}")  # noqa: TRY003
        if not hasattr(job, "DeleteFromDB"):
            raise RuntimeError("cdm: DeleteFromDB unavailable on job")  # noqa: TRY003
        try:
            job.DeleteFromDB()
        except Exception as e:
            raise RuntimeError(f"cdm: delete job failed: {e}") from e  # noqa: TRY003
        return {"success": True, "job_name": job_name}


def _iter_manifest_parts(manifest: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield every part dict of a manifest (sheet parts and unmatched parts)."""
    for sheet in manifest.get("sheets") or []:
        if not isinstance(sheet, dict):
            continue
        for part in sheet.get("parts") or []:
            if isinstance(part, dict):
                yield part
    for part in manifest.get("unmatched_parts") or []:
        if isinstance(part, dict):
            yield part


def _order_detail_sort_key(detail: dict[str, Any]) -> tuple[bool, int]:
    """Sort order details by cdm_pk; details without a cdm_pk go last (stable)."""
    pk = detail.get("cdm_pk")
    if isinstance(pk, int):
        return (False, pk)
    return (True, 0)


def _enrich_manifest_customer(manifest: dict[str, Any], job_name: str) -> None:
    """Fill part csv_customer_name/csv_order_number/csv_item_number from the database.

    Parts are matched by name ``"<job_name>_<style>_<n>"``, where ``<style>`` is
    the detail type_name (falling back to style_name) and ``<n>`` is the
    occurrence number of the style in order detail order (sorted by cdm_pk).
    Only empty values are filled; unmatched parts stay unchanged. A database
    read failure only logs a warning — the manifest is still returned.
    """
    try:
        details = cdm_db.order_details(job_name)
    except Exception as e:
        logger.warning("manifest: order details read failed for %s: %r", job_name, e)
        return
    if not details:
        return
    try:
        names = cdm_db.custom_field_names()
    except Exception as e:
        logger.warning("manifest: custom field names read failed for %s: %r", job_name, e)
        names = {}
    ordered = sorted((d for d in details if isinstance(d, dict)), key=_order_detail_sort_key)
    counts: dict[str, int] = {}
    detail_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for detail in ordered:
        style = detail.get("type_name")
        if not isinstance(style, str) or not style:
            style = detail.get("style_name")
        if not isinstance(style, str) or not style:
            continue
        counts[style] = counts.get(style, 0) + 1
        detail_by_key[(style, counts[style])] = detail

    prefix = f"{job_name}_"
    for part in _iter_manifest_parts(manifest):
        name = part.get("name")
        if not isinstance(name, str) or not name.startswith(prefix):
            continue
        style, sep, n_str = name[len(prefix) :].rpartition("_")
        if not sep or not style:
            continue
        try:
            n = int(n_str)
        except (TypeError, ValueError):
            continue
        matched = detail_by_key.get((style, n))
        if matched is None:
            continue
        fill_keys = [
            "csv_customer_name",
            "csv_order_number",
            "csv_item_number",
            "production_comment",
        ]
        fill_keys += [f"custom_field_{n}" for n in range(1, 26)]
        custom_fields = matched.get("custom_fields")
        if not isinstance(custom_fields, dict):
            custom_fields = {}
        for key in fill_keys:
            if not part.get(key):
                if key == "production_comment":
                    part[key] = matched.get("production_comment")
                elif key.startswith("custom_field_"):
                    field_num = key.removeprefix("custom_field_")
                    value = custom_fields.get(field_num)
                    if isinstance(value, str) and value.strip():
                        part[key] = value
                else:
                    part[key] = matched.get(key)
    for part in _iter_manifest_parts(manifest):
        named: dict[str, str] = {}
        for n in range(1, 26):
            value = part.get(f"custom_field_{n}")
            if not isinstance(value, str) or not value.strip():
                continue
            label = names.get(n) or f"custom_field_{n}"
            named[label] = value.strip()
        part["custom_fields"] = named


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


def _resolve_import_setting(import_setting: str | int | None) -> dict[str, Any]:
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
            raise RuntimeError(  # noqa: TRY003
                f"cdm: import settings not found: {import_setting}"
            )
        available = ", ".join(
            f"{s.get('id')} '{s.get('name')}'" for s in settings if bool(s.get("is_cdm_import"))
        )
        raise RuntimeError(  # noqa: TRY003
            "cdm: no import setting selected; pass --import-setting or select one in "
            "Automation Manager" + (f" (available: {available})" if available else "")
        )
    if not bool(setting.get("is_cdm_import")):
        name = setting.get("name") or import_setting
        raise RuntimeError(  # noqa: TRY003
            f"cdm: import settings '{name}' is not a CDM import setting"
        )
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
        return explicit
    for detail in details:
        raw = detail.get("job_name")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
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
