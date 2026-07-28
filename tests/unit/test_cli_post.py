from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from alphacam_cli.main import app

runner = CliRunner()


def test_post_list_no_posts_dir() -> None:
    """Posts directory doesn't exist — expect exit code 1."""
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch("os.path.isdir", return_value=False),
    ):
        result = runner.invoke(app, ["post", "list"])
    assert result.exit_code == 1
    assert "Posts directory not found" in result.stderr


def test_post_list_empty() -> None:
    """Posts directory exists but empty — expect exit code 0 with 'No post-processors found'."""
    from tests.unit.test_cli import _mock_com

    with (
        _mock_com(),
        patch("os.path.isdir", return_value=True),
        patch("glob.glob", return_value=[]),
    ):
        result = runner.invoke(app, ["post", "list"])
    assert result.exit_code == 0
    assert "No post-processors found" in result.stderr


def test_post_list_with_posts() -> None:
    """Posts found in licomdir — verify table output."""
    from tests.unit.test_cli import _mock_com

    mock_files = [
        "C:\\Licomdir\\posts\\fanuc.vba",
        "C:\\Licomdir\\posts\\heidenhain.vba",
        "C:\\Licomdir\\posts\\siemens.dll",
    ]
    with (
        _mock_com(),
        patch("os.path.isdir", return_value=True),
        patch("glob.glob", return_value=mock_files),
    ):
        result = runner.invoke(app, ["post", "list"])
    assert result.exit_code == 0
    assert "fanuc" in result.stderr
    assert "heidenhain" in result.stderr
    assert "siemens" in result.stderr
    assert "3 found" in result.stderr


def test_post_list_licomdat_fallback() -> None:
    """No posts in licomdir, but found in licomdat — verify fallback output."""
    from tests.unit.test_cli import _mock_com

    def _glob_side_effect(pattern: str) -> list[str]:
        if "licomdat" in pattern.lower():
            return ["C:\\Licomdat\\posts\\okuma.vba"]
        return []

    with (
        _mock_com(),
        patch("os.path.isdir", return_value=True),
        patch("glob.glob", side_effect=_glob_side_effect),
    ):
        result = runner.invoke(app, ["post", "list"])
    assert result.exit_code == 0
    assert "okuma" in result.stderr
    assert "Licomdat" in result.stderr
