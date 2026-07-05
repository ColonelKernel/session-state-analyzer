"""REAPER-specific track-colour decoding (OS-dependent byte order).

REAPER stores custom colours as an OS-native packed integer, so both the
"custom colour in use" flag and the red/blue byte order are REAPER format
knowledge — they live with the driver, not in core utils.
"""

from __future__ import annotations

from typing import Optional


def decode_color(packed: Optional[int], swell_order: bool = False) -> Optional[str]:
    """Decode a REAPER packed colour integer into ``#rrggbb``.

    REAPER stores custom colours as an OS-native integer OR-ed with the
    0x1000000 "custom colour in use" flag (SDK ``I_CUSTOMCOLOR``: "If you do not
    |0x1000000, then it will not be used, but will store the color"). A value
    without that flag therefore means *no custom colour*, and we return ``None``
    — this also makes black-in-use (exactly 0x1000000) decode to ``#000000``.

    The byte order of the low three bytes depends on the OS the project was
    authored on (SDK ``ColorToNative``: "OS dependent color ... e.g. RGB() macro
    on Windows"): Windows COLORREF puts R in the low byte, while SWELL
    (macOS/Linux) puts R in bits 16-23. Pass ``swell_order=True`` for
    non-Windows-authored projects; the default assumes the Windows layout.
    """

    if packed is None:
        return None
    try:
        value = int(packed)
    except (TypeError, ValueError):
        return None
    if not (value & 0x1000000):
        return None  # colour stored but not in use (SDK: I_CUSTOMCOLOR)
    value &= 0xFFFFFF  # drop the custom-colour flag bit
    if swell_order:
        red = (value >> 16) & 0xFF
        green = (value >> 8) & 0xFF
        blue = value & 0xFF
    else:
        red = value & 0xFF
        green = (value >> 8) & 0xFF
        blue = (value >> 16) & 0xFF
    return f"#{red:02x}{green:02x}{blue:02x}"


def swell_platform(header: Optional[str]) -> Optional[bool]:
    """Classify the project-header platform token for colour byte order.

    Returns ``True`` for SWELL platforms (macOS/Linux, R in the high byte),
    ``False`` for Windows (R in the low byte), ``None`` when unknown.
    """

    if not header:
        return None
    lowered = header.lower()
    # SWELL tokens are checked first: "darwin" contains the substring "win",
    # so the Windows check must not run before it.
    if any(token in lowered for token in ("osx", "macos", "darwin", "linux")):
        return True
    # "x64" covers legacy Windows headers (e.g. "5.983/x64"); macOS builds of
    # that era wrote "OSX64", which the SWELL check above already caught.
    if "win" in lowered or "x64" in lowered:
        return False
    return None
