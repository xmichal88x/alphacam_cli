from __future__ import annotations

import glob
import os
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    import win32com.client as win32  # type: ignore[import-untyped]

    from alphacam_cli.core.drawing import Drawing
    from alphacam_cli.core.machining import MillData
    from alphacam_cli.core.nesting import Nesting
    from alphacam_cli.core.tool import Tool

from alphacam_cli.com.constants import MODULE_MILL, MODULE_ROUTER
from alphacam_cli.core import cdm_db
from alphacam_cli.core.drawing import Drawing
from alphacam_cli.core.machining import MillData
from alphacam_cli.core.nesting import Nesting
from alphacam_cli.core.tool import Tool

_ADDINS_INTERFACE_TYPELIB = "{D216BAAC-A717-4793-92D3-1AE37AE3AC2E}"
_ADDINS_TYPELIB = "{A87DD4DB-67C9-4F1B-BC79-A71EE8C7D1E5}"
_ADDINS_INTERFACE_CLSID = "{39BFE38A-D3E4-43EA-89D0-584C776B97A9}"


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
        depth: float | None = None,
        tool: str | None = None,
        spindle: int | None = None,
        feed: float | None = None,
        down_feed: float | None = None,
    ) -> dict[str, Any]:
        """Create a parametric door/frame panel and optionally machine it."""
        drw = self.create_temp_drawing()
        if drw is None:
            raise RuntimeError("Failed to create drawing")  # noqa: TRY003
        outer, inner = drw.create_panel(width, height, offset, fillet)
        if depth is not None:
            if tool:
                self.select_tool(tool)
            md = self.create_mill_data()
            md.safe_rapid_level = 10.0
            md.rapid_down_to = 2.0
            md.material_top = 0.0
            md.final_depth = depth
            if spindle is not None:
                md.spindle_speed = spindle
            if feed is not None:
                md.cut_feed = feed
            if down_feed is not None:
                md.down_feed = down_feed
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
            app = gencache.EnsureDispatch("Ar5axaps.Application")
            clsid = pythoncom.MakeIID(_ADDINS_INTERFACE_CLSID)
            ai = w32.Dispatch(
                pythoncom.CoCreateInstance(
                    clsid, None, pythoncom.CLSCTX_ALL, pythoncom.IID_IDispatch
                )
            )
            return ai.GetAddInsInterface(app)
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

    def reports_create(self) -> dict[str, Any]:
        """Create production reports for the active drawing (headless, no dialogs)."""
        reports = self.get_reports_addin()
        drw = self.get_active_drawing()
        raw = drw.raw_dispatch if drw is not None else None
        job = reports.CreateReportsJob(raw, False, True)
        job.CreateReports()
        return {"success": True, "job": "ok", "active_drawing": drw is not None}

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

    def run_cdm(
        self,
        job_name: str,
        type_name: str,
        width: float = 400,
        length: float = 300,
        quantity: int = 1,
        bypass_nest: bool = False,
        material: str | None = None,
    ) -> dict[str, Any]:
        """Create a CDM job with a single order detail (headless, no dialogs)."""
        job_name = job_name.strip()
        if not job_name:
            raise RuntimeError("cdm: job_name is required")  # noqa: TRY003
        type_name = type_name.strip()
        if not type_name:
            raise RuntimeError("cdm: type_name is required")  # noqa: TRY003
        if width <= 0:
            raise RuntimeError("cdm: width must be positive")  # noqa: TRY003
        if length <= 0:
            raise RuntimeError("cdm: length must be positive")  # noqa: TRY003
        if quantity <= 0:
            raise RuntimeError("cdm: quantity must be positive")  # noqa: TRY003
        am = self.get_automation_manager_addin()
        if cdm_db.find_cdm_job(am, job_name) is not None:
            raise RuntimeError(f"cdm: job already exists: {job_name}")  # noqa: TRY003
        material_name = (material or "").strip() or None
        material_id: int | None = None
        if material_name is not None:
            material_id = cdm_db.sheet_materials().get(material_name)
            if material_id is None:
                raise RuntimeError(f"cdm: material not found: {material_name}")  # noqa: TRY003
        else:
            material_id = cdm_db.vdb5_job_defaults().get("material_id")
        material_label: str | None = material_name
        if material_label is None and material_id is not None:
            material_label = next(
                (n for n, mid in cdm_db.sheet_materials().items() if mid == material_id),
                None,
            )
        try:
            job = am.NewCDMJob()
            job.JobName = job_name
            job.SaveToDatabase()
        except Exception as e:
            raise RuntimeError(f"cdm: create job failed: {e}") from e  # noqa: TRY003
        material_error: str | None = None
        if material_id is not None and not cdm_db.set_job_material(job_name, material_id):
            material_error = "failed to set material"
        try:
            detail = job.AddCDMOrderDetail(type_name)
        except Exception as e:
            raise RuntimeError(f"cdm: door type not found: {type_name}") from e  # noqa: TRY003
        try:
            detail.Width = width
            detail.Length = length
            detail.Quantity = quantity
            detail.ByPassNest = bypass_nest
            detail.SaveToDatabase()
        except Exception as e:
            raise RuntimeError(f"cdm: save order detail failed: {e}") from e  # noqa: TRY003
        result: dict[str, Any] = {
            "success": True,
            "job_name": job_name,
            "type_name": type_name,
            "width": width,
            "length": length,
            "quantity": quantity,
            "material": material_label,
        }
        if material_error is not None:
            result["material_error"] = material_error
        return result

    def cdm_types(self) -> dict[str, Any]:
        """List CDM door types from the vdb5 database + existing jobs (headless-safe)."""
        am = self.get_automation_manager_addin()
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
        am = self.get_automation_manager_addin()
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
        separator: str = ",",
        has_header: bool = False,
        material: str | None = None,
    ) -> dict[str, Any]:
        """Import a CSV door order into a single CDM job (headless, no dialogs).

        CSV columns: Style,Quantity,Width,Height,DesignDimensions,Material. The
        Material column (6th) or the ``material`` argument sets the job's material
        via AM_JobDetails.fkMaterialID; columns beyond 6 are ignored silently. With
        --job the rows are added to an existing job; otherwise a new job is created
        (name from --name or the CSV basename, max 60 chars).
        """
        if job and name:
            raise RuntimeError("cdm: --name and --job are mutually exclusive")  # noqa: TRY003
        if not csv.strip():
            raise RuntimeError("cdm: csv path is required")  # noqa: TRY003
        if not os.path.exists(csv):
            raise RuntimeError(f"cdm: csv file not found: {csv}")  # noqa: TRY003
        try:
            rows = cdm_db.read_cdm_csv(csv, separator)
        except Exception as e:
            raise RuntimeError(f"cdm: import csv failed: {e}") from e  # noqa: TRY003
        details, errors = cdm_db.parse_cdm_rows(rows, has_header)
        material_name = (material or "").strip() or None
        if material_name is None:
            for n, row in enumerate(rows, start=1):
                if has_header and n == 1:
                    continue
                if not any(str(cell).strip() for cell in row):
                    continue
                if len(row) > 5 and str(row[5]).strip():
                    material_name = str(row[5]).strip()
                    break
        defaults: dict[str, Any] | None = None
        material_id: int | None = None
        if material_name:
            material_id = cdm_db.sheet_materials().get(material_name)
            if material_id is None:
                raise RuntimeError(  # noqa: TRY003
                    f"cdm: material not found: {material_name}"
                )
        else:
            defaults = cdm_db.vdb5_job_defaults()
            material_id = defaults.get("material_id")
        material_label: str | None = material_name
        if material_label is None and material_id is not None:
            material_label = next(
                (n for n, mid in cdm_db.sheet_materials().items() if mid == material_id),
                None,
            )
        if not details:
            return {
                "success": False,
                "job_name": job or "",
                "items": 0,
                "material": material_label,
                "errors": errors,
            }
        am = self.get_automation_manager_addin()
        cdm_job: Any = None
        if job:
            try:
                cdm_job = cdm_db.find_cdm_job(am, job)
            except Exception as e:
                raise RuntimeError(f"cdm: import csv failed: {e}") from e  # noqa: TRY003
            if cdm_job is None:
                raise RuntimeError(f"cdm: job not found: {job}")  # noqa: TRY003
            job_name = job
        else:
            config_name = (config or "").strip()
            if not config_name:
                if defaults is None:
                    defaults = cdm_db.vdb5_job_defaults()
                config_name = str(defaults.get("config_name") or "").strip()
                if not config_name:
                    raise RuntimeError(  # noqa: TRY003
                        "cdm: no default configuration found"
                    )
            default_job_name = os.path.splitext(os.path.basename(csv))[0]
            job_name = (name or default_job_name)[:60]
            try:
                cdm_job = am.NewCDMJob()
            except Exception as e:
                raise RuntimeError(f"cdm: create job failed: {e}") from e  # noqa: TRY003
            cdm_job.JobName = job_name
            if config_name:
                try:
                    cdm_job.ConfigurationSetting = am.ConfigurationSettings.GetByName(config_name)
                except Exception as e:
                    raise RuntimeError(  # noqa: TRY003
                        f"cdm: config not found: {config_name}"
                    ) from e
            try:
                cdm_job.SaveToDatabase()
            except Exception as e:
                raise RuntimeError(f"cdm: create job failed: {e}") from e  # noqa: TRY003
        items = 0
        for d in details:
            try:
                detail = cdm_job.AddCDMOrderDetail(d["style"])
            except Exception:
                errors.append(f"row {d['row']}: door type not found: {d['style']}")
                continue
            detail.Width = d["width"]
            detail.Length = d["length"]
            detail.Quantity = d["quantity"]
            design_dims = d["design_dims"]
            if design_dims:
                parts = [p for p in design_dims.split(";") if p != ""]
                if len(parts) < cdm_db.DESIGN_DIMS_FIELDS:
                    parts += ["0"] * (cdm_db.DESIGN_DIMS_FIELDS - len(parts))
                detail.UserVariableString = ";".join(parts)
            try:
                detail.SaveToDatabase()
            except Exception as e:
                errors.append(f"row {d['row']}: save order detail failed: {e}")
                continue
            items += 1
        if material_id is not None:
            if not cdm_db.set_job_material(job_name, material_id):
                errors.append(f"job {job_name}: failed to set material")
        elif material_name is None:
            errors.append(f"job {job_name}: no material set (required for processing)")
        if items == 0 and not job:
            if hasattr(cdm_job, "DeleteFromDB"):
                try:
                    cdm_job.DeleteFromDB()
                except Exception as e:
                    errors.append(f"job {job_name}: no valid order details, cleanup failed: {e}")
                else:
                    errors.append(f"job {job_name}: no valid order details, deleted")
            else:
                errors.append(f"job {job_name}: no valid order details, cleanup failed")
        return {
            "success": items > 0,
            "job_name": job_name,
            "items": items,
            "material": material_label,
            "errors": errors,
        }

    def delete_cdm_job(self, job_name: str) -> dict[str, Any]:
        """Delete a CDM job from the database (headless, no dialogs)."""
        am = self.get_automation_manager_addin()
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

    def machining_pipeline(
        self,
        agq: str | None = None,
        ara: str | None = None,
        layer_map: str | None = None,
    ) -> dict[str, Any]:
        """Run the full machining pipeline on the active drawing.

        1. Create/assign layers ("NAME:1,2;NAME2:3", 1-based geometry indices),
        2. optionally run a geometry query (.agq),
        3. apply an auto-style file (.ara) via the AutoStyles add-in.
        """
        drw = self.get_active_drawing()
        if drw is None:
            raise RuntimeError("No active drawing")  # noqa: TRY003
        if ara is None:
            raise RuntimeError("ara is required")  # noqa: TRY003
        if layer_map:
            geometries = drw.geometries()
            for layer_name, indices in _parse_layer_map(layer_map).items():
                layer = drw.create_layer(layer_name)
                for idx in indices:
                    if idx < 1 or idx > len(geometries):
                        raise RuntimeError(  # noqa: TRY003
                            f"Layer '{layer_name}': geometry index {idx} "
                            f"out of range (1-{len(geometries)})"
                        )
                    geometries[idx - 1].set_layer(layer)
        if agq:
            drw.run_query(agq)
        astyles = self.get_auto_styles_addin()
        try:
            astyles.Apply(ara)
        except Exception as e:
            raise RuntimeError(  # noqa: TRY003
                f"failed to apply auto-style '{ara}': invalid or unrecognized "
                "AutoStyles file (check format .ara)"
            ) from e
        return {
            "success": True,
            "geometries_count": drw.geometries_count,
            "tool_paths_count": drw.tool_paths_count,
        }


def _parse_layer_map(layer_map: str) -> dict[str, list[int]]:
    """Parse "NAME:1,2;NAME2:3" into {layer_name: [1-based indices]}."""
    parsed: dict[str, list[int]] = {}
    for entry in layer_map.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        if ":" not in entry:
            raise ValueError(  # noqa: TRY003
                f"Invalid layer map entry: '{entry}' (expected NAME:1,2)"
            )
        name, _, indices_part = entry.partition(":")
        name = name.strip()
        if not name:
            raise ValueError(  # noqa: TRY003
                f"Invalid layer map entry: '{entry}' (empty layer name)"
            )
        indices: list[int] = []
        for part in indices_part.split(","):
            part = part.strip()
            if not part:
                continue
            if not part.isdigit():
                raise ValueError(  # noqa: TRY003
                    f"Invalid layer map index: '{part}' in '{entry}'"
                )
            indices.append(int(part))
        parsed[name] = indices
    return parsed
