from __future__ import annotations

import csv
from typing import Any
from unittest.mock import MagicMock, mock_open, patch

from typer.testing import CliRunner

from alphacam_cli.main import app

runner = CliRunner()

CSV_DATA = "filename,count\npart1.amd,3\npart2.amd,5\n"


class _BadFloat:
    """float() on this raises TypeError (simulates COM conversion failure)."""

    def __float__(self) -> float:
        raise TypeError("cannot convert")  # noqa: TRY003


class _RaiseOnAttr:
    """Attribute access raises (simulates unavailable COM property)."""

    def __getattr__(self, _name: str) -> Any:
        raise Exception("property unavailable")  # noqa: TRY002,TRY003


def _advanced_mocks() -> tuple[MagicMock, MagicMock]:
    nest_app = MagicMock()
    nesting = nest_app.Nesting
    nesting.Nest.return_value = MagicMock(Count=1)
    return nest_app, nesting


def test_nest_list_no_files() -> None:
    with patch("glob.glob", return_value=[]):
        result = runner.invoke(app, ["nest", "list"])
    assert result.exit_code == 0
    assert "No .anl" in result.stderr


def test_nest_list_with_files() -> None:
    with patch("glob.glob", return_value=["test.anl", "parts.anl"]):
        result = runner.invoke(app, ["nest", "list"])
    assert result.exit_code == 0
    assert "test" in result.stderr
    assert "parts" in result.stderr


def test_nest_run_csv_not_found() -> None:
    from tests.unit.test_cli import _mock_com

    with _mock_com():
        result = runner.invoke(app, ["nest", "run", "/nonexistent.csv"])
    assert result.exit_code == 1
    assert "CSV file not found" in result.stderr


def test_nest_run_invalid_csv() -> None:
    from tests.unit.test_cli import _mock_com

    csv_data = "filename,count\npart1,abc\npart2,xyz\n"
    with (
        _mock_com(),
        patch("os.path.isfile", return_value=True),
        patch("builtins.open", mock_open(read_data=csv_data)),
    ):
        result = runner.invoke(app, ["nest", "run", "parts.csv"])
    assert result.exit_code == 1
    assert "No valid parts" in result.stderr


def test_nest_run_valid_csv() -> None:
    from tests.unit.test_cli import _mock_com

    csv_data = "filename,count\npart1.amd,3\npart2.amd,5\n"
    with (
        _mock_com(),
        patch("os.path.isfile", return_value=True),
        patch("builtins.open", mock_open(read_data=csv_data)),
    ):
        result = runner.invoke(app, ["nest", "run", "parts.csv"])
    assert result.exit_code == 0
    assert "Nesting completed" in result.stderr


def test_nest_run_empty_rows_in_csv() -> None:
    from tests.unit.test_cli import _mock_com

    csv_data = "filename,count\npart1.amd,3\n,\npart2.amd,5\n"
    with (
        _mock_com(),
        patch("os.path.isfile", return_value=True),
        patch("builtins.open", mock_open(read_data=csv_data)),
    ):
        result = runner.invoke(app, ["nest", "run", "parts.csv"])
    assert result.exit_code == 0
    assert "Nesting completed" in result.stderr


def test_nest_run_csv_error() -> None:
    from tests.unit.test_cli import _mock_com

    mock_reader = MagicMock()
    mock_reader.__iter__.side_effect = csv.Error("parse error")
    with (
        _mock_com(),
        patch("os.path.isfile", return_value=True),
        patch("builtins.open", mock_open(read_data="dummy")),
        patch("csv.DictReader", return_value=mock_reader),
    ):
        result = runner.invoke(app, ["nest", "run", "parts.csv"])
    assert result.exit_code == 1
    assert "CSV error" in result.stderr


def test_nest_run_drawing_fails() -> None:
    from tests.unit.test_cli import _mock_com

    csv_data = "filename,count\npart1.amd,3\n"
    with (
        _mock_com() as mock_app,
        patch("os.path.isfile", return_value=True),
        patch("builtins.open", mock_open(read_data=csv_data)),
    ):
        mock_app.ActiveDrawing = None
        result = runner.invoke(app, ["nest", "run", "parts.csv"])
    assert result.exit_code == 1
    assert "Failed to create drawing" in result.stderr


def test_nest_list_glob_error() -> None:
    with patch("glob.glob", side_effect=OSError("permission denied")):
        result = runner.invoke(app, ["nest", "list"])
    assert result.exit_code == 1
    assert "Error" in result.stderr


def test_nest_run_advanced() -> None:
    from tests.unit.test_cli import _mock_com

    nest_app, nesting = _advanced_mocks()
    nest_part = nesting.NewNestList.return_value.AddFile.return_value
    nest_sheet = nesting.NewSheetList.return_value.Add.return_value
    with (
        _mock_com(app_mock=nest_app),
        patch("os.path.isfile", return_value=True),
        patch("builtins.open", mock_open(read_data=CSV_DATA)),
    ):
        result = runner.invoke(app, ["nest", "run", "parts.csv", "--advanced"])
    assert result.exit_code == 0
    assert "Nesting completed" in result.stderr
    assert "Total parts: 8" in result.stderr
    assert "Un-nested parts: 1" in result.stderr
    nesting.NewNestList.assert_called_once()
    assert nest_part.Required == 5
    assert nest_sheet.Required == 1
    nesting.Nest.assert_called_once()
    nesting.DeleteAllNestLists.assert_called_once()


def test_nest_run_advanced_options() -> None:
    from tests.unit.test_cli import _mock_com

    nest_app, nesting = _advanced_mocks()
    nl = nesting.NewNestList.return_value
    with (
        _mock_com(app_mock=nest_app),
        patch("os.path.isfile", return_value=True),
        patch("builtins.open", mock_open(read_data=CSV_DATA)),
    ):
        result = runner.invoke(
            app,
            [
                "nest",
                "run",
                "parts.csv",
                "--advanced",
                "--total-time",
                "60",
                "--optimise-level",
                "1",
                "--part-gap",
                "2.0",
                "--cut-width",
                "3.0",
                "--nesting-method",
                "2",
                "--optimise-for-cuts",
                "1",
                "--cut-direction",
                "1",
                "--resolution",
                "0.5",
                "--select-best-sheet",
                "1",
                "--no-aperture-nesting",
                "--order-by-part",
                "--no-subroutines",
                "--minimise-tool-changes",
                "--strict-priorities",
                "--inner-first",
                "--preserve-sheet-edge",
                "--gap",
                "7",
                "--edge-gap",
                "3",
                "--lead-gap",
                "1",
            ],
        )
    assert result.exit_code == 0
    assert nl.TotalTime == 60.0
    assert nl.OptimiseLevel == 1
    assert nl.PartGap == 2.0
    assert nl.CutWidth == 3.0
    assert nl.NestingMethod == 2
    assert nl.OptimiseForCuts == 1
    assert nl.CutDirection == 1
    assert nl.Resolution == 0.5
    assert nl.SelectBestSheet == 1
    assert nl.PreventApertureNest is True
    assert nl.OrderByPart is True
    assert nl.UseSubroutines is False
    assert nl.MinimiseToolChanges is True
    assert nl.StrictPriorities is True
    assert nl.InnerFirst is True
    assert nl.PreserveSheetEdge is True
    assert nl.EdgeGap == 3.0
    assert nl.LeadInGap == 1.0


def test_nest_run_advanced_sheet_from_library() -> None:
    from tests.unit.test_cli import _mock_com

    nest_app, nesting = _advanced_mocks()
    sheet = nesting.SheetDatabase.FindSheet.return_value
    sheet.Thickness.Thickness = 19.0
    with (
        _mock_com(app_mock=nest_app),
        patch("os.path.isfile", return_value=True),
        patch("builtins.open", mock_open(read_data=CSV_DATA)),
    ):
        result = runner.invoke(
            app, ["nest", "run", "parts.csv", "--advanced", "--sheet-name", "MDF_18"]
        )
    assert result.exit_code == 0
    nesting.SheetDatabase.FindSheet.assert_called_once_with("MDF_18")
    sheet.InsertInActiveDrawingAtPoint.assert_called_once_with(0.0, 0.0)
    nest_sheet = nesting.NewSheetList.return_value.Add.return_value
    assert nest_sheet.Thickness == 19.0


def test_nest_run_advanced_sheet_thickness_fallback() -> None:
    from tests.unit.test_cli import _mock_com

    nest_app, nesting = _advanced_mocks()
    sheet = nesting.SheetDatabase.FindSheet.return_value
    sheet.Thickness.Thickness = _BadFloat()
    with (
        _mock_com(app_mock=nest_app),
        patch("os.path.isfile", return_value=True),
        patch("builtins.open", mock_open(read_data=CSV_DATA)),
    ):
        result = runner.invoke(
            app, ["nest", "run", "parts.csv", "--advanced", "--sheet-name", "MDF_18"]
        )
    assert result.exit_code == 0
    assert nesting.NewSheetList.return_value.Add.return_value.Thickness == 18.0


def test_nest_run_advanced_sheet_not_found() -> None:
    from tests.unit.test_cli import _mock_com

    nest_app, nesting = _advanced_mocks()
    nesting.SheetDatabase.FindSheet.side_effect = Exception("not in library")
    with (
        _mock_com(app_mock=nest_app),
        patch("os.path.isfile", return_value=True),
        patch("builtins.open", mock_open(read_data=CSV_DATA)),
    ):
        result = runner.invoke(
            app, ["nest", "run", "parts.csv", "--advanced", "--sheet-name", "NOPE"]
        )
    assert result.exit_code == 1
    assert "sheet from library not found" in result.stderr


def test_nest_run_gap_options() -> None:
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com() as mock_app,
        patch("os.path.isfile", return_value=True),
        patch("builtins.open", mock_open(read_data=CSV_DATA)),
    ):
        result = runner.invoke(
            app, ["nest", "run", "parts.csv", "--gap", "4", "--edge-gap", "6", "--lead-gap", "2"]
        )
    assert result.exit_code == 0
    nd = mock_app.ActiveDrawing.CreateNestData.return_value
    assert nd.Gap == 4.0
    assert nd.EdgeGap == 6.0
    assert nd.LeadGap == 2.0


def test_nest_run_sheet_from_library() -> None:
    from tests.unit.test_cli import _mock_com

    nest_app, nesting = _advanced_mocks()
    sheet = nesting.SheetDatabase.FindSheet.return_value
    sheet.Thickness.Thickness = 19.0
    sheet.Material.Name = "MDF"
    sheet.Quantity = 2
    paths = sheet.InsertInActiveDrawingAtPoint.return_value
    with (
        _mock_com(app_mock=nest_app) as mock_app,
        patch("os.path.isfile", return_value=True),
        patch("builtins.open", mock_open(read_data=CSV_DATA)),
    ):
        result = runner.invoke(app, ["nest", "run", "parts.csv", "--sheet-name", "MDF_18"])
    assert result.exit_code == 0
    assert "Nesting completed" in result.stderr
    nd = mock_app.ActiveDrawing.CreateNestData.return_value
    nd.AddSheet.assert_called_once_with(paths.Item(1), "MDF", 19.0, 2)
    nd.DoNest.assert_called_once_with()


def test_nest_run_sheet_thickness_fallback() -> None:
    from tests.unit.test_cli import _mock_com

    nest_app, nesting = _advanced_mocks()
    sheet = nesting.SheetDatabase.FindSheet.return_value
    sheet.Thickness = _RaiseOnAttr()
    sheet.Material.Name = "MDF"
    sheet.Quantity = 1
    paths = sheet.InsertInActiveDrawingAtPoint.return_value
    with (
        _mock_com(app_mock=nest_app) as mock_app,
        patch("os.path.isfile", return_value=True),
        patch("builtins.open", mock_open(read_data=CSV_DATA)),
    ):
        result = runner.invoke(app, ["nest", "run", "parts.csv", "--sheet-name", "MDF_18"])
    assert result.exit_code == 0
    nd = mock_app.ActiveDrawing.CreateNestData.return_value
    nd.AddSheet.assert_called_once_with(paths.Item(1), "MDF", 18.0, 1)


def test_nest_run_sheet_not_found() -> None:
    from tests.unit.test_cli import _mock_com

    nest_app, nesting = _advanced_mocks()
    nesting.SheetDatabase.FindSheet.side_effect = Exception("not in library")
    with (
        _mock_com(app_mock=nest_app),
        patch("os.path.isfile", return_value=True),
        patch("builtins.open", mock_open(read_data=CSV_DATA)),
    ):
        result = runner.invoke(app, ["nest", "run", "parts.csv", "--sheet-name", "NOPE"])
    assert result.exit_code == 1
    assert "sheet from library not found" in result.stderr
