from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DIR_ENV = "ALPHACAM_GATEWAY_LOG_DIR"
_DEFAULT_LOG_DIR = r"%PROGRAMDATA%\AlphaCAMGateway"
_LOG_FILE_NAME = "gateway.log"
_LOG_MAX_BYTES = 10 * 1024 * 1024
_LOG_BACKUP_COUNT = 5


def _log_dir() -> str:
    configured = os.environ.get(_LOG_DIR_ENV, "").strip()
    return os.path.expandvars(configured or _DEFAULT_LOG_DIR)


def _log_file_path() -> str:
    return os.path.join(_log_dir(), _LOG_FILE_NAME)


def _add_file_handler(logger: logging.Logger) -> logging.Handler | None:
    try:
        log_path = _log_file_path()
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        handler = RotatingFileHandler(
            log_path,
            maxBytes=_LOG_MAX_BYTES,
            backupCount=_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)
    except Exception:
        logger.warning("Cannot create gateway log file; stderr only", exc_info=True)
        return None
    else:
        return handler


def run_server(host: str = "0.0.0.0", port: int = 8721) -> None:
    from alphacam_cli.gateway.server import GatewayServer

    server = GatewayServer(host, port)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)
    _add_file_handler(logging.getLogger())
    host = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8721
    print(f"Starting AlphaCAM gateway on {host}:{port}...")
    run_server(host, port)


if __name__ == "__main__":
    main()
