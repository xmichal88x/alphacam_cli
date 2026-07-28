from __future__ import annotations


class NcEventHandler:
    """COM event handler for AlphaCAM NC output events.

    Handles BeforeOutputNcDialogBox to prevent blocking on modal dialogs.
    """

    def __init__(self, nc_path: str) -> None:
        self.nc_path = nc_path

    def OnBeforeOutputNcDialogBox(self) -> int:  # noqa: N802
        return 1  # 1 = File mode

    def OnBeforeCreateNc(self) -> str:  # noqa: N802
        return ""

    def OnAfterOutputNc(self, file_name: str) -> None:  # noqa: N802
        pass

    def OnBeforeOutputNc(self) -> str:  # noqa: N802
        return self.nc_path
