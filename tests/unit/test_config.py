from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from alphacam_cli.core.config import AlphaCamConfig


def test_load_existing_config() -> None:
    mock_data = (
        '{"visible": true, "default_post": "fanuc",'
        ' "default_spindle_speed": 24000, "default_feed": 5000.0}'
    )
    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(Path, "read_text", return_value=mock_data),
    ):
        config = AlphaCamConfig.load()
    assert config.visible is True
    assert config.default_post == "fanuc"
    assert config.default_spindle_speed == 24000
    assert config.default_feed == 5000.0


def test_load_missing_config() -> None:
    with patch.object(Path, "exists", return_value=False):
        config = AlphaCamConfig.load()
    assert config.visible is False
    assert config.default_post == ""
    assert config.default_spindle_speed == 12000
    assert config.default_feed == 3000.0


def test_load_invalid_json() -> None:
    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(Path, "read_text", return_value="not valid json"),
    ):
        config = AlphaCamConfig.load()
    assert config.visible is False
    assert config.default_spindle_speed == 12000


def test_load_filters_unknown_keys() -> None:
    mock_data = '{"visible": true, "unknown_key": "value"}'
    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(Path, "read_text", return_value=mock_data),
    ):
        config = AlphaCamConfig.load()
    assert config.visible is True


def test_save_creates_directory_and_writes() -> None:
    expected = {
        "visible": False,
        "default_post": "",
        "default_spindle_speed": 12000,
        "default_feed": 3000.0,
        "remote_mode": False,
        "remote_host": "127.0.0.1",
        "remote_port": 8721,
    }
    with (
        patch.object(Path, "mkdir") as mock_mkdir,
        patch.object(Path, "write_text") as mock_write,
    ):
        config = AlphaCamConfig()
        config.save()
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    written = json.loads(mock_write.call_args[0][0])
    assert written == expected


def test_save_handles_oserror() -> None:
    with (
        patch.object(Path, "mkdir", side_effect=OSError("Permission denied")),
        patch("logging.getLogger") as mock_get_logger,
    ):
        config = AlphaCamConfig()
        config.save()
    mock_get_logger.return_value.exception.assert_called_once()


def test_merge_with_cli_overrides() -> None:
    config = AlphaCamConfig(
        visible=False,
        default_post="fanuc",
        default_spindle_speed=12000,
        default_feed=3000.0,
    )
    merged = config.merge_with_cli(visible=True, default_spindle_speed=24000)
    assert merged.visible is True
    assert merged.default_post == "fanuc"
    assert merged.default_spindle_speed == 24000
    assert merged.default_feed == 3000.0
    assert config.visible is False


def test_merge_with_cli_ignores_unknown() -> None:
    config = AlphaCamConfig()
    merged = config.merge_with_cli(visible=True, nonexistent_key="x")
    assert merged.visible is True
