from __future__ import annotations

import csv
from unittest.mock import MagicMock, mock_open, patch

from typer.testing import CliRunner

from alphacam_cli.main import app

runner = CliRunner()


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
