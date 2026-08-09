from __future__ import annotations

import csv
import os
import sys
import tempfile
import time

import pytest

from alphacam_cli.com.constants import ACAM_TOOL_OUTSIDE


def _test_dir() -> str:
    """Return writable temp dir, configurable via ALPHACAM_TEST_DIR.
    Uses C:\temp as fallback if system temp is problematic."""
    return os.environ.get("ALPHACAM_TEST_DIR") or "C:\\temp"


def _remove_with_retry(path: str, attempts: int = 120, delay: float = 0.5) -> None:
    """Remove a file, retrying while Acam.exe still holds the handle."""
    for _ in range(attempts):
        try:
            os.remove(path)
        except OSError:
            time.sleep(delay)
        else:
            return
    raise RuntimeError(f"Cannot remove {path}: file handle still held")  # noqa: TRY003


@pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows + AlphaCAM")
class TestProductionWorkflows:
    """Integration tests that require a real AlphaCAM installation.

    Uses a single COM connection for all tests (setup/teardown per class)
    to avoid restarting AlphaCAM between tests.

    Set ALPHACAM_TEST_DIR env var to use a specific output directory
    (e.g. D:\\temp if C: is full).
    """

    def setup_method(self, _method: object) -> None:
        from alphacam_cli.com.manager import alphacam_context
        from alphacam_cli.core.application import Application

        self._ctx = alphacam_context(visible=False, keep_alive=True)
        self._raw = self._ctx.__enter__()
        self.ac = Application(self._raw)

    def teardown_method(self, _method: object) -> None:
        self._ctx.__exit__(None, None, None)

    def _write_dir(self) -> str:
        d = _test_dir()
        os.makedirs(d, exist_ok=True)
        # Verify the directory is writable
        probe = os.path.join(d, ".alphacam_test_probe")
        try:
            open(probe, "w").close()
            os.remove(probe)
        except OSError as e:
            raise RuntimeError(  # noqa: TRY003
                f"Cannot write to {d}. Set ALPHACAM_TEST_DIR to a writable path (e.g. D:\\temp)."
            ) from e
        return d

    def test_full_workflow_create_mill_nc(self) -> None:
        """Create a drawing, apply rough milling, generate NC output."""
        drw = self.ac.create_temp_drawing()
        assert drw is not None, "Failed to create temp drawing"

        # Create geometry
        path = drw.create_rectangle(0, 0, 200, 100)
        assert path is not None
        path.tool_in_out = ACAM_TOOL_OUTSIDE
        drw.select_all_geometries()

        # Select a tool — search multiple extensions, including subdirectories
        import glob as _glob

        tool_files = (
            self.ac.find_tool_files("*.amt")
            or self.ac.find_tool_files("*.tool")
            or self.ac.find_tool_files("*.art")
        )
        if not tool_files:
            tool_files = sorted(
                _glob.glob(os.path.join(self.ac.licomdat_path, "**", "*.art"), recursive=True)
            )
        if not tool_files:
            tool_files = sorted(
                _glob.glob(os.path.join(self.ac.licomdat_path, "**", "*.tool"), recursive=True)
            )
        if not tool_files:
            tool_files = sorted(
                _glob.glob(os.path.join(self.ac.licomdat_path, "**", "*.amt"), recursive=True)
            )
        if not tool_files:
            pytest.skip(f"No tool files found in {self.ac.licomdat_path}")

        self.ac.select_tool(tool_files[0])

        # Configure mill data
        md = self.ac.create_mill_data()
        md.safe_rapid_level = 10
        md.rapid_down_to = 2
        md.material_top = 0
        md.final_depth = -5
        md.spindle_speed = 12000
        md.down_feed = 2000
        md.cut_feed = 3000
        md.max_depth_per_cut = 2.5
        md.width_of_cut = 5
        md.stock = 0.5

        # Execute rough finish
        md.rough_finish()
        assert drw.tool_paths_count > 0, "No toolpaths generated"

        # Output NC to writable dir
        nc_path = os.path.join(self._write_dir(), "alphacam_test_workflow.nc")
        try:
            drw.output_nc(nc_path)
            assert os.path.exists(nc_path)
            with open(nc_path, encoding="utf-8", errors="replace") as f:
                content = f.read()
            assert len(content.strip()) > 0, "NC file is empty"
        finally:
            if os.path.exists(nc_path):
                _remove_with_retry(nc_path)

    def test_batch_processing(self) -> None:
        """Process multiple .amd files in batch mode."""
        tmpdir = tempfile.mkdtemp(dir=self._write_dir(), prefix="alphacam_batch_")
        try:
            # Create 2 test drawings
            for i in range(2):
                drw = self.ac.create_temp_drawing()
                assert drw is not None
                drw.create_rectangle(0, 0, 100 + i * 50, 50 + i * 30)
                path = os.path.join(tmpdir, f"test_part_{i}.amd")
                drw.save_as(path)

            # Run batch CLI
            from typer.testing import CliRunner

            from alphacam_cli.main import app

            output_dir = os.path.join(tmpdir, "output")
            runner = CliRunner()
            result = runner.invoke(
                app,
                [
                    "batch",
                    "process",
                    tmpdir,
                    "--output",
                    output_dir,
                ],
            )
            assert result.exit_code == 0, f"Batch failed: {result.stderr}"
            assert "OK: 2" in result.stderr

            # Verify NC files were generated
            for i in range(2):
                nc_path = os.path.join(output_dir, f"test_part_{i}.nc")
                assert os.path.exists(nc_path), f"NC file not found: {nc_path}"
                with open(nc_path, encoding="utf-8", errors="replace") as f:
                    assert len(f.read().strip()) > 0, f"NC file empty: {nc_path}"
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_nesting_from_csv(self) -> None:
        """Import a CSV part list, run nesting, verify sheet layout."""
        tmpdir = tempfile.mkdtemp(dir=self._write_dir(), prefix="alphacam_nest_")
        try:
            # Create part drawings
            part_specs = [
                ("part_a.amd", 100, 50),
                ("part_b.amd", 80, 40),
            ]
            # Select a tool once for the session — required by RoughFinish
            import glob as _glob

            tool_files = (
                self.ac.find_tool_files("*.amt")
                or self.ac.find_tool_files("*.tool")
                or self.ac.find_tool_files("*.art")
            )
            if not tool_files:
                tool_files = sorted(
                    _glob.glob(os.path.join(self.ac.licomdat_path, "**", "*.art"), recursive=True)
                )
            if not tool_files:
                tool_files = sorted(
                    _glob.glob(os.path.join(self.ac.licomdat_path, "**", "*.tool"), recursive=True)
                )
            if not tool_files:
                tool_files = sorted(
                    _glob.glob(os.path.join(self.ac.licomdat_path, "**", "*.amt"), recursive=True)
                )
            if not tool_files:
                pytest.skip(f"No tool files found in {self.ac.licomdat_path}")

            self.ac.select_tool(tool_files[0])

            for fname, w, h in part_specs:
                drw = self.ac.create_temp_drawing()
                assert drw is not None
                drw.create_rectangle(0, 0, w, h)
                drw.select_all_geometries()
                md = self.ac.create_mill_data()
                md.safe_rapid_level = 10
                md.rapid_down_to = 2
                md.material_top = 0
                md.final_depth = -5
                md.spindle_speed = 12000
                md.down_feed = 2000
                md.cut_feed = 3000
                md.rough_finish()
                path = os.path.join(tmpdir, fname)
                drw.save_as(path)

            # Create CSV manifest
            csv_path = os.path.join(tmpdir, "nest_parts.csv")
            with open(csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["filename", "width", "height", "count"])
                writer.writerow(["part_a.amd", 100, 50, 3])
                writer.writerow(["part_b.amd", 80, 40, 2])

            # Create sheet drawing
            sheet_drw = self.ac.create_temp_drawing()
            assert sheet_drw is not None
            sheet_rect = sheet_drw.create_rectangle(0, 0, 600, 300)

            nesting = self.ac.get_nesting()
            nesting.suppress_dialogs = True

            anl_path = os.path.join(tmpdir, "test_nest.anl")
            nest_list = nesting.new_nest_list(anl_path)
            assert nest_list is not None
            nest_list.total_time = 10

            # Add parts from CSV
            with open(csv_path, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    fname = row["filename"]
                    fp = os.path.join(tmpdir, fname)
                    part = nest_list.add_file(fp)
                    part.required = int(row["count"])

            # Create sheet list
            sheet_list = nesting.new_sheet_list()
            sheet_list.add(sheet_rect)

            # Run nesting
            result_list = nesting.nest(nest_list, sheet_list)
            assert result_list is not None
            assert result_list.count > 0

            # Save nest list
            result_list.save()
            assert os.path.exists(anl_path)
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)
