# ruff: noqa: TRY003

from __future__ import annotations

import contextlib
import logging
import socket
from typing import Any, cast

from alphacam_cli.gateway.protocol import (
    COM_ERROR,
    make_request,
    pack_message,
    read_frame,
)


class RemoteConnectionError(Exception):
    """Connection-level errors."""


class RemoteComError(Exception):
    """COM errors on the server."""


class RemoteSession:
    def __init__(self, host: str = "127.0.0.1", port: int = 8721, timeout: float = 180.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._msg_id: int = 0
        self._logger = logging.getLogger("alphacam.remote")

    def connect(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(self.timeout)
        self._sock.connect((self.host, self.port))
        self._logger.info("Connected to %s:%s", self.host, self.port)

    def _call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._msg_id += 1
        msg_id = self._msg_id
        request = make_request(method, params or {}, msg_id)
        packed = pack_message(request)
        if self._sock is None:
            raise RemoteConnectionError("Not connected")
        self._sock.sendall(packed)
        raw = read_frame(self._sock)
        if raw is None:
            raise RemoteConnectionError("Connection closed by server")
        response = cast(dict[str, Any], raw)
        if "error" in response:
            error = cast(dict[str, Any], response["error"])
            code = error.get("code")
            message = error.get("message", "Unknown error")
            if code == COM_ERROR:
                raise RemoteComError(str(message))
            raise RemoteConnectionError(f"JSON-RPC error ({code}): {message}")
        return response["result"]

    def close(self) -> None:
        if self._sock is not None:
            with contextlib.suppress(Exception):
                self._sock.close()
            self._sock = None
            self._logger.debug("Connection closed")

    def __enter__(self) -> RemoteSession:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def ping(self) -> dict[str, Any]:
        return self._call("ping")  # type: ignore[no-any-return]

    def get_info(self) -> dict[str, Any]:
        return self._call("get_info")  # type: ignore[no-any-return]

    def new_drawing(
        self, width: float = 100, height: float = 50, fillet: float = 0, text: str = ""
    ) -> dict[str, Any]:
        return self._call(  # type: ignore[no-any-return]
            "new_drawing", {"width": width, "height": height, "fillet": fillet, "text": text}
        )

    def create_temp_drawing(self) -> dict[str, Any]:
        return self._call("create_temp_drawing")  # type: ignore[no-any-return]

    def zoom_all(self) -> dict[str, Any]:
        return self._call("zoom_all")  # type: ignore[no-any-return]

    def open_drawing(self, path: str) -> dict[str, Any]:
        return self._call("open_drawing", {"path": path})  # type: ignore[no-any-return]

    def save_active_drawing(self, path: str) -> dict[str, Any]:
        return self._call("save_active_drawing", {"path": path})  # type: ignore[no-any-return]

    def get_active_drawing(self) -> dict[str, Any] | None:
        return self._call("get_active_drawing")  # type: ignore[no-any-return]

    def list_tools(self, pattern: str = "*.art") -> list[str]:
        return self._call("list_tools", {"pattern": pattern})  # type: ignore[no-any-return]

    def select_tool(self, name: str) -> dict[str, Any]:
        return self._call("select_tool", {"name": name})  # type: ignore[no-any-return]

    def get_current_tool(self) -> dict[str, Any] | None:
        return self._call("get_current_tool")  # type: ignore[no-any-return]

    def mill_rough(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("mill_rough", kwargs)  # type: ignore[no-any-return]

    def mill_pocket(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("mill_pocket", kwargs)  # type: ignore[no-any-return]

    def mill_drill(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("mill_drill", kwargs)  # type: ignore[no-any-return]

    def output_nc(self, path: str, post: str = "") -> dict[str, Any]:
        return self._call("output_nc", {"path": path, "post": post})  # type: ignore[no-any-return]

    def apply_style(self, style: str, tool: str = "") -> dict[str, Any]:
        return self._call("apply_style", {"style": style, "tool": tool})  # type: ignore[no-any-return]

    def batch_process(
        self,
        files: list[str],
        output_dir: str = "",
        post: str = "",
        continue_on_error: bool = False,
    ) -> list[dict[str, Any]]:
        return self._call(  # type: ignore[no-any-return]
            "batch_process",
            {
                "files": files,
                "output_dir": output_dir,
                "post": post,
                "continue_on_error": continue_on_error,
            },
        )

    def list_posts(self) -> list[dict[str, Any]]:
        return self._call("list_posts")  # type: ignore[no-any-return]

    def select_post(self, name: str) -> dict[str, Any]:
        return self._call("select_post", {"name": name})  # type: ignore[no-any-return]

    def run_nest(
        self,
        parts: list[dict[str, Any]],
        output_dir: str = "",
        sheet_width: float = 2440,
        sheet_height: float = 1220,
    ) -> dict[str, Any]:
        return self._call(  # type: ignore[no-any-return]
            "run_nest",
            {
                "parts": parts,
                "output_dir": output_dir,
                "sheet_width": sheet_width,
                "sheet_height": sheet_height,
            },
        )

    def find_drawing_files(self, pattern: str = "*.amd") -> list[str]:
        return self._call("find_drawing_files", {"pattern": pattern})  # type: ignore[no-any-return]

    def glob_files(self, directory: str, pattern: str = "*.amd") -> list[str]:
        return self._call("glob_files", {"directory": directory, "pattern": pattern})  # type: ignore[no-any-return]
