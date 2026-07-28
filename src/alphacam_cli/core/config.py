from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

CONFIG_DIR = Path.home() / ".alphacam"
CONFIG_PATH = CONFIG_DIR / "config.json"


@dataclass
class AlphaCamConfig:
    visible: bool = False
    default_post: str = ""
    default_spindle_speed: int = 12000
    default_feed: float = 3000.0
    remote_mode: bool = False
    remote_host: str = "127.0.0.1"
    remote_port: int = 8721

    @classmethod
    def load(cls) -> AlphaCamConfig:
        try:
            if CONFIG_PATH.exists():
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                valid_keys = set(cls.__dataclass_fields__)
                filtered = {k: v for k, v in data.items() if k in valid_keys}
                return cls(**filtered)
        except (json.JSONDecodeError, OSError, TypeError):
            pass
        return cls()

    def save(self) -> None:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(
                json.dumps(asdict(self), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            logging.getLogger("alphacam").exception("Failed to save config")

    def merge_with_cli(self, *, visible: bool | None = None, **kwargs: object) -> AlphaCamConfig:
        merged = AlphaCamConfig(**asdict(self))
        if visible is not None:
            merged.visible = visible
        for key, value in kwargs.items():
            if value is not None and hasattr(merged, key):
                setattr(merged, key, value)
        return merged
