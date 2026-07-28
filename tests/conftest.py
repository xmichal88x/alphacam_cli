from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# --- Fake win32com/pythoncom modules for Linux testing ---
_win32com = MagicMock(name="win32com")
_win32com.client = MagicMock(name="win32com.client")
_win32com.client.gencache = MagicMock(name="win32com.client.gencache")
_win32com.client.gencache.EnsureDispatch = MagicMock(name="EnsureDispatch")

_pythoncom = MagicMock(name="pythoncom")
_pythoncom.CoInitialize = MagicMock(name="CoInitialize")

sys.modules["win32com"] = _win32com
sys.modules["win32com.client"] = _win32com.client
sys.modules["win32com.client.gencache"] = _win32com.client.gencache
sys.modules["pythoncom"] = _pythoncom


@pytest.fixture
def mock_com():
    """Mock win32com.client.gencache.EnsureDispatch for testing without AlphaCAM."""
    with patch("win32com.client.gencache.EnsureDispatch") as mock:
        app = MagicMock()
        app.Visible = False
        app.AlphacamVersion = "2024.1"
        app.FullName = "C:\\AlphaCAM\\alphaCAM.exe"
        app.Name = "AlphaCAM"
        app.ProgramLevel = 3
        app.ProgramLetter = 82  # 'R'
        app.LicomdatPath = "C:\\Licomdat"
        app.LicomdirPath = "C:\\Licomdir"
        app.PostFileName = "fanuc.pst"
        app.ApiVersion = 20240315

        # Drawing mock
        drw = MagicMock()
        drw.Geometries.Count = 0
        drw.ToolPaths.Count = 0
        app.ActiveDrawing = drw
        app.CreateTempDrawing.return_value = drw
        app.OpenDrawing.return_value = drw

        # Tool mock
        tool = MagicMock()
        tool.Diameter = 10.0
        tool.Name = "Flat - 10mm"
        tool.Number = 1
        tool.Length = 50.0
        tool.Type = 0
        tool.FeedPerTooth = 0.1
        tool.FileName = "flat_10mm.amt"
        tool.Units = 1
        tool.CornerRadius = 0.0
        tool.Note = ""
        tool.NumberOfTeeth = 2
        app.SelectTool.return_value = tool
        app.GetCurrentTool = tool

        # MillData mock
        md = MagicMock()
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
        md.PocketType = 0
        md.SurfaceMCAction = 0
        md.BottomOfHole = -15.0
        md.DrillType = 0
        md.ChordError = 0.1
        app.CreateMillData.return_value = md

        # Nesting mock
        nest = MagicMock()
        nest.SuppressDialogs = False
        nl = MagicMock()
        nl.Count = 0
        nl.TotalTime = 0
        nest.NewNestList.return_value = nl
        nest.NewSheetList.return_value = MagicMock()
        app.Nesting = nest

        mock.return_value = app
        yield mock
