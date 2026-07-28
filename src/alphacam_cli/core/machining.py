from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import win32com.client as win32  # type: ignore[import-untyped]


class MillData:
    """Typed wrapper around AlphaCAM MillData COM object."""

    def __init__(self, dispatch: win32.CDispatch) -> None:
        self._md = dispatch

    # --- Properties ---
    @property
    def safe_rapid_level(self) -> float:
        return float(self._md.SafeRapidLevel)  # type: ignore[attr-defined]

    @safe_rapid_level.setter
    def safe_rapid_level(self, value: float) -> None:
        self._md.SafeRapidLevel = value  # type: ignore[attr-defined]

    @property
    def rapid_down_to(self) -> float:
        return float(self._md.RapidDownTo)  # type: ignore[attr-defined]

    @rapid_down_to.setter
    def rapid_down_to(self, value: float) -> None:
        self._md.RapidDownTo = value  # type: ignore[attr-defined]

    @property
    def final_depth(self) -> float:
        return float(self._md.FinalDepth)  # type: ignore[attr-defined]

    @final_depth.setter
    def final_depth(self, value: float) -> None:
        self._md.FinalDepth = value  # type: ignore[attr-defined]

    @property
    def spindle_speed(self) -> int:
        return int(self._md.SpindleSpeed)  # type: ignore[attr-defined]

    @spindle_speed.setter
    def spindle_speed(self, value: int) -> None:
        self._md.SpindleSpeed = value  # type: ignore[attr-defined]

    @property
    def down_feed(self) -> float:
        return float(self._md.DownFeed)  # type: ignore[attr-defined]

    @down_feed.setter
    def down_feed(self, value: float) -> None:
        self._md.DownFeed = value  # type: ignore[attr-defined]

    @property
    def cut_feed(self) -> float:
        return float(self._md.CutFeed)  # type: ignore[attr-defined]

    @cut_feed.setter
    def cut_feed(self, value: float) -> None:
        self._md.CutFeed = value  # type: ignore[attr-defined]

    @property
    def material_top(self) -> float:
        return float(self._md.MaterialTop)  # type: ignore[attr-defined]

    @material_top.setter
    def material_top(self, value: float) -> None:
        self._md.MaterialTop = value  # type: ignore[attr-defined]

    @property
    def max_depth_per_cut(self) -> float:
        return float(self._md.MaxDepthPerCut)  # type: ignore[attr-defined]

    @max_depth_per_cut.setter
    def max_depth_per_cut(self, value: float) -> None:
        self._md.MaxDepthPerCut = value  # type: ignore[attr-defined]

    @property
    def width_of_cut(self) -> float:
        return float(self._md.WidthOfCut)  # type: ignore[attr-defined]

    @width_of_cut.setter
    def width_of_cut(self, value: float) -> None:
        self._md.WidthOfCut = value  # type: ignore[attr-defined]

    @property
    def stock(self) -> float:
        return float(self._md.Stock)  # type: ignore[attr-defined]

    @stock.setter
    def stock(self, value: float) -> None:
        self._md.Stock = value  # type: ignore[attr-defined]

    @property
    def process_type(self) -> int:
        return int(self._md.ProcessType2)  # type: ignore[attr-defined]

    @process_type.setter
    def process_type(self, value: int) -> None:
        self._md.ProcessType2 = value  # type: ignore[attr-defined]

    @property
    def pocket_type(self) -> int:
        return int(self._md.PocketType)  # type: ignore[attr-defined]

    @pocket_type.setter
    def pocket_type(self, value: int) -> None:
        self._md.PocketType = value  # type: ignore[attr-defined]

    @property
    def surface_mc_action(self) -> int:
        return int(self._md.SurfaceMCAction)  # type: ignore[attr-defined]

    @surface_mc_action.setter
    def surface_mc_action(self, value: int) -> None:
        self._md.SurfaceMCAction = value  # type: ignore[attr-defined]

    @property
    def bottom_of_hole(self) -> float:
        return float(self._md.BottomOfHole)  # type: ignore[attr-defined]

    @bottom_of_hole.setter
    def bottom_of_hole(self, value: float) -> None:
        self._md.BottomOfHole = value  # type: ignore[attr-defined]

    @property
    def drill_type(self) -> int:
        return int(self._md.DrillType)  # type: ignore[attr-defined]

    @drill_type.setter
    def drill_type(self, value: int) -> None:
        self._md.DrillType = value  # type: ignore[attr-defined]

    @property
    def chord_error(self) -> float:
        return float(self._md.ChordError)  # type: ignore[attr-defined]

    @chord_error.setter
    def chord_error(self, value: float) -> None:
        self._md.ChordError = value  # type: ignore[attr-defined]

    # --- Methods ---
    def rough_finish(self) -> None:
        """Execute rough/finish operation on selected geometries."""
        self._md.RoughFinish()  # type: ignore[attr-defined]

    def pocket(self) -> None:
        """Execute pocket operation on selected geometries."""
        self._md.Pocket()  # type: ignore[attr-defined]

    def drill_tap(self) -> None:
        """Execute drill/tap operation on selected geometries."""
        self._md.DrillTap()  # type: ignore[attr-defined]

    def engrave(self) -> None:
        """Execute engrave operation on selected geometries."""
        self._md.Engrave()  # type: ignore[attr-defined]

    def saw(self) -> None:
        """Execute saw operation on selected geometries."""
        self._md.Saw()  # type: ignore[attr-defined]

    def machine_surfaces(self) -> None:
        """Execute surface machining on selected surfaces."""
        self._md.MachineSurfaces()  # type: ignore[attr-defined]
