"""Overlay position from the Windows work area (testable without Tk)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional, Tuple

OVERLAY_BOTTOM_MARGIN_PX = 28
SPI_GETWORKAREA = 0x30


@dataclass(frozen=True)
class WorkArea:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


def compute_overlay_xy(
    work: WorkArea,
    *,
    overlay_w: int,
    overlay_h: int,
    margin: int = OVERLAY_BOTTOM_MARGIN_PX,
) -> Tuple[int, int]:
    """Place overlay horizontally centered on the work area, margin px above its bottom."""
    x = work.left + max(0, (work.width - overlay_w) // 2)
    y = work.bottom - overlay_h - margin
    y = max(work.top, y)
    return x, y


def query_primary_work_area() -> Optional[WorkArea]:
    """Return the primary monitor work rectangle, or None if unavailable."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        rect = RECT()
        ok = ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETWORKAREA,
            0,
            ctypes.byref(rect),
            0,
        )
        if not ok:
            return None
        return WorkArea(rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        return None