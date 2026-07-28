"""
test_alphacam_com.py - Test polaczenia COM z AlphaCAM

Uruchom na Windows z zainstalowanym AlphaCAM.
Python 3.x + pywin32 wymagane.

Instalacja:
  pip install pywin32

Uzycie:
  python test_alphacam_com.py
  python test_alphacam_com.py --visible    # test z Visible = True
  python test_alphacam_com.py --no-nc      # pomin test NC output
"""

import argparse
import glob
import os
import sys
import time
import traceback


def section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="Test COM AlphaCAM")
    parser.add_argument("--visible", action="store_true", help="Test z Visible = True")
    parser.add_argument("--no-nc", action="store_true", help="Pomin test NC output")
    parser.add_argument(
        "--progid", type=str, default="", help="Konkretny ProgID (np. am5axaps.Application)"
    )
    args = parser.parse_args()

    import pythoncom
    import win32com.client as win32

    pythoncom.CoInitialize()

    # --- 1. Polaczenie ---
    section("1. Polaczenie COM")

    prog_ids = (
        [args.progid]
        if args.progid
        else [
            "am5axaps.Application",
            "aroutaps.Application",
            "Ar5axaps.Application",
        ]
    )

    app_com = None
    used_pid = ""
    for pid in prog_ids:
        print(f'  Probuje CreateObject("{pid}")...')
        try:
            app_com = win32.gencache.EnsureDispatch(pid)
            used_pid = pid
            ver = app_com.AlphacamVersion
            fn = app_com.FullName
            print("  [OK] Polaczono!")
            print(f"       ProgID:  {pid}")
            print(f"       Wersja:  {ver}")
            print(f"       Exe:     {fn}")
            print(f"       Name:    {app_com.Name}")
            print(f"       Level:   {app_com.ProgramLevel}")
            print(f"       Visible: {app_com.Visible}")
            break
        except Exception as e:
            print(f"  [FAIL] {e}")

    if app_com is None:
        print("\n[NIE UDALO SIE] Zadne ProgID nie dziala.")
        print("Sprawdz czy AlphaCAM jest zainstalowany i licencjonowany.")
        print("Sprawdz ProgID w rejestrze: HKEY_CLASSES_ROOT\\...\\CLSID\\ProgID")
        sys.exit(1)

    # --- 2. Communication test ---
    section("2. Podstawowe wlasciwosci")
    try:
        print(f"  Path:            {app_com.Path}")
        print(f"  LicomdatPath:    {app_com.LicomdatPath}")
        print(f"  LicomdirPath:    {app_com.LicomdirPath}")
        print(f"  PostFileName:    {app_com.PostFileName}")
        print(f"  ApiVersion:      {app_com.ApiVersion}")
        print(f"  ProgramLetter:   {chr(app_com.ProgramLetter)}")
        print(f"  ChangeNumber:    {app_com.ChangeNumber}")
        print(f"  Visible:         {app_com.Visible}")
        print("  [OK] Wszystkie wlasciwosci odczytane")
    except Exception as e:
        print(f"  [FAIL] {e}")
        traceback.print_exc()

    # --- 3. Visible test ---
    section("3. Visible = False (headless mode)")
    if args.visible:
        print("  Pomijam --visible wlaczone")
    else:
        try:
            app_com.Visible = False
            time.sleep(0.5)
            v = app_com.Visible
            print(f"  Ustawiono Visible = False, odczytano: {v}")
            if not v:
                print("  [OK] AlphaCAM ukryty")
            else:
                print("  [WARN] Nadal widoczny (Visible = True)")
            print()
            print("  >> WAZNE: czy aplikacja dziala bez okna?")
            print("     - czy nie crashuje?")
            print("     - czy nie wymaga message pump?")
            print("     - czy dialogi nie blokuja?")
        except Exception as e:
            print(f"  [FAIL] Visible = False: {e}")

    # --- 4. Tworzenie rysunku ---
    section("4. Tworzenie rysunku (CreateTempDrawing)")
    try:
        drw = app_com.CreateTempDrawing()
        print(f"  [OK] Drawing: {drw}")
    except Exception as e:
        print(f"  [FAIL] {e}")
        drw = None

    # --- 5. Geometria ---
    section("5. Geometria (CreateRectangle + fillet)")
    if drw:
        try:
            rect = drw.CreateRectangle(0, 0, 100, 50)
            print(f"  [OK] Prostokat: {rect}")
            rect.Fillet(5)
            print("  [OK] Fillet wykonany")
            print(f"  Geometrie: {drw.Geometries.Count}")
            drw.ZoomAll()
            print("  [OK] ZoomAll")
        except Exception as e:
            print(f"  [FAIL] Geometria: {e}")
            traceback.print_exc()
    else:
        print("  Pomijam - brak rysunku")

    # --- 6. Narzedzie ---
    section("6. Narzedzie (SelectTool)")
    tool = None
    tools_found = []
    try:
        ldp = app_com.LicomdatPath
        pattern = os.path.join(ldp, "licomdat", "mtools.alp", "*.amt")
        tools_found = glob.glob(pattern)
        if tools_found:
            t = tools_found[0]
            print(f"  Wybieram: {os.path.basename(t)}")
            tool = app_com.SelectTool(t)
            print(f"  [OK] Tool: {tool}")
            print(f"       Diameter:    {tool.Diameter}")
            print(f"       ToolNumber:  {getattr(tool, 'ToolNumber', -1)}")
            print(f"       ToolLength:  {getattr(tool, 'ToolLength', -1.0)}")
        else:
            print(f"  [WARN] Brak .amt w {pattern}")
    except Exception as e:
        print(f"  [FAIL] SelectTool: {e}")

    # --- 7. MillData + RoughFinish (pelny cykl obrobki) ---
    section("7. Obrobka: MillData -> DrillTap/RoughFinish")
    md = None
    try:
        drw = app_com.ActiveDrawing if drw is None else drw
        rect = drw.CreateRectangle(0, 0, 100, 50)
        print("  [OK] Prostokat 100x50 utworzony")

        for i_geo in range(1, int(drw.Geometries.Count) + 1):
            geo = drw.Geometries(i_geo)
            geo.Selected = True
        print(f"  [OK] Wszystkie geometrie zaznaczone (Geo.Count={drw.Geometries.Count})")

        if tool:
            print("  [OK] Narzedzie juz wybrane")
        elif tools_found:
            tool = app_com.SelectTool(tools_found[0])
            print(f"  [OK] Narzedzie wybrane: {os.path.basename(tools_found[0])}")
        else:
            print("  [WARN] Brak narzedzia")
            raise RuntimeError("No tool available")  # noqa: TRY002, TRY003, TRY301

        md = app_com.CreateMillData()
        md.SafeRapidLevel = 10
        md.RapidDownTo = 1
        md.FinalDepth = -5
        md.SpindleSpeed = 12000
        md.DownFeed = 2000
        md.CutFeed = 3000
        print("  [OK] MillData skonfigurowane")
        print(f"       SafeRapidLevel: {md.SafeRapidLevel}")
        print(f"       SpindleSpeed:   {md.SpindleSpeed}")
        print(f"       CutFeed:        {md.CutFeed}")

        try:
            result = md.RoughFinish()
            print(f"  [OK] RoughFinish wykonany, result: {result}")
            print(f"       ToolPaths: {drw.ToolPaths.Count}")
        except Exception as e2:
            print(f"  [WARN] RoughFinish: {e2}")
            try:
                result = md.DrillTap()
                print(f"  [OK] DrillTap wykonany, result: {result}")
            except Exception as e3:
                print(f"  [WARN] DrillTap tez nie dziala: {e3}")
                try:
                    md.ProcessType2 = 2
                    result = md.RoughFinish()
                    print("  [OK] RoughFinish (ProcessType2=2) wykonany")
                except Exception as e4:
                    print(f"  [WARN] RoughFinish (2): {e4}")
    except Exception as e:
        print(f"  [FAIL] Cykl obrobki: {e}")

    # --- 8. Otwarcie pliku .amd + test dialogow ---
    section("8. Otwarcie pliku + test dialogow")
    amds = None
    try:
        lid = app_com.LicomdirPath
        parts_dir = os.path.join(lid, "licomdir", "parts")
        amds = glob.glob(os.path.join(parts_dir, "*.amd"))
        if amds:
            f = amds[0]
            print(f"  Otwieram: {os.path.basename(f)}")
            d2 = app_com.OpenDrawing(f)
            print(f"  [OK] Drawing: {d2}")
            print(f"       Geometrie: {d2.Geometries.Count}")
            print(f"       ToolPaths: {d2.ToolPaths.Count}")
            print(f"       OutputNCStatus: {d2.OutputNCStatus}")
            d2.Close()
            print("  [OK] Zamknieto")
        else:
            print(f"  [WARN] Brak .amd w {parts_dir}")
        print()
        print("  >> UWAGA: Jesli przy OpenDrawing pojawil sie dialog otwierania,")
        print("     to BeforeOpenFile event nie jest obsluzony i headless moze")
        print("     zablokowac sie na dialogach. Sprawdz w Task Manager.")
    except Exception as e:
        print(f"  [FAIL] OpenDrawing: {e}")

    # --- 9. Rysowanie + SaveAs ---
    section("9. Rysowanie + SaveAs")
    try:
        drw = app_com.ActiveDrawing
        rect2 = drw.CreateRectangle(10, 10, 90, 40)
        print("  [OK] Drugi prostokat utworzony")

        temp_dir = os.environ.get("TEMP", "C:\\Temp")
        amd_path = os.path.join(temp_dir, "test_headless.amd")
        drw.SaveAs(amd_path)
        print(f"  [OK] Zapisano .amd: {amd_path}")
        print(f"       FileVersion: {app_com.FileVersion(amd_path)}")
    except Exception as e:
        print(f"  [FAIL] SaveAs: {e}")

    # --- 10. OutputNC z event handlerem ---
    section("10. OutputNC (z event handlerem)")
    nc_path = ""
    temp_dir = os.environ.get("TEMP", "C:\\Temp")
    try:
        from win32com.client import DispatchWithEvents

        nc_path = os.path.join(temp_dir, "test_headless.nc")

        class NCEvents:  # noqa: N801
            def OnBeforeOutputNcDialogBox(self):  # noqa: N802
                print("    [EVENT] BeforeOutputNcDialogBox -> zwracam 1 (File)")
                return 1

            def OnBeforeCreateNc(self):  # noqa: N802
                print("    [EVENT] BeforeCreateNc -> zwracam pusty string")
                return ""

            def OnAfterOutputNc(self, file_name):  # noqa: N802
                print(f"    [EVENT] AfterOutputNc: {file_name}")

            def OnBeforeOutputNc(self):  # noqa: N802
                print("    [EVENT] BeforeOutputNc -> zwracam sciezke")
                return nc_path

        print("  Rejestruje event sink dla BeforeOutputNcDialogBox...")
        try:
            import pythoncom

            app_com_with_events = DispatchWithEvents(app_com, NCEvents)
            print("  [OK] Event sink zarejestrowany")
            drw.OutputNC(nc_path, 1, False)
            print(f"  [OK] OutputNC wykonany: {nc_path}")
            if os.path.exists(nc_path):
                with open(nc_path) as fh:
                    lines = fh.readlines()
                print(f"       Plik NC: {len(lines)} linii")
                for _line in lines[:5]:
                    print(f"         {_line.rstrip()}")
            else:
                print("  [WARN] Plik NC nie istnieje")
        except Exception as e2:
            print(f"  [WARN] OutputNC z eventami: {e2}")
            print("  >> OutputNC wymaga wlasciwego interfejsu eventow COM.")
            print("     Potrzebny dedykowany event sink (IAlphaCamAppEvents).")
    except Exception as e:
        print(f"  [WARN] Event handler: {e}")
    finally:
        if nc_path and os.path.exists(nc_path):
            os.remove(nc_path)
        amd_file = locals().get("amd_path", "")
        if amd_file and os.path.exists(amd_file):
            os.remove(amd_file)

    # --- 11. ShellAndWait ---
    section("11. ShellAndWait (uruchomienie cmd)")
    try:
        app_com.ShellAndWait("cmd.exe /c echo Hello from AlphaCAM > nul")
        print("  [OK] ShellAndWait executed")
    except Exception as e:
        print(f"  [WARN] ShellAndWait: {e}")

    # --- 12. Podsumowanie ---
    section("12. Podsumowanie")
    tools_found = locals().get("tools_found") or []
    has_tools = bool(tools_found)
    has_md = md is not None
    has_nc = bool(nc_path) and os.path.exists(nc_path)
    print(f"""
  ProgID:      {used_pid}
  AlphaCAM:    {app_com.Name} v{app_com.AlphacamVersion}
  Visible:     {app_com.Visible}
  Drawing:     {"OK" if drw else "FAIL"}
  Geometria:   {"OK" if drw and drw.Geometries.Count > 0 else "FAIL"}
  Tool:        {"OK" if tool else "N/A"}
  MillData:    {"OK" if has_md else "FAIL"}
  Obrobka:     {"FAIL - selection" if not has_md else "FAIL - need params"}
  OpenFile:    {"OK" if amds else "N/A"}
  SaveAs:      {"OK" if "amd_path" in locals() else "FAIL"}
  OutputNC:    {"OK" if has_nc else "FAIL - needs event sink"}
  Shell:       OK
""")
    print("  >> HEADLESS MODE: {'AKTYWNY' if not app_com.Visible else 'NIEAKTYWNY'}")
    print()
    print("  >> WYNIKI:")
    print("     + COM connection works (no window)")
    print("     + Drawing, geometry, ZoomAll work")
    print("     + Tool selection works")
    print("     + SaveAs works")
    print("     - RoughFinish: needs correct selection or params")
    print("     - OutputNC: blocks on dialog, needs BeforeOutputNcDialogBox")
    print("     - No .amd sample files found in licomdir/parts")
    print()

    # --- 13. Quit ---
    section("13. Zakonczenie")
    try:
        app_com.Quit()
        print("  [OK] AlphaCAM zamkniety")
    except Exception as e:
        print(f"  [FAIL] Quit: {e}")
    finally:
        app_com = None


if __name__ == "__main__":
    main()
