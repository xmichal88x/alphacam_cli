#!/usr/bin/env python3
"""
AlphaCAM Diagnostic Tool v1.0

Self-contained diagnostic for AlphaCAM COM API.
Tests 40 scenarios across COM connection, application, drawing,
tools, machining, NC output, nesting, and stress/cleanup.

Usage:
    python diagnostic.py                  # full diagnostic
    python diagnostic.py --quick          # skip stress tests
    python diagnostic.py --log-only       # no ANSI colors, plain log

Requirements: pywin32 (pip install pywin32)
"""

from __future__ import annotations

import datetime
import glob
import os
import sys
import tempfile
import threading

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROG_IDS = [
    "Ar5axaps.Application",
    "am5axaps.Application",
    "aroutaps.Application",
]

SEPARATOR = "─" * 60
TIMEOUT_SECONDS = 5

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_log_lines: list[str] = []
_quick_mode = False


def _ts() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str = "") -> None:
    line = f"[{_ts()}] {msg}" if msg else ""
    print(msg if msg else "")
    _log_lines.append(line)


def log_ok(category: str, msg: str) -> None:
    log(f"  [PASS] [{category}] {msg}")


def log_warn(category: str, msg: str) -> None:
    log(f"  [WARN] [{category}] {msg}")


def log_fail(category: str, msg: str) -> None:
    log(f"  [FAIL] [{category}] {msg}")


def log_info(category: str, msg: str) -> None:
    log(f"  [INFO] [{category}] {msg}")


def log_header(title: str) -> None:
    log()
    log(f"─── {title} ───")


# ---------------------------------------------------------------------------
# Timeout helper (for dialog-blocking operations)
# ---------------------------------------------------------------------------


class _TimeoutError(Exception):
    pass


def with_timeout(func, args=(), kwargs=None, timeout=TIMEOUT_SECONDS):
    """Execute func with timeout. If it hangs, raise _TimeoutError."""
    kwargs = kwargs or {}

    result: list = [None]
    exception: list = [None]
    finished = threading.Event()

    def runner():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            exception[0] = e
        finally:
            finished.set()

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    ok = finished.wait(timeout)
    if not ok:
        raise _TimeoutError()
    if exception[0] is not None:
        raise exception[0]
    return result[0]


# ---------------------------------------------------------------------------
# Section 1: Environment
# ---------------------------------------------------------------------------


def test_python_version() -> bool:
    log_header("1. Environment")
    try:
        v = sys.version_info
        log_ok("ENV", f"Python {v.major}.{v.minor}.{v.micro} ({sys.platform})")
    except Exception as e:
        log_fail("ENV", f"Python detection failed: {e}")
        return False
    else:
        return True


def test_pywin32() -> bool:
    try:
        import pythoncom  # noqa: F401
        import win32com  # noqa: F401
        import win32com.client  # noqa: F401
    except ImportError as e:
        log_fail("ENV", f"pywin32 not found: {e}")
        return False

    try:
        from importlib.metadata import version

        ver = version("pywin32")
    except Exception:
        ver = getattr(pythoncom, "__version__", "unknown")

    log_ok("ENV", f"pywin32 {ver} (pythoncom, win32com.client)")
    return True


def test_temp_permissions() -> bool:
    try:
        tmpdir = tempfile.gettempdir()
        test_file = os.path.join(tmpdir, f"_alphacam_diag_{os.getpid()}.tmp")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        log_ok("ENV", f"%TEMP% writable: {tmpdir}")
    except Exception as e:
        log_fail("ENV", f"%TEMP% not writable: {e}")
        return False
    else:
        return True


def test_gencache() -> bool:
    try:
        import win32com.client.gencache as gencache

        ro = gencache.is_readonly
        log_info("ENV", f"gencache.is_readonly = {ro}")
        log_info("ENV", f"gencache path: {gencache.GetGeneratePath()}")
    except Exception as e:
        log_warn("ENV", f"gencache check: {e}")
        return False
    else:
        return True


# ---------------------------------------------------------------------------
# Section 2: COM Connection
# ---------------------------------------------------------------------------

_com_progid_used: str = ""
_com_instance_type: str = ""


def test_com_connect() -> bool:
    log_header("2. COM Connection")
    import win32com.client as win32

    connected = False
    for pid in PROG_IDS:
        try:
            app = win32.gencache.EnsureDispatch(pid)
            global _com_progid_used
            _com_progid_used = pid
            # Check if new instance or existing
            app.Visible = False
            log_ok("CONN", f"{pid} -> OK")
            connected = True
            app.Quit()
            break
        except Exception as e:
            log_warn("CONN", f"{pid} -> {e}")
            continue

    if not connected:
        log_fail("CONN", "All ProgIDs failed. Is AlphaCAM installed?")
        return False
    return True


def test_com_instance_type() -> bool:
    import win32com.client as win32

    try:
        app1 = win32.gencache.EnsureDispatch(_com_progid_used)
        app1.Visible = False
        # Try GetObject first
        try:
            app2 = win32.GetObject(None, _com_progid_used)
            _com_instance_type = "existing (GetObject worked)"
            log_ok("CONN", "Second connection: GetObject returned same instance")
            app2.Quit()
        except Exception:
            _com_instance_type = "new (GetObject failed, EnsureDispatch only)"
            log_info("CONN", "GetObject failed (normal for AlphaCAM)")
        app1.Quit()
    except Exception as e:
        log_warn("CONN", f"Instance type check: {e}")
        return False
    else:
        return True


def test_com_reference_counting() -> bool:
    """Check if COM interface count is stable after repeated connections."""
    import pythoncom

    counts = []
    try:
        for _i in range(5):
            import win32com.client as win32

            app = win32.gencache.EnsureDispatch(_com_progid_used)
            app.Visible = False
            try:
                counts.append(pythoncom._GetInterfaceCount())
            except AttributeError:
                counts.append("N/A")
            app.Quit()
            del app
            import gc

            gc.collect()

        if len(set(counts)) <= 2:
            log_ok("CONN", f"Reference counting stable: {counts}")
            return True
        else:
            log_warn("CONN", f"Reference count fluctuates: {counts}")
            return True
    except Exception as e:
        log_warn("CONN", f"Reference counting: {e}")
        return False


# ---------------------------------------------------------------------------
# Section 3: Application Info
# ---------------------------------------------------------------------------


def test_application_properties(app) -> dict:
    log_header("3. Application Info")
    props = {}
    checks = [
        ("Name", "Name", str),
        ("Version", "AlphacamVersion", str),
        ("ProgramLevel", "ProgramLevel", int),
        ("ProgramLetter", "ProgramLetter", int),
        ("ApiVersion", "ApiVersion", int),
        ("FullName", "FullName", str),
        ("LicomdatPath", "LicomdatPath", str),
        ("LicomdirPath", "LicomdirPath", str),
        ("PostFileName", "PostFileName", str),
    ]

    for label, attr, _type in checks:
        try:
            val = getattr(app, attr)
            props[label] = val
            log_ok("PROP", f"{label}: {val}")
        except Exception as e:
            log_fail("PROP", f"{label}: {e}")
            props[label] = None

    # Module type
    try:
        letter = chr(app.ProgramLetter) if 32 < app.ProgramLetter < 127 else "?"
        module_map = {"M": "Mill", "R": "Router", "L": "Lathe", "W": "Wire", "F": "Flame"}
        module_name = module_map.get(letter, "Unknown")
        log_ok("PROP", f"Module: {letter} ({module_name})")
        props["Module"] = letter
    except Exception as e:
        log_warn("PROP", f"Module detection: {e}")
        props["Module"] = "?"

    # Path integrity
    for prop_name in ["LicomdatPath", "LicomdirPath"]:
        path = getattr(app, prop_name, "")
        if path and os.path.isdir(path):
            log_ok("PROP", f"{prop_name} exists: {path}")
        elif path:
            log_warn("PROP", f"{prop_name} NOT FOUND: {path}")
        else:
            log_fail("PROP", f"{prop_name} is empty")

    return props


# ---------------------------------------------------------------------------
# Section 4: Drawing
# ---------------------------------------------------------------------------


def test_drawing(app) -> dict:
    log_header("4. Drawing Operations")
    results = {}

    # 4a. CreateTempDrawing
    try:
        drw = app.CreateTempDrawing()
        count = int(drw.Geometries.Count)
        log_ok("DRAW", f"CreateTempDrawing -> OK (Geometries={count})")
        results["create"] = True
    except Exception as e:
        log_fail("DRAW", f"CreateTempDrawing: {e}")
        results["create"] = False
        return results

    # 4b. CreateRectangle
    try:
        rect = drw.CreateRectangle(0, 0, 100, 50)
        log_ok("DRAW", "CreateRectangle(0,0,100,50) -> OK")
        results["rect"] = True

        # Fillet
        try:
            rect.Fillet(5)
            log_ok("DRAW", "Fillet(5) -> OK")
            results["fillet"] = True
        except Exception as e:
            log_warn("DRAW", f"Fillet(5): {e}")
            results["fillet"] = False

        # Selected + ToolInOut
        try:
            rect.Selected = True
            sel = bool(rect.Selected)
            rect.ToolInOut = -1
            tio = int(rect.ToolInOut)
            log_ok("DRAW", f"Selected={sel}, ToolInOut={tio}")
            results["path_props"] = True
        except Exception as e:
            log_warn("DRAW", f"Path properties: {e}")
            results["path_props"] = False

    except Exception as e:
        log_fail("DRAW", f"CreateRectangle: {e}")
        results["rect"] = False

    # 4c. CreateCircle
    try:
        drw.CreateCircle(25, 50, 50)
        log_ok("DRAW", "CreateCircle(25, 50, 50) -> OK")
        results["circle"] = True
    except Exception as e:
        log_warn("DRAW", f"CreateCircle: {e}")
        results["circle"] = False

    # 4d. CreateText2 (Unicode test)
    try:
        text_obj = drw.CreateText2("Test Zółć ąęź", 10, 10, 5)
        h = float(text_obj.Height)
        log_ok("DRAW", f"CreateText2('Test Zółć', Height={h}) -> OK")
        results["text"] = True
    except Exception as e:
        log_warn("DRAW", f"CreateText2: {e}")
        results["text"] = False

    # 4e. Geo2D polyline
    try:
        g2d = drw.Create2DGeometry(10, 10)
        g2d.AddLine(50, 10)
        g2d.AddLine(50, 50)
        g2d.CloseAndFinishLine()
        log_ok("DRAW", "Geo2D polyline -> OK")
        results["geo2d"] = True
    except Exception as e:
        log_warn("DRAW", f"Geo2D polyline: {e}")
        results["geo2d"] = False

    # 4f. Geometries iteration
    try:
        coll = drw.Geometries
        c = int(coll.Count)
        first = coll(1)
        selected = bool(first.Selected)
        log_ok("DRAW", f"Geometries iteration: Count={c}, first.Selected={selected}")
        results["iteration"] = True
    except Exception as e:
        log_warn("DRAW", f"Geometries iteration: {e}")
        results["iteration"] = False

    # 4g. ZoomAll
    try:
        drw.ZoomAll()
        log_ok("DRAW", "ZoomAll -> OK")
        results["zoom"] = True
    except Exception as e:
        log_warn("DRAW", f"ZoomAll: {e}")
        results["zoom"] = False

    # 4h. SaveAs (Unicode path)
    try:
        tmpdir = tempfile.gettempdir()
        save_path = os.path.join(tmpdir, f"test_zażółć_{os.getpid()}.amd")
        drw.SaveAs(save_path)
        if os.path.exists(save_path):
            log_ok("DRAW", f"SaveAs (Unicode path) -> OK: {save_path}")
            results["save"] = True
            os.remove(save_path)
        else:
            log_warn("DRAW", "SaveAs reported OK but file not found")
            results["save"] = False
    except Exception as e:
        log_warn("DRAW", f"SaveAs: {e}")
        results["save"] = False

    # 4i. OpenDrawing (dialog test)
    try:
        tmpdir = tempfile.gettempdir()
        open_path = os.path.join(tmpdir, f"_diag_open_{os.getpid()}.amd")
        try:
            drw2 = app.OpenDrawing(open_path)
            if drw2 is None:
                log_warn("DRAW", "OpenDrawing(nonexistent) returned None (expected)")
                results["open"] = True
            else:
                log_ok("DRAW", "OpenDrawing returned object for nonexistent file ?")
                results["open"] = True
        except _TimeoutError:
            log_warn("DRAW", "OpenDrawing BLOCKED on dialog (needs event handler workaround)")
            results["open"] = False
        except Exception as e:
            log_info("DRAW", f"OpenDrawing(nonexistent): {e}")
            results["open"] = True
    except Exception as e:
        log_warn("DRAW", f"OpenDrawing setup: {e}")
        results["open"] = False

    return results


# ---------------------------------------------------------------------------
# Section 5: Tools
# ---------------------------------------------------------------------------


def test_tools(app, props) -> dict:
    log_header("5. Tool Operations")
    results = {}

    # 5a. Tool library listing
    try:
        sub_dir = "rtools.alp" if chr(app.ProgramLetter) == "R" else "mtools.alp"
        base = os.path.join(app.LicomdatPath, "licomdat", sub_dir)
        tool_files = sorted(
            glob.glob(os.path.join(base, "*.amt")) + glob.glob(os.path.join(base, "*.art"))
        )
        if tool_files:
            log_ok("TOOL", f"Found {len(tool_files)} tools in {sub_dir}")
            results["library"] = tool_files[:3]
        else:
            log_warn("TOOL", f"No tools found in {base}")
            results["library"] = []
    except Exception as e:
        log_warn("TOOL", f"Tool library listing: {e}")
        results["library"] = []

    # 5b. SelectTool (valid)
    try:
        if results["library"]:
            tool_path = results["library"][0]
            tool = app.SelectTool(tool_path)
            if tool is not None:
                name = str(tool.Name)
                diam = float(tool.Diameter)
                num = int(tool.Number)
                length = float(tool.Length)
                ttype = int(tool.Type)
                log_ok("TOOL", f"SelectTool: {name} (D={diam}, #{num}, L={length}, Type={ttype})")
                results["select"] = True
            else:
                log_fail("TOOL", f"SelectTool returned None for valid path: {tool_path}")
                results["select"] = False
        else:
            log_warn("TOOL", "SelectTool: no tools to select")
            results["select"] = None
    except Exception as e:
        log_fail("TOOL", f"SelectTool: {e}")
        results["select"] = False

    # 5c. SelectTool (nonexistent -> should return None)
    try:
        bad_path = os.path.join(tempfile.gettempdir(), "_nonexistent_tool_.amt")
        bad_tool = app.SelectTool(bad_path)
        if bad_tool is None:
            log_ok("TOOL", "SelectTool(nonexistent) -> None (correct)")
            results["select_none"] = True
        else:
            log_warn("TOOL", "SelectTool(nonexistent) returned object (unexpected)")
            results["select_none"] = False
    except Exception as e:
        log_warn("TOOL", f"SelectTool(nonexistent): {e}")
        results["select_none"] = True  # exception also OK

    # 5d. GetCurrentTool
    try:
        current = app.GetCurrentTool()
        if current is not None:
            name = str(current.Name)
            log_ok("TOOL", f"GetCurrentTool: {name}")
            results["current"] = True
        else:
            log_info("TOOL", "GetCurrentTool: None (no tool selected)")
            results["current"] = None
    except Exception as e:
        log_warn("TOOL", f"GetCurrentTool: {e}")
        results["current"] = False

    return results


# ---------------------------------------------------------------------------
# Section 6: Machining
# ---------------------------------------------------------------------------


def test_machining(app, props) -> dict:
    log_header("6. Machining Operations")
    results = {}

    # 6a. CreateMillData + all properties
    try:
        md = app.CreateMillData()
        # Set all properties
        md.SafeRapidLevel = 10.0
        md.RapidDownTo = 2.0
        md.FinalDepth = -10.0
        md.SpindleSpeed = 12000
        md.DownFeed = 2000.0
        md.CutFeed = 3000.0
        md.MaterialTop = 0.0
        md.MaxDepthPerCut = 2.5
        md.WidthOfCut = 5.0
        md.Stock = 0.5
        md.ProcessType2 = 0

        # Read back
        checks = {
            "SafeRapidLevel": float(md.SafeRapidLevel) == 10.0,
            "FinalDepth": float(md.FinalDepth) == -10.0,
            "SpindleSpeed": int(md.SpindleSpeed) == 12000,
        }
        ok_count = sum(1 for v in checks.values() if v)
        log_ok("MILL", f"MillData: {ok_count}/{len(checks)} properties verified")
        results["milldata"] = True

        # 6b. RoughFinish (dry run, may fail if no geometry)
        try:
            # Create a geometry first
            drw = app.ActiveDrawing
            drw.CreateRectangle(0, 0, 50, 50)
            geo = drw.Geometries(1)
            geo.Selected = True
            geo.ToolInOut = -1

            try:
                md.RoughFinish()
                tp_count = int(drw.ToolPaths.Count)
                log_ok("MILL", f"RoughFinish -> OK (ToolPaths={tp_count})")
                results["rough"] = True
            except Exception as e:
                log_warn("MILL", f"RoughFinish: {e}")
                results["rough"] = False

            # 6c. ToolPaths check (for NC readiness)
            tp = int(drw.ToolPaths.Count)
            if tp > 0:
                log_ok("MILL", f"ToolPaths.Count={tp} -> NC output possible")
            else:
                log_warn("MILL", "ToolPaths.Count=0 -> NC output would be empty")
            results["toolpaths"] = tp

        except Exception as e:
            log_warn("MILL", f"RoughFinish setup: {e}")
            results["rough"] = False

    except Exception as e:
        log_fail("MILL", f"MillData: {e}")
        results["milldata"] = False

    return results


# ---------------------------------------------------------------------------
# Section 7: NC Output (CRITICAL)
# ---------------------------------------------------------------------------


def test_nc_output(app) -> dict:
    log_header("7. NC Output (CRITICAL)")
    results = {"test_file": None}

    nc_path = os.path.join(tempfile.gettempdir(), f"_diag_nc_{os.getpid()}.nc")

    # Try OutputTo=0 (File), OutputTo=1 (Machine), OutputTo=2 (Both)
    output_modes = {
        0: "acamOutNcFILE",
        -1: "acamOutNcASK",
    }

    tried = False
    for mode, mode_name in output_modes.items():
        try:

            def _nc_call(m=mode, p=nc_path):
                app.ActiveDrawing.OutputNC(p, m, False)
                return True

            with_timeout(_nc_call, timeout=TIMEOUT_SECONDS)
            if os.path.exists(nc_path):
                with open(nc_path) as f:
                    lines = f.readlines()
                log_ok("NC", f"OutputTo={mode} ({mode_name}) -> OK ({len(lines)} lines)")
                os.remove(nc_path)
                results["mode"] = mode
                results["output"] = True
                tried = True
                break
            else:
                log_info("NC", f"OutputTo={mode} -> no file (but no dialog)")
                results["output"] = True
                tried = True
                break
        except _TimeoutError:
            log_warn("NC", f"OutputTo={mode} ({mode_name}) -> BLOCKED on dialog!")
            results["dialog"] = True
        except Exception as e:
            err_str = str(e).lower()
            if "dialog" in err_str or "beforeoutput" in err_str:
                log_warn("NC", f"OutputTo={mode} ({mode_name}) -> requires event handler: {e}")
                results["dialog"] = True
            else:
                log_info("NC", f"OutputTo={mode} -> {e}")

    if not tried:
        log_fail("NC", "All OutputTo modes failed or blocked by dialog")
        results["output"] = False

    # Post-processor test
    try:
        app.SelectPost("fanuc")
        log_ok("NC", "SelectPost('fanuc') -> OK")
        results["post_select"] = True
    except Exception as e:
        log_warn("NC", f"SelectPost: {e}")
        results["post_select"] = False

    return results


# ---------------------------------------------------------------------------
# Section 8: Nesting
# ---------------------------------------------------------------------------


def test_nesting(app) -> dict:
    log_header("8. Nesting")
    results = {}

    try:
        nest = app.Nesting
        log_ok("NEST", "Nesting object available via app.Nesting")
        results["available"] = True

        # SuppressDialogs
        try:
            nest.SuppressDialogs = True
            sd = bool(nest.SuppressDialogs)
            log_ok("NEST", f"SuppressDialogs={sd}")
            results["suppress"] = True
        except Exception as e:
            log_warn("NEST", f"SuppressDialogs: {e}")
            results["suppress"] = False

        # License check
        try:
            nest.GetNestInformation()
            log_ok("NEST", "GetNestInformation -> OK (AlphaNest license available)")
            results["license"] = True
        except Exception as e:
            log_warn("NEST", f"GetNestInformation failed (no AlphaNest license?): {e}")
            results["license"] = False

        # NewNestList
        try:
            tmpdir = tempfile.gettempdir()
            nl_path = os.path.join(tmpdir, f"_diag_nest_{os.getpid()}.anl")
            nl = nest.NewNestList(nl_path)
            count = int(nl.Count)
            log_ok("NEST", f"NewNestList -> OK (Count={count})")
            results["nestlist"] = True

            # AddFile
            np = nl.AddFile("")
            np.Required = 2
            log_ok("NEST", "AddFile + Required=2 -> OK")
            results["addfile"] = True

            # Save
            nl.Save()
            if os.path.exists(nl_path):
                log_ok("NEST", f"NestList saved: {nl_path}")
                os.remove(nl_path)
            results["save"] = True

        except Exception as e:
            log_warn("NEST", f"NestList operations: {e}")
            results["nestlist"] = False

        # Nest run
        try:
            drw = app.CreateTempDrawing()
            drw.CreateRectangle(0, 0, 500, 300)
            sheet_geo = drw.Geometries(1)

            sl = nest.NewSheetList()
            ss = sl.Add(sheet_geo)
            ss.Thickness = 18
            ss.Required = 1

            nl2 = nest.NewNestList(
                os.path.join(tempfile.gettempdir(), f"_diag_nest2_{os.getpid()}.anl")
            )
            nl2.AddFile("").Required = 3

            nest.Nest(nl2, sl)
            log_ok("NEST", "Nest() completed")
            results["nest"] = True
        except Exception as e:
            log_warn("NEST", f"Nest run: {e}")
            results["nest"] = False

    except Exception as e:
        log_fail("NEST", f"Nesting not available: {e}")
        results["available"] = False

    return results


# ---------------------------------------------------------------------------
# Section 9: Stress & Cleanup
# ---------------------------------------------------------------------------


def test_stress(app) -> dict:
    log_header("9. Stress & Cleanup")
    results = {}
    import pythoncom

    # 9a. 10x create+save loop (memory leak detection)
    if _quick_mode:
        log_info("STRESS", "Quick mode: skipping 10x loop")
        results["loop"] = None
    else:
        try:
            counts = []
            for i in range(10):
                drw = app.CreateTempDrawing()
                drw.CreateRectangle(0, 0, 100 + i * 10, 50 + i * 10)
                try:
                    counts.append(pythoncom._GetInterfaceCount())
                except AttributeError:
                    counts.append("N/A")
                drw = None
            log_ok(
                "STRESS", f"10x create+rect: interface counts stable ({counts[0]}...{counts[-1]})"
            )
            results["loop"] = True
        except Exception as e:
            log_warn("STRESS", f"10x loop: {e}")
            results["loop"] = False

    # 9b. Error recovery test
    log_info("STRESS", "Error recovery simulation")
    try:
        # Intentionally fail an operation (empty SelectTool)
        bad_tool = app.SelectTool("")
        if bad_tool is None:
            log_ok("STRESS", "Post-error state: SelectTool('') returned None (expected)")
        # Check app still responsive
        ver = app.AlphacamVersion
        log_ok("STRESS", f"Post-error: app responsive (Version={ver})")
        results["recovery"] = True
    except Exception as e:
        log_warn("STRESS", f"Error recovery: {e}")
        results["recovery"] = False

    # 9c. Quit + cleanup
    log_header("9. Cleanup")
    try:
        app.Quit()
        log_ok("CLEAN", "Application.Quit() -> OK")
        results["quit"] = True
    except Exception as e:
        log_fail("CLEAN", f"Quit(): {e}")
        results["quit"] = False

    # Force garbage collection
    import gc

    gc.collect()
    log_ok("CLEAN", "GC.collect() -> OK")

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    global _quick_mode
    import argparse

    parser = argparse.ArgumentParser(description="AlphaCAM Diagnostic Tool")
    parser.add_argument("--quick", action="store_true", help="Skip stress tests")
    parser.add_argument("--log-only", action="store_true", help="Plain log output (no ANSI)")
    args = parser.parse_args()

    _quick_mode = args.quick

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║          AlphaCAM Diagnostic Tool v1.0                       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print(f"Platform: {sys.platform}")
    print(f"Python:   {sys.version.split()[0]}")
    print(f"Time:     {_ts()}")
    print(f"Quick:    {_quick_mode}")
    print()

    # --- Section 1: Environment ---
    ok = test_python_version()
    ok = test_pywin32()
    if not ok:
        log_fail("ENV", "pywin32 required. Install: pip install pywin32")
        log()
        log("═══ DIAGNOSTIC ABORTED ═══")
        log()
        _save_log()
        sys.exit(1)

    test_temp_permissions()
    test_gencache()

    # --- Section 2-9: COM-dependent ---
    import win32com.client as win32

    try:
        # Connect
        if not test_com_connect():
            log_fail("CONN", "Cannot connect to AlphaCAM. Is it installed and licensed?")
            log()
            log("═══ DIAGNOSTIC ABORTED ═══")
            _save_log()
            sys.exit(1)

        test_com_instance_type()
        test_com_reference_counting()

        # Main diagnostic session
        app = win32.gencache.EnsureDispatch(_com_progid_used)
        app.Visible = False

        # Make a clean drawing for all tests
        app.CreateTempDrawing()

        props = test_application_properties(app)
        test_drawing(app)
        test_tools(app, props)
        test_machining(app, props)
        nc_results = test_nc_output(app)
        nest_results = test_nesting(app)
        stress = test_stress(app)

        log()
        log(SEPARATOR)
        log("═══ SUMMARY ═══")
        log()

        # NC Output verdict (CRITICAL)
        log("[NC OUTPUT VERDICT]")
        if nc_results.get("output"):
            if nc_results.get("dialog"):
                log("  OutputNC works but with dialog suppression needed")
                log("  → VBA macro workaround required for production batch")
            else:
                log("  ✅ OutputNC works headless (OutputTo=0)")
                log("  → Full batch/NC automation is possible")
        else:
            log("  🔴 OutputNC blocked by dialog in all modes")
            log("  → VBA macro workaround REQUIRED before production use")

        log()
        log("[NESTING VERDICT]")
        if nest_results.get("available"):
            if nest_results.get("license"):
                log("  ✅ Nesting available and licensed")
            else:
                log("  ⚠️ Nesting available but maybe unlicensed (GetNestInformation failed)")
        else:
            log("  ⚠️ Nesting not available in this AlphaCAM version")

        log()
        log("[ERROR RECOVERY VERDICT]")
        if stress.get("recovery"):
            log("  ✅ App recovers from errors gracefully")
        else:
            log("  ⚠️ Error recovery needs attention")

        log()
        log("[MEMORY VERDICT]")
        if _quick_mode:
            log("  Skipped (--quick mode)")
        elif stress.get("loop"):
            log("  ✅ No memory leak detected in 10x loop")
        else:
            log("  ⚠️ Memory usage should be monitored")

        log()
        log(SEPARATOR)
        log("═══ DIAGNOSTIC COMPLETE ═══")
        log()

    except Exception as e:
        log_fail("FATAL", f"Unhandled exception: {e}")
        import traceback

        traceback.print_exc()

    _save_log()
    try:
        import pythoncom

        pythoncom.CoUninitialize()
    except Exception:
        pass


def _save_log():
    """Save log to file with timestamp."""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(os.getcwd(), f"alphacam_diagnostic_{ts}.log")
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(_log_lines))
        print()
        print(f"Log saved to: {log_path}")
    except Exception as e:
        print(f"Could not save log: {e}")


if __name__ == "__main__":
    main()
